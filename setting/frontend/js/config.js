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
    PROGRESS_LOG_THRESHOLD: 5 // 5%以上変化でログ出力
};

// 環境に応じてAPIのURLを自動選択
const getApiUrl = () => {
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
        return API_CONFIG.DEV_BACKEND_URL;
    }
    return API_CONFIG.BACKEND_URL;
};