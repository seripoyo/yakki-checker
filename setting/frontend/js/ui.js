/**
 * 薬機法リスクチェッカー UI制御モジュール
 * ユーザーインターフェースの動的操作とアニメーション制御
 */

class YakkiUIController {
    constructor() {
        this.animationDuration = 300;
        this.scrollOffset = 80;
        this.messageTimeout = 3000;
        this.pulseAnimationClass = 'pulse-animation';
        
        // アニメーションキューの管理
        this.animationQueue = [];
        this.isAnimating = false;
    }

    /**
     * 初期化
     */
    init() {
        console.log('UI Controller 初期化開始');
        this.setupGlobalStyles();
        this.setupKeyboardShortcuts();
        this.setupAccessibility();
        console.log('UI Controller 初期化完了');
    }

    /**
     * グローバルスタイルの設定
     */
    setupGlobalStyles() {
        // CSS アニメーションクラスを動的追加
        const style = document.createElement('style');
        style.textContent = `
            .pulse-animation {
                animation: pulseGlow 0.6s ease-in-out;
            }
            
            @keyframes pulseGlow {
                0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7); }
                50% { box-shadow: 0 0 0 10px rgba(37, 99, 235, 0.3); }
                100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
            }
            
            .fade-in-up {
                animation: fadeInUp 0.5s ease forwards;
            }
            
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .shake {
                animation: shake 0.5s ease-in-out;
            }
            
            @keyframes shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-5px); }
                75% { transform: translateX(5px); }
            }
            
            .highlight-glow {
                animation: highlightGlow 1s ease-in-out;
            }
            
            @keyframes highlightGlow {
                0%, 100% { background-color: transparent; }
                50% { background-color: rgba(245, 158, 11, 0.2); }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * キーボードショートカットの設定
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl + Enter でチェック実行
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                const checkButton = document.getElementById('check-button');
                if (checkButton && !checkButton.disabled) {
                    checkButton.click();
                }
            }
            
            // Escape でメッセージ削除
            if (e.key === 'Escape') {
                this.dismissAllMessages();
            }
            
            // Alt + C でクリア
            if (e.altKey && e.key === 'c') {
                e.preventDefault();
                const clearButton = document.getElementById('clear-button');
                if (clearButton) {
                    clearButton.click();
                }
            }
            
            // Tab キーでタブ切り替え（Ctrl + Tab）
            if (e.ctrlKey && e.key === 'Tab') {
                e.preventDefault();
                this.switchToNextTab();
            }
        });
    }

    /**
     * アクセシビリティの設定
     */
    setupAccessibility() {
        // フォーカス表示の改善
        document.addEventListener('focusin', (e) => {
            if (e.target.matches('button, input, textarea, select')) {
                e.target.style.outline = '2px solid var(--color-primary)';
                e.target.style.outlineOffset = '2px';
            }
        });

        document.addEventListener('focusout', (e) => {
            if (e.target.matches('button, input, textarea, select')) {
                e.target.style.outline = '';
                e.target.style.outlineOffset = '';
            }
        });

        // ARIA ラベルの動的更新
        this.updateAriaLabels();
    }

    /**
     * ARIA ラベルの更新
     */
    updateAriaLabels() {
        const checkButton = document.getElementById('check-button');
        const textInput = document.getElementById('text-input');
        const resultArea = document.getElementById('result-area');

        if (checkButton) {
            checkButton.setAttribute('aria-describedby', 'check-button-help');
        }

        if (textInput) {
            textInput.setAttribute('aria-describedby', 'char-count');
        }

        if (resultArea) {
            resultArea.setAttribute('aria-live', 'polite');
            resultArea.setAttribute('aria-atomic', 'true');
        }
    }

    /**
     * スムーズスクロール
     * @param {Element} element - スクロール先の要素
     * @param {number} offset - オフセット（デフォルト: 80px）
     */
    smoothScrollTo(element, offset = this.scrollOffset) {
        if (!element) return;

        const elementTop = element.offsetTop - offset;
        window.scrollTo({
            top: elementTop,
            behavior: 'smooth'
        });
    }

    /**
     * 要素のフェードイン表示
     * @param {Element} element - 表示する要素
     * @param {number} duration - アニメーション時間
     */
    fadeIn(element, duration = this.animationDuration) {
        if (!element) return;

        element.style.opacity = '0';
        element.style.display = 'block';
        element.classList.add('fade-in-up');

        setTimeout(() => {
            element.style.opacity = '1';
            element.classList.remove('fade-in-up');
        }, duration);
    }

    /**
     * 要素のフェードアウト
     * @param {Element} element - 非表示にする要素
     * @param {number} duration - アニメーション時間
     */
    fadeOut(element, duration = this.animationDuration) {
        if (!element) return;

        element.style.opacity = '1';
        element.style.transition = `opacity ${duration}ms ease`;
        element.style.opacity = '0';

        setTimeout(() => {
            element.style.display = 'none';
            element.style.transition = '';
        }, duration);
    }

    /**
     * 要素にパルスアニメーション適用
     * @param {Element} element - アニメーションを適用する要素
     */
    pulseElement(element) {
        if (!element) return;

        element.classList.add(this.pulseAnimationClass);
        setTimeout(() => {
            element.classList.remove(this.pulseAnimationClass);
        }, 600);
    }

    /**
     * 要素にシェイクアニメーション適用
     * @param {Element} element - アニメーションを適用する要素
     */
    shakeElement(element) {
        if (!element) return;

        element.classList.add('shake');
        setTimeout(() => {
            element.classList.remove('shake');
        }, 500);
    }

    /**
     * 要素をハイライト
     * @param {Element} element - ハイライトする要素
     */
    highlightElement(element) {
        if (!element) return;

        element.classList.add('highlight-glow');
        setTimeout(() => {
            element.classList.remove('highlight-glow');
        }, 1000);
    }

    /**
     * 進行状況の表示
     * @param {number} progress - 進行率（0-100）
     * @param {string} message - 進行状況メッセージ
     */
    showProgress(progress, message = '') {
        let progressContainer = document.getElementById('progress-container');
        
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'progress-container';
            progressContainer.innerHTML = `
                <div class="progress">
                    <div class="progress-bar" id="progress-bar"></div>
                </div>
                <div class="progress-message" id="progress-message"></div>
            `;
            
            const loadingSpinner = document.getElementById('loading-spinner');
            if (loadingSpinner) {
                loadingSpinner.appendChild(progressContainer);
            }
        }

        const progressBar = document.getElementById('progress-bar');
        const progressMessage = document.getElementById('progress-message');

        if (progressBar) {
            progressBar.style.width = `${Math.max(0, Math.min(100, progress))}%`;
        }

        if (progressMessage) {
            progressMessage.textContent = message;
        }
    }

    /**
     * 進行状況の非表示
     */
    hideProgress() {
        const progressContainer = document.getElementById('progress-container');
        if (progressContainer) {
            progressContainer.remove();
        }
    }

    /**
     * トーストメッセージの表示
     * @param {string} message - メッセージ内容
     * @param {string} type - メッセージタイプ
     * @param {number} duration - 表示時間
     */
    showToast(message, type = 'info', duration = this.messageTimeout) {
        const toastContainer = this.getOrCreateToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
            <span class="toast-message">${this.escapeHtml(message)}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;

        toastContainer.appendChild(toast);

        // フェードイン効果
        setTimeout(() => toast.classList.add('show'), 10);

        // 自動削除
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 300);
        }, duration);
    }

    /**
     * トーストコンテナの取得・作成
     */
    getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1000;
                max-width: 400px;
            `;
            document.body.appendChild(container);

            // トースト用のスタイルを追加
            this.addToastStyles();
        }

        return container;
    }

    /**
     * トースト用スタイルの追加
     */
    addToastStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .toast {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px 16px;
                margin-bottom: 8px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                transform: translateX(100%);
                opacity: 0;
                transition: all 0.3s ease;
            }
            
            .toast.show {
                transform: translateX(0);
                opacity: 1;
            }
            
            .toast-success { background: #d1fae5; color: #065f46; border-left: 4px solid #10b981; }
            .toast-error { background: #fee2e2; color: #991b1b; border-left: 4px solid #ef4444; }
            .toast-warning { background: #fef3c7; color: #92400e; border-left: 4px solid #f59e0b; }
            .toast-info { background: #dbeafe; color: #1e40af; border-left: 4px solid #3b82f6; }
            
            .toast-icon { font-size: 16px; flex-shrink: 0; }
            .toast-message { flex: 1; font-size: 14px; }
            .toast-close {
                background: none;
                border: none;
                font-size: 16px;
                cursor: pointer;
                opacity: 0.7;
                padding: 0;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .toast-close:hover { opacity: 1; }
        `;
        document.head.appendChild(style);
    }

    /**
     * 全てのメッセージを削除
     */
    dismissAllMessages() {
        // 通常のメッセージ削除
        document.querySelectorAll('.message').forEach(msg => msg.remove());
        
        // トースト削除
        document.querySelectorAll('.toast').forEach(toast => toast.remove());
    }

    /**
     * 次のタブに切り替え
     */
    switchToNextTab() {
        const activeTab = document.querySelector('.tab-button.active');
        const allTabs = document.querySelectorAll('.tab-button');
        
        if (activeTab && allTabs.length > 1) {
            const currentIndex = Array.from(allTabs).indexOf(activeTab);
            const nextIndex = (currentIndex + 1) % allTabs.length;
            allTabs[nextIndex].click();
        }
    }

    /**
     * フォーカス管理
     * @param {Element} element - フォーカスする要素
     */
    focusElement(element) {
        if (!element) return;

        setTimeout(() => {
            element.focus();
            this.pulseElement(element);
        }, 100);
    }

    /**
     * 要素の表示状態をトグル
     * @param {Element} element - 対象要素
     * @param {boolean} show - 表示するかどうか
     */
    toggleVisibility(element, show) {
        if (!element) return;

        if (show) {
            this.fadeIn(element);
        } else {
            this.fadeOut(element);
        }
    }

    /**
     * HTMLエスケープ
     * @param {string} text - エスケープするテキスト
     * @returns {string} エスケープされたテキスト
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * レスポンシブ対応チェック
     * @returns {boolean} モバイルデバイスかどうか
     */
    isMobile() {
        return window.innerWidth <= 768;
    }

    /**
     * デバイス向けの最適化
     */
    optimizeForDevice() {
        if (this.isMobile()) {
            // モバイル向けの最適化
            document.body.classList.add('mobile-device');
            this.scrollOffset = 60;
        } else {
            // デスクトップ向けの最適化
            document.body.classList.remove('mobile-device');
            this.scrollOffset = 80;
        }
    }
}

// グローバルUI コントローラーインスタンス
window.yakkiUI = new YakkiUIController();

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    window.yakkiUI.init();
    window.yakkiUI.optimizeForDevice();
});

// リサイズイベント
window.addEventListener('resize', () => {
    window.yakkiUI.optimizeForDevice();
});

console.log('薬機法リスクチェッカー ui.js 読み込み完了');