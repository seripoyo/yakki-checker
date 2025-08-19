#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
薬機法リスクチェッカー バックエンドAPI（リファクタリング版）
Flask アプリケーション - モジュール化されたクリーンなアーキテクチャ

リファクタリング内容:
- 2393行のモノリシックなコードを7つのモジュールに分割
- 設定管理、データ処理、API通信、キャッシュを独立化
- 非同期処理対応の準備完了
- メンテナンス性と拡張性を大幅改善
"""

import os
import logging
import time
from flask import Flask
from flask_cors import CORS

# 新しいモジュール化された構造のインポート
import sys
import os
sys.path.append(os.path.dirname(__file__))

from config import Config
from routes.api_routes import api_bp
from services.yakki_checker import YakkiChecker

# ログ設定
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

def create_app():
    """Flaskアプリケーションファクトリ"""
    app = Flask(__name__)
    
    # 設定の適用
    app.config.from_object(Config)
    
    # CORS設定
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:8000", "https://*.render.com"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "X-API-Key"],
            "supports_credentials": True
        }
    })
    
    # Blueprintの登録
    app.register_blueprint(api_bp)
    
    # グローバルエラーハンドラー
    @app.after_request
    def after_request(response):
        """レスポンス後処理"""
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-API-Key')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    return app

def initialize_services():
    """サービスの初期化"""
    try:
        logger.info("薬機法リスクチェッカー 初期化開始")
        
        # 設定値の検証
        Config.validate_config()
        logger.info("設定値検証完了")
        
        # YakkiCheckerサービスの初期化（他のサービスも含む）
        yakki_checker = YakkiChecker()
        
        # Claude APIの利用可能性確認
        if yakki_checker.claude_service.is_available():
            logger.info("Claude API接続確認完了")
        else:
            logger.warning("Claude APIが利用できません - デモモードで動作")
        
        # データファイルの読み込み確認
        ng_data = yakki_checker.data_service.load_ng_expressions()
        if ng_data is not None:
            logger.info(f"NG表現データ読み込み完了: {len(ng_data)}件")
        else:
            logger.warning("NG表現データの読み込みに失敗")
        
        # キャッシュ状態の確認
        cache_status = yakki_checker.get_cache_status()
        logger.info(f"キャッシュシステム初期化完了")
        
        logger.info("薬機法リスクチェッカー 初期化完了")
        return True
        
    except Exception as e:
        logger.error(f"初期化エラー: {e}")
        return False

def print_startup_info():
    """起動情報を表示"""
    print("=" * 60)
    print("薬機法リスクチェッカー API サーバー (リファクタリング版)")
    print("=" * 60)
    print(f"Port: {Config.PORT}")
    print(f"Debug: {Config.DEBUG}")
    print(f"Claude API: {'✅ 接続済み' if Config.CLAUDE_API_KEY else '❌ 未設定'}")
    print(f"API認証: {'✅ 有効' if Config.VALID_API_KEYS else '❌ 無効'}")
    print(f"Health Check: http://localhost:{Config.PORT}/")
    print(f"API Endpoint: http://localhost:{Config.PORT}/api/check")
    print("=" * 60)
    print("🏗️  アーキテクチャ改善:")
    print("   ✅ モジュール分割完了 (7つのモジュール)")
    print("   ✅ 設定管理の独立化")
    print("   ✅ キャッシュシステム最適化")
    print("   ✅ 非同期処理対応準備")
    print("   ✅ エラーハンドリング強化")
    print("=" * 60)

# Flaskアプリケーションの作成
app = create_app()

# Gunicornでも開発サーバーでも初期化が実行されるようにモジュールレベルで呼び出す
if initialize_services():
    logger.info("アプリケーション準備完了")
else:
    logger.error("アプリケーション初期化に失敗しました")

if __name__ == '__main__':
    # 起動情報の表示
    print_startup_info()
    
    # 開発サーバーの起動
    try:
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG
        )
    except KeyboardInterrupt:
        logger.info("サーバーが正常に停止されました")
    except Exception as e:
        logger.error(f"サーバー起動エラー: {e}")