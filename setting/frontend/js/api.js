/**
 * 薬機法リスクチェッカー API通信モジュール
 * バックエンドとの通信を専門に扱うモジュール
 */

class YakkiApiClient {
    constructor(baseUrl = null, apiKey = null) {
        // config.jsで定義されたgetApiUrl関数を使用
        this.baseUrl = baseUrl || getApiUrl();
        this.timeout = API_CONFIG.API_TIMEOUT || 30000;
        this.apiKey = apiKey || this.getApiKeyFromStorage();
        this.requestCount = 0;
        this.lastRequestTime = 0;
        this.minRequestInterval = 100; // 最小リクエスト間隔（ミリ秒）
    }

    /**
     * API キーをローカルストレージから取得
     * @returns {string|null} APIキー
     */
    getApiKeyFromStorage() {
        // 開発環境でのみローカルストレージから取得
        if (window.location.hostname === 'localhost') {
            const storedKey = localStorage.getItem('yakki_api_key');
            if (storedKey && storedKey !== 'demo_key_for_development_only') {
                return storedKey;
            }
            // .envファイルのVALID_API_KEYSと一致するキーを返す
            return 'demo_key_for_development_only';
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
     * APIヘルスチェック
     * @returns {Promise<Object>} ヘルスチェック結果
     */
    async healthCheck() {
        try {
            console.log('API ヘルスチェック開始');
            const response = await this.fetchWithTimeout(`${this.baseUrl}/`);
            const data = await response.json();
            console.log('API ヘルスチェック成功:', data);
            return data;
        } catch (error) {
            console.error('API ヘルスチェック失敗:', error);
            throw error;
        }
    }

    /**
     * 薬機法チェック API呼び出し
     * @param {string} text - チェックしたい文章
     * @param {string} category - 商品カテゴリ
     * @param {string} type - 文章の種類
     * @param {string} specialPoints - 特に訴求したいポイント（オプション）
     * @returns {Promise<Object>} チェック結果
     */
    async checkText(text, category, type, specialPoints = '') {
        try {
            console.log('🔍 薬機法チェック API呼び出し開始');
            
            // レート制限チェック
            this.checkRateLimit();
            
            // 入力値のサニタイゼーション
            const sanitizedText = this.sanitizeInput(text);
            const sanitizedCategory = this.sanitizeInput(category);
            const sanitizedType = this.sanitizeInput(type);
            const sanitizedSpecialPoints = this.sanitizeInput(specialPoints);
            
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

            // API呼び出し
            console.log('📡 fetchWithTimeout開始...');
            const response = await this.fetchWithTimeout(`${this.baseUrl}/api/check`, {
                method: 'POST',
                headers: this.getSecureHeaders(),
                body: JSON.stringify(requestBody)
            });
            console.log('📡 fetchWithTimeout完了、レスポンス受信:', response.status);

            // レスポンス処理
            console.log('📄 JSONパース開始...');
            const data = await response.json();
            console.log('📄 JSONパース完了:', data);
            
            // レスポンスバリデーション
            console.log('✅ レスポンスバリデーション実行中...');
            this.validateCheckResponse(data);
            console.log('✅ レスポンスバリデーション完了');
            
            console.log('🎉 薬機法チェック API呼び出し成功');
            return data;

        } catch (error) {
            console.error('薬機法チェック API呼び出し失敗:', error);
            throw this.enhanceError(error);
        }
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
        } finally {
            clearTimeout(timeoutId);
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
        let enhancedMessage = error.message;
        
        if (error.name === 'AbortError') {
            enhancedMessage = 'リクエストがタイムアウトしました。ネットワーク接続を確認してください。';
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            enhancedMessage = 'サーバーに接続できません。バックエンドが起動しているか確認してください。';
        } else if (error.message.includes('HTTP 401')) {
            // 開発環境での認証失敗時の詳細メッセージ
            if (window.location.hostname === 'localhost') {
                enhancedMessage = 'APIキー認証に失敗しました。開発環境では自動的に "demo_key_for_development_only" が使用されます。バックエンドの.envファイルのVALID_API_KEYSを確認してください。';
            } else {
                enhancedMessage = 'APIキーが無効です。正しいAPIキーを設定してください。';
            }
        } else if (error.message.includes('HTTP 403')) {
            enhancedMessage = 'アクセスが拒否されました。権限を確認してください。';
        } else if (error.message.includes('HTTP 429')) {
            enhancedMessage = 'リクエスト制限に達しました。しばらく時間をおいてから再試行してください。';
        } else if (error.message.includes('HTTP 400')) {
            enhancedMessage = '送信データに問題があります。入力内容を確認してください。';
        } else if (error.message.includes('HTTP 404')) {
            enhancedMessage = 'APIエンドポイントが見つかりません。';
        } else if (error.message.includes('HTTP 500')) {
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