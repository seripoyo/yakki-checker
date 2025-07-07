/**
 * 薬機法リスクチェッカー 設定ファイル
 * APIのエンドポイントなどの環境設定を管理
 */

const API_CONFIG = {
    // 本番環境のAPI URL（デプロイ後に更新してください）
    // 例: 'https://your-app-name.onrender.com'
    // 例: 'https://your-app-name.herokuapp.com'
    BACKEND_URL: 'https://your-backend-url.onrender.com',
    
    // 開発環境のAPI URL
    DEV_BACKEND_URL: 'http://localhost:5000',
    
    // タイムアウト設定（ミリ秒）
    API_TIMEOUT: 30000
};

// 環境に応じてAPIのURLを自動選択
const getApiUrl = () => {
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
        return API_CONFIG.DEV_BACKEND_URL;
    }
    return API_CONFIG.BACKEND_URL;
};