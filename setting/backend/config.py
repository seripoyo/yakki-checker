# リファクタリング: app.pyから設定管理機能を分離
# 変更内容: グローバル変数と環境設定を独立したモジュールに移動
"""
設定管理モジュール
環境変数、API設定、およびアプリケーション設定を管理
"""

import os
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    
    # Flask設定
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    JSON_AS_ASCII = False  # 日本語文字化け防止
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))
    HOST = '0.0.0.0'
    
    # Claude API設定
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
    CLAUDE_MODEL = 'claude-3-5-sonnet-20241022'
    CLAUDE_MAX_TOKENS = 4000
    CLAUDE_TEMPERATURE = 0.3
    
    # アプリケーション用API設定
    VALID_API_KEYS = os.environ.get('VALID_API_KEYS', '').split(',') if os.environ.get('VALID_API_KEYS') else []
    
    # Notion API設定
    NOTION_API_KEY = os.environ.get('NOTION_API_KEY')
    NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID')
    
    # ファイルパス設定
    DATA_DIR = 'data'
    RULE_DIR = 'rule'
    
    # キャッシュ設定
    CACHE_MAX_SIZE = 100
    CACHE_TTL = 3600  # 1時間（秒）
    
    # セキュリティ設定
    RATE_LIMIT_REQUESTS = 50
    RATE_LIMIT_WINDOW = 300  # 5分（秒）
    
    # ログ設定
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def validate_config(cls):
        """設定値の検証"""
        errors = []
        
        if not cls.CLAUDE_API_KEY:
            errors.append("CLAUDE_API_KEY is required")
        
        # 開発環境ではAPIキー認証をオプショナルにする
        if not cls.DEBUG and not cls.VALID_API_KEYS:
            errors.append("VALID_API_KEYS is required in production")
        
        if errors:
            raise ValueError(f"設定エラー: {', '.join(errors)}")
        
        return True

# グローバル変数の初期化（互換性のため）
claude_client = None
ng_expressions_data = None
csv_reference_text = ""
markdown_reference_text = ""
notion_api_key = Config.NOTION_API_KEY
notion_database_id = Config.NOTION_DATABASE_ID