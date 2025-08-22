#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
セキュリティミドルウェア
環境変数ファイルへの不正アクセスを防止
"""

import os
import re
from flask import abort, request
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# 危険なパスパターンの定義
DANGEROUS_PATTERNS = [
    r'\.env',           # .envファイル
    r'\.env\.',         # .env.local, .env.production等
    r'\.\./',           # ディレクトリトラバーサル
    r'\.\.\\',          # Windowsディレクトリトラバーサル
    r'%2e%2e',          # URLエンコードされた../
    r'%252e%252e',      # ダブルエンコード
    r'\.git',           # Gitディレクトリ
    r'\.ssh',           # SSHディレクトリ
    r'\.aws',           # AWS認証情報
    r'\.config',        # 設定ファイル
    r'\.htaccess',      # Apache設定
    r'\.htpasswd',      # パスワードファイル
    r'\.(bak|backup|old|orig|save|swp|tmp)$',  # バックアップファイル
]

# ブロックすべきファイル拡張子
BLOCKED_EXTENSIONS = [
    'env', 'ini', 'cfg', 'conf', 'config',
    'key', 'pem', 'cert', 'crt',
    'sql', 'db', 'sqlite',
    'log', 'pid',
    'bak', 'backup', 'old', 'orig', 'save', 'swp', 'tmp'
]

def check_path_security(path):
    """
    パスのセキュリティチェック
    危険なパターンが含まれている場合はFalseを返す
    """
    if not path:
        return True
    
    # パスの正規化
    normalized_path = os.path.normpath(path).replace('\\', '/')
    
    # 危険なパターンのチェック
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, normalized_path, re.IGNORECASE):
            logger.warning(f"危険なパスパターンを検出: {path} (パターン: {pattern})")
            return False
    
    # ファイル拡張子のチェック
    _, ext = os.path.splitext(normalized_path)
    if ext and ext[1:].lower() in BLOCKED_EXTENSIONS:
        logger.warning(f"ブロックされた拡張子を検出: {path} (拡張子: {ext})")
        return False
    
    # 絶対パスや親ディレクトリへの参照をチェック
    if normalized_path.startswith('/') or normalized_path.startswith('..'):
        logger.warning(f"不正なパス参照を検出: {path}")
        return False
    
    return True

def security_middleware(f):
    """
    セキュリティミドルウェアデコレータ
    リクエストパスとパラメータをチェック
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # リクエストパスのチェック
        if not check_path_security(request.path):
            logger.error(f"セキュリティ違反 - 不正なリクエストパス: {request.path} from {request.remote_addr}")
            abort(403, description="Access forbidden")
        
        # クエリパラメータのチェック
        for key, value in request.args.items():
            if not check_path_security(str(value)):
                logger.error(f"セキュリティ違反 - 不正なクエリパラメータ: {key}={value} from {request.remote_addr}")
                abort(403, description="Access forbidden")
        
        # JSONボディのチェック（POSTリクエストの場合）
        if request.method == 'POST' and request.is_json:
            data = request.get_json()
            if data:
                for key, value in data.items():
                    if isinstance(value, str) and not check_path_security(value):
                        logger.error(f"セキュリティ違反 - 不正なJSONパラメータ: {key}={value} from {request.remote_addr}")
                        abort(403, description="Access forbidden")
        
        # フォームデータのチェック
        if request.form:
            for key, value in request.form.items():
                if not check_path_security(str(value)):
                    logger.error(f"セキュリティ違反 - 不正なフォームデータ: {key}={value} from {request.remote_addr}")
                    abort(403, description="Access forbidden")
        
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit_middleware(max_requests=60, window_seconds=60):
    """
    レート制限ミドルウェア
    """
    from collections import defaultdict
    from time import time
    
    request_counts = defaultdict(list)
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time()
            
            # 古いリクエストを削除
            request_counts[client_ip] = [
                req_time for req_time in request_counts[client_ip]
                if current_time - req_time < window_seconds
            ]
            
            # リクエスト数をチェック
            if len(request_counts[client_ip]) >= max_requests:
                logger.warning(f"レート制限超過: {client_ip}")
                abort(429, description="Too many requests")
            
            # 新しいリクエストを記録
            request_counts[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

def validate_api_key(f):
    """
    APIキー検証ミドルウェア
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        valid_keys = os.getenv('VALID_API_KEYS', '').split(',')
        
        if not api_key or api_key not in valid_keys:
            logger.warning(f"無効なAPIキー: {api_key} from {request.remote_addr}")
            abort(401, description="Invalid API key")
        
        return f(*args, **kwargs)
    
    return decorated_function

# セキュリティヘッダーを追加する関数
def add_security_headers(response):
    """
    レスポンスにセキュリティヘッダーを追加（強化版）
    """
    # 基本的なセキュリティヘッダー
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Content Security Policy（API用に調整）
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    
    # HTTPS強制（本番環境用）
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # その他のセキュリティヘッダー
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = (
        'accelerometer=(), camera=(), geolocation=(), '
        'gyroscope=(), magnetometer=(), microphone=(), '
        'payment=(), usb=()'
    )
    
    # キャッシュ制御（機密データ用）
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response