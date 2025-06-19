# 薬機法リスクチェッカー

美容・化粧品業界の広告テキストが薬機法（医薬品医療機器等法）に適合しているかをAIで自動チェックするWebアプリケーションです。

## 🎯 主な機能

- **薬機法リスクチェック**: 広告文の薬機法抵触リスクを3段階で評価
- **詳細な指摘事項**: 問題のある表現を特定し、具体的な改善案を提案
- **代替表現の提案**: 薬機法に適合した安全な表現を3つずつ提案
- **修正版テキスト生成**: 指摘事項を修正した完全な代替文を自動生成
- **薬機法ガイド**: 基本的な注意点とNG/OK表現例をわかりやすく解説

## 🛠️ 技術スタック

- **バックエンド**: Python Flask + Claude API + Notion API
- **フロントエンド**: Vanilla JavaScript (依存関係なし)
- **データ管理**: CSV + Notion Database
- **AI**: Anthropic Claude API

## 📁 プロジェクト構成

```
yakki-checker/
├── README.md                      # このファイル
├── TECH_DESIGN.md                 # 技術設計書
├── yakkihou_checker_prompt.md     # 要件定義書
├── setup_repo.sh                  # リポジトリ自動セットアップスクリプト
│
├── backend/                       # バックエンド (Flask API)
│   ├── app.py                     # メインアプリケーション
│   ├── requirements.txt           # Python依存関係
│   ├── .env.example              # 環境変数設定例
│   ├── README.md                 # バックエンド詳細説明
│   └── data/
│       └── ng_expressions.csv    # NG表現データベース
│
└── frontend/                      # フロントエンド (Web UI)
    ├── index.html                 # メインHTML
    ├── README.md                 # フロントエンド詳細説明
    ├── css/
    │   ├── style.css             # メインスタイル
    │   └── components.css        # コンポーネントスタイル
    ├── js/
    │   ├── script.js             # メインJavaScript
    │   ├── api.js                # API通信処理
    │   └── ui.js                 # UI制御
    └── assets/
        └── images/               # 画像リソース
```

## 🚀 セットアップと実行手順

### 1. リポジトリのクローン
```bash
git clone https://github.com/seripoyo/yakki-checker.git
cd yakki-checker
```

### 2. 環境変数の設定（必須）
```bash
# バックエンドディレクトリに移動
cd backend

# 環境変数テンプレートをコピー
cp .env.example .env

# .envファイルを編集してAPIキーを設定
nano .env  # または好きなエディタを使用
```

### 3. CSVファイルの準備（オプション）
```bash
# NG表現データファイルがプロジェクトルートにある場合
# デフォルトでサンプルデータが使用されるため、この手順は任意です
```

### 4. バックエンドサーバーの起動
```bash
# backend ディレクトリで実行
cd backend
pip install -r requirements.txt
python app.py
```

サーバーは `http://localhost:5000` で起動します。

### 5. フロントエンドの起動
```bash
# 新しいターミナルを開いて frontend ディレクトリで実行
cd frontend

# HTTPサーバーで起動（方法1: Python使用）
python -m http.server 8080

# または方法2: Node.js使用
npx serve -p 8080

# または方法3: VSCode Live Server拡張機能を使用
```

ブラウザで `http://localhost:8080` にアクセスしてください。

## ⚙️ 環境変数

このアプリケーションを正常に動作させるためには、以下の環境変数の設定が必要です。

### 必須環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `CLAUDE_API_KEY` | AnthropicのClaude APIキー | `sk-ant-api03-...` |

### オプション環境変数（Notion連携用）

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `NOTION_API_KEY` | NotionインテグレーションのAPIキー | `secret_...` |
| `NOTION_DATABASE_ID` | 薬機法ガイド用NotionデータベースID | `a1b2c3d4-...` |

### その他の設定

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `DEBUG` | `True` | デバッグモード |
| `PORT` | `5000` | サーバーポート番号 |
| `LOG_LEVEL` | `INFO` | ログレベル |
| `DATA_PATH` | `./data/ng_expressions.csv` | CSVデータファイルパス |

### .envファイルの設定方法

1. `backend/.env.example` を `backend/.env` にコピー
2. 以下の内容を参考に、実際のAPIキーを設定:

```bash
# 必須: Claude API キー
CLAUDE_API_KEY=your_claude_api_key_here

# オプション: Notion API連携（ガイド機能用）
NOTION_API_KEY=your_notion_api_key_here
NOTION_DATABASE_ID=your_notion_database_id_here

# その他の設定
DEBUG=True
PORT=5000
LOG_LEVEL=INFO
DATA_PATH=./data/ng_expressions.csv
```

### APIキーの取得方法

#### Claude API キー（必須）
1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. アカウント作成・ログイン
3. API Keysページで新しいキーを作成
4. 作成されたキーを `CLAUDE_API_KEY` に設定

#### Notion API キー（オプション）
1. [Notion Integrations](https://www.notion.so/my-integrations) にアクセス
2. 「新しいインテグレーション」を作成
3. インテグレーション設定からAPIキーを取得
4. ガイド用データベースにインテグレーションを招待
5. データベースURLからIDを取得して設定

## 📡 API エンドポイント

### ヘルスチェック
```
GET /
```

### 薬機法チェック
```
POST /api/check
Content-Type: application/json

{
  "text": "チェックしたいテキスト",
  "type": "キャッチコピー | 商品説明文 | お客様の声"
}
```

### 薬機法ガイド取得
```
GET /api/guide
```

詳細なAPI仕様は [backend/README.md](./backend/README.md) をご覧ください。

## 🧪 テスト方法

### curlでのテスト例
```bash
# ヘルスチェック
curl http://localhost:5000/

# 薬機法チェック
curl -X POST http://localhost:5000/api/check \
  -H "Content-Type: application/json" \
  -d '{"text":"シミが消えるクリーム","type":"キャッチコピー"}'

# ガイド取得
curl http://localhost:5000/api/guide
```

## 🎨 画面構成

### 1. リスクチェッカータブ
- **入力エリア**: 文章種類選択、テキスト入力（500文字制限）
- **結果表示**: 総合リスクレベル、詳細指摘事項、修正版テキスト

### 2. 薬機法簡単ガイドタブ
- **基本知識**: 薬機法の概要説明
- **NG表現集**: 避けるべき表現例
- **OK表現集**: 安全な表現例
- **チェックポイント**: 注意すべきポイント

詳細なUI仕様は [frontend/README.md](./frontend/README.md) をご覧ください。

## 🔧 開発者向け情報

### 依存関係
- **Python**: 3.8以上
- **Flask**: 2.3.3
- **anthropic**: 0.3.11
- **pandas**: 2.0.3
- **requests**: 2.31.0

### コード品質
- **型安全性**: TypeScriptは使用せず、JSDocでの型注釈を推奨
- **リンティング**: ESLintやPrettierの設定は任意
- **テスト**: 現在未実装（将来的に追加予定）

### 拡張方法
- **新しいチェックロジック**: `backend/app.py` の `call_claude_api()` 関数を拡張
- **UI改善**: `frontend/css/` 内のスタイルファイルを編集
- **新機能追加**: モジュラー設計により容易に追加可能

## ⚠️ 重要な注意事項

1. **Claude API キーは必須**: アプリケーションが動作するためには `CLAUDE_API_KEY` の設定が必要です
2. **専門家への相談**: このツールは参考情報提供のみを目的としています。実際の広告作成時は必ず薬機法の専門家にご相談ください
3. **本番環境**: 本番環境では適切なセキュリティ設定（CORS制限、HTTPSなど）を実装してください
4. **責任の制限**: 本ツールの使用による法的問題について、開発者は一切の責任を負いません

## 📝 ライセンス

MIT License - 詳細は [LICENSE](./LICENSE) ファイルをご覧ください。

## 🤝 貢献方法

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/AmazingFeature`)
3. 変更をコミット (`git commit -m 'Add some AmazingFeature'`)
4. ブランチにプッシュ (`git push origin feature/AmazingFeature`)
5. プルリクエストを作成

## 📞 サポート

- **Issues**: [GitHub Issues](https://github.com/seripoyo/yakki-checker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/seripoyo/yakki-checker/discussions)

---

**開発バージョン**: 2.0.0  
**最終更新**: 2025年6月19日