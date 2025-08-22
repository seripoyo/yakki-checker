# リファクタリング: app.pyからキャッシュ管理機能を分離
# 変更内容: キャッシュ機能を独立したモジュールに移動し、効率化
"""
キャッシュ管理モジュール
メモリキャッシュとLRUキャッシュによる効率的なデータ管理
"""

import time
import threading
import hashlib
import logging
from functools import lru_cache
from collections import OrderedDict
from typing import Optional, Any, Callable

logger = logging.getLogger(__name__)

class CacheManager:
    """統合キャッシュマネージャー"""
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.lock = threading.Lock()
        
        # 複数の目的別キャッシュ
        self._caches = {
            'check_results': OrderedDict(),
            'data_files': OrderedDict(),
            'rule_files': OrderedDict(),
            'api_responses': OrderedDict()
        }
        
        # 統計情報
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _generate_key(self, data: Any) -> str:
        """データからキャッシュキーを生成"""
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            content = str(sorted(data.items()))
        else:
            content = str(data)
        
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get(self, cache_type: str, key: str) -> Optional[Any]:
        """キャッシュから取得"""
        with self.lock:
            cache = self._caches.get(cache_type)
            if not cache:
                return None
            
            if key in cache:
                data, timestamp = cache[key]
                if time.time() - timestamp < self.ttl:
                    # キャッシュヒット - 最後に移動（LRU）
                    cache.move_to_end(key)
                    self._stats['hits'] += 1
                    logger.debug(f"キャッシュヒット [{cache_type}]: {key[:8]}...")
                    return data
                else:
                    # 期限切れ
                    del cache[key]
                    logger.debug(f"キャッシュ期限切れ [{cache_type}]: {key[:8]}...")
            
            self._stats['misses'] += 1
            return None
    
    def set(self, cache_type: str, key: str, data: Any) -> None:
        """キャッシュに保存"""
        with self.lock:
            cache = self._caches.get(cache_type)
            if not cache:
                logger.warning(f"未知のキャッシュタイプ: {cache_type}")
                return
            
            # サイズ制限チェック
            if len(cache) >= self.max_size:
                # 最も古いものを削除（LRU）
                evicted_key, _ = cache.popitem(last=False)
                self._stats['evictions'] += 1
                logger.debug(f"キャッシュ削除 [{cache_type}]: {evicted_key[:8]}...")
            
            cache[key] = (data, time.time())
            logger.debug(f"キャッシュ保存 [{cache_type}]: サイズ {len(cache)}/{self.max_size}")
    
    def invalidate(self, cache_type: str = None, key: str = None) -> None:
        """キャッシュを無効化"""
        with self.lock:
            if cache_type and key:
                # 特定のキーを削除
                cache = self._caches.get(cache_type)
                if cache and key in cache:
                    del cache[key]
                    logger.info(f"キャッシュ無効化 [{cache_type}]: {key[:8]}...")
            elif cache_type:
                # 特定のタイプをクリア
                cache = self._caches.get(cache_type)
                if cache:
                    cache.clear()
                    logger.info(f"キャッシュクリア [{cache_type}]")
            else:
                # 全キャッシュをクリア
                for cache in self._caches.values():
                    cache.clear()
                self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}
                logger.info("全キャッシュクリア")
    
    def get_stats(self) -> dict:
        """キャッシュ統計を取得"""
        with self.lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
            
            cache_sizes = {
                cache_type: len(cache) 
                for cache_type, cache in self._caches.items()
            }
            
            return {
                'hit_rate': round(hit_rate, 2),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'cache_sizes': cache_sizes,
                'total_entries': sum(cache_sizes.values())
            }

# LRUキャッシュを使用したデコレータ関数
def cached_function(maxsize: int = 128, ttl: int = 3600):
    """関数結果をキャッシュするデコレータ"""
    def decorator(func: Callable) -> Callable:
        # 基本のLRUキャッシュ
        cached_func = lru_cache(maxsize=maxsize)(func)
        
        # TTL機能を追加
        cache_times = {}
        
        def wrapper(*args, **kwargs):
            # キャッシュキーを生成
            key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # TTLチェック
            if key in cache_times:
                if current_time - cache_times[key] > ttl:
                    # 期限切れの場合、関数を再実行
                    cached_func.cache_clear()
                    del cache_times[key]
            
            # 結果を取得（キャッシュまたは実行）
            result = cached_func(*args, **kwargs)
            cache_times[key] = current_time
            
            return result
        
        # オリジナル関数の属性を保持
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.cache_info = cached_func.cache_info
        wrapper.cache_clear = cached_func.cache_clear
        
        return wrapper
    return decorator

# メモリ効率的なキャッシュウォーマー
class CacheWarmer:
    """キャッシュのプリロード機能"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.preload_functions = {}
    
    def register_preload(self, cache_type: str, func: Callable):
        """プリロード関数を登録"""
        self.preload_functions[cache_type] = func
    
    def warm_cache(self, cache_type: str = None):
        """キャッシュをウォームアップ"""
        if cache_type:
            func = self.preload_functions.get(cache_type)
            if func:
                try:
                    func()
                    logger.info(f"キャッシュウォームアップ完了: {cache_type}")
                except Exception as e:
                    logger.error(f"キャッシュウォームアップ失敗 [{cache_type}]: {e}")
        else:
            # 全てのキャッシュをウォームアップ
            for cache_type, func in self.preload_functions.items():
                try:
                    func()
                    logger.info(f"キャッシュウォームアップ完了: {cache_type}")
                except Exception as e:
                    logger.error(f"キャッシュウォームアップ失敗 [{cache_type}]: {e}")