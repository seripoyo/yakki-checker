#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
認証セキュリティモジュール
APIキー認証、レート制限、ブルートフォース対策を提供
"""

import hashlib
import hmac
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import secrets

logger = logging.getLogger(__name__)

class AuthSecurityManager:
    """認証とセキュリティを管理するクラス"""
    
    def __init__(self, max_attempts=5, lockout_duration=900, rate_limit_window=60):
        """
        初期化
        
        Args:
            max_attempts: 最大試行回数
            lockout_duration: ロックアウト期間（秒）
            rate_limit_window: レート制限ウィンドウ（秒）
        """
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration  # 15分
        self.rate_limit_window = rate_limit_window  # 1分
        
        # 失敗試行の追跡
        self.failed_attempts = defaultdict(list)
        # ロックアウト状態
        self.lockouts = {}
        # レート制限の追跡
        self.rate_limits = defaultdict(list)
        # 正当なAPIキーのキャッシュ（ハッシュ化）
        self.valid_api_keys = set()
        
    def add_valid_api_key(self, api_key):
        """
        有効なAPIキーを追加（ハッシュ化して保存）
        
        Args:
            api_key: APIキー
        """
        hashed = self._hash_api_key(api_key)
        self.valid_api_keys.add(hashed)
        
    def _hash_api_key(self, api_key, salt=None):
        """
        APIキーをハッシュ化
        
        Args:
            api_key: APIキー
            salt: ソルト（オプション）
            
        Returns:
            ハッシュ化されたAPIキー
        """
        if salt is None:
            # 本番環境では環境変数から取得すべき
            salt = b'yakki_checker_salt_2025'
        
        return hmac.new(salt, api_key.encode(), hashlib.sha256).hexdigest()
    
    def is_locked_out(self, identifier):
        """
        識別子（IPアドレスなど）がロックアウトされているか確認
        
        Args:
            identifier: 識別子
            
        Returns:
            ロックアウトされている場合True
        """
        if identifier in self.lockouts:
            lockout_until = self.lockouts[identifier]
            if datetime.now() < lockout_until:
                return True
            else:
                # ロックアウト期間が終了
                del self.lockouts[identifier]
                self.failed_attempts[identifier] = []
        return False
    
    def record_failed_attempt(self, identifier):
        """
        失敗した認証試行を記録
        
        Args:
            identifier: 識別子
        """
        now = datetime.now()
        self.failed_attempts[identifier].append(now)
        
        # 古い試行記録を削除
        cutoff = now - timedelta(seconds=self.lockout_duration)
        self.failed_attempts[identifier] = [
            attempt for attempt in self.failed_attempts[identifier]
            if attempt > cutoff
        ]
        
        # ロックアウトチェック
        if len(self.failed_attempts[identifier]) >= self.max_attempts:
            self.lockouts[identifier] = now + timedelta(seconds=self.lockout_duration)
            logger.warning(f"ロックアウト発生: {identifier} - {self.lockout_duration}秒間")
            
    def clear_failed_attempts(self, identifier):
        """
        成功した認証後に失敗試行をクリア
        
        Args:
            identifier: 識別子
        """
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]
        if identifier in self.lockouts:
            del self.lockouts[identifier]
            
    def check_rate_limit(self, identifier, max_requests=60):
        """
        レート制限をチェック
        
        Args:
            identifier: 識別子
            max_requests: ウィンドウ内の最大リクエスト数
            
        Returns:
            制限を超えている場合True
        """
        now = time.time()
        
        # 古いリクエストを削除
        self.rate_limits[identifier] = [
            req_time for req_time in self.rate_limits[identifier]
            if now - req_time < self.rate_limit_window
        ]
        
        # 新しいリクエストを追加
        self.rate_limits[identifier].append(now)
        
        # 制限チェック
        if len(self.rate_limits[identifier]) > max_requests:
            logger.warning(f"レート制限超過: {identifier}")
            return True
            
        return False
    
    def validate_api_key(self, api_key):
        """
        APIキーを検証
        
        Args:
            api_key: 検証するAPIキー
            
        Returns:
            有効な場合True
        """
        if not api_key:
            return False
            
        hashed = self._hash_api_key(api_key)
        return hashed in self.valid_api_keys
    
    def generate_secure_token(self, length=32):
        """
        セキュアなトークンを生成
        
        Args:
            length: トークンの長さ
            
        Returns:
            セキュアなトークン
        """
        return secrets.token_urlsafe(length)
    
    def constant_time_compare(self, a, b):
        """
        タイミング攻撃を防ぐための定数時間比較
        
        Args:
            a: 比較値1
            b: 比較値2
            
        Returns:
            等しい場合True
        """
        return hmac.compare_digest(a, b)


# グローバルインスタンス
auth_manager = AuthSecurityManager()


def enhanced_api_key_required(f):
    """
    強化されたAPIキー認証デコレータ
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # IPアドレスまたは他の識別子を取得
        identifier = request.remote_addr or 'unknown'
        
        # ロックアウトチェック
        if auth_manager.is_locked_out(identifier):
            remaining_time = (auth_manager.lockouts[identifier] - datetime.now()).seconds
            return jsonify({
                "error": "Too many failed attempts",
                "message": f"アカウントがロックされています。{remaining_time}秒後に再試行してください。"
            }), 429
        
        # レート制限チェック
        if auth_manager.check_rate_limit(identifier):
            return jsonify({
                "error": "Rate limit exceeded",
                "message": "リクエストが多すぎます。しばらく待ってから再試行してください。"
            }), 429
        
        # APIキーの取得
        api_key = None
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        elif 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                api_key = auth_header[7:]
        
        if not api_key:
            logger.warning(f"APIキーなしのアクセス: {identifier}")
            return jsonify({
                "error": "Authentication required",
                "message": "APIキーが必要です。X-API-KeyヘッダーまたはAuthorizationヘッダーで送信してください。"
            }), 401
        
        # APIキーの検証
        if not auth_manager.validate_api_key(api_key):
            auth_manager.record_failed_attempt(identifier)
            logger.warning(f"無効なAPIキー: {identifier}")
            
            attempts_left = auth_manager.max_attempts - len(auth_manager.failed_attempts[identifier])
            return jsonify({
                "error": "Invalid API key",
                "message": f"無効なAPIキーです。残り試行回数: {attempts_left}"
            }), 401
        
        # 認証成功
        auth_manager.clear_failed_attempts(identifier)
        logger.info(f"認証成功: {identifier}")
        
        # リクエストにユーザー情報を追加（必要に応じて）
        request.authenticated = True
        request.identifier = identifier
        
        return f(*args, **kwargs)
    
    return decorated_function


def init_auth_security(app, valid_api_keys=None):
    """
    認証セキュリティを初期化
    
    Args:
        app: Flaskアプリケーション
        valid_api_keys: 有効なAPIキーのリスト
    """
    if valid_api_keys:
        for key in valid_api_keys:
            auth_manager.add_valid_api_key(key)
    
    # エラーハンドラーの登録
    @app.errorhandler(429)
    def handle_rate_limit(e):
        return jsonify({
            "error": "Too Many Requests",
            "message": "リクエストが多すぎます。しばらく待ってから再試行してください。"
        }), 429
    
    @app.errorhandler(401)
    def handle_unauthorized(e):
        return jsonify({
            "error": "Unauthorized",
            "message": "認証が必要です。"
        }), 401
    
    logger.info("認証セキュリティモジュールを初期化しました")