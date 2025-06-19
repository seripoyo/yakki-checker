# 薬機法リスクチェッカー バックエンド

薬機法リスクチェッカーのFlask APIサーバー

## 🚀 クイックスタート

### 1. 依存関係のインストール
```bash
cd backend
pip install -r requirements.txt
```

### 2. 環境変数の設定（任意）
```bash
cp .env.example .env
# .envファイルを編集（必要に応じて）
```

### 3. サーバーの起動
```bash
python app.py
```

サーバーは `http://localhost:5000` で起動します。

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
├── README.md             # このファイル
└── data/
    └── ng_expressions.csv # NG表現データベース
```

## 🔧 設定

### 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `DEBUG` | `True` | デバッグモード |
| `PORT` | `5000` | サーバーポート |
| `LOG_LEVEL` | `INFO` | ログレベル |

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

- 現在はダミーデータを返すスタブ実装です
- 実際のAI API連携は今後実装予定
- 本番環境では適切なセキュリティ設定が必要です