# セキュリティガイド

## 🚨 重要な変更事項

### APIキーの無効化について
**2025年7月時点で、以下のAPIキーはセキュリティ上の理由により無効化されています：**

- Claude API キー：公開された可能性があるため無効化済み
- Notion API キー：公開された可能性があるため無効化済み

**必須対応：新しいAPIキーの発行と設定が必要です。**

## 🔐 セキュリティ機能

### 実装済みセキュリティ対策

#### 1. API認証システム
- **APIキー認証**：すべてのAPIエンドポイントで認証必須
- **ハッシュ化保存**：APIキーはSHA256でハッシュ化して保存
- **複数キー対応**：カンマ区切りで複数のAPIキーを設定可能

#### 2. レート制限
- **IP別制限**：1時間あたり100リクエスト/IP
- **メモリベース**：シンプルなメモリ管理による制限
- **自動クリーンアップ**：古い記録の自動削除

#### 3. セキュリティヘッダー
- **XSS対策**：X-XSS-Protection, X-Content-Type-Options
- **クリックジャッキング対策**：X-Frame-Options: DENY
- **HTTPS強制**：本番環境でStrict-Transport-Security
- **CSP**：Content-Security-Policyヘッダー

#### 4. 入力値検証
- **サーバーサイド**：厳格なバリデーション
- **クライアントサイド**：HTMLエスケープ処理
- **文字数制限**：500文字以内
- **カテゴリ・タイプ検証**：許可されたリストとの照合

#### 5. エラーハンドリング
- **情報漏洩防止**：詳細なエラー情報の非表示
- **ログ管理**：適切なログレベル設定
- **フォールバック機能**：エラー時の安全な処理

## 🔧 セットアップ手順

### 1. APIキーの発行

#### Claude API キー
1. https://console.anthropic.com/ にアクセス
2. 新しいAPIキーを発行
3. `.env`ファイルの`CLAUDE_API_KEY`に設定

#### Notion API キー（オプション）
1. https://www.notion.so/my-integrations にアクセス
2. 新しいインテグレーションを作成
3. APIキーを取得
4. `.env`ファイルの`NOTION_API_KEY`に設定

### 2. アクセス認証キーの生成
```bash
# 安全なAPIキーを生成
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

生成されたキーを`.env`ファイルの`VALID_API_KEYS`に設定：
```env
VALID_API_KEYS=生成されたキー1,生成されたキー2
```

### 3. 環境設定

#### 開発環境
```env
DEBUG=True
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

#### 本番環境
```env
DEBUG=False
ENVIRONMENT=production
ALLOWED_ORIGINS=https://yourdomain.github.io,https://your-xserver-domain.com
```

## 🌐 GitHub Pages + Xserver 導入時の注意点

### GitHub Pages
1. **静的ファイルのみ**：バックエンドは別サーバーで運用
2. **HTTPS自動化**：GitHub Pagesは自動でHTTPS化
3. **カスタムドメイン**：必要に応じて設定

### Xserver FTP導入
1. **.envファイルの保護**：
   ```apache
   # .htaccess ファイルに追加
   <Files ".env">
       Order allow,deny
       Deny from all
   </Files>
   ```

2. **ディレクトリ構造**：
   ```
   public_html/
   ├── index.html
   ├── setting/
   │   ├── frontend/ (公開)
   │   └── backend/  (非公開推奨)
   ```

3. **PHP設定**（必要な場合）：
   ```php
   # PHP利用時は適切な設定を追加
   ```

## 📋 セキュリティチェックリスト

### 導入前チェック
- [ ] Claude APIキーを新規発行
- [ ] Notion APIキーを新規発行（使用する場合）
- [ ] アクセス認証キーを生成
- [ ] `.env`ファイルを適切に設定
- [ ] `.gitignore`で`.env`ファイルを除外
- [ ] 本番環境で`DEBUG=False`に設定

### 運用時チェック
- [ ] APIキーの定期的な更新
- [ ] ログの定期的な確認
- [ ] アクセス状況の監視
- [ ] セキュリティアップデートの適用

### GitHub公開時チェック
- [ ] `.env`ファイルがコミットされていないことを確認
- [ ] APIキーが含まれるファイルがないことを確認
- [ ] 不要なログファイルが含まれていないことを確認

## 🚨 セキュリティインシデント対応

### APIキー漏洩時の対応
1. **即座にAPIキーを無効化**
2. **新しいAPIキーを発行**
3. **影響範囲の調査**
4. **ログの確認**

### 不正アクセス検知時の対応
1. **アクセスログの確認**
2. **IPアドレスのブロック**
3. **認証キーの変更**
4. **システムの点検**

## 📞 サポート

セキュリティに関する質問や問題が発生した場合は、適切な専門家にご相談ください。

---

**最終更新：2025年7月26日**
**対象バージョン：v2.0.0以降**