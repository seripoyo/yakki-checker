/**
 * 薬機法リスクチェッカー API通信モジュール
 * バックエンドとの通信を専門に扱うモジュール
 */

class YakkiApiClient {
    constructor(baseUrl = null, apiKey = null) {
        // config.jsで定義されたgetApiUrl関数を使用
        this.baseUrl = baseUrl || getApiUrl();
        this.timeout = API_CONFIG.API_TIMEOUT || 120000;
        this.apiKey = apiKey || this.getApiKeyFromStorage();
        this.requestCount = 0;
        this.lastRequestTime = 0;
        this.minRequestInterval = 1000; // 最小リクエスト間隔（ミリ秒）- 開発環境用に緩和
        this.serverStatus = 'unknown'; // 'online', 'sleeping', 'unknown'
    }

    /**
     * API キーをローカルストレージから取得
     * @returns {string|null} APIキー
     */
    getApiKeyFromStorage() {
        // 開発環境でのみローカルストレージから取得
        if (window.location.hostname === 'localhost') {
            // 古いキーをクリア
            const storedKey = localStorage.getItem('yakki_api_key');
            if (storedKey === 'demo_key_for_development_only') {
                localStorage.removeItem('yakki_api_key');
            }
            
            // 新しいAPIキーを設定・返却
            const newApiKey = 'Mfe43kjAWKxa8sDSAn64450dKAX261UJg2XV3bCer-8';
            localStorage.setItem('yakki_api_key', newApiKey);
            return newApiKey;
        }
        return null;
    }

    /**
     * API キーを設定
     * @param {string} apiKey - APIキー
     */
    setApiKey(apiKey) {
        this.apiKey = apiKey;
        // 開発環境でのみローカルストレージに保存
        if (window.location.hostname === 'localhost') {
            localStorage.setItem('yakki_api_key', apiKey);
        }
        console.log('API キーが設定されました');
    }

    /**
     * リクエスト制限チェック
     */
    checkRateLimit() {
        const now = Date.now();
        // 開発環境ではレート制限を無効化
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            this.lastRequestTime = now;
            this.requestCount++;
            return; // 開発環境ではチェックをスキップ
        }
        
        if (now - this.lastRequestTime < this.minRequestInterval) {
            throw new Error('リクエストが頻繁すぎます。少し時間をおいてから再試行してください。');
        }
        this.lastRequestTime = now;
        this.requestCount++;
    }

    /**
     * セキュアなヘッダーを生成
     * @returns {Object} HTTPヘッダー
     */
    getSecureHeaders() {
        const headers = {
            'Content-Type': 'application/json',
        };

        // APIキーがある場合は追加
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }

        return headers;
    }

    /**
     * 入力値のサニタイゼーション
     * @param {string} text - サニタイズするテキスト
     * @returns {string} サニタイズされたテキスト
     */
    sanitizeInput(text) {
        if (typeof text !== 'string') {
            return '';
        }
        
        // HTML特殊文字のエスケープ
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            .replace(/\//g, '&#x2F;')
            .trim();
    }

    /**
     * サーバー起動チェック（本番環境用）
     * @returns {Promise<boolean>} サーバーがオンラインかどうか
     */
    async wakeUpServer() {
        console.log('🌟 サーバー起動チェック開始...');
        
        // 本番環境でない場合はスキップ
        if (window.location.hostname === 'localhost') {
            this.serverStatus = 'online';
            return true;
        }
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.HEALTH_CHECK_TIMEOUT);
            
            const response = await fetch(`${this.baseUrl}/`, {
                method: 'GET',
                signal: controller.signal,
                headers: {
                    'Cache-Control': 'no-cache'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                console.log('✅ サーバーはオンラインです');
                this.serverStatus = 'online';
                return true;
            } else {
                console.log('⚠️ サーバーレスポンスが異常:', response.status);
                this.serverStatus = 'unknown';
                return false;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('⏰ サーバー起動中... 少し時間がかかります');
                this.serverStatus = 'sleeping';
            } else {
                console.log('❌ サーバー接続エラー:', error.message);
                this.serverStatus = 'unknown';
            }
            return false;
        }
    }

    /**
     * リトライ機能付きAPIコール
     * @param {Function} apiCall - API呼び出し関数
     * @param {string} operationName - 操作名（ログ用）
     * @param {Function} progressCallback - 進捗報告用コールバック
     * @returns {Promise} API結果
     */
    async callWithRetry(apiCall, operationName = 'API呼び出し', progressCallback = null) {
        let lastError;
        
        for (let attempt = 1; attempt <= API_CONFIG.MAX_RETRIES; attempt++) {
            try {
                console.log(`🔄 ${operationName} - 試行 ${attempt}/${API_CONFIG.MAX_RETRIES}`);
                
                // 最初の試行前にサーバー起動チェック
                if (attempt === 1 && this.serverStatus !== 'online') {
                    if (progressCallback) progressCallback({
                        stage: 'preparing',
                        progress: 2,
                        message: 'サーバーの状態を確認中...'
                    });
                    
                    const isOnline = await this.wakeUpServer();
                    if (!isOnline && this.serverStatus === 'sleeping') {
                        // サーバーがスリープ中の場合、起動を待つ
                        console.log('😴 サーバーが起動中です。しばらくお待ちください...');
                        
                        if (progressCallback) progressCallback({
                            stage: 'preparing',
                            progress: 5,
                            message: 'サーバーを起動中...'
                        });
                        
                        await this.delay(5000); // 5秒待機
                    }
                }
                
                const result = await apiCall();
                console.log(`✅ ${operationName} 成功 (試行 ${attempt})`);
                this.serverStatus = 'online';
                return result;
                
            } catch (error) {
                lastError = error;
                console.log(`❌ ${operationName} 失敗 (試行 ${attempt}):`, error.message);
                
                // 最後の試行でない場合は待機
                if (attempt < API_CONFIG.MAX_RETRIES) {
                    const delay = API_CONFIG.RETRY_DELAY * attempt; // 指数バックオフ
                    console.log(`⏳ ${delay}ms 待機してリトライします...`);
                    
                    if (progressCallback) progressCallback({
                        stage: 'preparing',
                        progress: Math.max(1, (attempt / API_CONFIG.MAX_RETRIES) * 10),
                        message: `接続に失敗しました。${Math.floor(delay / 1000)}秒後にリトライします...`
                    });
                    
                    await this.delay(delay);
                }
            }
        }
        
        // 全ての試行が失敗した場合
        console.error(`💥 ${operationName} 最終的に失敗:`, lastError);
        throw lastError;
    }
    
    /**
     * 遅延実行用のユーティリティ
     * @param {number} ms - 待機時間（ミリ秒）
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * APIヘルスチェック
     * @returns {Promise<Object>} ヘルスチェック結果
     */
    async healthCheck() {
        try {
            console.log('API ヘルスチェック開始');
            const response = await this.fetchWithTimeout(`${this.baseUrl}/`);
            const data = await response.json();
            console.log('API ヘルスチェック成功:', data);
            this.serverStatus = 'online';
            return data;
        } catch (error) {
            console.error('API ヘルスチェック失敗:', error);
            this.serverStatus = 'unknown';
            throw error;
        }
    }

    /**
     * 薬機法チェック API呼び出し
     * @param {string} text - チェックしたい文章
     * @param {string} category - 商品カテゴリ
     * @param {string} type - 文章の種類
     * @param {string} specialPoints - 特に訴求したいポイント（オプション）
     * @param {Function} progressCallback - 進捗報告用コールバック
     * @returns {Promise<Object>} チェック結果
     */
    async checkText(text, category, type, specialPoints = '', progressCallback = null) {
        // リトライ機能付きでAPIコールを実行
        return await this.callWithRetry(async () => {
            console.log('🔍 薬機法チェック API呼び出し開始');
            
            // 進捗報告: 準備段階
            if (progressCallback) progressCallback({
                stage: 'preparing',
                progress: 5,
                message: 'リクエストを準備中...'
            });
            
            // レート制限チェック
            this.checkRateLimit();
            
            // 入力値のサニタイゼーション
            const sanitizedText = this.sanitizeInput(text);
            const sanitizedCategory = this.sanitizeInput(category);
            const sanitizedType = this.sanitizeInput(type);
            const sanitizedSpecialPoints = this.sanitizeInput(specialPoints);
            
            // 進捗報告: データ準備完了
            if (progressCallback) progressCallback({
                stage: 'validating',
                progress: 10,
                message: 'データを検証中...'
            });
            
            console.log('📋 入力データ:', { 
                text: sanitizedText.substring(0, 50) + '...', 
                category: sanitizedCategory, 
                type: sanitizedType,
                specialPoints: sanitizedSpecialPoints ? sanitizedSpecialPoints.substring(0, 30) + '...' : '(なし)'
            });
            console.log('🌐 API URL:', `${this.baseUrl}/api/check`);
            
            // リクエストボディの構築
            const requestBody = {
                text: sanitizedText,
                category: sanitizedCategory,
                type: sanitizedType
            };
            
            // 特に訴求したいポイントが入力されている場合のみ追加
            if (sanitizedSpecialPoints && sanitizedSpecialPoints.trim()) {
                requestBody.special_points = sanitizedSpecialPoints;
            }
            console.log('📦 リクエストボディ:', requestBody);

            // バリデーション
            console.log('✅ リクエストバリデーション実行中...');
            this.validateCheckRequest(requestBody);
            console.log('✅ リクエストバリデーション完了');

            // 進捗報告: サーバーへ送信中
            if (progressCallback) progressCallback({
                stage: 'sending',
                progress: 20,
                message: 'サーバーへリクエストを送信中...'
            });

            // API呼び出し（進捗付き）
            console.log('📡 fetchWithTimeout開始...');
            const response = await this.fetchWithTimeoutProgress(`${this.baseUrl}/api/check`, {
                method: 'POST',
                headers: this.getSecureHeaders(),
                body: JSON.stringify(requestBody)
            }, progressCallback);
            console.log('📡 fetchWithTimeout完了、レスポンス受信:', response.status);

            // 進捗報告: レスポンス処理中
            if (progressCallback) progressCallback({
                stage: 'processing',
                progress: 90,
                message: 'レスポンスを処理中...'
            });

            // レスポンス処理
            console.log('📄 JSONパース開始...');
            const data = await response.json();
            console.log('📄 JSONパース完了:', data);
            
            // レスポンスバリデーション
            console.log('✅ レスポンスバリデーション実行中...');
            this.validateCheckResponse(data);
            console.log('✅ レスポンスバリデーション完了');
            
            // 進捗報告: 完了
            if (progressCallback) progressCallback({
                stage: 'completed',
                progress: 100,
                message: 'チェック完了！'
            });
            
            console.log('🎉 薬機法チェック API呼び出し成功');
            return data;

        }, '薬機法チェック', progressCallback);
    }

    /**
     * 薬機法ガイド取得 API呼び出し
     * @returns {Promise<Object>} ガイドデータ
     */
    async getGuide() {
        try {
            console.log('薬機法ガイド API呼び出し開始');
            
            const response = await this.fetchWithTimeout(`${this.baseUrl}/api/guide`);
            const data = await response.json();
            
            console.log('薬機法ガイド API呼び出し成功:', data);
            return data;
            
        } catch (error) {
            console.error('薬機法ガイド API呼び出し失敗:', error);
            throw this.enhanceError(error);
        }
    }

    /**
     * タイムアウト付きfetch
     * @param {string} url - リクエストURL
     * @param {Object} options - fetchオプション
     * @returns {Promise<Response>} fetch結果
     */
    async fetchWithTimeout(url, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort('Request timeout'), this.timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return response;
        } catch (error) {
            // AbortErrorの場合、より分かりやすいエラーメッセージを設定
            if (error.name === 'AbortError') {
                const timeoutError = new Error('Request timeout');
                timeoutError.name = 'AbortError';
                throw timeoutError;
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    /**
     * 進捗報告付きタイムアウト付きfetch
     * @param {string} url - リクエストURL
     * @param {Object} options - fetchオプション
     * @param {Function} progressCallback - 進捗報告用コールバック
     * @returns {Promise<Response>} fetch結果
     */
    async fetchWithTimeoutProgress(url, options = {}, progressCallback = null) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort('Request timeout'), this.timeout);

        // 進捗制御用の変数
        let currentProgress = 30;
        let progressStep = 0;
        const maxProgress = 80;
        // GitHub Pages環境かどうかを判定
        const isGitHubPages = window.location.hostname.includes('github.io');
        
        const progressSteps = isGitHubPages ? [
            { progress: 35, message: 'GitHub Pages → Renderサーバー接続中...' },
            { progress: 45, message: 'Renderサーバーが起動中です...' },
            { progress: 60, message: 'Claude APIで薬機法分析を実行中...' },
            { progress: 75, message: '修正案を3パターン生成中...' },
            { progress: 80, message: '分析結果をまとめています...' }
        ] : [
            { progress: 35, message: 'サーバーに接続中...' },
            { progress: 45, message: 'データをアップロード中...' },
            { progress: 60, message: 'Claude APIで分析中...' },
            { progress: 75, message: '結果を生成中...' },
            { progress: 80, message: 'レスポンスを準備中...' }
        ];

        // 進捗のスマートなシミュレーション（頻度制限付き）
        const progressInterval = setInterval(() => {
            if (progressCallback && progressStep < progressSteps.length) {
                const step = progressSteps[progressStep];
                progressCallback({
                    stage: 'uploading',
                    progress: step.progress,
                    message: step.message
                });
                progressStep++;
            }
        }, API_CONFIG.PROGRESS_UPDATE_INTERVAL); // 設定値を使用

        try {
            // 進捗報告: 送信開始
            if (progressCallback) progressCallback({
                stage: 'uploading',
                progress: 30,
                message: 'データを送信中...'
            });

            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            clearInterval(progressInterval);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // 進捗報告: 受信完了
            if (progressCallback) progressCallback({
                stage: 'receiving',
                progress: 85,
                message: 'レスポンスを受信中...'
            });

            return response;
        } catch (error) {
            clearInterval(progressInterval);
            
            // AbortErrorの場合、より分かりやすいエラーメッセージを設定
            if (error.name === 'AbortError') {
                const timeoutError = new Error('Request timeout');
                timeoutError.name = 'AbortError';
                throw timeoutError;
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
            clearInterval(progressInterval);
        }
    }

    /**
     * チェックリクエストのバリデーション
     * @param {Object} requestBody - リクエストボディ
     */
    validateCheckRequest(requestBody) {
        if (!requestBody.text || typeof requestBody.text !== 'string') {
            throw new Error('テキストが正しく指定されていません');
        }

        if (requestBody.text.length === 0) {
            throw new Error('テキストが空です');
        }

        if (requestBody.text.length > 500) {
            throw new Error('テキストが長すぎます（500文字以内）');
        }

        const validCategories = ['化粧品', '薬用化粧品', '医薬部外品', 'サプリメント', '美容機器・健康器具・その他'];
        if (!validCategories.includes(requestBody.category)) {
            throw new Error('商品カテゴリが正しく指定されていません');
        }

        const validTypes = ['キャッチコピー', 'LP見出し・タイトル', '商品説明文・広告文・通常テキスト', 'お客様の声'];
        if (!validTypes.includes(requestBody.type)) {
            throw new Error('文章の種類が正しく指定されていません');
        }
    }

    /**
     * チェックレスポンスのバリデーション
     * @param {Object} data - レスポンスデータ
     */
    validateCheckResponse(data) {
        // 必須フィールドの確認
        const requiredFields = ['overall_risk', 'risk_counts', 'issues'];
        for (const field of requiredFields) {
            if (!(field in data)) {
                throw new Error(`レスポンスに必須フィールド '${field}' がありません`);
            }
        }

        // overall_riskの確認
        const validRiskLevels = ['高', '中', '低'];
        if (!validRiskLevels.includes(data.overall_risk)) {
            throw new Error('総合リスクレベルが不正です');
        }

        // risk_countsの確認
        if (!data.risk_counts || typeof data.risk_counts !== 'object') {
            throw new Error('リスク件数データが不正です');
        }

        const requiredCountFields = ['total', 'high', 'medium', 'low'];
        for (const field of requiredCountFields) {
            if (typeof data.risk_counts[field] !== 'number' || data.risk_counts[field] < 0) {
                throw new Error(`リスク件数の '${field}' が不正です`);
            }
        }

        // issuesの確認
        if (!Array.isArray(data.issues)) {
            throw new Error('指摘事項データが不正です');
        }

        // 各指摘事項の確認
        for (const issue of data.issues) {
            if (!issue.fragment || !issue.reason || !issue.risk_level || !Array.isArray(issue.suggestions)) {
                throw new Error('指摘事項のデータ構造が不正です');
            }

            if (!validRiskLevels.includes(issue.risk_level)) {
                throw new Error('指摘事項のリスクレベルが不正です');
            }
        }

        // rewritten_textsの確認（新形式・旧形式両対応）
        if (data.rewritten_texts && typeof data.rewritten_texts === 'object') {
            const requiredVariations = ['conservative', 'balanced', 'appealing'];
            for (const variation of requiredVariations) {
                const variationData = data.rewritten_texts[variation];
                
                // 新形式（オブジェクト）の場合
                if (typeof variationData === 'object' && variationData !== null) {
                    if (typeof variationData.text !== 'string' || typeof variationData.explanation !== 'string') {
                        throw new Error(`修正版テキスト '${variation}' のオブジェクト形式が不正です`);
                    }
                }
                // 旧形式（文字列）の場合
                else if (typeof variationData !== 'string') {
                    throw new Error(`修正版テキスト '${variation}' が不正です`);
                }
            }
        }
        // 後方互換性：rewritten_textの確認（旧形式）
        else if (data.rewritten_text && typeof data.rewritten_text !== 'string') {
            throw new Error('修正版テキストが不正です');
        }
        // どちらも存在しない場合
        else if (!data.rewritten_texts && !data.rewritten_text) {
            throw new Error('修正版テキストが見つかりません');
        }
    }

    /**
     * エラー情報の拡張
     * @param {Error} error - 元のエラー
     * @returns {Error} 拡張されたエラー
     */
    enhanceError(error) {
        // AbortErrorや他の読み取り専用プロパティを持つエラーの場合、新しいErrorオブジェクトを作成
        let enhancedMessage = error.message || 'エラーが発生しました';
        
        if (error.name === 'AbortError') {
            enhancedMessage = 'リクエストがタイムアウトしました。ネットワーク接続を確認してください。';
        } else if (error.name === 'TypeError' && error.message && error.message.includes('fetch')) {
            enhancedMessage = 'サーバーに接続できません。バックエンドが起動しているか確認してください。';
        } else if (error.message && error.message.includes('HTTP 401')) {
            // 開発環境での認証失敗時の詳細メッセージ
            if (window.location.hostname === 'localhost') {
                enhancedMessage = 'APIキー認証に失敗しました。開発環境では自動的に "demo_key_for_development_only" が使用されます。バックエンドの.envファイルのVALID_API_KEYSを確認してください。';
            } else {
                enhancedMessage = 'APIキーが無効です。正しいAPIキーを設定してください。';
            }
        } else if (error.message && error.message.includes('HTTP 403')) {
            enhancedMessage = 'アクセスが拒否されました。権限を確認してください。';
        } else if (error.message && error.message.includes('HTTP 429')) {
            enhancedMessage = 'リクエスト制限に達しました。しばらく時間をおいてから再試行してください。';
        } else if (error.message && error.message.includes('HTTP 400')) {
            enhancedMessage = '送信データに問題があります。入力内容を確認してください。';
        } else if (error.message && error.message.includes('HTTP 404')) {
            enhancedMessage = 'APIエンドポイントが見つかりません。';
        } else if (error.message && error.message.includes('HTTP 500')) {
            enhancedMessage = 'サーバーエラーが発生しました。しばらく待ってから再試行してください。';
        }

        // メッセージが変更された場合、新しいErrorオブジェクトを作成
        if (enhancedMessage !== error.message) {
            const enhancedError = new Error(enhancedMessage);
            enhancedError.name = error.name;
            enhancedError.stack = error.stack;
            enhancedError.originalError = error;
            return enhancedError;
        }

        return error;
    }

    /**
     * 接続テスト
     * @returns {Promise<boolean>} 接続可能かどうか
     */
    async testConnection() {
        try {
            await this.healthCheck();
            return true;
        } catch (error) {
            console.warn('接続テスト失敗:', error.message);
            return false;
        }
    }

    /**
     * APIベースURLの設定
     * @param {string} baseUrl - 新しいベースURL
     */
    setBaseUrl(baseUrl) {
        this.baseUrl = baseUrl;
        console.log('API ベースURL変更:', baseUrl);
    }

    /**
     * タイムアウト時間の設定
     * @param {number} timeout - タイムアウト時間（ミリ秒）
     */
    setTimeout(timeout) {
        this.timeout = timeout;
        console.log('API タイムアウト変更:', timeout);
    }
}

// グローバルAPI クライアントインスタンス
window.yakkiApi = new YakkiApiClient();

// 開発環境での自動接続テスト（非同期で実行、エラーでも継続）
if (window.location.hostname === 'localhost') {
    setTimeout(() => {
        window.yakkiApi.testConnection().then(connected => {
            if (connected) {
                console.log('✅ バックエンドAPI接続確認済み');
            } else {
                console.warn('⚠️ バックエンドAPIに接続できません - 手動で確認してください');
            }
        }).catch(error => {
            console.warn('⚠️ API接続テスト中にエラー:', error.message);
        });
    }, 1000); // 1秒後に実行
}

console.log('薬機法リスクチェッカー api.js 読み込み完了');