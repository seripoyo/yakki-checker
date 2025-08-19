/**
 * セキュリティユーティリティモジュール
 * 入力検証、サニタイゼーション、XSS対策を提供
 */

class SecurityUtils {
    /**
     * HTMLエスケープ処理
     * @param {string} str - エスケープする文字列
     * @returns {string} エスケープ済み文字列
     */
    static escapeHtml(str) {
        if (typeof str !== 'string') return '';
        
        const escapeMap = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
            '/': '&#x2F;',
            '`': '&#x60;',
            '=': '&#x3D;'
        };
        
        return str.replace(/[&<>"'`=\/]/g, char => escapeMap[char]);
    }

    /**
     * 危険なパターンの検出と除去
     * @param {string} input - 検証する入力文字列
     * @returns {object} 検証結果 {isClean: boolean, cleanedValue: string, removedPatterns: array}
     */
    static sanitizeInput(input) {
        if (typeof input !== 'string') {
            return { isClean: true, cleanedValue: '', removedPatterns: [] };
        }

        const dangerousPatterns = [
            // HTMLタグの検出（より厳密）
            { pattern: /<script[^>]*>[\s\S]*?<\/script>/gi, name: 'script tag' },
            { pattern: /<iframe[^>]*>[\s\S]*?<\/iframe>/gi, name: 'iframe tag' },
            { pattern: /<object[^>]*>[\s\S]*?<\/object>/gi, name: 'object tag' },
            { pattern: /<embed[^>]*>/gi, name: 'embed tag' },
            { pattern: /<applet[^>]*>[\s\S]*?<\/applet>/gi, name: 'applet tag' },
            { pattern: /<meta[^>]*>/gi, name: 'meta tag' },
            { pattern: /<link[^>]*>/gi, name: 'link tag' },
            { pattern: /<style[^>]*>[\s\S]*?<\/style>/gi, name: 'style tag' },
            
            // JavaScriptプロトコル
            { pattern: /javascript:/gi, name: 'javascript protocol' },
            { pattern: /vbscript:/gi, name: 'vbscript protocol' },
            { pattern: /data:text\/html/gi, name: 'data URI scheme' },
            
            // イベントハンドラ
            { pattern: /on\w+\s*=\s*["'][^"']*["']/gi, name: 'event handler' },
            { pattern: /on\w+\s*=\s*[^\s>]*/gi, name: 'unquoted event handler' },
            
            // 危険な属性
            { pattern: /srcdoc\s*=/gi, name: 'srcdoc attribute' },
            { pattern: /formaction\s*=/gi, name: 'formaction attribute' },
            
            // SQLインジェクション基本パターン
            { pattern: /(\bor\b|\band\b)\s+\d+\s*=\s*\d+/gi, name: 'SQL injection pattern' },
            { pattern: /['"];\s*(drop|delete|truncate|update|insert)/gi, name: 'SQL command injection' },
            
            // コマンドインジェクション
            { pattern: /[;&|`$()]/g, name: 'command injection characters' }
        ];

        let cleanedValue = input;
        const removedPatterns = [];
        let isClean = true;

        dangerousPatterns.forEach(({ pattern, name }) => {
            if (pattern.test(cleanedValue)) {
                cleanedValue = cleanedValue.replace(pattern, '');
                removedPatterns.push(name);
                isClean = false;
                
                // パターンをリセット（グローバルフラグのため）
                pattern.lastIndex = 0;
            }
        });

        return {
            isClean,
            cleanedValue,
            removedPatterns
        };
    }

    /**
     * 入力値の長さ検証
     * @param {string} input - 検証する文字列
     * @param {number} maxLength - 最大文字数
     * @returns {object} 検証結果 {isValid: boolean, truncated: string}
     */
    static validateLength(input, maxLength = 500) {
        if (typeof input !== 'string') {
            return { isValid: false, truncated: '' };
        }

        const trimmedInput = input.trim();
        
        if (trimmedInput.length === 0) {
            return { isValid: false, truncated: trimmedInput };
        }

        if (trimmedInput.length > maxLength) {
            return {
                isValid: false,
                truncated: trimmedInput.substring(0, maxLength)
            };
        }

        return {
            isValid: true,
            truncated: trimmedInput
        };
    }

    /**
     * 薬機法チェック用の入力検証（総合）
     * @param {string} input - 検証する文字列
     * @param {object} options - オプション
     * @returns {object} 検証結果
     */
    static validateYakkiInput(input, options = {}) {
        const {
            maxLength = 500,
            allowHtml = false,
            strict = true
        } = options;

        const result = {
            isValid: true,
            cleanedValue: input,
            errors: [],
            warnings: []
        };

        // 空文字チェック
        if (!input || input.trim().length === 0) {
            result.isValid = false;
            result.errors.push('テキストを入力してください');
            return result;
        }

        // サニタイゼーション
        const sanitized = this.sanitizeInput(input);
        if (!sanitized.isClean) {
            result.cleanedValue = sanitized.cleanedValue;
            result.warnings.push(`セキュリティ上の理由により、以下のパターンが削除されました: ${sanitized.removedPatterns.join(', ')}`);
            
            if (strict) {
                result.isValid = false;
                result.errors.push('不正な文字列が含まれています');
            }
        }

        // 長さ検証
        const lengthValidation = this.validateLength(result.cleanedValue, maxLength);
        if (!lengthValidation.isValid) {
            if (lengthValidation.truncated.length === 0) {
                result.isValid = false;
                result.errors.push('有効なテキストを入力してください');
            } else {
                result.cleanedValue = lengthValidation.truncated;
                result.warnings.push(`文字数制限（${maxLength}文字）を超えたため、切り詰められました`);
            }
        }

        // HTMLタグの検出（allowHtmlがfalseの場合）
        if (!allowHtml && /<[^>]+>/.test(result.cleanedValue)) {
            result.isValid = false;
            result.errors.push('HTMLタグは使用できません');
        }

        // 絵文字や特殊文字の過度な使用をチェック
        const emojiCount = (result.cleanedValue.match(/[\u{1F300}-\u{1F9FF}]/gu) || []).length;
        if (emojiCount > 10) {
            result.warnings.push('絵文字の使用が多すぎる可能性があります');
        }

        return result;
    }

    /**
     * CSRFトークンの生成
     * @returns {string} CSRFトークン
     */
    static generateCSRFToken() {
        const array = new Uint8Array(32);
        crypto.getRandomValues(array);
        return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    }

    /**
     * セッションの有効性チェック
     * @returns {boolean} セッションが有効かどうか
     */
    static isSessionValid() {
        const sessionExpiry = sessionStorage.getItem('session_expiry');
        if (!sessionExpiry) return false;
        
        return new Date().getTime() < parseInt(sessionExpiry);
    }

    /**
     * セッションの更新
     * @param {number} expiryMinutes - セッション有効期限（分）
     */
    static updateSession(expiryMinutes = 30) {
        const expiryTime = new Date().getTime() + (expiryMinutes * 60 * 1000);
        sessionStorage.setItem('session_expiry', expiryTime.toString());
    }
}

// グローバルスコープにエクスポート
window.SecurityUtils = SecurityUtils;