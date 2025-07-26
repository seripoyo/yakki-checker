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

# ログ設定を先に行う
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import csv
import requests
from datetime import datetime
from flask import Flask, request, jsonify
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
        'http://127.0.0.1:3000',
        'http://127.0.0.1:8000'
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
REQUEST_LIMIT = 100  # 1時間あたりのリクエスト数制限
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
3. **3つのバリエーションリライト**: 指摘事項を全て修正し、広告効果をできるだけ維持したまま、薬機法に準拠した文章を3種類作成
   - **保守的バージョン**: 最も安全で確実な表現を使用
   - **バランス版**: 安全性と訴求力のバランスを重視
   - **訴求力重視版**: 法的リスクを最小限にしつつ、訴求力を最大化
   - **重要**: 「特に訴求したいポイント」が指定されている場合、各リライト案でそのポイントを薬機法に準拠しながら可能な限り反映すること
   - **重要**: 各リライト案には、なぜそのリライトが薬機法的に適切なのかの解説を必ず含めること
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
    """
    # カテゴリ別のデモ応答を生成
    if category == "化粧品":
        demo_issues = [
            {
                "fragment": "美白効果",
                "reason": "「美白」は医薬部外品でのみ使用可能な効能表現で、一般化粧品では使用できません。",
                "risk_level": "高",
                "suggestions": ["透明感のある肌へ", "明るい印象の肌に導く", "くすみのない肌へ"]
            }
        ]
        overall_risk = "高"
        conservative = "透明感のある健やかな肌へ"
        balanced = "明るく透明感のある肌に導く"
        appealing = "輝くような透明感、理想の肌へ"
    else:
        # その他のカテゴリ用のデモ応答
        demo_issues = [
            {
                "fragment": "サンプルNG表現",
                "reason": f"{category}では薬機法上適切ではない表現です。",
                "risk_level": "中",
                "suggestions": ["適切な表現1", "適切な表現2", "適切な表現3"]
            }
        ]
        overall_risk = "中"
        conservative = "デモ用保守的リライト案"
        balanced = "デモ用バランス型リライト案"
        appealing = "デモ用訴求力重視リライト案"
    
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
        
        # Claude API呼び出し
        result = call_claude_api(text, text_type, category, special_points)
        
        logger.info("チェック完了 - Claude APIレスポンス受信")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

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
        
        # JSONパース
        try:
            result = json.loads(response_text)
            
            # レスポンス構造の検証
            validate_claude_response(result)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Claude APIレスポンスのJSONパースエラー: {str(e)}")
            logger.error(f"Raw response: {response_text}")
            
            # フォールバック: 構造化された応答を生成
            return create_fallback_response(text, "JSONパースエラーのため、基本的なチェック結果を返します")
    
    except anthropic.APIError as e:
        logger.error(f"Claude API エラー: {str(e)}")
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラー詳細: {e.__dict__ if hasattr(e, '__dict__') else 'No details'}")
        
        # モデルが見つからない場合は3.5-sonnetにフォールバック
        if "model_not_found" in str(e).lower() or "does not exist" in str(e).lower():
            logger.warning("指定されたモデルが見つかりません。Claude 3.5 Sonnetにフォールバックします。")
            return call_claude_api_fallback(text, text_type, category)
        
        return create_fallback_response(text, f"Claude API呼び出しエラー: {str(e)}")
    
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        logger.error(f"エラータイプ: {type(e).__name__}")
        import traceback
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        return create_fallback_response(text, f"予期しないエラー: {str(e)}")

def call_claude_api_fallback(text, text_type, category):
    """
    モデルエラー時のフォールバック処理
    Claude 3.5 Sonnetを使用して再度API呼び出しを行う
    """
    try:
        logger.info("フォールバック: Claude 3.5 Sonnetで再試行")
        
        # プロンプトの構築
        system_prompt = create_system_prompt()
        user_prompt = create_user_prompt(text, text_type, category, csv_reference_text, markdown_reference_text)
        
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
        
        # JSONパース
        result = json.loads(response_text)
        validate_claude_response(result)
        
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
            "conservative": text,
            "balanced": text,
            "appealing": text
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