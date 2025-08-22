# 薬機法リスクチェッカー クイックデプロイガイド

## 🚀 最速デプロイ方法（Render.com使用）

### 前提条件
- GitHubアカウント
- Claude API キー（[Anthropic Console](https://console.anthropic.com/)で取得）
- Notion API キー（オプション）

### ステップ1: GitHubにプッシュ

```bash
# リポジトリをGitHubに作成してプッシュ
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/yakki-checker.git
git push -u origin main
```

### ステップ2: Renderでデプロイ

1. [Render.com](https://render.com)にサインアップ
2. GitHubアカウントを連携
3. 「New +」→「Blueprint」をクリック
4. GitHubリポジトリを選択
5. `render.yaml`が自動的に検出される
6. 環境変数を設定：
   - `CLAUDE_API_KEY`: あなたのClaude APIキー（必須）
   - `NOTION_API_KEY`: NotionのAPIキー（オプション）
   - `NOTION_DATABASE_ID`: NotionのデータベースID（オプション）

### ステップ3: フロントエンドの設定更新

デプロイ完了後、フロントエンドのAPIエンドポイントを更新：

1. RenderダッシュボードでバックエンドサービスのURLをコピー
2. `frontend/js/api.js`を編集：

```javascript
// 変更前
const API_BASE_URL = 'http://localhost:5000';

// 変更後（実際のURLに置き換え）
const API_BASE_URL = 'https://yakki-checker-backend.onrender.com';
```

3. 変更をコミット＆プッシュ：

```bash
git add frontend/js/api.js
git commit -m "Update API endpoint for production"
git push
```

### ステップ4: 動作確認

1. フロントエンドのURLにアクセス
2. テキストを入力して「チェック」をクリック
3. 結果が表示されることを確認

## 🔒 セキュリティ注意事項

1. **APIキーの管理**
   - `.env`ファイルは絶対にGitにコミットしない
   - 環境変数として設定する

2. **CORS設定**
   - 本番環境では`app.py`のCORS設定を更新：
   ```python
   CORS(app, origins=['https://your-frontend-url.onrender.com'])
   ```

3. **デバッグモード**
   - 本番環境では必ず`DEBUG=False`に設定

## 🛠️ トラブルシューティング

### 「APIキーが無効です」エラー
- Renderの環境変数設定を確認
- APIキーが正しくコピーされているか確認

### CORSエラー
- バックエンドのCORS設定にフロントエンドURLを追加
- ブラウザのキャッシュをクリア

### 「サーバーに接続できません」エラー
- バックエンドサービスが起動しているか確認
- `api.js`のURLが正しいか確認

## 📱 その他のデプロイオプション

### Vercel（フロントエンド専用）
```bash
npx vercel --prod
```

### Netlify（フロントエンド専用）
```bash
npx netlify deploy --prod
```

### Heroku（バックエンド）
```bash
heroku create yakki-checker-backend
heroku config:set CLAUDE_API_KEY=your_key_here
git push heroku main
```

## 🎉 完了！

これで薬機法リスクチェッカーが本番環境で動作します。
URLを関係者に共有して、フィードバックを集めましょう！