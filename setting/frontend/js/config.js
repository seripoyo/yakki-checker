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
    API_KEY_PLACEHOLDER: 'YOUR_API_KEY_HERE', // プレースホルダー
    
    // デバッグモード設定
    // URLパラメータ ?debug=true で一時的に有効化可能
    DEBUG_MODE: false
};

// 環境に応じてAPIのURLを自動選択
const getApiUrl = () => {
    // ローカル環境では開発用APIを使用
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
        // 初回のみログ出力（デバッグモード設定前なので直接制御）
        if (!window._apiUrlLogged) {
            console.log('🔧 開発環境を検出 - ローカルAPIを使用:', API_CONFIG.DEV_BACKEND_URL);
            window._apiUrlLogged = true;
        }
        return API_CONFIG.DEV_BACKEND_URL;
    }
    // 初回のみログ出力
    if (!window._apiUrlLogged) {
        console.log('🌐 本番環境を検出 - RenderAPIを使用:', API_CONFIG.BACKEND_URL);
        window._apiUrlLogged = true;
    }
    return API_CONFIG.BACKEND_URL;
};

// デバッグモードの判定
const isDebugMode = () => {
    // URLパラメータでデバッグモードを確認
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('debug') === 'true') {
        return true;
    }
    
    // ローカル環境の場合は自動的にデバッグモード
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
        // ローカルでもdebug=falseで無効化可能
        return urlParams.get('debug') !== 'false';
    }
    
    return API_CONFIG.DEBUG_MODE;
};

// デバッグログ出力ユーティリティ
const debugLog = (message, ...args) => {
    if (isDebugMode()) {
        console.log(message, ...args);
    }
};

const debugError = (message, ...args) => {
    // エラーは常に出力（本番環境でも重要）
    console.error(message, ...args);
};

const debugWarn = (message, ...args) => {
    if (isDebugMode()) {
        console.warn(message, ...args);
    }
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
    
    // 開発環境でも本番環境と同じAPIキーを使用
    // 本番環境のAPIキー（統一使用）
    const apiKey = 'Mfe43kjAWKxa8sDSAn64450dKAX261UJg2XV3bCer-8';
    // APIキー設定のログは初回のみ
    if (!window._apiKeyLogged) {
        console.log('🔑 APIキー設定済み');
        window._apiKeyLogged = true;
    }
    return apiKey;
    
    return null;
};