# リファクタリング: app.pyからデータモデルクラスを分離
# 変更内容: DataCache、CheckCache、DataFileEventHandlerクラスを独立したモジュールに移動
"""
データモデルモジュール
キャッシュ管理とファイル監視に関するクラスを定義
"""

import os
import time
import threading
import hashlib
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)

# watchdogの可用性チェック
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdogが利用できません。ファイル監視機能が制限されます。")

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
    
    def get_cached_data_content(self, load_all_data_files_func):
        """キャッシュされたデータコンテンツを取得（必要に応じて更新）"""
        with self.lock:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
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
                self.data_cache[cache_key] = load_all_data_files_func()
                
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
    
    def get_cached_rule_content(self, text_type, load_rule_file_func):
        """キャッシュされたルールコンテンツを取得（必要に応じて更新）"""
        with self.lock:
            rule_dir = os.path.join(os.path.dirname(__file__), '..', 'rule')
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
                self.rule_cache[cache_key] = load_rule_file_func(text_type)
                self.update_file_timestamp(file_path)
                logger.info(f"ルールキャッシュ更新完了: {filename}")
            
            return self.rule_cache[cache_key]
    
    def start_file_watcher(self):
        """ファイル監視を開始"""
        if not WATCHDOG_AVAILABLE:
            logger.info("watchdogが利用できないため、ポーリングベースの更新を使用します")
            return
        
        try:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            rule_dir = os.path.join(os.path.dirname(__file__), '..', 'rule')
            
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


class DataFileEventHandler:
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


# watchdog が利用可能な場合のみ FileSystemEventHandler を継承
if WATCHDOG_AVAILABLE:
    class DataFileEventHandler(FileSystemEventHandler, DataFileEventHandler):
        pass


class CheckCache:
    """チェック結果のキャッシュシステム"""
    def __init__(self, max_size=100, ttl=3600):
        self.cache = OrderedDict()  # 順序を保持して古いものから削除
        self.max_size = max_size
        self.ttl = ttl  # Time To Live (秒)
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()
    
    def get_cache_key(self, text, category, text_type, special_points=None, medical_approval=False):
        """キャッシュキーの生成"""
        content = f"{text}|{category}|{text_type}|{special_points or ''}|{medical_approval}"
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