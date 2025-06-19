#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
薬機法リスクチェッカー バックエンドAPI
Flask アプリケーション

このAPIは薬機法に関するテキストチェックを行い、
リスク評価と代替表現の提案をJSON形式で返します。
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from datetime import datetime

# Flaskアプリケーションの初期化
app = Flask(__name__)

# CORS設定 - フロントエンドからのアクセスを許可
CORS(app, origins=['*'])  # 開発環境用（本番では具体的なドメインを指定）

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# アプリケーション設定
app.config['JSON_AS_ASCII'] = False  # 日本語文字化け防止


@app.route('/', methods=['GET'])
def health_check():
    """
    ヘルスチェックエンドポイント
    APIサーバーの稼働状況を確認
    """
    return jsonify({
        "status": "healthy",
        "service": "薬機法リスクチェッカー API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/check', methods=['POST'])
def check_text():
    """
    薬機法リスクチェック メインエンドポイント
    
    POST /api/check
    Request Body:
    {
        "text": "チェックしたいテキスト",
        "type": "キャッチコピー | 商品説明文 | お客様の声"
    }
    
    Response:
    {
        "overall_risk": "高 | 中 | 低",
        "risk_counts": {...},
        "issues": [...],
        "rewritten_text": "修正後の全文"
    }
    """
    try:
        # リクエストデータの取得とバリデーション
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        # 必須パラメータのチェック
        if 'text' not in data or 'type' not in data:
            return jsonify({
                "error": "Missing required parameters. 'text' and 'type' are required."
            }), 400
        
        text = data['text'].strip()
        text_type = data['type']
        
        # テキストの空文字チェック
        if not text:
            return jsonify({"error": "Text cannot be empty"}), 400
        
        # 文章タイプの妥当性チェック
        valid_types = ["キャッチコピー", "商品説明文", "お客様の声"]
        if text_type not in valid_types:
            return jsonify({
                "error": f"Invalid type. Must be one of: {', '.join(valid_types)}"
            }), 400
        
        # ログ出力
        logger.info(f"チェック開始 - Type: {text_type}, Text length: {len(text)}")
        
        # 【スタブ実装】ダミーの薬機法チェック結果を返す
        # 実際のAI APIはまだ呼び出さず、要件定義書の形式に従ったダミーデータを返す
        dummy_response = generate_dummy_response(text, text_type)
        
        logger.info("チェック完了 - ダミーレスポンス返却")
        
        return jsonify(dummy_response)
    
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


def generate_dummy_response(text, text_type):
    """
    ダミーの薬機法チェック結果を生成
    
    Args:
        text (str): チェック対象のテキスト
        text_type (str): テキストの種類
    
    Returns:
        dict: 要件定義書に従ったJSON形式のダミーレスポンス
    """
    
    # テキストタイプに応じたダミーデータのカスタマイズ
    if "シミ" in text or "しみ" in text:
        risk_level = "高"
        issues = [
            {
                "fragment": "シミが消える",
                "reason": "化粧品の効能効果の範囲を逸脱し、医薬品的な効果（シミの治療）を暗示しているため、薬機法違反となる可能性が非常に高いです。",
                "risk_level": "高",
                "suggestions": [
                    "メラニンの生成を抑え、シミ・そばかすを防ぐ",
                    "乾燥による小じわを目立たなくする",
                    "キメを整え、明るい印象の肌へ導く"
                ]
            }
        ]
        rewritten = text.replace("シミが消える", "メラニンの生成を抑え、シミ・そばかすを防ぐ")
        
    elif "アンチエイジング" in text:
        risk_level = "高"
        issues = [
            {
                "fragment": "アンチエイジング",
                "reason": "老化防止を直接的に謳う表現は、化粧品の効能効果を逸脱し薬機法違反のリスクが高いです。",
                "risk_level": "高",
                "suggestions": [
                    "エイジングケア（年齢に応じたお手入れ）",
                    "ハリ・ツヤを与える",
                    "うるおいのある肌へ導く"
                ]
            }
        ]
        rewritten = text.replace("アンチエイジング", "エイジングケア")
        
    elif "完全に" in text or "絶対に" in text:
        risk_level = "中"
        issues = [
            {
                "fragment": "完全に" if "完全に" in text else "絶対に",
                "reason": "断定的な表現は、効果を保証するように受け取られる可能性があり、薬機法上問題となる場合があります。",
                "risk_level": "中",
                "suggestions": [
                    "個人差がありますが",
                    "使用感には個人差があります",
                    "お肌の状態によって"
                ]
            }
        ]
        target = "完全に" if "完全に" in text else "絶対に"
        rewritten = text.replace(target, "個人差がありますが")
        
    else:
        # 問題なしのケース
        risk_level = "低"
        issues = []
        rewritten = text
    
    # リスク件数の集計
    risk_counts = {
        "total": len(issues),
        "high": len([i for i in issues if i["risk_level"] == "高"]),
        "medium": len([i for i in issues if i["risk_level"] == "中"]),
        "low": len([i for i in issues if i["risk_level"] == "低"])
    }
    
    # 総合リスクレベルの決定
    if risk_counts["high"] > 0:
        overall_risk = "高"
    elif risk_counts["medium"] > 0:
        overall_risk = "中"
    else:
        overall_risk = "低"
    
    return {
        "overall_risk": overall_risk,
        "risk_counts": risk_counts,
        "issues": issues,
        "rewritten_text": rewritten
    }


@app.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """405エラーハンドラー"""
    return jsonify({
        "error": "Method Not Allowed",
        "message": "The method is not allowed for the requested URL"
    }), 405


if __name__ == '__main__':
    # 開発サーバーの起動
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print("=" * 50)
    print("薬機法リスクチェッカー API サーバー")
    print("=" * 50)
    print(f"Port: {port}")
    print(f"Debug: {debug_mode}")
    print(f"Health Check: http://localhost:{port}/")
    print(f"API Endpoint: http://localhost:{port}/api/check")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode
    )