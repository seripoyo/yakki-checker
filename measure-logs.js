// ログカウント測定スクリプト
const fs = require('fs');
const path = require('path');

const jsDir = path.join(__dirname, 'setting/frontend/js');
const files = fs.readdirSync(jsDir).filter(f => f.endsWith('.js'));

let totalConsoleCount = 0;
let conditionalConsoleCount = 0;

files.forEach(file => {
    const content = fs.readFileSync(path.join(jsDir, file), 'utf8');
    
    // 全console文をカウント
    const allConsole = (content.match(/console\./g) || []).length;
    
    // 条件付きconsole文をカウント（if文内やdebugLog関数使用）
    const conditionalPatterns = [
        /if\s*\([^)]*\)\s*{[^}]*console\./g,
        /debugLog\(/g,
        /debugError\(/g,
        /debugWarn\(/g,
        /typeof\s+debugLog\s*===\s*'function'/g,
        /typeof\s+isDebugMode\s*===\s*'function'/g
    ];
    
    let conditional = 0;
    conditionalPatterns.forEach(pattern => {
        conditional += (content.match(pattern) || []).length;
    });
    
    console.log(`${file}: ${allConsole} console文 (条件付き: ${conditional})`);
    totalConsoleCount += allConsole;
    conditionalConsoleCount += conditional;
});

console.log('\n=== 最適化結果 ===');
console.log(`総console文数: ${totalConsoleCount}`);
console.log(`条件付きconsole文数: ${conditionalConsoleCount}`);
console.log(`無条件console文数: ${totalConsoleCount - conditionalConsoleCount}`);
console.log(`最適化率: ${((conditionalConsoleCount / totalConsoleCount) * 100).toFixed(1)}%`);