# 薬機法リスクチェッカー

## 概要
薬機法（薬機法）に関するテキストのコンプライアンスチェックを行うWEBアプリケーションです。Claude APIを活用して高精度な薬機法抵触リスクの分析と改善提案を提供します。

## 🚨 重要: セキュリティ対策について

### 実装済みセキュリティ機能

#### 1. API認証システム
- **認証必須**: すべてのAPIエンドポイントでAPIキー認証を実装
- **ハッシュ化保存**: APIキーはSHA256でハッシュ化して安全に保存
- **複数キー対応**: 開発・本番環境で異なるAPIキーを設定可能

#### 2. レート制限
- **IP別制限**: 1時間あたり100リクエスト/IPアドレス
- **クライアントサイド制限**: 連続リクエストの防止（100ms間隔）
- **自動クリーンアップ**: 古いアクセス記録の自動削除

#### 3. セキュリティヘッダー
- **XSS対策**: X-XSS-Protection, X-Content-Type-Options設定
- **クリックジャッキング対策**: X-Frame-Options: DENY
- **HTTPS強制**: 本番環境でStrict-Transport-Security
- **CSP**: Content-Security-Policyで外部リソース制限

#### 4. 入力値検証・サニタイゼーション
- **サーバーサイド**: 厳格な入力値バリデーション
- **クライアントサイド**: HTMLエスケープ処理
- **文字数制限**: 500文字以内の制限
- **許可リスト**: カテゴリ・タイプの厳格な検証

#### 5. 環境設定の分離
- **開発/本番分離**: 環境別の設定管理
- **デバッグモード制御**: 本番環境では詳細エラー非表示
- **CORS設定**: 環境に応じた適切なオリジン制限

## 🔧 セットアップ手順

### 1. 必要なAPIキーの発行

#### Claude API キー（必須）
1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. 新しいAPIキーを発行
3. `.env`ファイルの`CLAUDE_API_KEY`に設定

#### アクセス認証キー（必須）
安全なAPIキーを生成してください：
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. 環境設定ファイルの作成

`setting/backend/.env`ファイルを作成し、以下を設定：

```env
# Claude API設定
CLAUDE_API_KEY=your_claude_api_key_here

# アクセス認証（カンマ区切りで複数指定可能）
VALID_API_KEYS=your_generated_secure_key_here

# 環境設定
DEBUG=False
ENVIRONMENT=production

# CORS設定（本番環境のドメインを指定）
ALLOWED_ORIGINS=https://yourdomain.github.io,https://your-xserver-domain.com

# Notion設定（オプション）
NOTION_API_KEY=your_notion_api_key_here
NOTION_DATABASE_ID=your_database_id_here
```

### 3. 依存関係のインストール

```bash
cd setting/backend
pip install -r requirements.txt
```

### 4. フロントエンド・バックエンドの起動

#### バックエンド起動
```bash
cd setting/backend
python app.py
```

#### フロントエンド起動（開発環境）
```bash
cd setting/frontend
python -m http.server 8000
```

アクセス: http://localhost:8000

## 📁 ディレクトリ構造

```
yakki-checker/
├── index.html              # メインHTML（ルートに配置）
├── CLAUDE.md               # プロジェクト設定
├── .gitignore              # Git除外設定
├── README.md               # このファイル
├── setting/                # アプリケーション本体
│   ├── frontend/           # フロントエンド
│   │   ├── css/
│   │   ├── js/
│   │   └── index.html
│   └── backend/            # バックエンド
│       ├── app.py          # メインアプリケーション
│       ├── data/           # 薬機法データ
│       ├── rule/           # カテゴリ別ルール
│       ├── .env            # 環境変数（要作成）
│       └── requirements.txt
└── doc/                    # ドキュメント
    └── SECURITY.md         # 詳細セキュリティガイド
```

## 🌐 デプロイメント

### GitHub Pages + Xserver構成

#### GitHub Pages（フロントエンド）
1. リポジトリをGitHub Pagesで公開
2. `index.html`がルートに配置されているため自動認識
3. HTTPSが自動で有効化される

#### Xserver（バックエンド）
1. FTPで`setting/backend/`をアップロード
2. `.htaccess`ファイルで追加セキュリティ設定
3. 環境変数を本番用に設定

### セキュリティ設定（Xserver用）

`.htaccess`に以下を追加：
```apache
# 環境変数ファイルの保護
<Files ".env">
    Order allow,deny
    Deny from all
</Files>

# セキュリティヘッダー
<IfModule mod_headers.c>
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"
</IfModule>
```

## 🔄 リアルタイム機能

### ファイル監視システム
- `data/`ディレクトリ: 薬機法データの自動更新
- `rule/`ディレクトリ: カテゴリ別ルールの自動更新
- ファイル変更時に自動でキャッシュを無効化・更新

## 📋 セキュリティチェックリスト

### 導入前必須チェック
- [ ] Claude APIキーを新規発行して設定
- [ ] アクセス認証キーを生成して設定
- [ ] `.env`ファイルを適切に設定
- [ ] 本番環境で`DEBUG=False`に設定
- [ ] `ALLOWED_ORIGINS`を本番ドメインに限定

### 運用時チェック
- [ ] APIキーの定期的な更新（3ヶ月毎推奨）
- [ ] アクセスログの定期確認
- [ ] 不正アクセスの監視
- [ ] セキュリティアップデートの適用

### GitHub公開前チェック
- [ ] `.env`ファイルがコミット対象外であることを確認
- [ ] 機密情報が含まれるファイルがないことを確認
- [ ] `requirements.txt`が最新であることを確認

## ⚠️ 注意事項

### APIキーの管理
- **絶対にAPIキーをGitにコミットしない**
- 開発環境と本番環境で異なるキーを使用
- 定期的なローテーションを実施

### 本番環境での運用
- デバッグモードは必ず無効化
- 適切なログ監視体制を構築
- 定期的なセキュリティ監査を実施

## 🔧 開発時の注意点

### APIキーのテスト
開発環境では以下でAPIキーを設定可能：
```javascript
// ブラウザコンソールで実行
window.yakkiApi.setApiKey('your_development_key');
```

### ログ確認
バックエンドログで処理状況を確認：
```bash
tail -f backend.log
```

## 📞 トラブルシューティング

### よくある問題

#### 1. チェックボタンが動作しない
- バックエンドが起動しているか確認
- APIキーが正しく設定されているか確認
- ブラウザコンソールでエラーを確認

#### 2. CORS エラー
- `ALLOWED_ORIGINS`に正しいドメインが設定されているか確認
- 本番環境では開発用URLが除外されているか確認

#### 3. Rate Limit エラー
- 1時間あたり100リクエストの制限を確認
- IPアドレス単位での制限であることを確認

---

## 📄 詳細ドキュメント

セキュリティに関する詳細情報は [doc/SECURITY.md](doc/SECURITY.md) をご参照ください。

**最終更新：2025年7月26日**
**バージョン：v2.0.0**