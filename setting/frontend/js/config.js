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
    API_TIMEOUT: 60000 // 60秒（Claude APIの応答が遅い場合があるため）
};

// 環境に応じてAPIのURLを自動選択
const getApiUrl = () => {
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
        return API_CONFIG.DEV_BACKEND_URL;
    }
    return API_CONFIG.BACKEND_URL;
};