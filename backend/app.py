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

# ログ設定を先に行う
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import csv
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# Flaskアプリケーションの初期化
app = Flask(__name__)

# CORS設定 - フロントエンドからのアクセスを許可
CORS(app, origins=[
    'https://seripoyo.github.io',
    'http://localhost:3000', 
    'http://localhost:8000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8000'
])

# アプリケーション設定
app.config['JSON_AS_ASCII'] = False  # 日本語文字化け防止

# ===== グローバル変数 =====
claude_client = None
ng_expressions_data = None
csv_reference_text = ""
notion_api_key = None
notion_database_id = None

def initialize_app():
    """
    アプリケーションの初期化処理
    APIキーの確認とCSVファイルの読み込み
    """
    global claude_client, ng_expressions_data, csv_reference_text, notion_api_key, notion_database_id
    
    logger.info("薬機法リスクチェッカー 初期化開始")
    
    # 1. Claude API キーの確認
    claude_api_key = os.getenv('CLAUDE_API_KEY')
    if not claude_api_key:
        logger.error("CLAUDE_API_KEY環境変数が設定されていません")
        # Gunicornで動作するようにexit()を使わない
        claude_client = None
    
    # Claude クライアントの初期化
    if claude_api_key:
        try:
            claude_client = anthropic.Anthropic(api_key=claude_api_key)
            logger.info("Claude API クライアント初期化完了")
        except Exception as e:
            logger.error(f"Claude API クライアント初期化失敗: {str(e)}")
            claude_client = None
    else:
        claude_client = None
    
    # Notion API キーの確認（オプション）
    notion_api_key = os.getenv('NOTION_API_KEY')
    notion_database_id = os.getenv('NOTION_DATABASE_ID')
    
    if notion_api_key and notion_database_id:
        logger.info("Notion API 設定確認完了")
    else:
        logger.warning("Notion API設定が不完全です（NOTION_API_KEY, NOTION_DATABASE_IDが必要）")
        logger.warning("薬機法ガイド機能は無効化されます")
    
    # 2. CSVファイルの読み込み
    csv_file_path = os.path.join(os.path.dirname(__file__), 'data', 'ng_expressions.csv')
    
    try:
        if not os.path.exists(csv_file_path):
            logger.warning(f"CSVファイルが見つかりません: {csv_file_path}")
            # デフォルトのNG表現データを使用
            ng_expressions_data = create_default_ng_data()
            csv_reference_text = format_ng_data_for_prompt(ng_expressions_data)
        else:
            ng_expressions_data = read_csv_file(csv_file_path)
            csv_reference_text = format_csv_for_prompt(ng_expressions_data)
            logger.info(f"CSVファイル読み込み完了: {len(ng_expressions_data)}件のNG表現データ")
    
    except Exception as e:
        logger.error(f"CSVファイル読み込みエラー: {str(e)}")
        # フォールバック: デフォルトデータを使用
        ng_expressions_data = create_default_ng_data()
        csv_reference_text = format_ng_data_for_prompt(ng_expressions_data)
        logger.info("デフォルトのNG表現データを使用")
    
    logger.info("薬機法リスクチェッカー 初期化完了")

def read_csv_file(file_path):
    """
    CSVファイルを読み込んで辞書のリストとして返す
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

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
    return default_data

def format_csv_for_prompt(data):
    """
    データリストをプロンプト用の文字列形式に変換
    """
    if not data:
        return "参考データなし"
    
    reference_text = "=== 薬機法NG表現参考データ ===\n"
    
    # 通常のリストの場合
    for row in data:
        reference_text += f"NG表現: {row.get('NG表現', 'N/A')}\n"
        reference_text += f"カテゴリ: {row.get('カテゴリ', 'N/A')}\n"
        reference_text += f"リスクレベル: {row.get('リスクレベル', 'N/A')}\n"
        
        # 代替表現があれば追加
        alternatives = []
        for i in range(1, 4):
            alt_key = f"代替表現{i}"
            if alt_key in row and row[alt_key]:
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
        "notion_api": "connected" if notion_api_key and notion_database_id else "disconnected",
        "ng_data_count": len(ng_expressions_data) if ng_expressions_data is not None else 0,
        "csv_module": "enabled",
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

@app.route('/api/guide', methods=['GET'])
def get_guide():
    """
    薬機法ガイドコンテンツ取得エンドポイント
    Notionデータベースから薬機法ガイド情報を取得
    """
    try:
        # Notion API設定の確認
        if not notion_api_key or not notion_database_id:
            logger.warning("Notion API設定が不完全 - フォールバックデータを返却")
            return jsonify(get_fallback_guide_data())
        
        logger.info("Notion API呼び出し開始")
        
        # Notion API呼び出し
        guide_data = fetch_notion_database()
        
        logger.info(f"Notion APIからガイドデータ取得完了: {len(guide_data)}件")
        
        return jsonify({
            "status": "success",
            "data": guide_data,
            "source": "notion",
            "count": len(guide_data),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Notion API呼び出しエラー: {str(e)}")
        
        # フォールバック: 静的データを返却
        fallback_data = get_fallback_guide_data()
        
        return jsonify({
            "status": "fallback",
            "data": fallback_data,
            "source": "fallback",
            "error_message": str(e),
            "count": len(fallback_data),
            "timestamp": datetime.now().isoformat()
        })

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
        
        # Claude クライアントの確認
        if claude_client is None:
            logger.error("Claude クライアントが初期化されていません")
            raise Exception("Claude API クライアントが利用できません")
        
        # Claude APIリクエスト
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",  # 最新モデルに更新
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

def fetch_notion_database():
    """
    Notion APIからデータベースコンテンツを取得
    
    Returns:
        list: 整形されたガイドデータのリスト
    """
    try:
        # Notion API エンドポイント
        url = f"https://api.notion.com/v1/databases/{notion_database_id}/query"
        
        # リクエストヘッダー
        headers = {
            "Authorization": f"Bearer {notion_api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # リクエストボディ（フィルタリングやソートが必要な場合）
        payload = {
            "page_size": 100  # 最大100件取得
            # ソートは一旦削除（Notionのプロパティ名が不明なため）
        }
        
        logger.info(f"Notion API Request: {url}")
        
        # Notion API呼び出し
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Notion API Error: {response.status_code} - {response.text}")
            raise Exception(f"Notion API returned status {response.status_code}")
        
        data = response.json()
        
        # データの整形
        guide_items = []
        
        for page in data.get("results", []):
            try:
                # ページのプロパティから情報抽出
                properties = page.get("properties", {})
                
                # タイトルの抽出（通常は "名前" または "タイトル" プロパティ）
                title = extract_title_from_properties(properties)
                
                # コンテンツの抽出（ページの子ブロックから取得）
                content = extract_content_from_page(page.get("id"))
                
                # カテゴリなどの追加情報
                category = extract_property_value(properties, "カテゴリ")
                priority = extract_property_value(properties, "優先度")
                
                guide_item = {
                    "id": page.get("id"),
                    "title": title,
                    "content": content,
                    "category": category,
                    "priority": priority,
                    "created_time": page.get("created_time"),
                    "last_edited_time": page.get("last_edited_time")
                }
                
                guide_items.append(guide_item)
                
            except Exception as e:
                logger.warning(f"ページの処理中にエラー: {str(e)}")
                continue
        
        return guide_items
        
    except requests.RequestException as e:
        logger.error(f"Notion API通信エラー: {str(e)}")
        raise Exception(f"Notion API通信に失敗しました: {str(e)}")
    
    except Exception as e:
        logger.error(f"Notion データ処理エラー: {str(e)}")
        raise Exception(f"Notionデータの処理に失敗しました: {str(e)}")

def extract_title_from_properties(properties):
    """
    Notionページのプロパティからタイトルを抽出
    """
    # 一般的なタイトルプロパティ名を順番に確認
    title_candidates = ["名前", "タイトル", "Title", "Name"]
    
    for candidate in title_candidates:
        if candidate in properties:
            prop = properties[candidate]
            if prop.get("type") == "title" and prop.get("title"):
                return "".join([text.get("plain_text", "") for text in prop["title"]])
    
    # フォールバック: 最初のtitleタイプのプロパティを使用
    for prop_name, prop_value in properties.items():
        if prop_value.get("type") == "title" and prop_value.get("title"):
            return "".join([text.get("plain_text", "") for text in prop_value["title"]])
    
    return "無題"

def extract_property_value(properties, property_name):
    """
    Notionページの特定のプロパティから値を抽出
    """
    if property_name not in properties:
        return None
    
    prop = properties[property_name]
    prop_type = prop.get("type")
    
    if prop_type == "rich_text" and prop.get("rich_text"):
        return "".join([text.get("plain_text", "") for text in prop["rich_text"]])
    elif prop_type == "select" and prop.get("select"):
        return prop["select"].get("name")
    elif prop_type == "multi_select" and prop.get("multi_select"):
        return [item.get("name") for item in prop["multi_select"]]
    elif prop_type == "number":
        return prop.get("number")
    elif prop_type == "checkbox":
        return prop.get("checkbox")
    elif prop_type == "date" and prop.get("date"):
        return prop["date"].get("start")
    
    return None

def extract_content_from_page(page_id):
    """
    Notionページの子ブロックからコンテンツを抽出
    """
    try:
        # ページの子ブロック取得
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        headers = {
            "Authorization": f"Bearer {notion_api_key}",
            "Notion-Version": "2022-06-28"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"ブロック取得エラー: {response.status_code}")
            return ""
        
        blocks_data = response.json()
        content_parts = []
        
        for block in blocks_data.get("results", []):
            block_type = block.get("type")
            
            if block_type == "paragraph" and block.get("paragraph", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["paragraph"]["rich_text"]])
                if text.strip():
                    content_parts.append(text.strip())
            
            elif block_type == "heading_1" and block.get("heading_1", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["heading_1"]["rich_text"]])
                if text.strip():
                    content_parts.append(f"# {text.strip()}")
            
            elif block_type == "heading_2" and block.get("heading_2", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["heading_2"]["rich_text"]])
                if text.strip():
                    content_parts.append(f"## {text.strip()}")
            
            elif block_type == "bulleted_list_item" and block.get("bulleted_list_item", {}).get("rich_text"):
                text = "".join([text.get("plain_text", "") for text in block["bulleted_list_item"]["rich_text"]])
                if text.strip():
                    content_parts.append(f"• {text.strip()}")
        
        return "\n\n".join(content_parts) if content_parts else ""
        
    except Exception as e:
        logger.warning(f"コンテンツ抽出エラー: {str(e)}")
        return ""

def get_fallback_guide_data():
    """
    Notion API が利用できない場合のフォールバックガイドデータ
    """
    return [
        {
            "id": "fallback-1",
            "title": "薬機法の基本",
            "content": "薬機法（医薬品医療機器等法）は、化粧品や医薬品の品質、有効性、安全性を確保するための法律です。美容系商品の広告では、効果効能の表現に厳格な制限があります。",
            "category": "基本知識",
            "priority": "高",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        },
        {
            "id": "fallback-2", 
            "title": "化粧品で使用できない表現",
            "content": "• 「シミが消える」「シワがなくなる」- 医薬品的な効果を暗示\n• 「アンチエイジング効果」「老化防止」- 老化に関する直接的な表現\n• 「医学的に証明された」「臨床試験で実証」- 科学的根拠の過度な強調\n• 「完全に」「絶対に」「確実に」- 効果を断定的に表現",
            "category": "NG表現",
            "priority": "高",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        },
        {
            "id": "fallback-3",
            "title": "化粧品で使用可能な表現",
            "content": "• 「うるおいを与える」「乾燥を防ぐ」- 化粧品の基本的な効能効果\n• 「肌を整える」「肌にハリを与える」- 適切な効果の表現\n• 「メイクアップ効果により」- 見た目の効果を明確化\n• 「使用感には個人差があります」- 効果の個人差を明記",
            "category": "OK表現", 
            "priority": "高",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        },
        {
            "id": "fallback-4",
            "title": "チェックのポイント",
            "content": "• 医薬品的な効果を暗示していないか\n• 効果を断定的に表現していないか\n• 科学的根拠を過度に強調していないか\n• 化粧品の効能効果の範囲内か\n• 個人差について言及しているか",
            "category": "チェックポイント",
            "priority": "中",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat()
        }
    ]

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

# Gunicornでもフラスコ開発サーバーでも初期化が実行されるようにモジュールレベルで呼び出す
initialize_app()

if __name__ == '__main__':
    
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