/**
 * 薬機法リスクチェッカー API通信モジュール
 * バックエンドとの通信を専門に扱うモジュール
 */

class YakkiApiClient {
    constructor(baseUrl = 'http://localhost:5000') {
        this.baseUrl = baseUrl;
        this.timeout = 30000; // 30秒タイムアウト
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
     * @param {string} type - 文章の種類
     * @returns {Promise<Object>} チェック結果
     */
    async checkText(text, type) {
        try {
            console.log('薬機法チェック API呼び出し開始:', { text: text.substring(0, 50) + '...', type });
            
            // リクエストボディの構築
            const requestBody = {
                text: text.trim(),
                type: type
            };

            // バリデーション
            this.validateCheckRequest(requestBody);

            // API呼び出し
            const response = await this.fetchWithTimeout(`${this.baseUrl}/api/check`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            // レスポンス処理
            const data = await response.json();
            
            // レスポンスバリデーション
            this.validateCheckResponse(data);
            
            console.log('薬機法チェック API呼び出し成功');
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
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

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

        const validTypes = ['キャッチコピー', '商品説明文', 'お客様の声'];
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
        const requiredFields = ['overall_risk', 'risk_counts', 'issues', 'rewritten_text'];
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

        // rewritten_textの確認
        if (typeof data.rewritten_text !== 'string') {
            throw new Error('修正版テキストが不正です');
        }
    }

    /**
     * エラー情報の拡張
     * @param {Error} error - 元のエラー
     * @returns {Error} 拡張されたエラー
     */
    enhanceError(error) {
        if (error.name === 'AbortError') {
            error.message = 'リクエストがタイムアウトしました。ネットワーク接続を確認してください。';
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            error.message = 'サーバーに接続できません。バックエンドが起動しているか確認してください。';
        } else if (error.message.includes('HTTP 400')) {
            error.message = '送信データに問題があります。入力内容を確認してください。';
        } else if (error.message.includes('HTTP 404')) {
            error.message = 'APIエンドポイントが見つかりません。';
        } else if (error.message.includes('HTTP 500')) {
            error.message = 'サーバーエラーが発生しました。しばらく待ってから再試行してください。';
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