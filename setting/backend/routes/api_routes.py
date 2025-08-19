# リファクタリング: app.pyからAPIエンドポイントを分離
# 変更内容: Flask API ルート定義を独立したBlueprintモジュールに移動
"""
APIルートモジュール
Flask APIエンドポイントの定義とリクエスト処理
"""

import json
import time
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context
from functools import wraps

from services.yakki_checker import YakkiChecker
from config import Config

logger = logging.getLogger(__name__)

# Blueprintの作成
api_bp = Blueprint('api', __name__)

# サービスインスタンス
yakki_checker = YakkiChecker()

# セキュリティ機能
def require_api_key(f):
    """APIキー認証デコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 認証が無効化されている場合はスキップ
        if not Config.VALID_API_KEYS:
            return f(*args, **kwargs)
        
        # APIキーの確認
        api_key = None
        
        # Headerから取得
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        # クエリパラメータから取得（後方互換性）
        elif 'api_key' in request.args:
            api_key = request.args.get('api_key')
        # JSONボディから取得
        elif request.is_json and request.json and 'api_key' in request.json:
            api_key = request.json['api_key']
        
        if not api_key:
            return jsonify({
                "error": "API key required",
                "message": "API key must be provided in X-API-Key header, query parameter, or request body"
            }), 401
        
        # APIキーの検証（ハッシュ化して比較）
        import hashlib
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        
        if hashed_key not in {hashlib.sha256(key.encode()).hexdigest() for key in Config.VALID_API_KEYS}:
            logger.warning(f"無効なAPIキーでのアクセス試行: {request.remote_addr}")
            return jsonify({
                "error": "Invalid API key",
                "message": "The provided API key is not valid"
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

def add_security_headers(response):
    """セキュリティヘッダーを追加"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

@api_bp.route('/', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント"""
    try:
        status = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "2.0.0",
            "services": {
                "claude_api": yakki_checker.claude_service.is_available(),
                "data_service": True,
                "cache_service": True
            },
            "cache_stats": yakki_checker.get_cache_status()
        }
        
        response = jsonify(status)
        return add_security_headers(response)
        
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/api/check', methods=['POST'])
@require_api_key
def check_text():
    """メインの薬機法チェックエンドポイント"""
    try:
        start_time = time.time()
        
        # リクエストデータの検証
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.json
        required_fields = ['text', 'category', 'text_type']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                "error": "Missing required fields",
                "missing_fields": missing_fields
            }), 400
        
        # 入力値の取得とサニタイズ
        text = str(data['text']).strip()
        category = str(data['category']).strip()
        text_type = str(data['text_type']).strip()
        special_points = str(data.get('special_points', '')).strip()
        medical_approval = bool(data.get('medical_approval', False))
        
        # 入力値の検証
        if not text:
            return jsonify({"error": "Text cannot be empty"}), 400
        
        if len(text) > 5000:  # 文字数制限
            return jsonify({"error": "Text is too long (max 5000 characters)"}), 400
        
        # 薬機法チェック実行
        result = yakki_checker.check_text(
            text=text,
            text_type=text_type,
            category=category,
            special_points=special_points,
            medical_approval=medical_approval
        )
        
        # レスポンス時間を追加
        processing_time = time.time() - start_time
        result['processing_time'] = round(processing_time, 2)
        
        logger.info(f"チェック完了: {processing_time:.2f}秒")
        
        response = jsonify(result)
        return add_security_headers(response)
        
    except Exception as e:
        logger.error(f"チェック処理エラー: {e}")
        import traceback
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        
        return jsonify({
            "error": "Internal server error",
            "message": "チェック処理中にエラーが発生しました"
        }), 500

@api_bp.route('/api/check/stream', methods=['POST'])
@require_api_key
def check_text_stream():
    """ストリーミング対応の薬機法チェックエンドポイント"""
    try:
        # リクエストデータの検証（check_textと同様）
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.json
        required_fields = ['text', 'category', 'text_type']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                "error": "Missing required fields",
                "missing_fields": missing_fields
            }), 400
        
        # 入力値の取得
        text = str(data['text']).strip()
        category = str(data['category']).strip()
        text_type = str(data['text_type']).strip()
        special_points = str(data.get('special_points', '')).strip()
        medical_approval = bool(data.get('medical_approval', False))
        
        def generate_stream():
            """ストリーミングレスポンス生成"""
            try:
                # 処理開始の通知
                yield f"data: {json.dumps({'status': 'processing', 'message': 'チェック開始'})}\n\n"
                
                # キャッシュチェック
                cache_key = yakki_checker.check_cache.get_cache_key(
                    text, category, text_type, special_points, medical_approval
                )
                
                cached_result = yakki_checker.check_cache.get(cache_key)
                if cached_result:
                    # キャッシュヒット時は即座に全結果を返す
                    cached_result['from_cache'] = True
                    yield f"data: {json.dumps(cached_result)}\n\n"
                    yield "data: {\"status\": \"completed\"}\n\n"
                    return
                
                # チェック実行
                yield f"data: {json.dumps({'status': 'analyzing', 'message': 'AI分析中'})}\n\n"
                
                result = yakki_checker.check_text(
                    text=text,
                    text_type=text_type,
                    category=category,
                    special_points=special_points,
                    medical_approval=medical_approval
                )
                
                # 結果送信
                yield f"data: {json.dumps(result)}\n\n"
                yield "data: {\"status\": \"completed\"}\n\n"
                
            except Exception as e:
                logger.error(f"ストリーミング処理エラー: {e}")
                error_data = {
                    "status": "error",
                    "error": "処理中にエラーが発生しました",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        response = Response(
            stream_with_context(generate_stream()),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )
        
        return add_security_headers(response)
        
    except Exception as e:
        logger.error(f"ストリーミング初期化エラー: {e}")
        return jsonify({
            "error": "Streaming initialization failed",
            "message": str(e)
        }), 500

@api_bp.route('/api/cache/refresh', methods=['POST'])
@require_api_key
def refresh_cache():
    """キャッシュ無効化エンドポイント"""
    try:
        data = request.json or {}
        cache_type = data.get('type', 'all')  # all, data, rule, check
        
        if cache_type == 'check':
            yakki_checker.check_cache.clear()
            message = "チェック結果キャッシュを無効化しました"
        elif cache_type in ['data', 'rule']:
            yakki_checker.data_service.invalidate_cache(cache_type)
            message = f"{cache_type}キャッシュを無効化しました"
        else:
            yakki_checker.clear_cache()
            message = "全キャッシュを無効化しました"
        
        logger.info(f"キャッシュ無効化: {cache_type}")
        
        response = jsonify({
            "status": "success",
            "message": message,
            "cache_type": cache_type,
            "timestamp": time.time()
        })
        
        return add_security_headers(response)
        
    except Exception as e:
        logger.error(f"キャッシュ無効化エラー: {e}")
        return jsonify({
            "error": "Cache refresh failed",
            "message": str(e)
        }), 500

@api_bp.route('/api/cache/status', methods=['GET'])
def cache_status():
    """キャッシュ状態確認エンドポイント"""
    try:
        status = yakki_checker.get_cache_status()
        
        response = jsonify({
            "status": "success",
            "timestamp": time.time(),
            "cache_status": status
        })
        
        return add_security_headers(response)
        
    except Exception as e:
        logger.error(f"キャッシュ状態確認エラー: {e}")
        return jsonify({
            "error": "Failed to get cache status",
            "message": str(e)
        }), 500

@api_bp.route('/api/guide', methods=['GET'])
def get_guide():
    """薬機法ガイド情報取得エンドポイント"""
    try:
        # 基本的なガイド情報を返す
        guide_data = {
            "categories": {
                "化粧品": "一般化粧品として、効果効能の表現に特に注意が必要です。",
                "薬用化粧品": "医薬部外品として承認された効果効能のみ表現可能です。",
                "医薬部外品": "承認された効果効能の範囲内での表現が必要です。",
                "サプリメント・健康食品": "健康食品として、医薬品的な効果表現は禁止されています。",
                "美容機器・健康器具・その他": "機器の分類に応じた適切な表現が必要です。"
            },
            "text_types": {
                "キャッチコピー": "短く印象的でありながら、誇大表現を避ける必要があります。",
                "LP見出し・タイトル": "注目を集めつつ、薬機法に準拠した表現が重要です。",
                "商品説明文・広告文・通常テキスト": "詳細な説明において、客観的で根拠のある表現を心がけてください。",
                "お客様の声": "個人の感想として、効果を断定しない表現が必要です。"
            },
            "common_ng_expressions": [
                {"expression": "即効性", "reason": "効果の即時性を示唆", "alternative": "お手入れ"},
                {"expression": "完治", "reason": "医学的治療効果", "alternative": "お手入れ"},
                {"expression": "美白", "reason": "薬用化粧品以外では使用不可", "alternative": "透明感"}
            ]
        }
        
        response = jsonify({
            "status": "success",
            "data": guide_data,
            "timestamp": time.time()
        })
        
        return add_security_headers(response)
        
    except Exception as e:
        logger.error(f"ガイド情報取得エラー: {e}")
        return jsonify({
            "error": "Failed to get guide data",
            "message": str(e)
        }), 500

# エラーハンドラー
@api_bp.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    response = jsonify({
        "error": "Not Found",
        "message": "The requested resource was not found"
    })
    return add_security_headers(response), 404

@api_bp.errorhandler(405)
def method_not_allowed(error):
    """405エラーハンドラー"""
    response = jsonify({
        "error": "Method Not Allowed",
        "message": "The method is not allowed for the requested URL"
    })
    return add_security_headers(response), 405

@api_bp.errorhandler(500)
def internal_error(error):
    """500エラーハンドラー"""
    logger.error(f"内部サーバーエラー: {error}")
    response = jsonify({
        "error": "Internal Server Error",
        "message": "An internal server error occurred"
    })
    return add_security_headers(response), 500