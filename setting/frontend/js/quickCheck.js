/**
 * 薬機法リスクチェッカー ローカル簡易チェック機能
 * Claude APIを呼び出す前に、明らかなNG表現を即座に検出
 */

class QuickChecker {
    constructor() {
        // 明らかなNG表現のデータベース
        this.ngPatterns = {
            // 効果・効能の断定的表現
            効果断定: {
                words: ['治る', '治す', '完治', '根治', '治療', '改善する', '解消', '消える', '無くなる', '痛みが消えた', '症状が消えた'],
                message: '病気の治療効果を断定的に表現することはできません',
                riskLevel: '高'
            },
            
            // 効果の保証
            効果保証: {
                words: ['必ず', '絶対に', '確実に', '100%', '全員に', '誰でも'],
                message: '効果を保証する表現は使用できません',
                riskLevel: '高'
            },
            
            // 医薬品的な効能効果
            医薬品的効果: {
                words: ['効く', '効果がある', '作用する', '症状が消える', '痛みが消える', '症状を抑える'],
                message: '医薬品的な効能効果の表現は使用できません',
                riskLevel: '高'
            },
            
            // 身体機能の増強
            身体機能: {
                words: ['血圧を下げる', '血糖値を下げる', '脂肪を燃焼', '代謝を上げる', 'ホルモンを増やす'],
                message: '身体機能への直接的な作用は表現できません',
                riskLevel: '中'
            },
            
            // 最上級表現
            最上級: {
                words: ['最高', '最強', '最も効果的', '日本一', '世界一', 'No.1'],
                message: '最上級表現は客観的データなしには使用できません',
                riskLevel: '中'
            },
            
            // 安全性の断定
            安全性断定: {
                words: ['副作用なし', '副作用ゼロ', '安全性100%', '全く害がない'],
                message: '安全性を断定する表現は避けるべきです',
                riskLevel: '中'
            }
        };
        
        // カテゴリ別の特殊ルール
        this.categorySpecificRules = {
            'サプリメント': ['病気', '疾病', '疾患', '症状', '診断', '処方'],
            '化粧品': ['シミが消える', 'シワが消える', 'たるみ解消', '美白効果', 'アンチエイジング'],
            '薬用化粧品': ['アトピー', 'アレルギー', '皮膚病', '炎症を治す'],
            '美容機器・健康器具・その他': ['治療器', '医療機器', '診察', '検査']
        };
    }
    
    /**
     * テキストの簡易チェックを実行
     * @param {string} text - チェック対象のテキスト
     * @param {string} category - 商品カテゴリ
     * @returns {Object} チェック結果
     */
    performQuickCheck(text, category) {
        const startTime = performance.now();
        const results = {
            hasIssues: false,
            issues: [],
            estimatedRiskLevel: '低',
            checkedIn: 0
        };
        
        // 基本的なNG表現チェック
        for (const [patternType, pattern] of Object.entries(this.ngPatterns)) {
            for (const word of pattern.words) {
                if (text.includes(word)) {
                    results.hasIssues = true;
                    results.issues.push({
                        word: word,
                        type: patternType,
                        message: pattern.message,
                        riskLevel: pattern.riskLevel,
                        position: text.indexOf(word)
                    });
                }
            }
        }
        
        // カテゴリ別の特殊ルールチェック
        if (this.categorySpecificRules[category]) {
            for (const word of this.categorySpecificRules[category]) {
                if (text.includes(word)) {
                    results.hasIssues = true;
                    results.issues.push({
                        word: word,
                        type: 'カテゴリ特有',
                        message: `${category}では「${word}」という表現は使用できません`,
                        riskLevel: '高',
                        position: text.indexOf(word)
                    });
                }
            }
        }
        
        // リスクレベルの判定
        const highRiskCount = results.issues.filter(i => i.riskLevel === '高').length;
        const mediumRiskCount = results.issues.filter(i => i.riskLevel === '中').length;
        
        if (highRiskCount > 0) {
            results.estimatedRiskLevel = '高';
        } else if (mediumRiskCount > 0) {
            results.estimatedRiskLevel = '中';
        }
        
        // 処理時間の記録
        results.checkedIn = Math.round(performance.now() - startTime);
        
        return results;
    }
    
    /**
     * 簡易チェック結果を表示用HTMLに変換
     * @param {Object} quickResults - 簡易チェック結果
     * @returns {string} 表示用HTML
     */
    formatQuickResults(quickResults) {
        if (!quickResults.hasIssues) {
            return '';
        }
        
        const groupedIssues = {};
        quickResults.issues.forEach(issue => {
            if (!groupedIssues[issue.type]) {
                groupedIssues[issue.type] = [];
            }
            groupedIssues[issue.type].push(issue);
        });
        
        let html = `
            <div class="quick-check-alert">
                <h4>⚡ 簡易チェックで以下の問題が検出されました</h4>
                <p class="quick-check-time">（${quickResults.checkedIn}ms で検出）</p>
        `;
        
        for (const [type, issues] of Object.entries(groupedIssues)) {
            const riskClass = issues[0].riskLevel === '高' ? 'high-risk' : 
                            issues[0].riskLevel === '中' ? 'medium-risk' : 'low-risk';
            
            html += `
                <div class="quick-check-group ${riskClass}">
                    <h5>${type}</h5>
                    <p class="risk-message">${issues[0].message}</p>
                    <ul class="detected-words">
            `;
            
            issues.forEach(issue => {
                html += `<li>「${issue.word}」</li>`;
            });
            
            html += `
                    </ul>
                </div>
            `;
        }
        
        html += `
                <p class="quick-check-note">
                    ※ これは簡易チェックの結果です。詳細な分析を実行中...
                </p>
            </div>
        `;
        
        return html;
    }
}

// グローバルに公開
window.quickChecker = new QuickChecker();

console.log('薬機法リスクチェッカー quickCheck.js 読み込み完了');