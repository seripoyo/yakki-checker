# 薬機法リスクチェッカー 開発ガイド

## Project Overview
薬機法リスクチェッカー - 美容業界の広告・制作担当者のための、手軽で直感的な一次チェック＆リライト支援ツール

### 開発背景と目的
美容業界（サロン、化粧品メーカー）の広告・制作担当者や、専門知識を持たない外部デザイナー・ライターは、広告表現における薬機法遵守に課題を抱えている。本アプリは、これらの担当者が広告文のラフ案を手軽に一次チェックできる環境を提供することで、**手戻りを削減し、制作スピードを向上させること**を主目的とする。

### ターゲットユーザー
- 美容サロンの広告担当者、オーナー
- 化粧品メーカーの広告担当者
- 美容系の記事・LP・バナー等の制作を請け負うデザイナー、ライター

## プロジェクト実行手順（エラーなし完全版）

### 前提条件
- Python 3.8以上がインストールされていること
- 有効なClaude APIキーを取得していること
- Git（開発時のみ）

### 重要：プロジェクト構造
プロジェクトは `/home/seri/yakki-check/` にクローンされています。
実際のアプリケーションファイルは `yakki-checker/` サブディレクトリ内にあります。

### 1. プロジェクトディレクトリへの移動
```bash
# すでにクローン済みの場合
cd /home/seri/yakki-check
```

### 2. バックエンドのセットアップと起動

#### 2.1 ターミナル1でバックエンドディレクトリへ移動
```bash
cd yakki-checker/setting/backend
```

#### 2.2 環境変数の設定（.envファイルが存在しない場合）
```bash
# .envファイルを作成
echo "CLAUDE_API_KEY=your_actual_api_key_here" > .env
echo "VALID_API_KEYS=your_app_api_key_here" >> .env
```

#### 2.3 必要なパッケージの確認とインストール
```bash
# Pythonバージョンの確認
python3 --version

# 必要なパッケージがインストールされていない場合のみ実行
# 注意：仮想環境なしで直接インストール
pip3 install -r requirements.txt
```

#### 2.4 バックエンドサーバーの起動
```bash
# Python3コマンドを使用（pythonコマンドが存在しない環境のため）
python3 app.py
```

バックエンドが正常に起動すると以下のメッセージが表示されます：
```
============================================================
薬機法リスクチェッカー API サーバー (Claude API連携版)
============================================================
Port: 5000
Debug: True
Claude API: ✅ 接続済み
NG表現データ: 18件
Health Check: http://localhost:5000/
API Endpoint: http://localhost:5000/api/check
============================================================
```

**注意**: バックエンドサーバーは実行したままにしてください。Ctrl+Cで停止しないでください。

### 3. フロントエンドのセットアップと起動

#### 3.1 新しいターミナル（ターミナル2）を開く
バックエンドを実行したまま、新しいターミナルウィンドウまたはタブを開きます

#### 3.2 プロジェクトルートへ移動
```bash
cd /home/seri/yakki-check/yakki-checker
```

#### 3.3 ポート8000が使用中でないか確認
```bash
# ポート8000を使用中のプロセスがあれば終了
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
```

#### 3.4 フロントエンドサーバーの起動
```bash
# 正しいディレクトリでPython3のhttp.serverを使用
cd /home/seri/yakki-check/yakki-checker
python3 -m http.server 8000
```

フロントエンドが正常に起動すると以下のメッセージが表示されます：
```
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

ブラウザでアクセスすると、以下のようなログが表示されます：
```
127.0.0.1 - - [29/Jul/2025 12:29:57] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [29/Jul/2025 12:29:57] "GET /setting/frontend/css/style.css HTTP/1.1" 200 -
127.0.0.1 - - [29/Jul/2025 12:29:57] "GET /setting/frontend/css/components.css HTTP/1.1" 200 -
```

### 4. アプリケーションへのアクセス

ブラウザで以下のURLにアクセス：
```
http://localhost:8000
```

### 5. 動作確認

1. **商品カテゴリを選択**（例：化粧品）
2. **文章の種類を選択**（例：キャッチコピー）
3. **チェックしたい文章を入力**（例：毎日のお手入れで、うるおいのある肌へ）
4. **チェック開始ボタンをクリック**

正常に動作すれば、薬機法リスクレベルとリライト案が表示されます。

## 本番環境（Render.com）デプロイ

### デプロイメント構成
- **バックエンド**: Render Web Service（Python Flask + Gunicorn）
- **フロントエンド**: GitHub Pages
- **API通信**: CORS設定済み

### デプロイ手順
1. Render.comアカウント作成
2. GitHubリポジトリ連携
3. `render.yaml`設定ファイルでの自動デプロイ
4. 環境変数（`CLAUDE_API_KEY`）の手動設定
5. GitHub Pagesでのフロントエンド公開

## プロジェクト構成（最新）
```
yakki-checker/
├── setting/
│   ├── backend/                    # バックエンドAPI
│   │   ├── app.py                 # Flask APIサーバー
│   │   ├── requirements.txt       # Python依存関係
│   │   ├── .env                  # 環境変数（要作成）
│   │   ├── data/                 # 薬機法関連データ
│   │   │   ├── ng_expressions.csv
│   │   │   ├── law1.md
│   │   │   ├── law2.md
│   │   │   ├── ng.md
│   │   │   ├── 医療機器.md
│   │   │   └── 美容・健康関連機器.md
│   │   ├── rule/                 # 文章種類別ルール
│   │   │   ├── キャッチコピー.md
│   │   │   ├── LP見出し・タイトル.md
│   │   │   ├── 商品説明文.md
│   │   │   └── お客様の声.md
│   │   ├── Procfile              # Render.com用
│   │   └── runtime.txt           # Python版指定
│   └── frontend/                   # フロントエンド
│       ├── js/                   # JavaScript
│       │   ├── api.js           # API通信（XSS対策強化済み）
│       │   ├── script.js        # メインロジック
│       │   ├── config.js        # 環境設定
│       │   ├── quickCheck.js    # 簡易チェック機能
│       │   ├── streaming.js     # ストリーミング対応
│       │   └── ui.js           # UI制御
│       ├── css/                 # スタイルシート
│       │   ├── style.css        # メインスタイル
│       │   └── components.css   # コンポーネント
│       └── yakki-guide/         # 薬機法ガイド
│           └── html/
├── index.html                     # メインHTML（CSP対応）
├── render.yaml                    # Render.com設定
└── doc/                          # ドキュメント
    ├── DEPLOYMENT.md
    ├── SECURITY.md
    └── TECH_DESIGN.md
```

## 機能仕様詳細

### アプリケーション構成
本アプリは、以下の2つの主要なタブで構成される：

1. **リスクチェッカータブ**: メイン機能。テキストを入力し、薬機法リスクをチェックする
2. **薬機法簡単ガイドタブ**: サブ機能。薬機法初心者向けの解説コンテンツを提供する

### リスクチェッカー機能

#### 入力仕様
1. **商品カテゴリ選択**:
   - 化粧品（一般化粧品）
   - 薬用化粧品（医薬部外品）
   - 医薬部外品（化粧品以外）
   - サプリメント・健康食品
   - 美容機器・健康器具・その他

2. **文章の種類選択**:
   - キャッチコピー
   - LP見出し・タイトル
   - 商品説明文・広告文・通常テキスト
   - お客様の声

3. **テキスト入力**: 指定されたテキストエリアに、チェックしたい文章をコピー＆ペーストで入力（500文字以内、XSS対策強化済み）

4. **特に訴求したいポイント**: 任意入力でリライト案に反映

#### 出力・表示仕様
「チェック開始」ボタン押下後、結果表示エリアに以下の情報が表示される：

1. **総合リスクレベル**: テキスト全体のリスクを「高」「中」「低」の3段階で表示
2. **リスク件数サマリー**: 検出されたリスクの件数（総検出数、高・中・低リスク別）
3. **詳細結果（2カラム表示）**:
   - **左カラム**: ユーザー入力文章＋問題箇所のハイライト表示
   - **右カラム**: 指摘事項のリスト（問題の表現、抵触理由、リスクレベル、代替表現提案）
4. **修正版テキスト（3つのバリエーション）**:
   - **保守的版**: 最も安全で確実な表現（問題なしの場合：より品格のある表現）
   - **バランス版**: 安全性と訴求力のバランス（問題なしの場合：感情的な魅力を加えた表現）
   - **訴求力重視版**: 法的リスクを最小限にしつつ訴求力を最大化（問題なしの場合：より刺激的で印象的な表現）

#### 問題なしの場合の特別対応
薬機法的に問題がない表現でも、より魅力的で訴求力のあるリライト案を提供：
- タイトル変更: 「💡 3つの修正版提案」→「✨ より魅力的な3つのリライト案」
- 自然な日本語生成: 文章種類に応じた適切な表現（お客様の声は顧客口調、企業説明文は丁寧語等）

### AI処理仕様

#### 知識ソース
- **プライマリ**: マークダウンファイル（law1.md, law2.md, ng.md, 美容・健康関連機器.md, 医療機器.md）
- **補助**: ng_expressions.csv（NG表現データベース）
- **文章種類別**: rule/ディレクトリのルールファイル

#### 自然な日本語生成機能
- **お客様の声**: 実際の顧客が話すような自然な口調
- **企業説明文**: 適切な敬語使用、重複表現の排除
- **キャッチコピー**: リズム感のある印象的な表現
- **重複敬語の排除**: 「〜していただいております」「〜頂戴しております」等の防止

#### API出力形式
```json
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
      "reason": "抵触する理由...",
      "risk_level": "高" | "中" | "低",
      "suggestions": ["代替案1", "代替案2", "代替案3"]
    }
  ],
  "rewritten_texts": {
    "conservative": {
      "text": "保守的版のリライト文...",
      "explanation": "このリライトが薬機法的に適切な理由..."
    },
    "balanced": {
      "text": "バランス版のリライト文...",
      "explanation": "このリライトが薬機法的に適切な理由..."
    },
    "appealing": {
      "text": "訴求力重視版のリライト文...",
      "explanation": "このリライトが薬機法的に適切な理由..."
    }
  }
}
```

## 技術仕様

### バックエンド
- **フレームワーク**: Python Flask 2.3.3
- **AI API**: Anthropic Claude API
- **WSGI**: Gunicorn（本番環境）
- **セキュリティ**: CORS、APIキー認証、入力サニタイゼーション

### フロントエンド
- **言語**: Vanilla JavaScript (ES6+)
- **セキュリティ**: 
  - Content Security Policy (CSP)
  - XSS対策（入力時・表示時のエスケープ処理）
  - 危険パターンの自動除去
- **レスポンシブ**: SP版対応、container padding調整

### セキュリティ強化
1. **XSS対策**: 
   - 入力時の危険パターン検出・除去
   - 表示時のHTMLエスケープ処理
   - CSPヘッダーによる実行制限

2. **APIセキュリティ**:
   - Claude APIキー認証
   - アプリケーション用APIキー
   - リクエストサニタイゼーション

## 開発・運用コマンド

### ローカル開発（エラーなし起動手順）

#### ステップ1: バックエンド起動（ターミナル1）
```bash
# プロジェクトディレクトリへ移動
cd /home/seri/yakki-check/yakki-checker/setting/backend

# Python3でバックエンドを起動
python3 app.py
```

#### ステップ2: フロントエンド起動（ターミナル2）
```bash
# 新しいターミナルを開く
# 正しいプロジェクトディレクトリへ移動（重要）
cd /home/seri/yakki-check/yakki-checker

# ポート8000が空いているか確認
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# フロントエンドを起動
python3 -m http.server 8000
```

**重要**: フロントエンドは必ず `/home/seri/yakki-check/yakki-checker` ディレクトリから起動する必要があります。このディレクトリに `index.html` が存在し、CSSやJSファイルへの相対パスが正しく設定されています。

### サーバー管理
```bash
# サーバー停止
lsof -ti:5000 | xargs kill -9  # バックエンド
lsof -ti:8000 | xargs kill -9  # フロントエンド

# ログ確認
tail -f setting/backend/backend.log
```

### よくあるエラーと対処法

#### 1. python: command not found
```bash
# python3コマンドを使用する
python3 app.py
```

#### 2. Address already in use (ポートが使用中)
```bash
# 使用中のプロセスを終了してから再起動
lsof -ti:8000 | xargs kill -9
python3 -m http.server 8000
```

#### 3. No such file or directory
```bash
# 正しいディレクトリパスを使用
cd /home/seri/yakki-check/yakki-checker/setting/backend
```

## トラブルシューティング

### 完全起動手順（エラー発生時の確実な対処法）

#### 手順、1: 既存プロセスの終了
```bash
# バックエンドとフロントエンドのプロセスをすべて終了
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
```

#### 手順、2: バックエンドの起動（ターミナル1）
```bash
cd /home/seri/yakki-check/yakki-checker/setting/backend
python3 app.py
```

#### 手順、3: フロントエンドの起動（ターミナル2）
```bash
# 新しいターミナルを開いて実行
cd /home/seri/yakki-check/yakki-checker
python3 -m http.server 8000
```

**正常起動確認方法**:
- サーバー起動後、ブラウザで http://localhost:8000 にアクセス
- ターミナルに以下のようなログが表示されれば成功:
```
127.0.0.1 - - [date] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [date] "GET /setting/frontend/css/style.css HTTP/1.1" 200 -
```

### Claude API認証エラー
1. `.env`ファイルのCLAUDE_API_KEYが正しく設定されているか確認
```bash
cd /home/seri/yakki-check/yakki-checker/setting/backend
cat .env
```
2. Render.com環境変数でCLAUDE_API_KEYを手動設定
3. サービス再デプロイが必要（環境変数更新後）

### バックエンドが起動しない場合
```bash
# ポート確認・強制終了
lsof -ti:5000 | xargs kill -9

# Python3コマンドを使用
cd /home/seri/yakki-check/yakki-checker/setting/backend
python3 app.py

# 依存関係の再インストールが必要な場合
pip3 install -r requirements.txt --force-reinstall
```

### フロントエンドが表示されない場合
```bash
# キャッシュクリア: Ctrl+Shift+R（Windows）またはCmd+Shift+R（Mac）
# ポート確認
lsof -ti:8000 | xargs kill -9
cd /home/seri/yakki-check/yakki-checker
python3 -m http.server 8000
```

## 非機能要件

### 免責事項
アプリケーション内のフッター等、常に視認できる場所に以下の趣旨の免責事項を明記する：
- 本アプリのチェック結果は、広告表現の適法性を保証するものではありません
- あくまで作成担当者のための参考情報としてご利用ください
- 本ツール使用時の最終的な広告表現の判断は、必ず貴社の法務・薬事担当者または専門家にご相談ください

### ビジネス要件（外部リンク）
免責事項の下に、外部の専門サービスへ誘導するためのボタンを設置：
- **ボタン文言**: `薬機法管理者に相談する`
- **デザイン**: 目立つ配色
- **リンク先**: 専門家の相談窓口URL

## Code Style Guidelines
- Pythonは PEP 8 に従う
- JavaScriptは ES6+ の記法を使用
- 関数名・変数名は分かりやすい名前を使用
- 複雑なロジックには日本語コメントを追加
- XSS対策のため、innerHTML使用時は必ずエスケープ処理を実行

# General

- ユーザーとの対話には日本語を使う
- ユーザーの指示なく、以下の作業を行わない
  - 次のタスクを開始
  - Git コミット
  - GitHub にプッシュ
- `~/.ssh`にアクセスしない

## コーディングガイドライン

### コミットメッセージ
- コミットメッセージは日本語で書く
- Conventional Commits のルールに従う

### コード内コメント
- コード内コメントやコミット時のコメントは日本語で書く

### セキュリティ
- 入力値は必ずサニタイゼーション処理を行う
- HTMLエスケープ処理を確実に実行する
- 危険なパターン（script、iframe等）の除去を行う

### コーディングスタイル
`~/.claude`ディレクトリにある言語やライブラリごとのルールを参照する。

## 最新の更新履歴
- XSS対策の強化（入力時・表示時のセキュリティ対策）
- 自然な日本語生成機能の実装
- 問題なしの場合のリライト案提供機能
- SP版レスポンシブ対応
- CSP（Content Security Policy）の実装
- 文章種類別の自然な表現ガイド機能