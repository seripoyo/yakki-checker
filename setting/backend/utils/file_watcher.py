# リファクタリング: app.pyからファイル監視機能を分離
# 変更内容: ファイル監視とリアルタイム更新機能を独立したモジュールに移動
"""
ファイル監視モジュール
データファイルとルールファイルの変更をリアルタイムで監視
"""

import os
import time
import threading
import logging
from typing import Callable, List, Dict, Optional

logger = logging.getLogger(__name__)

# watchdogの可用性チェック
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdogが利用できません。ファイル監視機能が制限されます。")

class FileWatcher:
    """ファイル監視とイベント処理クラス"""
    
    def __init__(self, debounce_time: float = 1.0):
        self.observers = []
        self.event_handlers = {}
        self.debounce_time = debounce_time
        self.last_event_times = {}
        self.lock = threading.Lock()
        self.is_running = False
    
    def add_watch_directory(self, directory: str, callback: Callable[[str, str], None], 
                          recursive: bool = False) -> bool:
        """監視ディレクトリを追加"""
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdogが利用できないため、ファイル監視を開始できません")
            return False
        
        if not os.path.exists(directory):
            logger.error(f"監視ディレクトリが存在しません: {directory}")
            return False
        
        try:
            event_handler = FileChangeHandler(self, callback)
            observer = Observer()
            observer.schedule(event_handler, directory, recursive=recursive)
            
            self.observers.append(observer)
            self.event_handlers[directory] = event_handler
            
            logger.info(f"ファイル監視ディレクトリ追加: {directory} (recursive={recursive})")
            return True
            
        except Exception as e:
            logger.error(f"ファイル監視の設定に失敗: {directory} - {e}")
            return False
    
    def start_watching(self) -> bool:
        """ファイル監視を開始"""
        if not WATCHDOG_AVAILABLE or not self.observers:
            logger.info("ファイル監視を開始できません（watchdog未利用またはobserver未設定）")
            return False
        
        try:
            for observer in self.observers:
                observer.start()
            
            self.is_running = True
            logger.info(f"ファイル監視開始: {len(self.observers)}個のディレクトリを監視中")
            return True
            
        except Exception as e:
            logger.error(f"ファイル監視の開始に失敗: {e}")
            return False
    
    def stop_watching(self) -> None:
        """ファイル監視を停止"""
        if not self.is_running:
            return
        
        for observer in self.observers:
            try:
                observer.stop()
                observer.join(timeout=5.0)
            except Exception as e:
                logger.error(f"ファイル監視の停止に失敗: {e}")
        
        self.observers.clear()
        self.event_handlers.clear()
        self.is_running = False
        logger.info("ファイル監視を停止しました")
    
    def should_process_event(self, file_path: str) -> bool:
        """デバウンス処理: イベントを処理すべきかチェック"""
        with self.lock:
            current_time = time.time()
            last_time = self.last_event_times.get(file_path, 0)
            
            if current_time - last_time < self.debounce_time:
                return False
            
            self.last_event_times[file_path] = current_time
            return True
    
    def get_status(self) -> Dict[str, any]:
        """ファイル監視の状態を取得"""
        return {
            'is_running': self.is_running,
            'watchdog_available': WATCHDOG_AVAILABLE,
            'monitored_directories': len(self.observers),
            'last_events_count': len(self.last_event_times)
        }

class FileChangeHandler:
    """ファイル変更イベントハンドラー"""
    
    def __init__(self, file_watcher: FileWatcher, callback: Callable[[str, str], None]):
        self.file_watcher = file_watcher
        self.callback = callback
    
    def on_modified(self, event):
        """ファイル変更時の処理"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if not self.file_watcher.should_process_event(file_path):
            return
        
        filename = os.path.basename(file_path)
        logger.info(f"ファイル変更検知: {filename}")
        
        try:
            self.callback(file_path, 'modified')
        except Exception as e:
            logger.error(f"ファイル変更コールバックでエラー: {filename} - {e}")
    
    def on_created(self, event):
        """ファイル作成時の処理"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        filename = os.path.basename(file_path)
        logger.info(f"新規ファイル作成検知: {filename}")
        
        try:
            self.callback(file_path, 'created')
        except Exception as e:
            logger.error(f"ファイル作成コールバックでエラー: {filename} - {e}")
    
    def on_deleted(self, event):
        """ファイル削除時の処理"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        filename = os.path.basename(file_path)
        logger.info(f"ファイル削除検知: {filename}")
        
        try:
            self.callback(file_path, 'deleted')
        except Exception as e:
            logger.error(f"ファイル削除コールバックでエラー: {filename} - {e}")

# watchdog が利用可能な場合のみ FileSystemEventHandler を継承
if WATCHDOG_AVAILABLE:
    class FileChangeHandler(FileSystemEventHandler, FileChangeHandler):
        pass

class PollingFileWatcher:
    """ポーリングベースのファイル監視（watchdog代替）"""
    
    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self.watched_files = {}
        self.callbacks = {}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def add_file(self, file_path: str, callback: Callable[[str, str], None]) -> bool:
        """監視ファイルを追加"""
        if not os.path.exists(file_path):
            logger.warning(f"監視ファイルが存在しません: {file_path}")
            return False
        
        with self.lock:
            try:
                mtime = os.path.getmtime(file_path)
                self.watched_files[file_path] = mtime
                self.callbacks[file_path] = callback
                logger.info(f"ポーリング監視ファイル追加: {file_path}")
                return True
            except OSError as e:
                logger.error(f"ファイルの監視設定に失敗: {file_path} - {e}")
                return False
    
    def start(self) -> None:
        """ポーリング監視を開始"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()
        logger.info(f"ポーリングベースファイル監視開始: {len(self.watched_files)}ファイル")
    
    def stop(self) -> None:
        """ポーリング監視を停止"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=self.interval + 1)
        logger.info("ポーリングベースファイル監視停止")
    
    def _polling_loop(self) -> None:
        """ポーリングループ"""
        while self.running:
            try:
                with self.lock:
                    for file_path, old_mtime in list(self.watched_files.items()):
                        if not os.path.exists(file_path):
                            # ファイルが削除された
                            callback = self.callbacks.get(file_path)
                            if callback:
                                callback(file_path, 'deleted')
                            continue
                        
                        try:
                            new_mtime = os.path.getmtime(file_path)
                            if new_mtime > old_mtime:
                                # ファイルが変更された
                                self.watched_files[file_path] = new_mtime
                                callback = self.callbacks.get(file_path)
                                if callback:
                                    callback(file_path, 'modified')
                        except OSError:
                            continue
                
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"ポーリング監視でエラー: {e}")
                time.sleep(self.interval)