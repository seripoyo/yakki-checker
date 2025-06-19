# 薬機法リスクチェッカー 技術設計書

- **バージョン:** 1.0
- **作成日:** 2025年6月19日
- **作成者:** Claude Code

---

## 1. 技術スタック選定

### 1.1. バックエンド: Python Flask

**選定理由:**
- **初心者フレンドリー**: Pythonは学習コストが低く、Flaskは最軽量のWebフレームワーク
- **AI連携の優位性**: 薬機法チェックにAI（Claude API、OpenAI API等）を活用する際、Pythonは豊富なライブラリを持つ
- **迅速な開発**: 最小限のコードでAPIサーバーを構築可能
- **JSON処理**: 要件定義で指定されたJSON形式のレスポンスを容易に実装
- **CSVデータ処理**: pandas等でNG表現CSVファイルの読み込みが簡単

### 1.2. フロントエンド: Vanilla JavaScript

**選定理由:**
- **依存関係ゼロ**: npm install不要、ブラウザだけで動作
- **軽量性**: React/Vueなどのフレームワーク不要で高速ロード
- **保守性**: 特定のフレームワークのバージョンアップに依存しない
- **学習コストの低さ**: HTML/CSS/JSの基礎知識のみで開発・保守可能
- **要件適合性**: 2タブ構成のシンプルなUIには過度なフレームワークは不要

---

## 2. 推奨ファイル構造

```
yakki-checker/
├── README.md                      # プロジェクト概要・セットアップ手順
├── .gitignore                     # Git除外ファイル設定
├── setup_repo.sh                  # リポジトリ自動セットアップスクリプト
├── yakkihou_checker_prompt.md     # 要件定義書
├── TECH_DESIGN.md                 # 技術設計書（本ファイル）
│
├── backend/                       # バックエンドアプリケーション
│   ├── app.py                     # Flask メインアプリケーション
│   ├── requirements.txt           # Python依存パッケージ定義
│   ├── config.py                  # 設定ファイル（API Key等）
│   ├── checker.py                 # 薬機法チェックロジック
│   ├── data/
│   │   └── ng_expressions.csv     # NG表現データベース
│   └── templates/                 # 開発用テンプレート（任意）
│
├── frontend/                      # フロントエンドアプリケーション
│   ├── index.html                 # メインHTMLファイル
│   ├── css/
│   │   ├── style.css              # メインスタイルシート
│   │   └── components.css         # コンポーネント別スタイル
│   ├── js/
│   │   ├── script.js              # メインJavaScript
│   │   ├── api.js                 # API通信処理
│   │   └── ui.js                  # UI操作・表示制御
│   └── assets/
│       └── images/                # 画像ファイル
│
└── docs/                          # ドキュメント（任意）
    ├── api_documentation.md       # API仕様書
    └── deployment_guide.md        # デプロイメントガイド
```

---

## 3. 各ファイルの役割説明

### 3.1. バックエンドファイル

| ファイル名 | 役割 | 概要 |
|-----------|------|------|
| `app.py` | Flask メインアプリケーション | APIエンドポイント定義、CORS設定、リクエスト処理 |
| `requirements.txt` | Python依存関係管理 | flask, requests, pandas, python-dotenv等を定義 |
| `config.py` | 設定管理 | API Key、データベースパス、デバッグモード等の設定 |
| `checker.py` | 薬機法チェックロジック | AI API呼び出し、CSV読み込み、リスク評価処理 |
| `ng_expressions.csv` | NG表現データ | 薬機法違反表現とカテゴリのマスタデータ |

### 3.2. フロントエンドファイル

| ファイル名 | 役割 | 概要 |
|-----------|------|------|
| `index.html` | メインHTML | 2タブ構成、入力フォーム、結果表示エリアの定義 |
| `style.css` | メインスタイル | 全体レイアウト、タブUI、レスポンシブデザイン |
| `components.css` | コンポーネントスタイル | ボタン、カード、ハイライト等の個別スタイル |
| `script.js` | メインJavaScript | タブ切り替え、フォーム処理、結果表示制御 |
| `api.js` | API通信モジュール | バックエンドとの通信、エラーハンドリング |
| `ui.js` | UI制御モジュール | ハイライト表示、アニメーション、インタラクション |

### 3.3. プロジェクト管理ファイル

| ファイル名 | 役割 | 概要 |
|-----------|------|------|
| `README.md` | プロジェクト説明 | 概要、セットアップ手順、使用方法 |
| `.gitignore` | Git除外設定 | `__pycache__/`, `.env`, `node_modules/`等を除外 |
| `setup_repo.sh` | 自動セットアップ | リポジトリ初期化スクリプト |

---

## 4. API設計

### 4.1. エンドポイント仕様

```
POST /api/check
Content-Type: application/json

Request Body:
{
  "text": "チェックしたいテキスト",
  "type": "キャッチコピー | 商品説明文 | お客様の声"
}

Response:
{
  "overall_risk": "高 | 中 | 低",
  "risk_counts": {
    "total": Number,
    "high": Number,
    "medium": Number,
    "low": Number
  },
  "issues": [
    {
      "fragment": "問題のある表現",
      "reason": "抵触理由の説明",
      "risk_level": "高 | 中 | 低",
      "suggestions": ["代替案1", "代替案2", "代替案3"]
    }
  ],
  "rewritten_text": "修正後の全文"
}
```

### 4.2. CORS設定

フロントエンドとバックエンドの分離開発のため、適切なCORS設定を実装する。

---

## 5. 開発環境セットアップ

### 5.1. バックエンド起動
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 5.2. フロントエンド起動
```bash
cd frontend
# HTTPサーバーでの起動（Python使用例）
python -m http.server 8080
# または Live Server 等のVSCode拡張機能を使用
```

### 5.3. 環境変数設定
```bash
# .env ファイル作成
OPENAI_API_KEY=your_api_key_here
CLAUDE_API_KEY=your_claude_key_here
DEBUG=True
```

---

## 6. 技術的考慮事項

### 6.1. セキュリティ
- API Keyの環境変数管理
- CSRF対策（必要に応じて）
- 入力値のサニタイゼーション

### 6.2. パフォーマンス
- AI API呼び出しの非同期処理
- CSVファイルの効率的な読み込み
- フロントエンドでの適切なローディング表示

### 6.3. 拡張性
- 新しいチェックロジックの追加が容易な構造
- NG表現データの更新機能
- 複数AI APIの切り替え対応

---

**次のステップ**: この設計に基づき、各ファイルの実装を順次進めていきます。