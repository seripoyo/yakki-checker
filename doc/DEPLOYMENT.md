# 薬機法リスクチェッカー デプロイガイド

## デプロイオプション

### 1. Render（推奨・無料枠あり）

最も簡単で、無料枠があるため個人利用に最適です。

#### バックエンド（Flask API）のデプロイ

1. [Render](https://render.com)にアカウントを作成
2. GitHubリポジトリを接続
3. 新しい「Web Service」を作成
4. 以下の設定を使用：
   - **Name**: yakki-checker-backend
   - **Root Directory**: yakki-checker/backend
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `CLAUDE_API_KEY`: あなたのClaude APIキー
     - `NOTION_API_KEY`: あなたのNotion APIキー（オプション）
     - `NOTION_DATABASE_ID`: あなたのNotion Database ID（オプション）
     - `DEBUG`: False

#### フロントエンドのデプロイ

1. 新しい「Static Site」を作成
2. 以下の設定を使用：
   - **Name**: yakki-checker-frontend
   - **Root Directory**: yakki-checker/frontend
   - **Build Command**: （なし）
   - **Publish Directory**: .

3. デプロイ後、`frontend/js/api.js`のAPIエンドポイントURLを更新：
   ```javascript
   const API_BASE_URL = 'https://yakki-checker-backend.onrender.com';
   ```

### 2. Vercel + Supabase

より高度な機能が必要な場合の選択肢です。

#### バックエンドの準備

1. `yakki-checker/backend/vercel.json`を作成：
```json
{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

2. `yakki-checker/backend/requirements.txt`に追加：
```
gunicorn==21.2.0
```

#### Vercelでのデプロイ

1. [Vercel](https://vercel.com)にアカウントを作成
2. GitHubリポジトリをインポート
3. 環境変数を設定（Render同様）
4. デプロイ

### 3. Railway

開発者向けのシンプルなデプロイプラットフォーム。

1. [Railway](https://railway.app)にアカウントを作成
2. GitHubリポジトリを接続
3. 環境変数を設定
4. 自動的にデプロイが開始

### 4. Google Cloud Run（本番向け）

スケーラビリティと信頼性が必要な場合。

#### Dockerファイルの作成

`yakki-checker/backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```

`yakki-checker/frontend/Dockerfile`:
```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
```

#### デプロイコマンド

```bash
# バックエンドのデプロイ
cd yakki-checker/backend
gcloud run deploy yakki-checker-backend \
  --source . \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars "CLAUDE_API_KEY=$CLAUDE_API_KEY,NOTION_API_KEY=$NOTION_API_KEY"

# フロントエンドのデプロイ
cd ../frontend
gcloud run deploy yakki-checker-frontend \
  --source . \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated
```

## 環境変数の管理

### セキュリティベストプラクティス

1. **APIキーを絶対にコードにハードコーディングしない**
2. **`.env`ファイルを`.gitignore`に追加**
3. **本番環境では環境変数を使用**

### 各プラットフォームでの環境変数設定

- **Render**: ダッシュボードの「Environment」タブで設定
- **Vercel**: プロジェクト設定の「Environment Variables」で設定
- **Railway**: プロジェクト設定の「Variables」で設定
- **Google Cloud Run**: `--set-env-vars`フラグまたはSecret Managerを使用

## デプロイ前のチェックリスト

- [ ] APIキーが環境変数として設定されている
- [ ] `DEBUG`モードが`False`に設定されている
- [ ] フロントエンドのAPI URLが本番URLに更新されている
- [ ] CORSの設定が本番環境に合わせて調整されている
- [ ] `.env`ファイルがgitignoreに含まれている
- [ ] requirements.txtに必要なパッケージがすべて含まれている

## トラブルシューティング

### よくある問題

1. **「pandas not available」エラー**
   - 解決策：requirements.txtに`pandas`を追加（ファイルサイズが大きくなるため注意）

2. **CORS エラー**
   - 解決策：`app.py`のCORS設定でフロントエンドのURLを明示的に許可

3. **ポート設定エラー**
   - 解決策：環境変数`$PORT`を使用するよう設定

4. **メモリ不足エラー**
   - 解決策：無料プランの場合、より大きなプランにアップグレード

## 推奨事項

1. **開発環境と本番環境の分離**
   - 開発用と本番用で別々のAPIキーを使用
   - ステージング環境の設置を検討

2. **監視とロギング**
   - エラートラッキングツール（Sentry等）の導入
   - アクセスログの定期的な確認

3. **セキュリティ**
   - HTTPSの強制
   - Rate limitingの実装
   - 入力値のバリデーション強化

4. **パフォーマンス**
   - CDNの使用（フロントエンド）
   - キャッシングの実装
   - データベースの最適化（将来的に必要な場合）