# 薬機法リスクチェッカー バックエンド

薬機法リスクチェッカーのFlask APIサーバー（Claude API連携版）

## 🚀 クイックスタート

### 1. 依存関係のインストール
```bash
cd backend
pip install -r requirements.txt
```

### 2. 環境変数の設定（必須）
```bash
cp .env.example .env
# .envファイルを編集してCLAUDE_API_KEYを設定
export CLAUDE_API_KEY='your_claude_api_key_here'
```

### 3. サーバーの起動
```bash
python app.py
```

サーバーは `http://localhost:5000` で起動します。

## ⚠️ 重要な注意点

- **Claude API キーが必須**: 環境変数 `CLAUDE_API_KEY` の設定が必要
- APIキーが未設定の場合、アプリケーションは起動しません

## 📡 API エンドポイント

### ヘルスチェック
```
GET /
```

レスポンス例:
```json
{
  "status": "healthy",
  "service": "薬機法リスクチェッカー API",
  "version": "1.0.0",
  "timestamp": "2025-06-19T..."
}
```

### 薬機法チェック
```
POST /api/check
Content-Type: application/json
```

リクエスト例:
```json
{
  "text": "このクリームでシミが完全に消えます！",
  "type": "キャッチコピー"
}
```

レスポンス例:
```json
{
  "overall_risk": "高",
  "risk_counts": {
    "total": 2,
    "high": 1,
    "medium": 1,
    "low": 0
  },
  "issues": [
    {
      "fragment": "シミが消える",
      "reason": "化粧品の効能効果の範囲を逸脱し...",
      "risk_level": "高",
      "suggestions": [
        "メラニンの生成を抑え、シミ・そばかすを防ぐ",
        "乾燥による小じわを目立たなくする",
        "キメを整え、明るい印象の肌へ導く"
      ]
    }
  ],
  "rewritten_text": "このクリームでメラニンの生成を抑え、シミ・そばかすを防ぎます！"
}
```

## 🗂️ ファイル構成

```
backend/
├── app.py                 # Flask メインアプリケーション
├── requirements.txt       # Python依存関係
├── .env.example          # 環境変数設定例
├── .env                  # 環境変数設定（要作成）
├── README.md             # このファイル
├── data/                 # 薬機法関連データ（要配置）
│   ├── .gitkeep         # ディレクトリ保持用
│   ├── ng_expressions.csv # NG表現データベース
│   ├── law1.md          # 薬機法ガイド1
│   ├── law2.md          # 薬機法ガイド2
│   ├── ng.md            # NG表現詳細
│   ├── 医療機器.md      # 医療機器関連ルール
│   └── 美容・健康関連機器.md # 美容機器関連ルール
└── rule/                 # 文章種類別ルール（要配置）
    ├── .gitkeep         # ディレクトリ保持用
    ├── キャッチコピー.md
    ├── LP見出し・タイトル.md
    ├── 商品説明文.md
    └── お客様の声.md
```

## ⚠️ データファイルの配置について

**重要**: セキュリティおよび著作権保護の理由により、`data/`および`rule/`ディレクトリ内のファイルはGitHubリポジトリに含まれません。これらのファイルには薬機法関連の機密情報が含まれています。

### データファイルの入手と配置

1. **データファイルの入手**
   - プロジェクト管理者またはリポジトリオーナーから必要なデータファイルを入手してください
   - ファイルの入手に関するお問い合わせは、GitHubのIssueまたはプロジェクト管理者へご連絡ください

2. **ファイルの配置**
   ```bash
   # プロジェクトルートから実行する場合
   cd yakki-checker
   
   # dataディレクトリに配置
   cp /path/to/datafiles/* setting/backend/data/
   
   # ruleディレクトリに配置
   cp /path/to/rulefiles/* setting/backend/rule/
   ```

3. **必須ファイルの確認**
   アプリケーションの正常動作には以下のファイルが必要です：
   
   **dataディレクトリ:**
   - `ng_expressions.csv` - NG表現のデータベース
   - `law1.md` - 薬機法基本ガイドライン
   - `law2.md` - 薬機法詳細ガイドライン
   - `ng.md` - NG表現の詳細説明
   - `医療機器.md` - 医療機器関連の薬機法ルール
   - `美容・健康関連機器.md` - 美容・健康機器関連の薬機法ルール
   
   **ruleディレクトリ:**
   - `キャッチコピー.md` - キャッチコピー用のルール
   - `LP見出し・タイトル.md` - LP見出し用のルール
   - `商品説明文.md` - 商品説明文用のルール
   - `お客様の声.md` - お客様の声用のルール

4. **ファイル配置の確認**
   ```bash
   # ファイルが正しく配置されているか確認
   ls -la setting/backend/data/
   ls -la setting/backend/rule/
   ```
   
   各ディレクトリに必要なファイルがすべて存在することを確認してください。

## 🔧 設定

### 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `CLAUDE_API_KEY` | **必須** | Claude APIの認証キー |
| `DEBUG` | `True` | デバッグモード |
| `PORT` | `5000` | サーバーポート |
| `LOG_LEVEL` | `INFO` | ログレベル |

**注意**: `CLAUDE_API_KEY`は必須の環境変数です。未設定の場合、アプリケーションは正常に動作しません。

### CORS設定

開発環境では全てのオリジンからのアクセスを許可しています。  
本番環境では具体的なドメインを指定することを推奨します。

## 🧪 テスト

### curlでのテスト例
```bash
# ヘルスチェック
curl http://localhost:5000/

# 薬機法チェック
curl -X POST http://localhost:5000/api/check \
  -H "Content-Type: application/json" \
  -d '{"text":"シミが消えるクリーム","type":"キャッチコピー"}'
```

## 📝 注意事項

- **Claude API連携**: 本アプリはClaude APIを使用してリアルタイムで薬機法チェックを実行します
- **データファイル**: 上記の「データファイルの配置について」の手順に従って、必要なファイルを配置してください
- **セキュリティ**: 本番環境では適切なAPIキー管理とセキュリティ設定が必要です
- **免責事項**: 本ツールのチェック結果は参考情報であり、最終的な判断は専門家にご相談ください