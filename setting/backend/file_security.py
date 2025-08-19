#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静的ファイル配信のセキュリティ強化
.envファイルへのアクセスを完全にブロック
"""

import os
import mimetypes
from flask import abort, send_from_directory, request
import logging

logger = logging.getLogger(__name__)

# ブロックすべきファイル名パターン
BLOCKED_FILES = [
    '.env',
    '.env.local',
    '.env.production',
    '.env.development',
    '.env.test',
    '.htaccess',
    '.htpasswd',
    '.git',
    '.gitignore',
    'config.ini',
    'settings.py',
    'secrets.json',
]

# ブロックすべきディレクトリ
BLOCKED_DIRS = [
    '__pycache__',
    '.git',
    '.github',
    'node_modules',
    'venv',
    'env',
    '.venv',
]

def serve_static_file(directory, filename):
    """
    静的ファイル配信関数（セキュリティチェック付き）
    """
    
    # ファイル名の正規化
    filename = os.path.normpath(filename)
    
    # 相対パスのチェック（ディレクトリトラバーサル防止）
    if '..' in filename or filename.startswith('/'):
        logger.warning(f"不正なファイルパス要求: {filename} from {request.remote_addr}")
        abort(403)
    
    # ブロックすべきファイル名のチェック
    basename = os.path.basename(filename).lower()
    for blocked in BLOCKED_FILES:
        if basename == blocked.lower() or basename.startswith(blocked.lower()):
            logger.warning(f"ブロックされたファイルへのアクセス試行: {filename} from {request.remote_addr}")
            abort(403)
    
    # ブロックすべきディレクトリのチェック
    parts = filename.split(os.sep)
    for part in parts:
        if part.lower() in [d.lower() for d in BLOCKED_DIRS]:
            logger.warning(f"ブロックされたディレクトリへのアクセス試行: {filename} from {request.remote_addr}")
            abort(403)
    
    # ファイルの存在確認
    file_path = os.path.join(directory, filename)
    if not os.path.exists(file_path):
        abort(404)
    
    # ディレクトリへのアクセスを防ぐ
    if os.path.isdir(file_path):
        abort(403)
    
    # MIMEタイプの確認
    mime_type, _ = mimetypes.guess_type(file_path)
    
    # 実行可能ファイルのブロック
    if mime_type and mime_type.startswith('application/'):
        executable_types = [
            'application/x-executable',
            'application/x-sharedlib',
            'application/x-shellscript',
            'application/x-python-code',
        ]
        if mime_type in executable_types:
            logger.warning(f"実行可能ファイルへのアクセス試行: {filename} from {request.remote_addr}")
            abort(403)
    
    # セキュアにファイルを配信
    try:
        return send_from_directory(directory, filename)
    except Exception as e:
        logger.error(f"ファイル配信エラー: {e}")
        abort(500)

def register_file_routes(app):
    """
    Flaskアプリケーションに静的ファイルルートを登録
    """
    
    @app.route('/<path:filename>')
    def serve_file(filename):
        """任意のファイルパスへのリクエストを処理"""
        
        # .envファイルへの直接アクセスをブロック
        if '.env' in filename.lower():
            logger.error(f"重大: .envファイルへの直接アクセス試行: {filename} from {request.remote_addr}")
            abort(403)
        
        # 静的ファイルの配信
        static_dir = app.config.get('STATIC_FOLDER', 'static')
        return serve_static_file(static_dir, filename)
    
    @app.errorhandler(403)
    def forbidden(e):
        """403エラーのカスタムハンドラ"""
        return {"error": "Access Forbidden", "message": "You don't have permission to access this resource."}, 403
    
    @app.errorhandler(404)
    def not_found(e):
        """404エラーのカスタムハンドラ"""
        return {"error": "Not Found", "message": "The requested resource was not found."}, 404