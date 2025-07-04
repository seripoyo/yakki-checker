# 薬機法リスクチェッカー フロントエンド

薬機法リスクチェッカーのユーザーインターフェース

## 🎨 デザイン仕様

### カラーパレット
- **プライマリ**: `#2563eb` (青)
- **成功**: `#10b981` (緑)
- **警告**: `#f59e0b` (オレンジ)
- **危険**: `#ef4444` (赤)
- **グレー**: `#64748b` 系統

### リスクレベルカラー
- **高リスク**: 赤 (`#ef4444`)
- **中リスク**: オレンジ (`#f59e0b`)
- **低リスク**: 緑 (`#10b981`)

## 🏗️ ファイル構成

```
frontend/
├── index.html              # メインHTMLファイル
├── css/
│   ├── style.css           # メインスタイルシート
│   └── components.css      # コンポーネント別スタイル
├── js/
│   ├── script.js           # メインJavaScript（未実装）
│   ├── api.js              # API通信処理（未実装）
│   └── ui.js               # UI操作・表示制御（未実装）
└── assets/
    └── images/             # 画像ファイル
```

## 📱 画面構成

### 1. ヘッダー
- アプリタイトル「薬機法リスクチェッカー」
- サブタイトル「化粧品・コスメ広告の薬機法適合性チェックツール」
- グラデーション背景

### 2. タブナビゲーション
- **リスクチェッカータブ**: メイン機能
- **薬機法簡単ガイドタブ**: 解説コンテンツ

### 3. リスクチェッカー画面
#### 入力エリア
- 文章種類選択（キャッチコピー/商品説明文/お客様の声）
- テキスト入力エリア（500文字制限）
- 文字数カウンター
- チェック開始ボタン／クリアボタン

#### 結果表示エリア
- **総合リスクレベル**: 大きなバッジ表示
- **リスク件数サマリー**: グリッド形式
- **詳細結果**: 2カラム表示
  - 左: ハイライト付き入力文
  - 右: 指摘事項リスト
- **修正版テキスト**: リライト結果

### 4. 薬機法簡単ガイド画面
- 薬機法の基本説明
- NG表現例（❌マーク付き）
- OK表現例（✅マーク付き）
- チェックポイント

### 5. フッター
- 免責事項
- 専門家相談リンクボタン
- バージョン情報

## 🎯 主要な要素ID

### フォーム要素
- `text-type`: 文章種類選択
- `text-input`: テキスト入力エリア
- `check-button`: チェック開始ボタン
- `clear-button`: クリアボタン
- `char-count`: 文字数表示

### 表示エリア
- `loading-spinner`: ローディング表示
- `result-area`: 結果表示エリア全体
- `overall-risk`: 総合リスクレベル
- `risk-badge`: リスクバッジ
- `risk-level-text`: リスクレベルテキスト

### リスク件数
- `total-count`: 総検出数
- `high-count`: 高リスク件数
- `medium-count`: 中リスク件数
- `low-count`: 低リスク件数

### 詳細結果
- `highlighted-text`: ハイライト表示エリア
- `issues-list`: 指摘事項リスト
- `rewritten-text`: 修正版テキスト

### タブ制御
- `tab-checker`: チェッカータブボタン
- `tab-guide`: ガイドタブボタン
- `checker-content`: チェッカーコンテンツ
- `guide-content`: ガイドコンテンツ

## 🎨 スタイリング特徴

### レスポンシブデザイン
- モバイルファースト設計
- 768px以下でレイアウト調整
- フレキシブルグリッドシステム

### アニメーション
- フェードイン効果
- ホバーエフェクト
- ローディングスピナー
- スムーズなトランジション

### アクセシビリティ
- セマンティックHTML
- 適切なカラーコントラスト
- キーボードナビゲーション対応
- スクリーンリーダー対応

## 🚀 起動方法

```bash
# HTTPサーバーで起動（Python使用例）
cd frontend
python -m http.server 8080

# または Live Server 等のVSCode拡張機能を使用
```

ブラウザで `http://localhost:8080` にアクセス

## 📝 注意事項

- 現在はスタイルとレイアウトのみ実装
- JavaScript機能は未実装（次のステップで実装予定）
- バックエンドAPIとの連携は未実装