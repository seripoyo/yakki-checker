/**
 * 薬機法リスクチェッカー 設定ファイル
 * APIのエンドポイントなどの環境設定を管理
 */

const API_CONFIG = {
    // 本番環境のAPI URL
    BACKEND_URL: 'https://yakki-checker.onrender.com',
    
    // 開発環境のAPI URL
    DEV_BACKEND_URL: 'http://localhost:5000',
    
    // タイムアウト設定（ミリ秒）
    API_TIMEOUT: 180000, // 180秒（GitHub Pages + Renderの組み合わせ対応）
    
    // リトライ設定
    MAX_RETRIES: 2, // リトライ回数を削減してユーザー待機時間を短縮
    RETRY_DELAY: 3000, // 3秒（サーバー起動時間を考慮）
    
    // ヘルスチェックの設定
    HEALTH_CHECK_TIMEOUT: 45000, // 45秒（Render起動時間を考慮）
    
    // 進捗更新設定
    PROGRESS_UPDATE_INTERVAL: 3000, // 3秒間隔
    PROGRESS_LOG_THRESHOLD: 5, // 5%以上変化でログ出力
    
    // APIキー設定（環境変数から取得することを推奨）
    // 本番環境ではサーバーサイドで管理し、クライアントには露出しない
    API_KEY_PLACEHOLDER: 'YOUR_API_KEY_HERE' // プレースホルダー
};

// 環境に応じてAPIのURLを自動選択
const getApiUrl = () => {
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
        return API_CONFIG.DEV_BACKEND_URL;
    }
    return API_CONFIG.BACKEND_URL;
};

// APIキーの取得（セキュア版）
// 本番環境では環境変数やサーバーサイドから取得すべき
const getApiKey = () => {
    // 環境変数から取得を試みる（ビルド時に設定）
    if (typeof process !== 'undefined' && process.env && process.env.YAKKI_API_KEY) {
        return process.env.YAKKI_API_KEY;
    }
    
    // セッションストレージから取得（一時的な保存）
    const sessionKey = sessionStorage.getItem('yakki_api_key_temp');
    if (sessionKey) {
        return sessionKey;
    }
    
    // 開発環境の場合は警告を表示
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.warn('⚠️ APIキーが設定されていません。管理者に確認してください。');
        // 開発用の一時的なキーを返す（本番では使用しない）
        return 'dev_temp_key_' + Date.now();
    }
    
    return null;
};