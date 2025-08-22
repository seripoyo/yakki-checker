# リファクタリング: routesパッケージの初期化
# 変更内容: APIエンドポイントを格納するパッケージを作成
"""
ルートパッケージ
Flask APIエンドポイントとルーティング設定を定義
"""

from .api_routes import api_bp

__all__ = ['api_bp']