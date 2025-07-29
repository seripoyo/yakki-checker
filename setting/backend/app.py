#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
薬機法リスクチェッカー バックエンドAPI
Flask アプリケーション（Claude API連携版）

このAPIは薬機法に関するテキストチェックを行い、
Claude APIとローカルCSVデータを活用して高精度な
リスク評価と代替表現の提案をJSON形式で返します。
"""

import os
import json
import logging
import time
import threading
import secrets
import hashlib
from functools import lru_cache, wraps
from collections import OrderedDict

# ログ設定を先に行う
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import csv
import re
import requests
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv

# ファイル監視用
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # FileSystemEventHandlerのダミークラスを定義
    class FileSystemEventHandler:
        def on_modified(self, event): pass
        def on_created(self, event): pass  
        def on_deleted(self, event): pass
    logger.warning("watchdogが利用できません。ファイル監視機能は無効です。pip install watchdog で有効化できます。")

# 環境変数を読み込み
load_dotenv()

# Flaskアプリケーションの初期化
app = Flask(__name__)

# CORS設定 - 環境に応じたドメイン設定
allowed_origins = os.getenv('ALLOWED_ORIGINS', '').split(',')
if not allowed_origins or allowed_origins == ['']:
    # デフォルト設定（開発環境用）
    allowed_origins = [
        'https://seripoyo.github.io',
        'http://localhost:3000', 
        'http://localhost:8000',
        'http://localhost:8080',  # 追加
        'http://127.0.0.1:3000',
        'http://127.0.0.1:8000',
        'http://127.0.0.1:8080'   # 追加
    ]

# 本番環境では開発用URLを除外
environment = os.getenv('ENVIRONMENT', 'development')
if environment == 'production':
    allowed_origins = [origin for origin in allowed_origins if not origin.startswith('http://localhost') and not origin.startswith('http://127.0.0.1')]
    logger.info(f"本番環境モード - 許可ドメイン: {allowed_origins}")

CORS(app, origins=allowed_origins)

# アプリケーション設定
app.config['JSON_AS_ASCII'] = False  # 日本語文字化け防止

# ===== グローバル変数 =====
claude_client = None
ng_expressions_data = None
csv_reference_text = ""
markdown_reference_text = ""
notion_api_key = None
notion_database_id = None

# ===== ファイル監視・キャッシュ管理クラス =====
class DataCache:
    """データファイルのキャッシュとリアルタイム更新を管理"""
    
    def __init__(self):
        self.data_cache = {}
        self.rule_cache = {}
        self.file_timestamps = {}
        self.lock = threading.Lock()
        self.observer = None
        
    def get_file_timestamp(self, file_path):
        """ファイルのタイムスタンプを取得"""
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return 0
    
    def is_file_modified(self, file_path):
        """ファイルが変更されたかチェック"""
        current_timestamp = self.get_file_timestamp(file_path)
        cached_timestamp = self.file_timestamps.get(file_path, 0)
        return current_timestamp > cached_timestamp
    
    def update_file_timestamp(self, file_path):
        """ファイルのタイムスタンプを更新"""
        self.file_timestamps[file_path] = self.get_file_timestamp(file_path)
    
    def invalidate_cache(self, cache_type="all"):
        """キャッシュを無効化"""
        with self.lock:
            if cache_type == "all" or cache_type == "data":
                self.data_cache.clear()
                logger.info("データキャッシュを無効化しました")
            if cache_type == "all" or cache_type == "rule":
                self.rule_cache.clear()
                logger.info("ルールキャッシュを無効化しました")
    
    def get_cached_data_content(self):
        """キャッシュされたデータコンテンツを取得（必要に応じて更新）"""
        with self.lock:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            cache_key = "all_data_content"
            
            # データディレクトリ内のファイルをチェック
            needs_update = False
            if cache_key not in self.data_cache:
                needs_update = True
            else:
                # 全ファイルの変更チェック
                try:
                    for filename in os.listdir(data_dir):
                        file_path = os.path.join(data_dir, filename)
                        if os.path.isfile(file_path) and self.is_file_modified(file_path):
                            needs_update = True
                            break
                except OSError:
                    needs_update = True
            
            # 必要に応じてキャッシュを更新
            if needs_update:
                logger.info("dataディレクトリの変更を検知 - キャッシュを更新中...")
                self.data_cache[cache_key] = load_all_data_files_direct()
                
                # タイムスタンプを更新
                try:
                    for filename in os.listdir(data_dir):
                        file_path = os.path.join(data_dir, filename)
                        if os.path.isfile(file_path):
                            self.update_file_timestamp(file_path)
                except OSError:
                    pass
                
                logger.info(f"データキャッシュ更新完了: {len(self.data_cache[cache_key])}文字")
            
            return self.data_cache[cache_key]
    
    def get_cached_rule_content(self, text_type):
        """キャッシュされたルールコンテンツを取得（必要に応じて更新）"""
        with self.lock:
            rule_dir = os.path.join(os.path.dirname(__file__), 'rule')
            cache_key = f"rule_{text_type}"
            
            # ルールファイルのマッピング
            rule_file_mapping = {
                'キャッチコピー': 'キャッチコピー.md',
                'LP見出し・タイトル': 'LP見出し・タイトル.md',
                '商品説明文・広告文・通常テキスト': '商品説明文.md',
                'お客様の声': 'お客様の声.md'
            }
            
            filename = rule_file_mapping.get(text_type)
            if not filename:
                return ""
            
            file_path = os.path.join(rule_dir, filename)
            
            # ファイル変更チェック
            needs_update = False
            if cache_key not in self.rule_cache:
                needs_update = True
            elif self.is_file_modified(file_path):
                needs_update = True
            
            # 必要に応じてキャッシュを更新
            if needs_update:
                logger.info(f"ルールファイル '{filename}' の変更を検知 - キャッシュを更新中...")
                self.rule_cache[cache_key] = load_rule_file_direct(text_type)
                self.update_file_timestamp(file_path)
                logger.info(f"ルールキャッシュ更新完了: {filename}")
            
            return self.rule_cache[cache_key]
    
    def start_file_watcher(self):
        """ファイル監視を開始"""
        if not WATCHDOG_AVAILABLE:
            logger.info("watchdogが利用できないため、ポーリングベースの更新を使用します")
            return
        
        try:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            rule_dir = os.path.join(os.path.dirname(__file__), 'rule')
            
            event_handler = DataFileEventHandler(self)
            self.observer = Observer()
            
            # dataディレクトリを監視
            if os.path.exists(data_dir):
                self.observer.schedule(event_handler, data_dir, recursive=False)
                logger.info(f"ファイル監視開始: {data_dir}")
            
            # ruleディレクトリを監視
            if os.path.exists(rule_dir):
                self.observer.schedule(event_handler, rule_dir, recursive=False)
                logger.info(f"ファイル監視開始: {rule_dir}")
            
            self.observer.start()
            logger.info("リアルタイムファイル監視が開始されました")
            
        except Exception as e:
            logger.error(f"ファイル監視の開始に失敗: {str(e)}")
    
    def stop_file_watcher(self):
        """ファイル監視を停止"""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("ファイル監視を停止しました")

class DataFileEventHandler(FileSystemEventHandler):
    """ファイル変更イベントハンドラー"""
    
    def __init__(self, data_cache):
        self.data_cache = data_cache
        self.last_event_time = {}
        self.debounce_time = 1.0  # 1秒のデバウンス
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # デバウンス処理（短時間での重複イベントを防ぐ）
        current_time = time.time()
        last_time = self.last_event_time.get(event.src_path, 0)
        if current_time - last_time < self.debounce_time:
            return
        
        self.last_event_time[event.src_path] = current_time
        
        file_path = event.src_path
        filename = os.path.basename(file_path)
        
        logger.info(f"ファイル変更検知: {filename}")
        
        # dataディレクトリのファイルが変更された場合
        if '/data/' in file_path:
            self.data_cache.invalidate_cache("data")
            logger.info("dataディレクトリの変更によりキャッシュを無効化")
        
        # ruleディレクトリのファイルが変更された場合
        elif '/rule/' in file_path:
            self.data_cache.invalidate_cache("rule")
            logger.info("ruleディレクトリの変更によりキャッシュを無効化")
    
    def on_created(self, event):
        if not event.is_directory:
            logger.info(f"新規ファイル作成検知: {os.path.basename(event.src_path)}")
            self.on_modified(event)
    
    def on_deleted(self, event):
        if not event.is_directory:
            logger.info(f"ファイル削除検知: {os.path.basename(event.src_path)}")
            # ファイル削除の場合も同様にキャッシュを無効化
            if '/data/' in event.src_path:
                self.data_cache.invalidate_cache("data")
            elif '/rule/' in event.src_path:
                self.data_cache.invalidate_cache("rule")

# グローバルキャッシュインスタンス
data_cache = DataCache()

# ===== チェック結果キャッシュシステム =====
class CheckCache:
    """チェック結果のキャッシュシステム"""
    def __init__(self, max_size=100, ttl=3600):
        self.cache = OrderedDict()  # 順序を保持して古いものから削除
        self.max_size = max_size
        self.ttl = ttl  # Time To Live (秒)
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()
    
    def get_cache_key(self, text, category, text_type, special_points=None):
        """キャッシュキーの生成"""
        content = f"{text}|{category}|{text_type}|{special_points or ''}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get(self, key):
        """キャッシュから取得"""
        with self.lock:
            if key in self.cache:
                data, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    # キャッシュヒット - 最後に移動
                    self.cache.move_to_end(key)
                    self.hits += 1
                    logger.info(f"キャッシュヒット - ヒット率: {self.get_hit_rate():.1f}%")
                    return data
                else:
                    # 期限切れ
                    del self.cache[key]
            
            self.misses += 1
            return None
    
    def set(self, key, data):
        """キャッシュに保存"""
        with self.lock:
            # サイズ制限チェック
            if len(self.cache) >= self.max_size:
                # 最も古いものを削除
                self.cache.popitem(last=False)
            
            self.cache[key] = (data, time.time())
            logger.info(f"キャッシュ保存 - サイズ: {len(self.cache)}/{self.max_size}")
    
    def get_hit_rate(self):
        """キャッシュヒット率を計算"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100
    
    def clear(self):
        """キャッシュをクリア"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
            logger.info("キャッシュをクリアしました")

# チェック結果キャッシュインスタンスの作成
check_cache = CheckCache(max_size=100, ttl=3600)  # 1時間有効

# ===== セキュリティ機能 =====

# 有効なAPIキーを管理（環境変数から読み込み）
def load_valid_api_keys():
    """有効なAPIキーをハッシュ化して読み込み"""
    api_keys_env = os.getenv('VALID_API_KEYS', '')
    if not api_keys_env:
        logger.warning("有効なAPIキーが設定されていません。認証が無効化されます。")
        return set()
    
    # 複数のAPIキーをカンマ区切りで設定可能
    raw_keys = [key.strip() for key in api_keys_env.split(',') if key.strip()]
    # APIキーをハッシュ化して保存（平文保存を避ける）
    hashed_keys = {hashlib.sha256(key.encode()).hexdigest() for key in raw_keys}
    logger.info(f"有効なAPIキー数: {len(hashed_keys)}個")
    return hashed_keys

# 有効なAPIキーセット
VALID_API_KEYS = load_valid_api_keys()

# 認証が必要かどうかの設定
REQUIRE_AUTH = len(VALID_API_KEYS) > 0

def require_api_key(f):
    """APIキー認証デコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 認証が無効化されている場合はスキップ
        if not REQUIRE_AUTH:
            return f(*args, **kwargs)
        
        # APIキーの確認
        api_key = None
        
        # Headerから取得
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        # クエリパラメータから取得（非推奨だが互換性のため）
        elif 'api_key' in request.args:
            api_key = request.args.get('api_key')
            logger.warning("クエリパラメータでのAPIキー送信は非推奨です。ヘッダーを使用してください。")
        
        if not api_key:
            logger.warning(f"APIキーなしのアクセス試行: {request.remote_addr}")
            return jsonify({
                "error": "API key required",
                "message": "APIキーが必要です。X-API-KeyヘッダーでAPIキーを送信してください。"
            }), 401
        
        # APIキーの検証（ハッシュ化して比較）
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if api_key_hash not in VALID_API_KEYS:
            logger.warning(f"無効なAPIキーでのアクセス試行: {request.remote_addr}")
            return jsonify({
                "error": "Invalid API key",
                "message": "無効なAPIキーです。"
            }), 401
        
        logger.info(f"認証成功: {request.remote_addr}")
        return f(*args, **kwargs)
    return decorated_function

def add_security_headers(response):
    """セキュリティヘッダーを追加"""
    # XSS対策
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # HTTPS強制（本番環境用）
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Content Security Policy
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' https://api.anthropic.com https://api.notion.com"
    )
    
    return response

# レート制限用の辞書（メモリベース）
request_counts = {}
# 開発環境では制限を緩和
REQUEST_LIMIT = 1000 if os.getenv('DEBUG', 'True').lower() == 'true' else 100  # 開発環境では1000回/時間
RATE_LIMIT_WINDOW = 3600  # 1時間（秒）

def rate_limit_check():
    """シンプルなレート制限チェック"""
    client_ip = request.remote_addr
    current_time = time.time()
    
    # IPアドレス別のリクエスト履歴を管理
    if client_ip not in request_counts:
        request_counts[client_ip] = []
    
    # 古いリクエスト記録を削除（ウィンドウ外）
    request_counts[client_ip] = [
        timestamp for timestamp in request_counts[client_ip]
        if current_time - timestamp < RATE_LIMIT_WINDOW
    ]
    
    # 制限チェック
    if len(request_counts[client_ip]) >= REQUEST_LIMIT:
        logger.warning(f"レート制限違反: {client_ip}")
        return False
    
    # 新しいリクエストを記録
    request_counts[client_ip].append(current_time)
    return True

def require_rate_limit(f):
    """レート制限デコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not rate_limit_check():
            return jsonify({
                "error": "Rate limit exceeded",
                "message": f"1時間あたり{REQUEST_LIMIT}回のリクエスト制限を超過しました。しばらく時間をおいてから再試行してください。"
            }), 429
        return f(*args, **kwargs)
    return decorated_function

def initialize_app():
    """
    アプリケーションの初期化処理
    APIキーの確認、CSVファイル、マークダウンファイルの読み込み
    """
    global claude_client, ng_expressions_data, csv_reference_text, markdown_reference_text, notion_api_key, notion_database_id
    
    logger.info("薬機法リスクチェッカー 初期化開始")
    
    # 1. Claude API キーの確認
    claude_api_key = os.getenv('CLAUDE_API_KEY')
    if not claude_api_key or claude_api_key == 'dummy_key_for_demo':
        logger.warning("有効なCLAUDE_API_KEYが設定されていません - デモモードで動作します")
        claude_client = None
    else:
        # Claude クライアントの初期化
        try:
            claude_client = anthropic.Anthropic(api_key=claude_api_key)
            logger.info("Claude API クライアント初期化完了")
        except Exception as e:
            logger.error(f"Claude API クライアント初期化失敗: {str(e)}")
            claude_client = None
    
    # Notion API キーの確認（オプション）
    notion_api_key = os.getenv('NOTION_API_KEY')
    notion_database_id = os.getenv('NOTION_DATABASE_ID')
    
    if notion_api_key and notion_database_id:
        logger.info("Notion API 設定確認完了")
    else:
        logger.warning("Notion API設定が不完全です（NOTION_API_KEY, NOTION_DATABASE_IDが必要）")
        logger.warning("薬機法ガイド機能は無効化されます")
    
    # 2. CSVファイルの読み込み
    csv_file_path = os.path.join(os.path.dirname(__file__), 'data', 'ng_expressions.csv')
    
    try:
        if not os.path.exists(csv_file_path):
            logger.warning(f"CSVファイルが見つかりません: {csv_file_path}")
            # デフォルトのNG表現データを使用
            ng_expressions_data = create_default_ng_data()
            csv_reference_text = format_ng_data_for_prompt(ng_expressions_data)
        else:
            ng_expressions_data = read_csv_file(csv_file_path)
            csv_reference_text = format_csv_for_prompt(ng_expressions_data)
            logger.info(f"CSVファイル読み込み完了: {len(ng_expressions_data)}件のNG表現データ")
    
    except Exception as e:
        logger.error(f"CSVファイル読み込みエラー: {str(e)}")
        # フォールバック: デフォルトデータを使用
        ng_expressions_data = create_default_ng_data()
        csv_reference_text = format_ng_data_for_prompt(ng_expressions_data)
        logger.info("デフォルトのNG表現データを使用")
    
    # 3. 全データファイルの読み込み
    try:
        markdown_reference_text = load_all_data_files()
        logger.info(f"全データファイル読み込み完了: {len(markdown_reference_text)}文字")
    except Exception as e:
        logger.error(f"データファイル読み込みエラー: {str(e)}")
        markdown_reference_text = ""
    
    # ファイル監視の開始
    data_cache.start_file_watcher()
    
    logger.info("薬機法リスクチェッカー 初期化完了")

# セキュリティヘッダーを全レスポンスに適用
@app.after_request
def after_request(response):
    return add_security_headers(response)

def read_csv_file(file_path):
    """
    CSVファイルを読み込んで辞書のリストとして返す
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def create_default_ng_data():
    """
    デフォルトのNG表現データを作成
    """
    default_data = [
        {"NG表現": "シミが消える", "カテゴリ": "シミ", "リスクレベル": "高", 
         "代替表現1": "メラニンの生成を抑え、シミ・そばかすを防ぐ", 
         "代替表現2": "乾燥による小じわを目立たなくする", 
         "代替表現3": "キメを整え明るい印象の肌へ導く"},
        {"NG表現": "アンチエイジング", "カテゴリ": "老化", "リスクレベル": "高",
         "代替表現1": "エイジングケア（年齢に応じたお手入れ）",
         "代替表現2": "ハリ・ツヤを与える",
         "代替表現3": "うるおいのある肌へ導く"},
        {"NG表現": "完全に", "カテゴリ": "断定", "リスクレベル": "中",
         "代替表現1": "個人差がありますが",
         "代替表現2": "使用感には個人差があります",
         "代替表現3": "お肌の状態によって"},
    ]
    return default_data

def format_csv_for_prompt(data):
    """
    データリストをプロンプト用の文字列形式に変換
    """
    if not data:
        return "参考データなし"
    
    reference_text = "=== 薬機法NG表現参考データ ===\n"
    
    # 通常のリストの場合
    for row in data:
        reference_text += f"NG表現: {row.get('NG表現', 'N/A')}\n"
        reference_text += f"カテゴリ: {row.get('カテゴリ', 'N/A')}\n"
        reference_text += f"リスクレベル: {row.get('リスクレベル', 'N/A')}\n"
        
        # 代替表現があれば追加
        alternatives = []
        for i in range(1, 4):
            alt_key = f"代替表現{i}"
            if alt_key in row and row[alt_key]:
                alternatives.append(row[alt_key])
        
        if alternatives:
            reference_text += f"代替表現: {' | '.join(alternatives)}\n"
        
        reference_text += "---\n"
    
    return reference_text

def format_ng_data_for_prompt(df):
    """
    NG表現データをプロンプト用にフォーマット
    """
    return format_csv_for_prompt(df)

def load_all_data_files():
    """
    dataディレクトリ内の全ファイル（CSV、マークダウン）を読み込んで統合（キャッシュ使用）
    """
    return data_cache.get_cached_data_content()

def load_all_data_files_direct():
    """
    dataディレクトリ内の全ファイル（CSV、マークダウン）を直接読み込んで統合（キャッシュ更新用）
    """
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    combined_content = "=== 薬機法参考資料（全データファイル） ===\n\n"
    
    # dataディレクトリ内の全ファイルを取得
    try:
        all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
        logger.info(f"dataディレクトリ内のファイル: {all_files}")
        
        for filename in all_files:
            file_path = os.path.join(data_dir, filename)
            try:
                # CSVファイルの処理
                if filename.endswith('.csv'):
                    combined_content += f"### {filename}の内容（CSV形式）\n\n"
                    with open(file_path, 'r', encoding='utf-8') as f:
                        csv_content = f.read().strip()
                        if csv_content:
                            combined_content += csv_content + "\n\n"
                        combined_content += "---\n\n"
                
                # マークダウンファイルの処理
                elif filename.endswith('.md'):
                    combined_content += f"### {filename}の内容（マークダウン形式）\n\n"
                    with open(file_path, 'r', encoding='utf-8') as f:
                        md_content = f.read().strip()
                        if md_content:
                            combined_content += md_content + "\n\n"
                        combined_content += "---\n\n"
                
                # その他のテキストファイル
                elif filename.endswith(('.txt', '.json')):
                    combined_content += f"### {filename}の内容\n\n"
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read().strip()
                        if text_content:
                            combined_content += text_content + "\n\n"
                        combined_content += "---\n\n"
                        
            except Exception as e:
                logger.error(f"{filename}読み込みエラー: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"dataディレクトリアクセスエラー: {str(e)}")
    
    return combined_content

def load_rule_file(text_type):
    """
    ユーザーの選択に応じてruleディレクトリの特定マークダウンファイルを読み込み（キャッシュ使用）
    """
    return data_cache.get_cached_rule_content(text_type)

def load_rule_file_direct(text_type):
    """
    ユーザーの選択に応じてruleディレクトリの特定マークダウンファイルを直接読み込み（キャッシュ更新用）
    """
    if not text_type:
        return ""
    
    rule_dir = os.path.join(os.path.dirname(__file__), 'rule')
    
    # テキストタイプに応じたファイル名のマッピング
    rule_file_mapping = {
        'キャッチコピー': 'キャッチコピー.md',
        'LP見出し・タイトル': 'LP見出し・タイトル.md',
        '商品説明文・広告文・通常テキスト': '商品説明文.md',
        'お客様の声': 'お客様の声.md'
    }
    
    filename = rule_file_mapping.get(text_type)
    if not filename:
        logger.warning(f"未対応のテキストタイプ: {text_type}")
        return ""
    
    file_path = os.path.join(rule_dir, filename)
    rule_content = ""
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    rule_content = f"=== {text_type}用の薬機法ルール・ガイドライン ===\n\n"
                    rule_content += content + "\n\n"
                    rule_content += "---\n\n"
                    logger.info(f"ルールファイル読み込み完了: {filename}")
                else:
                    logger.info(f"{filename}は空ファイルです")
        else:
            logger.warning(f"ルールファイルが見つかりません: {file_path}")
    except Exception as e:
        logger.error(f"ルールファイル読み込みエラー: {str(e)}")
    
    return rule_content

def load_markdown_files():
    """
    従来のマークダウンファイル読み込み（後方互換性のため残す）
    """
    return load_all_data_files()

def create_system_prompt():
    """
    Claude API用のシステムプロンプトを生成
    """
    return """あなたは、日本の薬機法（医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律）に精通した、最高の薬機法管理者・AIアシスタントです。

**あなたの役割・視点**:
- 行政機関の薬務監視員と同等の厳格さで判断する
- 法令遵守を第一に、消費者保護の観点で分析する
- 表現の微妙なニュアンスや暗示的な表現も見逃さない
- 一般消費者が誤解する可能性を常に考慮する

あなたのタスクは、入力された美容関連の広告テキストを分析し、薬機法抵触リスクを評価して、具体的な改善案をJSON形式で出力することです。

このAIは、美容サロンや化粧品メーカーの広告担当者、薬機法に不慣れなライター向けの「薬機法リスクチェッカー」というWebアプリのバックエンドとして機能します。目的は、担当者が作成した広告文のラフ案を手軽に一次チェックし、専門家への確認前に手戻りを減らすことです。

以下の5つのタスクを厳密に実行してください：

1. **全体リスク評価**: テキスト全体としての薬機法抵触リスクを「高」「中」「低」の3段階で評価
2. **問題点の抽出と分析**: 
   - テキスト内から薬機法に抵触する可能性のある全ての表現(fragment)を特定
   - 各表現について抵触の具体的な理由(reason)、リスクレベル(risk_level)を評価
   - リスク評価に基づいた安全な代替表現の候補(suggestions)を3つ提案
3. **3つのバリエーションリライト**: 
   **【重要】薬機法的に問題がない場合でも、より魅力的で訴求力のあるリライト案を必ず提供してください**
   - **保守的バージョン**: 最も安全で確実な表現を使用（問題ない場合は、より品格のある表現に）
   - **バランス版**: 安全性と訴求力のバランスを重視（問題ない場合は、感情的な魅力を加えた表現に）
   - **訴求力重視版**: 法的リスクを最小限にしつつ、訴求力を最大化（問題ない場合は、より刺激的で印象的な表現に）
   - **重要**: 「特に訴求したいポイント」が指定されている場合、各リライト案でそのポイントを薬機法に準拠しながら可能な限り反映すること
   - **重要**: 元の文章が薬機法的に問題ない場合は、「この表現をベースに、より魅力的で訴求力を高めた表現」として3つのバリエーションを提供
   - **【自然な日本語要件】**: リライト案は必ず自然で読みやすい日本語にしてください
     * **お客様の声・体験談の場合**: 実際の顧客が話すような自然な口調で、「です・ます調」や「だ・である調」を適切に使い分ける
     * **企業からの説明文の場合**: 敬語を適切に使用し、冗長な表現を避けて簡潔で分かりやすい文章にする
     * **キャッチコピーの場合**: リズム感があり、覚えやすく、印象的な表現にする
     * **重複表現の排除**: 「〜していただいております」「〜頂戴しております」など、同じ意味の敬語を重複させない
     * **文体の統一**: 一つの文章内で「です・ます調」と「だ・である調」を混在させない
   - **重要**: 各リライト案には、なぜそのリライトが薬機法的に適切かつ訴求力向上につながるかの解説を必ず含めること
4. **リスク件数集計**: 高・中・低リスクの件数をそれぞれカウント

必ず以下のJSON形式で、キーの名前も厳密に守って出力してください。他の説明文は一切含めないでください：

{
  "overall_risk": "高" | "中" | "低",
  "risk_counts": {
    "total": Number,
    "high": Number,
    "medium": Number,
    "low": Number
  },
  "issues": [
    {
      "fragment": "問題のある表現",
      "reason": "抵触する理由の詳細説明...",
      "risk_level": "高" | "中" | "低",
      "suggestions": ["代替案1", "代替案2", "代替案3"]
    }
  ],
  "rewritten_texts": {
    "conservative": {
      "text": "保守的バージョンのリライト文...",
      "explanation": "このリライトが薬機法的に適切な理由の詳細解説..."
    },
    "balanced": {
      "text": "バランス版のリライト文...",
      "explanation": "このリライトが薬機法的に適切な理由の詳細解説..."
    },
    "appealing": {
      "text": "訴求力重視版のリライト文...",
      "explanation": "このリライトが薬機法的に適切な理由の詳細解説..."
    }
  }
}"""

def get_text_type_guidance(text_type):
    """
    文章種類に応じた自然な表現ガイドを返す
    """
    guidance_map = {
        "お客様の声": """
リライト時は以下の点に注意してください：
- 実際の顧客が話すような自然な口調にする
- 「です・ます調」で統一する（体験談では丁寧語が自然）
- 企業的な敬語（「〜させていただいております」など）は使わない
- 顧客の感情や体験が伝わる表現にする
- 例：「毎日使っています」「気に入っています」「続けやすいです」

【NG例】「〜していただいております」「〜頂戴しております」
【OK例】「〜しています」「〜と感じています」「〜が気に入っています」
        """,
        "キャッチコピー": """
リライト時は以下の点に注意してください：
- 短くリズム感のある表現にする
- 覚えやすく印象的な言葉を使う
- 読み手の感情に訴える表現を心がける
- 冗長な敬語は避け、簡潔に仕上げる
- 例：「毎日のケアに」「あなたの笑顔のために」「新しい私へ」
        """,
        "商品説明文・広告文・通常テキスト": """
リライト時は以下の点に注意してください：
- 適切な敬語を使用し、丁寧で分かりやすい文章にする
- 冗長な表現を避け、簡潔で読みやすくする
- 「です・ます調」で統一する
- 同じ意味の敬語を重複させない
- 企業として信頼感のある表現を心がける

【NG例】「ご利用いただいておりますお客様から〜頂戴しております」
【OK例】「ご利用のお客様から〜いただいています」
        """,
        "LP見出し・タイトル": """
リライト時は以下の点に注意してください：
- インパクトがあり、読み手の注意を引く表現にする
- 簡潔で分かりやすい言葉を選ぶ
- 冗長な敬語は避け、ストレートな表現を心がける
- 読み手のメリットが明確に伝わるようにする
- 例：「理想の肌へ」「新習慣始めませんか」「選ばれる理由」
        """
    }
    
    return guidance_map.get(text_type, "")

def create_user_prompt(text, text_type, category, all_data_content, rule_content, special_points=''):
    """
    Claude API用のユーザープロンプトを生成（全データファイル・ルールファイル対応）
    """
    # データ内容を簡潔にまとめて高速化
    data_summary = all_data_content[:3000] + "..." if len(all_data_content) > 3000 else all_data_content
    rule_summary = rule_content[:1500] + "..." if len(rule_content) > 1500 else rule_content
    
    # カテゴリ別の詳細ガイダンス
    category_guidance = get_category_guidance(category)
    
    prompt = f"""【薬機法チェック要請】
入力文: {text}
文章種類: {text_type}
商品カテゴリ: {category}
"""
    
    # 特に訴求したいポイントが指定されている場合は追加
    if special_points and special_points.strip():
        prompt += f"""特に訴求したいポイント: {special_points}

"""
    
    # 文章種類に応じた自然な表現ガイドを追加
    text_type_guidance = get_text_type_guidance(text_type)
    if text_type_guidance:
        prompt += f"""
【{text_type}の自然な表現ガイド】
{text_type_guidance}

"""
    
    prompt += f"""
【カテゴリ別チェック基準】
{category_guidance}

【全参考データ（dataディレクトリ）】
{data_summary}
"""
    
    # ルールファイルが存在する場合は追加
    if rule_summary.strip():
        prompt += f"""
【{text_type}専用ルール・ガイドライン】
{rule_summary}
"""
    
    # 特に訴求したいポイントがある場合の指示を追加
    final_instruction = f"{category}の薬機法管理者として、上記の全参考データと専用ルールを踏まえ、入力文を厳格に分析し、指定JSON形式で即座に回答してください。"
    
    if special_points and special_points.strip():
        final_instruction += f"""

【最重要指令】リライト案作成時の特別配慮事項：
「{special_points}」

上記の訴求ポイントを、薬機法に完全準拠しながらも可能な限り反映したリライト案を作成してください。
単に安全にするだけでなく、このポイントが消費者に伝わるよう、表現技法を駆使して工夫してください。
各リライト案の解説では、どのようにこの訴求ポイントを薬機法に適合する形で表現したかを必ず説明してください。"""
    
    prompt += f"""
{final_instruction}"""
    
    return prompt

def get_category_guidance(category):
    """
    商品カテゴリ別の詳細なチェック基準を取得
    """
    guidance_map = {
        "化粧品": """
【化粧品の効能効果56項目以外は全て薬機法違反】
- 医薬部外品専用表現「メラニンの生成を抑え」「シミ・そばかすを防ぐ」は使用不可
- 「美白」単体は使用不可（「美白効果」「美白成分」等も同様）
- 治療的効果の暗示は一切禁止
- 身体機能への影響表現は禁止
- 「〜を防ぐ」「〜を抑える」等の予防効果は基本的に禁止
- 承認された範囲：うるおい、ツヤ、ハリ、キメ、保護、清浄など基本的機能のみ
""",
        "薬用化粧品": """
【医薬部外品（薬用化粧品）承認効能の範囲内でのみ表現可能】
- 承認を受けた効能効果のみ表現可能（美白、ニキビ予防、育毛等）
- 「メラニンの生成を抑え、シミ・そばかすを防ぐ」は美白系で使用可能
- ただし承認範囲を超える表現（「シミが消える」等）は禁止
- 効果の程度を過度に強調する表現は禁止
- 医薬品的効果を暗示する表現は禁止
""",
        "医薬部外品": """
【医薬部外品の承認効能範囲内でのみ表現可能】
- 薬用化粧品以外の医薬部外品（育毛剤、制汗剤、入浴剤等）
- 承認を受けた効能効果のみ表現可能
- 医薬品的効果を暗示しない範囲での表現
- 効果の確実性を表現することは禁止
""",
        "サプリメント": """
【健康食品・サプリメントの表現制限（健康増進法・景品表示法適用）】
- 医薬品的効能効果の表現は一切禁止
- 疾病の治療・予防効果の暗示は禁止
- 身体機能の向上・改善を明示することは禁止
- 栄養補給、健康維持の範囲内でのみ表現可能
- 機能性表示食品・特保でない限り、機能性を謳うことは禁止
""",
        "美容機器・健康器具・その他": """
【美容機器・健康器具の表現制限（美容・健康関連機器適正広告表示ガイド準拠）】
- 医療機器的効果（治療・診断・予防）は一切表現禁止
- 「リフトアップ」「脂肪燃焼」「アンチエイジング」「デトックス」等は使用禁止
- 「若返り」「シワが消える」「美白」「たるみ改善」等の身体変化表現は禁止
- 表現可能範囲：角質層まで、物理的作用、使用感、化粧品の効能効果に準ずる範囲
- EMS機器は「筋肉トレーニング」「筋肉を鍛える」の表現は可（エビデンス必要）
- 「血行促進」「細胞活性化」「ターンオーバー正常化」等の医療的表現は禁止
"""
    }
    
    return guidance_map.get(category, guidance_map["美容機器・健康器具・その他"])

def create_demo_response(text, text_type, category, special_points=''):
    """
    Claude APIが利用できない場合のデモ用レスポンスを生成
    実際の入力テキストを分析して適切な問題箇所を特定
    """
    demo_issues = []
    overall_risk = "低"
    
    # 実際のテキストを分析してNG表現を検出
    ng_patterns = {
        "アンチエイジング": {
            "reason": "「アンチエイジング」は老化に関する直接的な表現で、化粧品では使用できません。",
            "risk_level": "高",
            "suggestions": ["エイジングケア（年齢に応じたお手入れ）", "ハリ・ツヤを与える", "うるおいのある肌へ導く"]
        },
        "マイナス10歳": {
            "reason": "年齢に関する具体的な数値表現は、効果を断定的に表現するため薬機法に抵触します。",
            "risk_level": "高", 
            "suggestions": ["若々しい印象の肌へ", "ハリのある肌に導く", "つややかな肌へ"]
        },
        "美白": {
            "reason": "「美白」は医薬部外品でのみ使用可能な効能表現で、一般化粧品では使用できません。",
            "risk_level": "高",
            "suggestions": ["透明感のある肌へ", "明るい印象の肌に導く", "くすみのない肌へ"]
        },
        "シミが消える": {
            "reason": "「消える」は治療的効果を暗示する表現で、化粧品では使用できません。",
            "risk_level": "高",
            "suggestions": ["メラニンの生成を抑え、シミ・そばかすを防ぐ", "透明感を与える", "明るい肌へ導く"]
        }
    }
    
    # テキスト内のNG表現を検索
    for pattern, info in ng_patterns.items():
        if pattern in text:
            demo_issues.append({
                "fragment": pattern,
                "reason": info["reason"],
                "risk_level": info["risk_level"],
                "suggestions": info["suggestions"]
            })
            if info["risk_level"] == "高":
                overall_risk = "高"
            elif info["risk_level"] == "中" and overall_risk == "低":
                overall_risk = "中"
    
    # 問題が見つからない場合のフォールバック
    if not demo_issues:
        demo_issues = [
            {
                "fragment": "（特に大きな問題は検出されませんでした）",
                "reason": "この表現は比較的安全ですが、より薬機法に準拠した表現に改善することができます。",
                "risk_level": "低",
                "suggestions": ["より適切な表現1", "より適切な表現2", "より適切な表現3"]
            }
        ]
    
    # 実際のテキストに基づいてリライト案を生成
    if "アンチエイジング" in text and "マイナス10歳" in text:
        # アンチエイジング + 年齢関連の場合
        conservative = "エイジングケアクリーム（年齢に応じたお手入れ）でハリのある健やかな肌へ"
        balanced = "エイジングケアクリームで若々しい印象の肌に導く"
        appealing = "エイジングケアクリームで輝くようなハリ・ツヤ肌へ"
    elif "美白" in text:
        # 美白関連の場合
        conservative = "透明感のある健やかな肌へ導くクリーム"
        balanced = "明るく透明感のある肌に導くクリーム"
        appealing = "輝くような透明感、理想の肌へ導くクリーム"
    else:
        # その他の場合
        conservative = "健やかでうるおいのある肌へ導くクリーム"
        balanced = "ハリ・ツヤのある美しい肌に導くクリーム"
        appealing = "輝くような美肌へ導く高機能クリーム"
    
    return {
        "overall_risk": overall_risk,
        "risk_counts": {
            "total": len(demo_issues),
            "high": len([i for i in demo_issues if i["risk_level"] == "高"]),
            "medium": len([i for i in demo_issues if i["risk_level"] == "中"]),
            "low": len([i for i in demo_issues if i["risk_level"] == "低"])
        },
        "issues": demo_issues,
        "rewritten_texts": {
            "conservative": {
                "text": conservative,
                "explanation": "最も安全な表現を選択し、薬機法に抵触するリスクを最小限に抑えています。一般化粧品で使用可能な基本的な効能効果の範囲内で表現しています。"
            },
            "balanced": {
                "text": balanced,
                "explanation": "安全性を保ちながらも、消費者にとって魅力的な表現を使用しています。薬機法の範囲内で適切なイメージ訴求を行っています。"
            },
            "appealing": {
                "text": appealing,
                "explanation": "法的リスクを最小限に抑えつつ、消費者の興味を引く表現を使用しています。感覚的で印象的な言葉を活用して訴求力を高めています。"
            }
        }
    }

@app.route('/', methods=['GET'])
def health_check():
    """
    ヘルスチェックエンドポイント
    APIサーバーの稼働状況を確認
    """
    return jsonify({
        "status": "healthy",
        "service": "薬機法リスクチェッカー API",
        "version": "2.0.0",
        "claude_api": "connected" if claude_client else "disconnected",
        "notion_api": "connected" if notion_api_key and notion_database_id else "disconnected",
        "ng_data_count": len(ng_expressions_data) if ng_expressions_data is not None else 0,
        "csv_module": "enabled",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/check', methods=['POST'])
@require_api_key
@require_rate_limit
def check_text():
    """
    薬機法リスクチェック メインエンドポイント
    Claude APIとCSVデータを活用した高精度チェック
    """
    try:
        # リクエストデータの取得とバリデーション
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        # 必須パラメータのチェック
        if 'text' not in data or 'type' not in data:
            return jsonify({
                "error": "Missing required parameters. 'text' and 'type' are required."
            }), 400
        
        text = data['text'].strip()
        text_type = data['type']
        category = data.get('category', '化粧品')  # デフォルトは化粧品
        special_points = data.get('special_points', '').strip()  # 特に訴求したいポイント（オプション）
        
        # テキストの空文字チェック
        if not text:
            return jsonify({"error": "Text cannot be empty"}), 400
        
        # 文字数制限チェック
        if len(text) > 500:
            return jsonify({"error": "Text too long. Maximum 500 characters allowed."}), 400
        
        # 商品カテゴリの妥当性チェック
        valid_categories = ["化粧品", "薬用化粧品", "医薬部外品", "サプリメント", "美容機器・健康器具・その他"]
        if category not in valid_categories:
            return jsonify({
                "error": f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            }), 400
        
        # 文章タイプの妥当性チェック
        valid_types = ["キャッチコピー", "LP見出し・タイトル", "商品説明文・広告文・通常テキスト", "お客様の声"]
        if text_type not in valid_types:
            return jsonify({
                "error": f"Invalid type. Must be one of: {', '.join(valid_types)}"
            }), 400
        
        # ログ出力
        logger.info(f"チェック開始 - Category: {category}, Type: {text_type}, Text length: {len(text)}, Special points: {'あり' if special_points else 'なし'}")
        
        # キャッシュチェック
        cache_key = check_cache.get_cache_key(text, category, text_type, special_points)
        cached_result = check_cache.get(cache_key)
        
        if cached_result:
            logger.info("キャッシュから結果を返します")
            # キャッシュヒット時は高速レスポンスであることを示すフラグを追加
            cached_result['from_cache'] = True
            cached_result['response_time'] = 0.1  # キャッシュヒット時の応答時間
            return jsonify(cached_result)
        
        # 応答時間の計測開始
        start_time = time.time()
        
        # Claude API呼び出し
        result = call_claude_api(text, text_type, category, special_points)
        
        # 応答時間の計測終了
        response_time = round(time.time() - start_time, 2)
        result['response_time'] = response_time
        result['from_cache'] = False
        
        # キャッシュに保存
        check_cache.set(cache_key, result)
        
        logger.info(f"チェック完了 - Claude APIレスポンス受信 (応答時間: {response_time}秒)")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@app.route('/api/check/stream', methods=['POST'])
@require_api_key  
@require_rate_limit
def check_text_stream():
    """
    薬機法リスクチェック ストリーミングエンドポイント
    結果を段階的に返すことでUXを向上
    """
    def generate():
        try:
            # リクエストデータの取得
            data = request.get_json()
            text = data['text'].strip()
            text_type = data['type']
            category = data.get('category', '化粧品')
            special_points = data.get('special_points', '').strip()
            
            # イベント1: 開始通知
            yield f"data: {json.dumps({'type': 'start', 'message': 'チェックを開始しました'}, ensure_ascii=False)}\n\n"
            
            # キャッシュチェック
            cache_key = check_cache.get_cache_key(text, category, text_type, special_points)
            cached_result = check_cache.get(cache_key)
            
            if cached_result:
                # キャッシュヒット時は即座に全結果を返す
                yield f"data: {json.dumps({'type': 'cache_hit', 'message': 'キャッシュから結果を取得'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'complete', 'result': cached_result}, ensure_ascii=False)}\n\n"
                return
            
            # イベント2: CSVチェック開始
            yield f"data: {json.dumps({'type': 'csv_check', 'message': 'NG表現データベースをチェック中...'}, ensure_ascii=False)}\n\n"
            
            # CSVからNG表現をチェック（簡易版）
            csv_ng_words = []
            csv_file_path = os.path.join(os.path.dirname(__file__), 'data', 'ng_expressions.csv')
            if os.path.exists(csv_file_path):
                with open(csv_file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['NG表現'] in text:
                            csv_ng_words.append({
                                'word': row['NG表現'],
                                'risk': row.get('リスクレベル', '中')
                            })
            
            if csv_ng_words:
                yield f"data: {json.dumps({'type': 'ng_words_found', 'words': csv_ng_words}, ensure_ascii=False)}\n\n"
            
            # イベント3: AIチェック開始
            yield f"data: {json.dumps({'type': 'ai_check', 'message': 'AIによる詳細分析を実行中...'}, ensure_ascii=False)}\n\n"
            
            # Claude API呼び出し
            result = call_claude_api(text, text_type, category, special_points)
            
            # キャッシュに保存
            check_cache.set(cache_key, result)
            
            # イベント4: 完了
            yield f"data: {json.dumps({'type': 'complete', 'result': result}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"ストリーミングエラー: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # nginxのバッファリングを無効化
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/cache/refresh', methods=['POST'])
@require_api_key
def refresh_cache():
    """
    キャッシュを手動でリフレッシュするエンドポイント
    """
    try:
        cache_type = request.json.get('type', 'all') if request.is_json else 'all'
        
        # キャッシュを無効化
        data_cache.invalidate_cache(cache_type)
        
        return jsonify({
            "status": "success",
            "message": f"{cache_type}キャッシュをリフレッシュしました",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"キャッシュリフレッシュエラー: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/cache/status', methods=['GET'])
def cache_status():
    """
    キャッシュの状態を確認するエンドポイント
    """
    try:
        data_cache_keys = list(data_cache.data_cache.keys())
        rule_cache_keys = list(data_cache.rule_cache.keys())
        
        return jsonify({
            "status": "success",
            "data_cache": {
                "keys": data_cache_keys,
                "count": len(data_cache_keys)
            },
            "rule_cache": {
                "keys": rule_cache_keys,
                "count": len(rule_cache_keys)
            },
            "file_watcher_active": data_cache.observer and data_cache.observer.is_alive() if WATCHDOG_AVAILABLE else False,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"キャッシュ状態確認エラー: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/guide', methods=['GET'])
def get_guide():
    """
    薬機法ガイドコンテンツ取得エンドポイント
    Notionデータベースから薬機法ガイド情報を取得
    """
    try:
        # Notion API設定の確認
        if not notion_api_key or not notion_database_id:
            logger.warning("Notion API設定が不完全 - フォールバックデータを返却")
            return jsonify(get_fallback_guide_data())
        
        logger.info("Notion API呼び出し開始")
        
        # Notion API呼び出し
        guide_data = fetch_notion_database()
        
        logger.info(f"Notion APIからガイドデータ取得完了: {len(guide_data)}件")
        
        return jsonify({
            "status": "success",
            "data": guide_data,
            "source": "notion",
            "count": len(guide_data),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Notion API呼び出しエラー: {str(e)}")
        
        # フォールバック: 静的データを返却
        fallback_data = get_fallback_guide_data()
        
        return jsonify({
            "status": "fallback",
            "data": fallback_data,
            "source": "fallback",
            "error_message": str(e),
            "count": len(fallback_data),
            "timestamp": datetime.now().isoformat()
        })

def call_claude_api(text, text_type, category, special_points=''):
    """
    Claude APIを呼び出して薬機法チェックを実行
    
    Args:
        text (str): チェック対象のテキスト
        text_type (str): テキストの種類
        category (str): 商品カテゴリ
        special_points (str): 特に訴求したいポイント（オプション）
    
    Returns:
        dict: Claude APIからの応答（JSON形式）
    
    Raises:
        Exception: API呼び出しに失敗した場合
    """
    try:
        # データファイルとルールファイルの読み込み（キャッシュ使用）
        all_data_content = load_all_data_files()
        rule_content = load_rule_file(text_type)
        
        # プロンプトの構築
        system_prompt = create_system_prompt()
        user_prompt = create_user_prompt(text, text_type, category, all_data_content, rule_content, special_points)
        
        logger.info("Claude API呼び出し開始")
        
        # Claude クライアントの確認
        if claude_client is None:
            logger.warning("Claude APIが利用できません - デモ用の応答を生成します")
            return create_demo_response(text, text_type, category, special_points)
        
        # Claude APIリクエスト (高速化最適化)
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",  # Claude Sonnet 4
            max_tokens=4000,  # 3つのリライト案に対応
            temperature=0,  # 決定論的出力で最高速度
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        
        # レスポンスの解析
        response_text = response.content[0].text.strip()
        logger.info(f"Claude API応答受信: {len(response_text)} characters")
        
        # ```json```ブロックを除去
        if response_text.startswith("```json") and response_text.endswith("```"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```") and response_text.endswith("```"):
            response_text = response_text[3:-3].strip()
        
        # 堅牢なJSONパース処理
        result = parse_claude_response_robust(response_text, text)
        
        if result is None:
            logger.error("Claude APIレスポンスの解析に完全に失敗しました")
            return create_fallback_response(text, "Claude APIレスポンスの解析に失敗しました")
        
        return result
    
    except anthropic.APIError as e:
        logger.error(f"Claude API エラー: {str(e)}")
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラー詳細: {e.__dict__ if hasattr(e, '__dict__') else 'No details'}")
        
        # 認証エラーの場合は3.5-sonnetで再試行
        if "authentication_error" in str(e).lower() or "invalid x-api-key" in str(e).lower() or "401" in str(e):
            logger.warning("認証エラーが発生しました。Claude 3.5 Sonnetで再試行します。")
            return call_claude_api_fallback(text, text_type, category, special_points)
        
        # モデルが見つからない場合は3.5-sonnetにフォールバック
        if "model_not_found" in str(e).lower() or "does not exist" in str(e).lower():
            logger.warning("指定されたモデルが見つかりません。Claude 3.5 Sonnetにフォールバックします。")
            return call_claude_api_fallback(text, text_type, category, special_points)
        
        return create_fallback_response(text, f"Claude API呼び出しエラー: {str(e)}")
    
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        logger.error(f"エラータイプ: {type(e).__name__}")
        import traceback
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        return create_fallback_response(text, f"予期しないエラー: {str(e)}")

def parse_claude_response_robust(response_text, original_text):
    """
    Claude APIレスポンスを堅牢にJSON解析する
    
    Args:
        response_text (str): Claude APIからの応答テキスト
        original_text (str): 元のチェック対象テキスト
    
    Returns:
        dict: 解析されたJSONデータまたはNone
    """
    logger.info(f"JSON解析開始 - レスポンス長: {len(response_text)} 文字")
    
    # 手法1: 標準のJSONパースを試行
    try:
        result = json.loads(response_text)
        validate_claude_response(result)
        logger.info("標準JSONパース成功")
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"標準JSONパース失敗: {str(e)}")
    
    # 手法2: コードブロックを除去して再試行
    cleaned_text = clean_json_response(response_text)
    if cleaned_text != response_text:
        try:
            result = json.loads(cleaned_text)
            validate_claude_response(result)
            logger.info("クリーニング後JSONパース成功")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"クリーニング後JSONパース失敗: {str(e)}")
    
    # 手法3: 部分的なJSON修復を試行
    repaired_text = repair_incomplete_json(response_text)
    if repaired_text:
        try:
            result = json.loads(repaired_text)
            validate_claude_response(result)
            logger.info("修復後JSONパース成功")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"修復後JSONパース失敗: {str(e)}")
    
    # 手法4: 正規表現でJSON部分を抽出
    extracted_json = extract_json_with_regex(response_text)
    if extracted_json:
        try:
            result = json.loads(extracted_json)
            validate_claude_response(result)
            logger.info("正規表現抽出後JSONパース成功")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"正規表現抽出後JSONパース失敗: {str(e)}")
    
    # 手法5: 部分的なデータでフォールバック応答を生成
    partial_data = extract_partial_data(response_text)
    if partial_data:
        logger.info("部分データからフォールバック応答を生成")
        return create_partial_fallback_response(original_text, partial_data)
    
    # すべて失敗した場合
    logger.error("すべてのJSON解析手法が失敗しました")
    logger.error(f"Raw response: {response_text[:500]}...")  # 最初の500文字のみログ出力
    return None

def clean_json_response(response_text):
    """
    レスポンステキストからJSON以外の不要な部分を除去
    """
    # ```json```ブロックを除去
    if response_text.startswith("```json") and response_text.endswith("```"):
        return response_text[7:-3].strip()
    elif response_text.startswith("```") and response_text.endswith("```"):
        return response_text[3:-3].strip()
    
    # 前後の空白文字を除去
    cleaned = response_text.strip()
    
    # JSON以外のテキストが前後にある場合は除去を試行
    if cleaned.startswith('{') and cleaned.endswith('}'):
        return cleaned
    
    # JSON部分を探して抽出
    start = cleaned.find('{')
    end = cleaned.rfind('}') + 1
    
    if start != -1 and end > start:
        return cleaned[start:end]
    
    return cleaned

def repair_incomplete_json(response_text):
    """
    不完全なJSONを修復する試み
    """
    try:
        # 末尾のカンマやブレースが不足している場合を修復
        text = response_text.strip()
        
        # 末尾にカンマがある場合は除去
        if text.endswith(','):
            text = text[:-1]
        
        # 開きブレースの数を数えて、閉じブレースが不足している場合は追加
        open_braces = text.count('{')
        close_braces = text.count('}')
        
        if open_braces > close_braces:
            text += '}' * (open_braces - close_braces)
        
        # 開き括弧の数を数えて、閉じ括弧が不足している場合は追加
        open_brackets = text.count('[')
        close_brackets = text.count(']')
        
        if open_brackets > close_brackets:
            text += ']' * (open_brackets - close_brackets)
        
        # ダブルクォートが開いたままの文字列を修復
        text = fix_unclosed_strings(text)
        
        return text
        
    except Exception as e:
        logger.warning(f"JSON修復中にエラー: {str(e)}")
        return None

def fix_unclosed_strings(text):
    """
    開いたままの文字列を修復
    """
    try:
        # 簡単な修復: 最後のダブルクォートが閉じられていない場合
        quote_count = text.count('"')
        if quote_count % 2 == 1:  # 奇数の場合は最後に追加
            # 最後のダブルクォートの後に適切な位置で閉じる
            last_quote_pos = text.rfind('"')
            if last_quote_pos != -1:
                # 最後のクォートの後に適切な位置で終了
                remaining = text[last_quote_pos + 1:]
                # 次の区切り文字までを探してクォートで閉じる
                next_delimiter = -1
                for char in [',', '}', ']', '\n']:
                    pos = remaining.find(char)
                    if pos != -1 and (next_delimiter == -1 or pos < next_delimiter):
                        next_delimiter = pos
                
                if next_delimiter != -1:
                    text = text[:last_quote_pos + 1 + next_delimiter] + '"' + text[last_quote_pos + 1 + next_delimiter:]
                else:
                    text += '"'
        
        return text
        
    except Exception as e:
        logger.warning(f"文字列修復中にエラー: {str(e)}")
        return text

def extract_json_with_regex(response_text):
    """
    正規表現でJSON部分を抽出
    """
    try:
        # JSON構造を探す正規表現パターン
        # 開始の { から対応する } までを抽出
        pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        if matches:
            # 最も長いマッチ（最も完全な可能性が高い）を選択
            longest_match = max(matches, key=len)
            return longest_match
        
        # より簡単なパターンで再試行
        start = response_text.find('{')
        if start != -1:
            brace_count = 0
            for i, char in enumerate(response_text[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return response_text[start:i+1]
        
        return None
        
    except Exception as e:
        logger.warning(f"正規表現抽出中にエラー: {str(e)}")
        return None

def extract_partial_data(response_text):
    """
    レスポンスから部分的なデータを抽出
    """
    partial_data = {}
    
    try:
        # overall_riskを抽出
        risk_match = re.search(r'"overall_risk"\s*:\s*"(高|中|低)"', response_text)
        if risk_match:
            partial_data['overall_risk'] = risk_match.group(1)
        
        # issuesを抽出（簡単なパターン）
        issues_pattern = r'"fragment"\s*:\s*"([^"]+)"'
        fragment_matches = re.findall(issues_pattern, response_text)
        if fragment_matches:
            partial_data['fragments'] = fragment_matches
        
        # rewritten_textsを抽出
        rewrite_patterns = {
            'conservative': r'"conservative"\s*:\s*\{[^}]*"text"\s*:\s*"([^"]+)"',
            'balanced': r'"balanced"\s*:\s*\{[^}]*"text"\s*:\s*"([^"]+)"',
            'appealing': r'"appealing"\s*:\s*\{[^}]*"text"\s*:\s*"([^"]+)"'
        }
        
        for key, pattern in rewrite_patterns.items():
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                if 'rewrites' not in partial_data:
                    partial_data['rewrites'] = {}
                partial_data['rewrites'][key] = match.group(1)
        
        return partial_data if partial_data else None
        
    except Exception as e:
        logger.warning(f"部分データ抽出中にエラー: {str(e)}")
        return None

def create_partial_fallback_response(original_text, partial_data):
    """
    部分データからフォールバック応答を作成
    """
    # デフォルト値で基本構造を作成
    result = {
        "overall_risk": partial_data.get('overall_risk', '中'),
        "risk_counts": {
            "total": len(partial_data.get('fragments', [])) or 1,
            "high": 0,
            "medium": 1,
            "low": 0
        },
        "issues": [],
        "rewritten_texts": {
            "conservative": {
                "text": original_text,
                "explanation": "APIレスポンスが不完全なため、部分的な情報から生成しました。"
            },
            "balanced": {
                "text": original_text,
                "explanation": "APIレスポンスが不完全なため、部分的な情報から生成しました。"
            },
            "appealing": {
                "text": original_text,
                "explanation": "APIレスポンスが不完全なため、部分的な情報から生成しました。"
            }
        }
    }
    
    # 部分データがある場合は上書き
    if 'fragments' in partial_data:
        for fragment in partial_data['fragments']:
            result['issues'].append({
                "fragment": fragment,
                "reason": "レスポンスが不完全なため、詳細な分析結果を表示できません。手動で確認してください。",
                "risk_level": "中",
                "suggestions": ["専門家に相談してください", "手動で確認してください"]
            })
    
    if 'rewrites' in partial_data:
        for key, text in partial_data['rewrites'].items():
            if key in result['rewritten_texts']:
                result['rewritten_texts'][key]['text'] = text
                result['rewritten_texts'][key]['explanation'] = "部分的なAPIレスポンスから抽出されたリライト案です。完全な解析結果ではないため、専門家による確認をお勧めします。"
    
    return result

def call_claude_api_fallback(text, text_type, category, special_points=None):
    """
    モデルエラーや認証エラー時のフォールバック処理
    Claude 3.5 Sonnetを使用して再度API呼び出しを行う
    """
    try:
        logger.info("フォールバック: Claude 3.5 Sonnetで再試行")
        
        # プロンプトの構築
        system_prompt = create_system_prompt()
        user_prompt = create_user_prompt(text, text_type, category, csv_reference_text, markdown_reference_text, special_points)
        
        # Claude 3.5 Sonnetで再試行
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",  # 確実に存在するモデル
            max_tokens=4000,
            temperature=0,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        
        # レスポンスの解析
        response_text = response.content[0].text.strip()
        logger.info(f"フォールバック成功: {len(response_text)} characters")
        
        # ```json```ブロックを除去
        if response_text.startswith("```json") and response_text.endswith("```"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```") and response_text.endswith("```"):
            response_text = response_text[3:-3].strip()
        
        # JSONパース - 堅牢処理版を使用
        result = parse_claude_response_robust(response_text, text)
        
        if result is None:
            logger.error("フォールバックモデルでもJSON解析に失敗しました")
            return create_fallback_response(text, "JSON解析エラー")
        
        return result
        
    except Exception as e:
        logger.error(f"フォールバックも失敗: {str(e)}")
        return create_fallback_response(text, "Claude APIの呼び出しに失敗しました")

def validate_claude_response(response):
    """
    Claude APIレスポンスの構造を検証
    
    Args:
        response (dict): Claude APIからの応答
        
    Raises:
        ValueError: レスポンス構造が不正な場合
    """
    required_fields = ["overall_risk", "risk_counts", "issues", "rewritten_texts"]
    
    for field in required_fields:
        if field not in response:
            raise ValueError(f"必須フィールド '{field}' がレスポンスに含まれていません")
    
    # overall_riskの検証
    valid_risk_levels = ["高", "中", "低"]
    if response["overall_risk"] not in valid_risk_levels:
        raise ValueError("overall_riskの値が不正です")
    
    # risk_countsの検証
    risk_counts = response["risk_counts"]
    required_count_fields = ["total", "high", "medium", "low"]
    
    for field in required_count_fields:
        if field not in risk_counts or not isinstance(risk_counts[field], int):
            raise ValueError(f"risk_counts.{field}が不正です")
    
    # issuesの検証
    if not isinstance(response["issues"], list):
        raise ValueError("issuesはリスト形式である必要があります")
    
    for issue in response["issues"]:
        required_issue_fields = ["fragment", "reason", "risk_level", "suggestions"]
        for field in required_issue_fields:
            if field not in issue:
                raise ValueError(f"issue内の必須フィールド '{field}' が不足しています")
    
    # rewritten_textsの検証
    if not isinstance(response["rewritten_texts"], dict):
        raise ValueError("rewritten_textsは辞書形式である必要があります")
    
    required_rewrite_keys = ["conservative", "balanced", "appealing"]
    for key in required_rewrite_keys:
        if key not in response["rewritten_texts"]:
            raise ValueError(f"rewritten_texts.{key}が不足しています")
        
        rewrite_data = response["rewritten_texts"][key]
        
        # 新形式（オブジェクト）と旧形式（文字列）の両方をサポート
        if isinstance(rewrite_data, str):
            # 旧形式: 文字列として有効
            continue
        elif isinstance(rewrite_data, dict):
            # 新形式: textとexplanationを含むオブジェクト
            if "text" not in rewrite_data or not isinstance(rewrite_data["text"], str):
                raise ValueError(f"rewritten_texts.{key}.textが不正です")
            if "explanation" not in rewrite_data or not isinstance(rewrite_data["explanation"], str):
                raise ValueError(f"rewritten_texts.{key}.explanationが不正です")
        else:
            raise ValueError(f"rewritten_texts.{key}が不正な形式です")

def create_fallback_response(text, error_message):
    """
    Claude API呼び出しに失敗した場合のフォールバック応答を生成
    
    Args:
        text (str): 元のテキスト
        error_message (str): エラーメッセージ
        
    Returns:
        dict: フォールバック応答
    """
    logger.warning(f"フォールバック応答を生成: {error_message}")
    
    return {
        "overall_risk": "中",
        "risk_counts": {
            "total": 1,
            "high": 0,
            "medium": 1,
            "low": 0
        },
        "issues": [
            {
                "fragment": "API呼び出しエラー",
                "reason": f"システムエラーが発生しました。{error_message} 手動での確認をお勧めします。",
                "risk_level": "中",
                "suggestions": [
                    "専門家にご相談ください",
                    "手動でのチェックを実施してください",
                    "しばらく時間をおいて再試行してください"
                ]
            }
        ],
        "rewritten_texts": {
            "conservative": {
                "text": text,
                "explanation": "APIエラーのため、修正案を生成できませんでした。元のテキストを表示しています。"
            },
            "balanced": {
                "text": text, 
                "explanation": "APIエラーのため、修正案を生成できませんでした。元のテキストを表示しています。"
            },
            "appealing": {
                "text": text,
                "explanation": "APIエラーのため、修正案を生成できませんでした。元のテキストを表示しています。"
            }
        }
    }

def fetch_notion_database():
    """
    Notion APIからデータベースコンテンツを取得
    
    Returns:
        list: 整形されたガイドデータのリスト
    """
    try:
        # Notion API エンドポイント
        url = f"https://api.notion.com/v1/databases/{notion_database_id}/query"
        
        # リクエストヘッダー
        headers = {
            "Authorization": f"Bearer {notion_api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # リクエストボディ（フィルタリングやソートが必要な場合）
        payload = {
            "page_size": 100  # 最大100件取得
            # ソートは一旦削除（Notionのプロパティ名が不明なため）
        }
        
        logger.info(f"Notion API Request: {url}")
        
        # Notion API呼び出し
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Notion API Error: {response.status_code} - {response.text}")
            raise Exception(f"Notion API returned status {response.status_code}")
        
        data = response.json()
        
        # データの整形
        guide_items = []
        
        for page in data.get("results", []):
            try:
                # ページのプロパティから情報抽出
                properties = page.get("properties", {})
                
                # タイトルの抽出（通常は "名前" または "タイトル" プロパティ）
                title = extract_title_from_properties(properties)
                
                # コンテンツの抽出（ページの子ブロックから取得）
                content = extract_content_from_page(page.get("id"))
                
                # カテゴリなどの追加情報
                category = extract_property_value(properties, "カテゴリ")
                priority = extract_property_value(properties, "優先度")
                
                guide_item = {
                    "id": page.get("id"),
                    "title": title,
                    "content": content,
                    "category": category,
                    "priority": priority,
                    "created_time": page.get("created_time"),
                    "last_edited_time": page.get("last_edited_time")
                }
                
                guide_items.append(guide_item)
                
            except Exception as e:
                logger.warning(f"ページの処理中にエラー: {str(e)}")
                continue
        
        return guide_items
        
    except requests.RequestException as e:
        logger.error(f"Notion API通信エラー: {str(e)}")
        raise Exception(f"Notion API通信に失敗しました: {str(e)}")
    
    except Exception as e:
        logger.error(f"Notion データ処理エラー: {str(e)}")
        raise Exception(f"Notionデータの処理に失敗しました: {str(e)}")

def extract_title_from_properties(properties):
    """
    Notionページのプロパティからタイトルを抽出
    """
    # 一般的なタイトルプロパティ名を順番に確認
    title_candidates = ["名前", "タイトル", "Title", "Name"]
    
    for candidate in title_candidates:
        if candidate in properties:
            prop = properties[candidate]
            if prop.get("type") == "title" and prop.get("title"):
                return "".join([text.get("plain_text", "") for text in prop["title"]])
    
    # フォールバック: 最初のtitleタイプのプロパティを使用
    for prop_name, prop_value in properties.items():
        if prop_value.get("type") == "title" and prop_value.get("title"):
            return "".join([text.get("plain_text", "") for text in prop_value["title"]])
    
    return "無題"

def extract_property_value(properties, property_name):
    """
    Notionページの特定のプロパティから値を抽出
    """
    if property_name not in properties:
        return None
    
    prop = properties[property_name]
    prop_type = prop.get("type")
    
    if prop_type == "rich_text" and prop.get("rich_text"):
        return "".join([text.get("plain_text", "") for text in prop["rich_text"]])
    elif prop_type == "select" and prop.get("select"):
        return prop["select"].get("name")
    elif prop_type == "multi_select" and prop.get("multi_select"):
        return [item.get("name") for item in prop["multi_select"]]
    elif prop_type == "number":
        return prop.get("number")
    elif prop_type == "checkbox":
        return prop.get("checkbox")
    elif prop_type == "date" and prop.get("date"):
        return prop["date"].get("start")
    
    return None

def extract_content_from_page(page_id):
    """
    Notionページの子ブロックからコンテンツを抽出
    """
    try:
        # ページの子ブロック取得
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        headers = {
            "Authorization": f"Bearer {notion_api_key}",
            "Notion-Version": "2022-06-28"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"ブロック取得エラー: {response.status_code}")
            return ""
        
        blocks_data = response.json()
        content_parts = []
        
        for block in blocks_data.get("results", []):
            block_type = block.get("type")
            
            if block_type == "paragraph" and block.get("paragraph", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["paragraph"]["rich_text"]])
                if text.strip():
                    content_parts.append(text.strip())
            
            elif block_type == "heading_1" and block.get("heading_1", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["heading_1"]["rich_text"]])
                if text.strip():
                    content_parts.append(f"# {text.strip()}")
            
            elif block_type == "heading_2" and block.get("heading_2", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["heading_2"]["rich_text"]])
                if text.strip():
                    content_parts.append(f"## {text.strip()}")
            
            elif block_type == "bulleted_list_item" and block.get("bulleted_list_item", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["bulleted_list_item"]["rich_text"]])
                if text.strip():
                    content_parts.append(f"• {text.strip()}")
        
        return "\n\n".join(content_parts) if content_parts else ""
        
    except Exception as e:
        logger.warning(f"コンテンツ抽出エラー: {str(e)}")
        return ""

def get_fallback_guide_data():
    """
    Notion API が利用できない場合のフォールバックガイドデータ
    """
    return [
        {
            "id": "fallback-1",
            "title": "薬機法の基本",
            "content": "薬機法（医薬品医療機器等法）は、化粧品や医薬品の品質、有効性、安全性を確保するための法律です。美容系商品の広告では、効果効能の表現に厳格な制限があります。",
            "category": "基本知識",
            "priority": "高",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        },
        {
            "id": "fallback-2", 
            "title": "化粧品で使用できない表現",
            "content": "• 「シミが消える」「シワがなくなる」- 医薬品的な効果を暗示\n• 「アンチエイジング効果」「老化防止」- 老化に関する直接的な表現\n• 「医学的に証明された」「臨床試験で実証」- 科学的根拠の過度な強調\n• 「完全に」「絶対に」「確実に」- 効果を断定的に表現",
            "category": "NG表現",
            "priority": "高",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        },
        {
            "id": "fallback-3",
            "title": "化粧品で使用可能な表現",
            "content": "• 「うるおいを与える」「乾燥を防ぐ」- 化粧品の基本的な効能効果\n• 「肌を整える」「肌にハリを与える」- 適切な効果の表現\n• 「メイクアップ効果により」- 見た目の効果を明確化\n• 「使用感には個人差があります」- 効果の個人差を明記",
            "category": "OK表現", 
            "priority": "高",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        },
        {
            "id": "fallback-4",
            "title": "チェックのポイント",
            "content": "• 医薬品的な効果を暗示していないか\n• 効果を断定的に表現していないか\n• 科学的根拠を過度に強調していないか\n• 化粧品の効能効果の範囲内か\n• 個人差について言及しているか",
            "category": "チェックポイント",
            "priority": "中",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        }
    ]

@app.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """405エラーハンドラー"""
    return jsonify({
        "error": "Method Not Allowed",
        "message": "The method is not allowed for the requested URL"
    }), 405

# Gunicornでもフラスコ開発サーバーでも初期化が実行されるようにモジュールレベルで呼び出す
initialize_app()

if __name__ == '__main__':
    
    # 開発サーバーの起動
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print("=" * 60)
    print("薬機法リスクチェッカー API サーバー (Claude API連携版)")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Debug: {debug_mode}")
    print(f"Claude API: {'✅ 接続済み' if claude_client else '❌ 未接続'}")
    print(f"NG表現データ: {len(ng_expressions_data)}件" if ng_expressions_data is not None else "❌ 読み込み失敗")
    print(f"Health Check: http://localhost:{port}/")
    print(f"API Endpoint: http://localhost:{port}/api/check")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode
    )