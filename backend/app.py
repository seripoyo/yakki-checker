#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
薬機法リスクチェッカー バックエンドAPI
Flask アプリケーション（Claude API連携版）

このAPIは薬機法に関するテキストチェックを行い、
Claude APIとローカルCSVデータを活用して高精度な
リスク評価と代替表現の提案をJSON形式で返します。
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic

# Flaskアプリケーションの初期化
app = Flask(__name__)

# CORS設定 - フロントエンドからのアクセスを許可
CORS(app, origins=['*'])  # 開発環境用（本番では具体的なドメインを指定）

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# アプリケーション設定
app.config['JSON_AS_ASCII'] = False  # 日本語文字化け防止

# ===== グローバル変数 =====
claude_client = None
ng_expressions_data = None
csv_reference_text = ""

def initialize_app():
    """
    アプリケーションの初期化処理
    APIキーの確認とCSVファイルの読み込み
    """
    global claude_client, ng_expressions_data, csv_reference_text
    
    logger.info("薬機法リスクチェッカー 初期化開始")
    
    # 1. Claude API キーの確認
    claude_api_key = os.getenv('CLAUDE_API_KEY')
    if not claude_api_key:
        logger.error("CLAUDE_API_KEY環境変数が設定されていません")
        print("=" * 60)
        print("❌ エラー: CLAUDE_API_KEY環境変数が設定されていません")
        print("=" * 60)
        print("以下のコマンドでAPIキーを設定してください:")
        print("export CLAUDE_API_KEY='your_api_key_here'")
        print("または .env ファイルに CLAUDE_API_KEY=your_api_key_here を記述")
        print("=" * 60)
        exit(1)
    
    # Claude クライアントの初期化
    try:
        claude_client = anthropic.Anthropic(api_key=claude_api_key)
        logger.info("Claude API クライアント初期化完了")
    except Exception as e:
        logger.error(f"Claude API クライアント初期化失敗: {str(e)}")
        exit(1)
    
    # 2. CSVファイルの読み込み
    csv_file_path = os.path.join(os.path.dirname(__file__), 'data', 'ng_expressions.csv')
    
    try:
        if not os.path.exists(csv_file_path):
            logger.warning(f"CSVファイルが見つかりません: {csv_file_path}")
            # デフォルトのNG表現データを使用
            ng_expressions_data = create_default_ng_data()
            csv_reference_text = format_ng_data_for_prompt(ng_expressions_data)
        else:
            ng_expressions_data = pd.read_csv(csv_file_path, encoding='utf-8')
            csv_reference_text = format_csv_for_prompt(ng_expressions_data)
            logger.info(f"CSVファイル読み込み完了: {len(ng_expressions_data)}件のNG表現データ")
    
    except Exception as e:
        logger.error(f"CSVファイル読み込みエラー: {str(e)}")
        # フォールバック: デフォルトデータを使用
        ng_expressions_data = create_default_ng_data()
        csv_reference_text = format_ng_data_for_prompt(ng_expressions_data)
        logger.info("デフォルトのNG表現データを使用")
    
    logger.info("薬機法リスクチェッカー 初期化完了")

def create_default_ng_data():
    """
    デフォルトのNG表現データを作成
    """
    default_data = [
        {"NG表現": "シミが消える", "カテゴリ": "シミ", "リスクレベル": "高", 
         "代替表現1": "メラニンの生成を抑え、シミ・そばかすを防ぐ", 
         "代替表現2": "乾燥による小じわを目立たなくする", 
         "代替表現3": "キメを整え明るい印象の肌へ導く"},
        {"NG表現": "アンチエイジング", "カテゴリ": "老化", "リスクレベル": "高",
         "代替表現1": "エイジングケア（年齢に応じたお手入れ）",
         "代替表現2": "ハリ・ツヤを与える",
         "代替表現3": "うるおいのある肌へ導く"},
        {"NG表現": "完全に", "カテゴリ": "断定", "リスクレベル": "中",
         "代替表現1": "個人差がありますが",
         "代替表現2": "使用感には個人差があります",
         "代替表現3": "お肌の状態によって"},
    ]
    return pd.DataFrame(default_data)

def format_csv_for_prompt(df):
    """
    DataFrameをプロンプト用の文字列形式に変換
    """
    if df.empty:
        return "参考データなし"
    
    reference_text = "=== 薬機法NG表現参考データ ===\n"
    
    for _, row in df.iterrows():
        reference_text += f"NG表現: {row.get('NG表現', 'N/A')}\n"
        reference_text += f"カテゴリ: {row.get('カテゴリ', 'N/A')}\n"
        reference_text += f"リスクレベル: {row.get('リスクレベル', 'N/A')}\n"
        
        # 代替表現があれば追加
        alternatives = []
        for i in range(1, 4):
            alt_key = f"代替表現{i}"
            if alt_key in row and pd.notna(row[alt_key]):
                alternatives.append(row[alt_key])
        
        if alternatives:
            reference_text += f"代替表現: {' | '.join(alternatives)}\n"
        
        reference_text += "---\n"
    
    return reference_text

def format_ng_data_for_prompt(df):
    """
    NG表現データをプロンプト用にフォーマット
    """
    return format_csv_for_prompt(df)

def create_system_prompt():
    """
    Claude API用のシステムプロンプトを生成
    """
    return """あなたは、日本の薬機法（医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律）に精通した、最高のリーガルチェックAIアシスタントです。

あなたのタスクは、入力された美容関連の広告テキストを分析し、薬機法抵触リスクを評価して、具体的な改善案をJSON形式で出力することです。

このAIは、美容サロンや化粧品メーカーの広告担当者、薬機法に不慣れなライター向けの「薬機法リスクチェッカー」というWebアプリのバックエンドとして機能します。目的は、担当者が作成した広告文のラフ案を手軽に一次チェックし、専門家への確認前に手戻りを減らすことです。

以下の4つのタスクを厳密に実行してください：

1. **全体リスク評価**: テキスト全体としての薬機法抵触リスクを「高」「中」「低」の3段階で評価
2. **問題点の抽出と分析**: 
   - テキスト内から薬機法に抵触する可能性のある全ての表現(fragment)を特定
   - 各表現について抵触の具体的な理由(reason)、リスクレベル(risk_level)を評価
   - リスク評価に基づいた安全な代替表現の候補(suggestions)を3つ提案
3. **全文リライト**: 指摘事項を全て修正し、広告効果をできるだけ維持したまま、薬機法に準拠した文章(rewritten_text)を生成
4. **リスク件数集計**: 高・中・低リスクの件数をそれぞれカウント

必ず以下のJSON形式で、キーの名前も厳密に守って出力してください。他の説明文は一切含めないでください：

{
  "overall_risk": "高" | "中" | "低",
  "risk_counts": {
    "total": Number,
    "high": Number,
    "medium": Number,
    "low": Number
  },
  "issues": [
    {
      "fragment": "問題のある表現",
      "reason": "抵触する理由の詳細説明...",
      "risk_level": "高" | "中" | "低",
      "suggestions": ["代替案1", "代替案2", "代替案3"]
    }
  ],
  "rewritten_text": "リライトされた全文..."
}"""

def create_user_prompt(text, text_type, csv_data):
    """
    Claude API用のユーザープロンプトを生成
    """
    return f"""以下のテキストを薬機法の観点からチェックしてください。

【入力データ】
text: {text}
type: {text_type}

【参考情報】
{csv_data}

上記の参考情報を活用して、より精度の高い薬機法チェックを行い、指定されたJSON形式で結果を返してください。"""

@app.route('/', methods=['GET'])
def health_check():
    """
    ヘルスチェックエンドポイント
    APIサーバーの稼働状況を確認
    """
    return jsonify({
        "status": "healthy",
        "service": "薬機法リスクチェッカー API",
        "version": "2.0.0",
        "claude_api": "connected" if claude_client else "disconnected",
        "ng_data_count": len(ng_expressions_data) if ng_expressions_data is not None else 0,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/check', methods=['POST'])
def check_text():
    """
    薬機法リスクチェック メインエンドポイント
    Claude APIとCSVデータを活用した高精度チェック
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
        
        # 文字数制限チェック
        if len(text) > 500:
            return jsonify({"error": "Text too long. Maximum 500 characters allowed."}), 400
        
        # 文章タイプの妥当性チェック
        valid_types = ["キャッチコピー", "商品説明文", "お客様の声"]
        if text_type not in valid_types:
            return jsonify({
                "error": f"Invalid type. Must be one of: {', '.join(valid_types)}"
            }), 400
        
        # ログ出力
        logger.info(f"チェック開始 - Type: {text_type}, Text length: {len(text)}")
        
        # Claude API呼び出し
        result = call_claude_api(text, text_type)
        
        logger.info("チェック完了 - Claude APIレスポンス受信")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

def call_claude_api(text, text_type):
    """
    Claude APIを呼び出して薬機法チェックを実行
    
    Args:
        text (str): チェック対象のテキスト
        text_type (str): テキストの種類
    
    Returns:
        dict: Claude APIからの応答（JSON形式）
    
    Raises:
        Exception: API呼び出しに失敗した場合
    """
    try:
        # プロンプトの構築
        system_prompt = create_system_prompt()
        user_prompt = create_user_prompt(text, text_type, csv_reference_text)
        
        logger.info("Claude API呼び出し開始")
        
        # Claude APIリクエスト
        response = claude_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            temperature=0.1,  # 一貫性を重視
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        
        # レスポンスの解析
        response_text = response.content[0].text.strip()
        logger.info(f"Claude API応答受信: {len(response_text)} characters")
        
        # JSONパース
        try:
            result = json.loads(response_text)
            
            # レスポンス構造の検証
            validate_claude_response(result)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Claude APIレスポンスのJSONパースエラー: {str(e)}")
            logger.error(f"Raw response: {response_text}")
            
            # フォールバック: 構造化された応答を生成
            return create_fallback_response(text, "JSONパースエラーのため、基本的なチェック結果を返します")
    
    except anthropic.APIError as e:
        logger.error(f"Claude API エラー: {str(e)}")
        return create_fallback_response(text, f"Claude API呼び出しエラー: {str(e)}")
    
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return create_fallback_response(text, f"予期しないエラー: {str(e)}")

def validate_claude_response(response):
    """
    Claude APIレスポンスの構造を検証
    
    Args:
        response (dict): Claude APIからの応答
        
    Raises:
        ValueError: レスポンス構造が不正な場合
    """
    required_fields = ["overall_risk", "risk_counts", "issues", "rewritten_text"]
    
    for field in required_fields:
        if field not in response:
            raise ValueError(f"必須フィールド '{field}' がレスポンスに含まれていません")
    
    # overall_riskの検証
    valid_risk_levels = ["高", "中", "低"]
    if response["overall_risk"] not in valid_risk_levels:
        raise ValueError("overall_riskの値が不正です")
    
    # risk_countsの検証
    risk_counts = response["risk_counts"]
    required_count_fields = ["total", "high", "medium", "low"]
    
    for field in required_count_fields:
        if field not in risk_counts or not isinstance(risk_counts[field], int):
            raise ValueError(f"risk_counts.{field}が不正です")
    
    # issuesの検証
    if not isinstance(response["issues"], list):
        raise ValueError("issuesはリスト形式である必要があります")
    
    for issue in response["issues"]:
        required_issue_fields = ["fragment", "reason", "risk_level", "suggestions"]
        for field in required_issue_fields:
            if field not in issue:
                raise ValueError(f"issue内の必須フィールド '{field}' が不足しています")

def create_fallback_response(text, error_message):
    """
    Claude API呼び出しに失敗した場合のフォールバック応答を生成
    
    Args:
        text (str): 元のテキスト
        error_message (str): エラーメッセージ
        
    Returns:
        dict: フォールバック応答
    """
    logger.warning(f"フォールバック応答を生成: {error_message}")
    
    return {
        "overall_risk": "中",
        "risk_counts": {
            "total": 1,
            "high": 0,
            "medium": 1,
            "low": 0
        },
        "issues": [
            {
                "fragment": "API呼び出しエラー",
                "reason": f"システムエラーが発生しました。{error_message} 手動での確認をお勧めします。",
                "risk_level": "中",
                "suggestions": [
                    "専門家にご相談ください",
                    "手動でのチェックを実施してください",
                    "しばらく時間をおいて再試行してください"
                ]
            }
        ],
        "rewritten_text": text
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
    # アプリケーション初期化
    initialize_app()
    
    # 開発サーバーの起動
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print("=" * 60)
    print("薬機法リスクチェッカー API サーバー (Claude API連携版)")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Debug: {debug_mode}")
    print(f"Claude API: {'✅ 接続済み' if claude_client else '❌ 未接続'}")
    print(f"NG表現データ: {len(ng_expressions_data)}件" if ng_expressions_data is not None else "❌ 読み込み失敗")
    print(f"Health Check: http://localhost:{port}/")
    print(f"API Endpoint: http://localhost:{port}/api/check")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode
    )