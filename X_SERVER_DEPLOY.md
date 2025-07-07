# Xサーバーへのデプロイ手順

## 概要
このプロジェクトはフロントエンド（HTML/CSS/JavaScript）とバックエンド（Python/Flask）で構成されています。
Xサーバーは静的ファイルのみホスティング可能なため、以下の構成で公開します：

- **フロントエンド**: Xサーバーでホスティング
- **バックエンド**: Render.comなどの外部サービスでホスティング

## 手順

### 1. バックエンドAPIのデプロイ（Render.com使用例）

1. [Render.com](https://render.com)にアカウントを作成
2. GitHubリポジトリと連携
3. 新しいWeb Serviceを作成：
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. デプロイ完了後、APIのURLをコピー（例：`https://your-app-name.onrender.com`）

### 2. フロントエンドの設定更新

1. `frontend/js/config.js`を編集：
```javascript
const API_CONFIG = {
    // ここにRenderでデプロイしたAPIのURLを設定
    BACKEND_URL: 'https://your-app-name.onrender.com',
    // ... 他の設定
};
```

### 3. Xサーバーへのアップロード

#### アップロードするファイル・ディレクトリ：
```
yakki-checker/
├── index.html              # public_htmlディレクトリ直下に配置
└── frontend/               # public_htmlディレクトリ直下に配置
    ├── css/
    │   ├── style.css
    │   └── components.css
    └── js/
        ├── config.js       # API URLを設定済みのもの
        ├── api.js
        ├── ui.js
        └── script.js
```

#### FTPでのアップロード手順：
1. FTPクライアント（FileZillaなど）でXサーバーに接続
2. `public_html`ディレクトリに移動
3. 以下の順序でアップロード：
   - `index.html`を`public_html`直下に配置
   - `frontend`ディレクトリ全体を`public_html`直下に配置

### 4. 動作確認

1. ブラウザで `https://your-domain.com` にアクセス
2. 開発者ツールのコンソールでエラーがないか確認
3. テキストを入力してチェック機能が動作することを確認

## トラブルシューティング

### CORS（クロスオリジン）エラーが発生する場合

バックエンドの`app.py`で以下の設定を確認：
```python
CORS(app, origins=['https://your-domain.com'])
```

### APIに接続できない場合

1. `frontend/js/config.js`のAPI URLが正しいか確認
2. バックエンドAPIが正常に動作しているか確認（`https://your-api-url.onrender.com/`にアクセス）
3. ブラウザの開発者ツールでネットワークタブを確認

## 代替案：フロントエンドのみの実装

バックエンドAPIを使用せず、フロントエンドのみで薬機法チェックを実装することも可能です。
この場合、`backend/data/ng_expressions.csv`の内容をJavaScriptに移植する必要があります。

### メリット：
- サーバー設定が不要
- レスポンスが高速
- 運用コストがかからない

### デメリット：
- チェックロジックがクライアント側に公開される
- データの更新が困難
- 高度な処理ができない

## セキュリティ注意事項

- APIキーなどの機密情報はフロントエンドに含めない
- 本番環境では必ずHTTPSを使用する
- CORSの設定は必要最小限にする