/**
 * 薬機法リスクチェッカー メインJavaScript
 * ユーザーインタラクション、API通信、動的DOM操作を制御
 */

// ===== グローバル変数 =====
const API_BASE_URL = 'http://localhost:5000';
let currentCheckData = null;

// ===== DOM要素の取得 =====
const elements = {
    // フォーム要素
    productCategory: document.getElementById('product-category'),
    textType: document.getElementById('text-type'),
    textInput: document.getElementById('text-input'),
    specialPoints: document.getElementById('special-points'),
    checkButton: document.getElementById('check-button'),
    clearButton: document.getElementById('clear-button'),
    charCount: document.getElementById('char-count'),
    
    // 表示要素
    loadingSpinner: document.getElementById('loading-spinner'),
    resultArea: document.getElementById('result-area'),
    riskBadge: document.getElementById('risk-badge'),
    riskLevelText: document.getElementById('risk-level-text'),
    
    // リスク件数
    totalCount: document.getElementById('total-count'),
    highCount: document.getElementById('high-count'),
    mediumCount: document.getElementById('medium-count'),
    lowCount: document.getElementById('low-count'),
    
    // 詳細結果
    highlightedText: document.getElementById('highlighted-text'),
    issuesList: document.getElementById('issues-list'),
    rewrittenText: document.getElementById('rewritten-text'),
    copyRewrittenButton: document.getElementById('copy-rewritten'),
    
    // タブ要素
    tabChecker: document.getElementById('tab-checker'),
    tabGuide: document.getElementById('tab-guide'),
    checkerContent: document.getElementById('checker-content'),
    guideContent: document.getElementById('guide-content'),
    
    // その他
    consultButton: document.getElementById('consult-button')
};

// ===== 初期化処理 =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 薬機法リスクチェッカー 初期化開始');
    
    // DOM要素の存在確認
    console.log('🔍 DOM要素確認:');
    Object.keys(elements).forEach(key => {
        const element = elements[key];
        if (element) {
            console.log(`✅ ${key}:`, element);
        } else {
            console.error(`❌ ${key}: 要素が見つかりません`);
        }
    });
    
    // イベントリスナーの設定
    console.log('🔧 イベントリスナー設定開始');
    setupEventListeners();
    
    // 初期状態の設定
    console.log('⚙️ 初期状態設定開始');
    setupInitialState();
    
    // API クライアント確認
    console.log('🌐 APIクライアント確認:', window.yakkiApi ? '✅ 利用可能' : '❌ 未初期化');
    
    console.log('🎉 薬機法リスクチェッカー 初期化完了');
});

// ===== イベントリスナーの設定 =====
function setupEventListeners() {
    console.log('🔧 イベントリスナー設定開始');
    
    // DOM要素の存在確認
    if (!elements.checkButton) {
        console.error('❌ checkButton要素が見つかりません');
        return;
    }
    
    // チェック開始ボタン
    console.log('✅ checkButton要素確認:', elements.checkButton);
    elements.checkButton.addEventListener('click', handleCheckButtonClick);
    console.log('✅ checkButtonクリックイベントリスナー追加完了');
    
    // クリアボタン
    elements.clearButton.addEventListener('click', handleClearButtonClick);
    
    // テキスト入力の監視
    elements.textInput.addEventListener('input', handleTextInput);
    elements.textInput.addEventListener('paste', handleTextInput);
    
    // 商品カテゴリ選択の監視
    elements.productCategory.addEventListener('change', updateCheckButtonState);
    
    // 文章種類選択の監視
    elements.textType.addEventListener('change', updateCheckButtonState);
    
    // タブ切り替え
    elements.tabChecker.addEventListener('click', () => switchTab('checker'));
    elements.tabGuide.addEventListener('click', () => switchTab('guide'));
    
    // 修正版テキストコピー
    elements.copyRewrittenButton.addEventListener('click', handleCopyRewrittenText);
    
    // 専門家相談ボタン
    elements.consultButton.addEventListener('click', handleConsultButtonClick);
    
    // エンターキーでのチェック実行
    elements.textInput.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            if (!elements.checkButton.disabled) {
                handleCheckButtonClick();
            }
        }
    });
}

// ===== 初期状態の設定 =====
function setupInitialState() {
    // 結果エリアを非表示
    elements.resultArea.style.display = 'none';
    elements.loadingSpinner.style.display = 'none';
    
    // チェックボタンを無効化
    updateCheckButtonState();
    
    // 文字数カウンターの初期化
    updateCharacterCount();
    
    // 初期タブをアクティブに設定
    switchTab('checker');
}

// ===== テキスト入力処理 =====
function handleTextInput() {
    // 文字数制限のチェック
    const maxLength = 500;
    if (elements.textInput.value.length > maxLength) {
        elements.textInput.value = elements.textInput.value.substring(0, maxLength);
        showMessage('文字数の上限（500文字）に達しました。', 'warning');
    }
    
    // 文字数カウンターの更新
    updateCharacterCount();
    
    // チェックボタンの状態更新
    updateCheckButtonState();
    
    // 遅延実行で結果をクリア（入力中は結果を隠す）
    clearTimeout(window.inputTimeout);
    window.inputTimeout = setTimeout(() => {
        if (elements.resultArea.style.display !== 'none') {
            elements.resultArea.style.display = 'none';
        }
    }, 1000);
}

// ===== 文字数カウンターの更新 =====
function updateCharacterCount() {
    const currentLength = elements.textInput.value.length;
    const maxLength = 500;
    
    elements.charCount.textContent = currentLength;
    
    // 文字数に応じた色変更
    if (currentLength > maxLength * 0.9) {
        elements.charCount.style.color = 'var(--color-danger)';
    } else if (currentLength > maxLength * 0.7) {
        elements.charCount.style.color = 'var(--color-warning)';
    } else {
        elements.charCount.style.color = 'var(--color-gray-500)';
    }
}

// ===== チェックボタンの状態更新 =====
function updateCheckButtonState() {
    const hasText = elements.textInput.value.trim().length > 0;
    const hasCategory = elements.productCategory.value !== '';
    const hasType = elements.textType.value !== '';
    
    elements.checkButton.disabled = !(hasText && hasCategory && hasType);
}

// ===== チェック開始ボタンクリック処理 =====
async function handleCheckButtonClick() {
    console.log('🚀 チェック開始ボタンがクリックされました');
    console.log('📝 ボタン状態:', {
        disabled: elements.checkButton.disabled,
        textValue: elements.textInput.value,
        typeValue: elements.textType.value
    });
    
    try {
        // バリデーション
        const text = elements.textInput.value.trim();
        const category = elements.productCategory.value;
        const type = elements.textType.value;
        const specialPoints = elements.specialPoints.value.trim();
        
        if (!text) {
            showMessage('チェックしたい文章を入力してください。', 'warning');
            return;
        }
        
        if (!category) {
            showMessage('商品カテゴリを選択してください。', 'warning');
            return;
        }
        
        if (!type) {
            showMessage('文章の種類を選択してください。', 'warning');
            return;
        }
        
        // UI状態の更新
        showLoading(true);
        elements.resultArea.style.display = 'none';
        
        // API通信（専用クライアント使用）
        console.log('🌐 API通信開始:', { text, category, type, specialPoints });
        console.log('🔌 APIクライアント確認:', window.yakkiApi ? '✅ 利用可能' : '❌ 未初期化');
        
        if (!window.yakkiApi) {
            throw new Error('APIクライアントが初期化されていません');
        }
        
        console.log('📡 checkText関数呼び出し中...');
        const data = await window.yakkiApi.checkText(text, category, type, specialPoints);
        console.log('📨 API応答受信:', data);
        
        // レスポンス構造の検証
        if (!validateApiResponse(data)) {
            throw new Error('APIレスポンスの形式が不正です');
        }
        
        // 結果の保存と表示
        currentCheckData = data;
        displayCheckResult(data, text);
        
        showMessage('薬機法チェックが完了しました！', 'success');
        
    } catch (error) {
        console.error('チェック処理エラー:', error);
        
        // エラー種別に応じたメッセージ
        let message = 'チェック処理中にエラーが発生しました。';
        let details = '';
        
        if (error.message) {
            message = error.message;
        }
        
        // 401エラー（認証エラー）の場合は詳細な情報を表示
        if (error.message && error.message.includes('401')) {
            console.warn('🔒 API認証エラーが発生しました');
            if (window.location.hostname === 'localhost') {
                message = 'APIキー認証に失敗しました。開発環境では自動的に "demo_key_for_development_only" が使用されます。\n\n対処方法:\n1. バックエンドの.envファイルのVALID_API_KEYSが正しく設定されているか確認\n2. バックエンドサーバーが正常に起動しているか確認\n3. ブラウザのコンソールでエラー詳細を確認';
            }
        }
        
        // 開発環境でのデバッグ情報
        if (window.location.hostname === 'localhost') {
            details = `\n\nデバッグ情報:\n- エラー名: ${error.name || 'Unknown'}\n- API URL: ${window.yakkiApi?.baseUrl || 'N/A'}\n- APIキー設定: ${window.yakkiApi?.apiKey ? '設定済み' : '未設定'}\n- 詳細: ${error.stack || error.toString()}`;
        }
        
        showMessage(message + details, 'error');
        
        // エラー時に結果エリアを非表示
        elements.resultArea.style.display = 'none';
    } finally {
        showLoading(false);
    }
}

// ===== APIレスポンス検証 =====
function validateApiResponse(data) {
    if (!data || typeof data !== 'object') {
        console.error('レスポンスがオブジェクトではありません:', data);
        return false;
    }
    
    // 必須フィールドの確認
    const requiredFields = ['overall_risk', 'risk_counts', 'issues'];
    for (const field of requiredFields) {
        if (!(field in data)) {
            console.error(`必須フィールド '${field}' がありません:`, data);
            return false;
        }
    }
    
    // リライト関連フィールドの確認（新旧両対応）
    if (!data.rewritten_texts && !data.rewritten_text) {
        console.error('rewritten_texts または rewritten_text が必要です:', data);
        return false;
    }
    
    // リスクレベルの確認
    const validRiskLevels = ['高', '中', '低'];
    if (!validRiskLevels.includes(data.overall_risk)) {
        console.error('overall_risk が不正です:', data.overall_risk);
        return false;
    }
    
    // issues配列の確認
    if (!Array.isArray(data.issues)) {
        console.error('issues が配列ではありません:', data.issues);
        return false;
    }
    
    console.log('✅ APIレスポンス検証成功');
    return true;
}

// ===== API通信エラーハンドリング =====
function handleApiError(error) {
    let errorMessage = 'チェック処理中にエラーが発生しました。';
    
    if (error.name === 'TypeError') {
        errorMessage = 'サーバーに接続できません。バックエンドが起動しているか確認してください。';
    } else if (error.message.includes('400')) {
        errorMessage = '入力データに問題があります。内容を確認してください。';
    } else if (error.message.includes('500')) {
        errorMessage = 'サーバーエラーが発生しました。しばらく待ってから再試行してください。';
    }
    
    showMessage(errorMessage, 'error');
    elements.resultArea.style.display = 'none';
}

// ===== チェック結果の表示 =====
function displayCheckResult(data, originalText) {
    console.log('🎯 結果表示開始:', data);
    console.log('📊 elements.resultArea:', elements.resultArea);
    
    try {
        // 総合リスクレベルの表示
        console.log('📈 総合リスク表示開始:', data.overall_risk);
        displayOverallRisk(data.overall_risk);
        console.log('✅ 総合リスク表示完了');
        
        // リスク件数の表示
        console.log('📊 リスク件数表示開始:', data.risk_counts);
        displayRiskCounts(data.risk_counts);
        console.log('✅ リスク件数表示完了');
        
        // ハイライト付きテキストの表示
        console.log('🎨 ハイライトテキスト表示開始');
        displayHighlightedText(originalText, data.issues);
        console.log('✅ ハイライトテキスト表示完了');
        
        // 指摘事項リストの表示
        console.log('📋 指摘事項リスト表示開始');
        displayIssuesList(data.issues);
        console.log('✅ 指摘事項リスト表示完了');
        
        // 修正版テキストの表示（新旧形式両対応）
        console.log('📝 修正版テキスト表示開始');
        if (data.rewritten_texts) {
            console.log('🆕 新形式（3つのバリエーション）:', data.rewritten_texts);
            displayRewrittenTexts(data.rewritten_texts);
            console.log('✅ 新形式表示完了');
        } else if (data.rewritten_text) {
            console.log('🔄 旧形式（1つのリライト案）:', data.rewritten_text);
            displayLegacyRewrittenText(data.rewritten_text);
            console.log('✅ 旧形式表示完了');
        } else {
            console.warn('⚠️ 修正版テキストがレスポンスに含まれていません');
        }
        
        // 結果エリアを表示
        console.log('👁️ 結果エリア表示設定開始');
        if (elements.resultArea) {
            elements.resultArea.style.display = 'block';
            console.log('✅ resultArea display設定完了:', elements.resultArea.style.display);
            elements.resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
            console.log('✅ スクロール完了');
        } else {
            console.error('❌ elements.resultAreaが見つかりません');
        }
        
        // CTA表示
        showConsultationCTA();
        
        console.log('🎉 結果表示完了');
    } catch (error) {
        console.error('❌ 結果表示エラー:', error);
        throw error;
    }
}

// ===== 総合リスクレベルの表示 =====
function displayOverallRisk(riskLevel) {
    elements.riskLevelText.textContent = riskLevel;
    
    // クラスをリセット
    elements.riskBadge.className = 'risk-badge';
    
    // リスクレベルに応じたクラス追加
    switch (riskLevel) {
        case '高':
            elements.riskBadge.classList.add('high');
            break;
        case '中':
            elements.riskBadge.classList.add('medium');
            break;
        case '低':
            elements.riskBadge.classList.add('low');
            break;
    }
}

// ===== リスク件数の表示 =====
function displayRiskCounts(counts) {
    elements.totalCount.textContent = counts.total || 0;
    elements.highCount.textContent = counts.high || 0;
    elements.mediumCount.textContent = counts.medium || 0;
    elements.lowCount.textContent = counts.low || 0;
}

// ===== ハイライト付きテキストの表示 =====
function displayHighlightedText(originalText, issues) {
    if (!issues || issues.length === 0) {
        elements.highlightedText.textContent = originalText;
        return;
    }
    
    let highlightedHtml = originalText;
    
    // 各指摘事項についてハイライトを適用
    issues.forEach((issue, index) => {
        const fragment = issue.fragment;
        const riskClass = issue.risk_level === '高' ? 'high-risk' : 
                         issue.risk_level === '中' ? 'medium-risk' : 'low-risk';
        
        // HTMLエスケープして安全に処理
        const escapedFragment = escapeHtml(fragment);
        const markTag = `<mark class="${riskClass}" data-risk="${issue.risk_level}" data-issue-index="${index}">${escapedFragment}</mark>`;
        
        highlightedHtml = highlightedHtml.replace(
            new RegExp(escapeRegExp(fragment), 'g'),
            markTag
        );
    });
    
    elements.highlightedText.innerHTML = highlightedHtml;
    
    // ハイライト部分にクリックイベントを追加
    const highlights = elements.highlightedText.querySelectorAll('mark');
    highlights.forEach(mark => {
        mark.addEventListener('click', function() {
            const issueIndex = parseInt(this.dataset.issueIndex);
            scrollToIssue(issueIndex);
        });
    });
}

// ===== 指摘事項リストの表示 =====
function displayIssuesList(issues) {
    if (!issues || issues.length === 0) {
        elements.issuesList.innerHTML = '<p class="no-issues">指摘事項はありません。薬機法に適合していると思われます。</p>';
        return;
    }
    
    const issuesHtml = issues.map((issue, index) => {
        const riskClass = issue.risk_level === '高' ? 'high-risk' : 
                         issue.risk_level === '中' ? 'medium-risk' : 'low-risk';
        
        const suggestionsHtml = issue.suggestions.map(suggestion => 
            `<li onclick="applySuggestion('${escapeHtml(suggestion)}')">${escapeHtml(suggestion)}</li>`
        ).join('');
        
        return `
            <div class="issue-card ${riskClass}" id="issue-${index}">
                <div class="issue-fragment ${riskClass}">"${escapeHtml(issue.fragment)}"</div>
                <div class="issue-risk-level ${issue.risk_level === '高' ? 'high' : issue.risk_level === '中' ? 'medium' : 'low'}">${issue.risk_level}リスク</div>
                <div class="issue-reason">${escapeHtml(issue.reason)}</div>
                <div class="issue-suggestions">
                    <h5>💡 代替表現の提案</h5>
                    <ul class="suggestions-list">
                        ${suggestionsHtml}
                    </ul>
                </div>
            </div>
        `;
    }).join('');
    
    elements.issuesList.innerHTML = issuesHtml;
}

// ===== 修正版テキストの表示（3つのバリエーション） =====
function displayRewrittenTexts(rewrittenTexts) {
    console.log('📝 displayRewrittenTexts開始:', rewrittenTexts);
    
    const rewrittenContainer = document.getElementById('rewritten-texts-container');
    const legacyContainer = document.getElementById('legacy-rewritten');
    
    console.log('🔍 DOM要素確認:', {
        rewrittenContainer: rewrittenContainer,
        legacyContainer: legacyContainer
    });
    
    if (!rewrittenContainer) {
        console.error('❌ rewritten-texts-container要素が見つかりません');
        return;
    }
    
    // レガシーコンテナを非表示にして新コンテナを表示
    if (legacyContainer) {
        legacyContainer.style.display = 'none';
        console.log('✅ legacyContainer非表示設定完了');
    }
    rewrittenContainer.style.display = 'block';
    console.log('✅ rewrittenContainer表示設定完了');
    
    // 新しい形式（オブジェクト）と古い形式（文字列）の両方に対応
    const parseRewrittenText = (data) => {
        if (typeof data === 'string') {
            return { text: data, explanation: '' };
        } else if (typeof data === 'object' && data.text) {
            return { text: data.text, explanation: data.explanation || '' };
        }
        return { text: '', explanation: '' };
    };
    
    const texts = {
        conservative: parseRewrittenText(rewrittenTexts.conservative),
        balanced: parseRewrittenText(rewrittenTexts.balanced),
        appealing: parseRewrittenText(rewrittenTexts.appealing)
    };
    
    console.log('📄 テキストデータ:', texts);
    
    const labels = {
        conservative: '保守的版',
        balanced: 'バランス版', 
        appealing: '訴求力重視版'
    };
    
    const descriptions = {
        conservative: '最も安全で確実な表現',
        balanced: '安全性と訴求力のバランス',
        appealing: '法的リスクを最小限にしつつ訴求力を最大化'
    };
    
    let html = '<h4>💡 3つの修正版提案</h4>';
    
    Object.keys(texts).forEach((type, index) => {
        console.log(`🔄 処理中: ${type} = "${texts[type].text}"`);
        if (texts[type].text) {
            try {
                const escapedText = escapeHtml(texts[type].text);
                const escapedExplanation = escapeHtml(texts[type].explanation);
                console.log(`✅ エスケープ完了: ${type} = "${escapedText}"`);
                
                html += `
                    <div class="rewritten-variant" data-type="${type}">
                        <div class="variant-header">
                            <h5 class="variant-title">${labels[type]}</h5>
                            <p class="variant-description">${descriptions[type]}</p>
                        </div>
                        <div class="variant-content">
                            <div class="rewritten-text" id="rewritten-${type}">${escapedText}</div>
                            ${escapedExplanation ? `
                            <div class="legal-explanation">
                                <h6>🔍 薬機法的解説</h6>
                                <p>${escapedExplanation}</p>
                            </div>
                            ` : ''}
                            <button class="btn btn-secondary copy-variant-btn" onclick="copyVariantText('${type}')">
                                <span class="btn-icon">📋</span>${labels[type]}をコピー
                            </button>
                        </div>
                    </div>
                `;
            } catch (error) {
                console.error(`❌ ${type}のHTML生成エラー:`, error);
            }
        } else {
            console.warn(`⚠️ ${type}のテキストが空です`);
        }
    });
    
    console.log('🏗️ 生成HTML:', html);
    rewrittenContainer.innerHTML = html;
    console.log('✅ displayRewrittenTexts完了');
}

// ===== 相談促進CTA表示 =====
function showConsultationCTA() {
    console.log('📢 CTA表示開始');
    
    const ctaElement = document.getElementById('consultation-cta');
    if (ctaElement) {
        ctaElement.style.display = 'block';
        console.log('✅ CTA表示完了');
    } else {
        console.error('❌ CTA要素が見つかりません');
    }
}

// ===== 旧形式対応（後方互換性） =====
function displayLegacyRewrittenText(rewrittenText) {
    const legacyContainer = document.getElementById('legacy-rewritten');
    const newContainer = document.getElementById('rewritten-texts-container');
    
    // 新コンテナを非表示にして旧コンテナを表示
    if (newContainer) newContainer.style.display = 'none';
    if (legacyContainer) {
        legacyContainer.style.display = 'block';
        const textElement = document.getElementById('rewritten-text');
        if (textElement) {
            textElement.textContent = rewrittenText;
        }
    }
}

// ===== バリエーション別コピー機能 =====
function copyVariantText(type) {
    const textElement = document.getElementById(`rewritten-${type}`);
    if (!textElement) {
        showMessage('コピーするテキストが見つかりません', 'warning');
        return;
    }
    
    const text = textElement.textContent;
    if (!text) {
        showMessage('コピーするテキストがありません', 'warning');
        return;
    }
    
    const labels = {
        conservative: '保守的版',
        balanced: 'バランス版', 
        appealing: '訴求力重視版'
    };
    
    navigator.clipboard.writeText(text).then(() => {
        showMessage(`${labels[type]}をクリップボードにコピーしました！`, 'success');
        const button = document.querySelector(`[onclick="copyVariantText('${type}')"]`);
        if (button) {
            const originalHTML = button.innerHTML;
            button.innerHTML = '<span class="btn-icon">✅</span>コピー完了';
            setTimeout(() => {
                button.innerHTML = originalHTML;
            }, 2000);
        }
    }).catch(() => {
        showMessage('コピーに失敗しました', 'error');
    });
}

// ===== 指摘事項へのスクロール =====
function scrollToIssue(issueIndex) {
    const issueElement = document.getElementById(`issue-${issueIndex}`);
    if (issueElement) {
        issueElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        issueElement.style.animation = 'pulse 0.5s ease';
        setTimeout(() => {
            issueElement.style.animation = '';
        }, 500);
    }
}

// ===== 代替表現の適用 =====
function applySuggestion(suggestion) {
    navigator.clipboard.writeText(suggestion).then(() => {
        showMessage(`"${suggestion}" をクリップボードにコピーしました`, 'success');
    }).catch(() => {
        showMessage('コピーに失敗しました', 'error');
    });
}

// ===== 修正版テキストのコピー =====
function handleCopyRewrittenText() {
    const rewrittenText = elements.rewrittenText.textContent;
    if (!rewrittenText) {
        showMessage('コピーするテキストがありません', 'warning');
        return;
    }
    
    navigator.clipboard.writeText(rewrittenText).then(() => {
        showMessage('修正版テキストをクリップボードにコピーしました！', 'success');
        elements.copyRewrittenButton.innerHTML = '<span class="btn-icon">✅</span>コピー完了';
        setTimeout(() => {
            elements.copyRewrittenButton.innerHTML = '<span class="btn-icon">📋</span>修正版をコピー';
        }, 2000);
    }).catch(() => {
        showMessage('コピーに失敗しました', 'error');
    });
}

// ===== クリアボタンクリック処理 =====
function handleClearButtonClick() {
    console.log('クリアボタンがクリックされました');
    
    // フォームクリア
    elements.textInput.value = '';
    elements.textType.value = '';
    elements.productCategory.value = '';
    elements.specialPoints.value = '';
    
    // 状態リセット
    updateCharacterCount();
    updateCheckButtonState();
    
    // 結果エリア非表示
    elements.resultArea.style.display = 'none';
    currentCheckData = null;
    
    // CTA非表示
    const ctaElement = document.getElementById('consultation-cta');
    if (ctaElement) {
        ctaElement.style.display = 'none';
    }
    
    // フォーカスをテキストエリアに
    elements.textInput.focus();
    
    showMessage('入力内容をクリアしました', 'info');
}

// ===== タブ切り替え処理 =====
function switchTab(tabName) {
    console.log(`タブ切り替え: ${tabName}`);
    
    // タブボタンの状態更新
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    
    if (tabName === 'checker') {
        elements.tabChecker.classList.add('active');
        elements.checkerContent.classList.add('active');
    } else if (tabName === 'guide') {
        elements.tabGuide.classList.add('active');
        elements.guideContent.classList.add('active');
        
        // iframeが既に表示されているので、追加の読み込み処理は不要
        console.log('薬機法ガイドタブ表示 - iframe経由');
    }
}

// ===== NotionAPI関連機能削除済み =====
// 薬機法ガイドはiframe (yakki-guide/html/index.html) で表示

// ===== ローディング状態の制御 =====
function showLoading(show) {
    if (show) {
        elements.loadingSpinner.style.display = 'block';
        elements.checkButton.disabled = true;
        elements.checkButton.innerHTML = '<span class="btn-icon">⏳</span>チェック中...';
    } else {
        elements.loadingSpinner.style.display = 'none';
        elements.checkButton.disabled = false;
        elements.checkButton.innerHTML = '<span class="btn-icon">🔍</span>チェック開始';
        updateCheckButtonState();
    }
}

// ===== メッセージ表示 =====
function showMessage(message, type = 'info') {
    console.log(`Message [${type}]: ${message}`);
    
    // 既存のメッセージを削除
    const existingMessage = document.querySelector('.message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // メッセージ要素を作成
    const messageElement = document.createElement('div');
    messageElement.className = `message message-${type}`;
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    messageElement.innerHTML = `
        <span class="message-icon">${icons[type] || 'ℹ️'}</span>
        <span>${escapeHtml(message)}</span>
        <button class="message-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    // メッセージを画面上部に挿入
    const main = document.querySelector('.main .container');
    main.insertBefore(messageElement, main.firstChild);
    
    // 3秒後に自動削除
    setTimeout(() => {
        if (messageElement.parentNode) {
            messageElement.remove();
        }
    }, 3000);
}

// ===== 専門家相談ボタンクリック処理 =====
function handleConsultButtonClick() {
    console.log('専門家相談ボタンがクリックされました');
    
    // 実際のリンク先が決まったら更新
    const consultUrl = 'https://example.com/contact';
    
    // 新しいウィンドウで開く
    window.open(consultUrl, '_blank', 'noopener,noreferrer');
    
    showMessage('専門家への相談ページを開きます', 'info');
}

// ===== ユーティリティ関数 =====

// HTMLエスケープ
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 正規表現エスケープ
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// デバッグ用関数
function debugLog(message, data = null) {
    if (window.location.hostname === 'localhost') {
        console.log(`[DEBUG] ${message}`, data);
    }
}

// ===== エラーハンドリング =====
window.addEventListener('error', function(e) {
    console.error('JavaScriptエラー:', e.error);
    showMessage('予期しないエラーが発生しました', 'error');
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('未処理のPromise拒否:', e.reason);
    showMessage('処理中にエラーが発生しました', 'error');
});

console.log('薬機法リスクチェッカー script.js 読み込み完了');