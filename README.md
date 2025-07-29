# 薬機法リスクチェッカー

![薬機法リスクチェッカー](https://img.shields.io/badge/version-v2.1.0-blue)
![Claude API](https://img.shields.io/badge/AI-Claude%20API-orange)
![License](https://img.shields.io/badge/license-Proprietary-red)

## 🎯 アプリケーション概要

**薬機法リスクチェッカー**は、美容・健康業界の広告担当者やライター向けの薬機法適合性チェックツールです。Claude APIを活用し、広告文や商品説明文の薬機法抵触リスクを即座に分析。適切な代替表現を3つのバリエーションで提案します。

### 💡 主な特徴

- **🔍 高精度リスク分析**: Claude AIによる文脈を考慮した精密な薬機法チェック
- **📝 3つのリライト案**: 保守的版・バランス版・訴求力重視版の3パターン提案
- **⚡ リアルタイム処理**: ストリーミング対応で大量テキストも高速処理
- **🎨 直感的UI**: カテゴリ・文章種類を選ぶだけの簡単操作
- **🔒 セキュリティ重視**: APIキー認証、レート制限、XSS対策を完備

## 📱 対象ユーザー

- 🏢 **美容サロン・エステサロン**の広告担当者
- 💄 **化粧品メーカー**のマーケティング担当者
- ✍️ **広告制作会社**のコピーライター・デザイナー
- 📢 **ECサイト運営者**の商品説明文作成担当者
- 🎯 **インフルエンサー**・ブロガー

## 🚀 使い方

### 1. 商品カテゴリを選択
- 化粧品（一般化粧品）
- 薬用化粧品（医薬部外品）
- サプリメント・健康食品
- 美容機器・健康器具 など

### 2. 文章の種類を選択
- キャッチコピー
- LP見出し・タイトル
- 商品説明文
- お客様の声

### 3. チェックしたい文章を入力
最大500文字まで入力可能

### 4. チェック開始
AIが薬機法リスクを分析し、以下を表示：

#### 📊 分析結果
- **総合リスクレベル**: 高・中・低の3段階評価
- **問題箇所のハイライト**: リスクのある表現を色分け表示
- **詳細な指摘事項**: 各問題の理由と改善提案

#### ✨ 3つのリライト案
1. **保守的版**: 最も安全で確実な表現
2. **バランス版**: 安全性と訴求力のバランス
3. **訴求力重視版**: 法的リスクを最小限に訴求力を最大化

## 🔧 技術仕様

### バックエンド
- **言語**: Python 3.8+
- **フレームワーク**: Flask 2.3.3
- **AI**: Anthropic Claude API
- **認証**: APIキー認証システム
- **データ**: 薬機法NG表現データベース

### フロントエンド
- **言語**: Vanilla JavaScript (ES6+)
- **UI**: レスポンシブデザイン対応
- **通信**: Fetch API（ストリーミング対応）
- **セキュリティ**: CSP、XSS対策

## 📦 インストール方法

### 前提条件
- Python 3.8以上
- Claude APIキー（[Anthropic Console](https://console.anthropic.com/)で取得）

### セットアップ手順

1. **リポジトリのクローン**
```bash
git clone https://github.com/seripoyo/yakki-checker.git
cd yakki-checker
```

2. **バックエンドのセットアップ**
```bash
cd yakki-checker/setting/backend
pip install -r requirements.txt
```

3. **環境変数の設定**
`.env`ファイルを作成：
```env
CLAUDE_API_KEY=your_claude_api_key_here
VALID_API_KEYS=your_access_key_here
DEBUG=True
```

4. **サーバーの起動**

バックエンド（ターミナル1）:
```bash
cd yakki-checker/setting/backend
python3 app.py
```

フロントエンド（ターミナル2）:
```bash
cd yakki-checker
python3 -m http.server 8000
```

5. **アクセス**
ブラウザで http://localhost:8000 を開く

## 🌐 デプロイメント

### 推奨構成
- **フロントエンド**: GitHub Pages
- **バックエンド**: Render.com / Xserver

詳細は[デプロイメントガイド](doc/DEPLOYMENT.md)を参照

## 🔒 セキュリティ機能

- ✅ APIキー認証（SHA256ハッシュ化）
- ✅ レート制限（100リクエスト/時間/IP）
- ✅ CORS制限
- ✅ XSS対策（入力サニタイゼーション）
- ✅ セキュリティヘッダー設定

詳細は[セキュリティガイド](doc/SECURITY.md)を参照

## 📋 使用例

### 化粧品のキャッチコピー
**入力例**: 
```
シミが消える！医学的に証明された美白成分配合
```

**AIの指摘**:
- 🚨「シミが消える」→ 医薬品的効果（高リスク）
- ⚠️「医学的に証明」→ 効果の保証表現（中リスク）

**リライト案（バランス版）**:
```
透明感のある明るい印象へ。美白有効成分配合
※医薬部外品
```

## ⚠️ 免責事項

本ツールはあくまで参考情報の提供を目的としています。最終的な広告表現の判断は、必ず法務・薬事担当者または専門家にご相談ください。

## 📞 サポート

- **Issues**: [GitHub Issues](https://github.com/seripoyo/yakki-checker/issues)
- **ドキュメント**: [Wiki](https://github.com/seripoyo/yakki-checker/wiki)

## 📄 ライセンス

本プロジェクトは独自ライセンスです。商用利用についてはお問い合わせください。

---

**最終更新**: 2025年7月29日  
**バージョン**: v2.1.0  
**開発者**: [@seripoyo](https://github.com/seripoyo)