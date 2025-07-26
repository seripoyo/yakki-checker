/**
 * 薬機法リスクチェッカー ストリーミングレスポンス機能
 * Server-Sent Eventsを使用して段階的に結果を表示
 */

class StreamingClient {
    constructor() {
        this.eventSource = null;
        this.progressSteps = [];
        this.useStreaming = true; // ストリーミングを使用するかどうか
    }
    
    /**
     * ストリーミングチェックを開始
     * @param {Object} checkData - チェックデータ
     * @param {Function} onProgress - 進捗コールバック
     * @param {Function} onComplete - 完了コールバック
     * @param {Function} onError - エラーコールバック
     */
    async startStreamingCheck(checkData, onProgress, onComplete, onError) {
        // 既存の接続があれば閉じる
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        try {
            // APIキーを取得
            const apiKey = window.yakkiApi?.apiKey || 'demo_key_for_development_only';
            
            // fetchを使用してPOSTリクエストでストリーミングを開始
            const response = await fetch(`${window.yakkiApi.baseUrl}/api/check/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': apiKey
                },
                body: JSON.stringify(checkData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // ReadableStreamから読み取り
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.handleStreamEvent(data, onProgress, onComplete, onError);
                        } catch (e) {
                            console.error('JSONパースエラー:', e);
                        }
                    }
                }
            }
            
        } catch (error) {
            console.error('ストリーミング接続エラー:', error);
            onError(error);
            
            // フォールバック: 通常のAPIを使用
            this.fallbackToNormalAPI(checkData, onComplete, onError);
        }
    }
    
    /**
     * ストリームイベントを処理
     * @param {Object} data - イベントデータ
     * @param {Function} onProgress - 進捗コールバック
     * @param {Function} onComplete - 完了コールバック
     * @param {Function} onError - エラーコールバック
     */
    handleStreamEvent(data, onProgress, onComplete, onError) {
        console.log('ストリームイベント:', data);
        
        switch (data.type) {
            case 'start':
                onProgress({
                    step: 'start',
                    message: data.message,
                    progress: 10
                });
                break;
                
            case 'cache_hit':
                onProgress({
                    step: 'cache',
                    message: data.message,
                    progress: 50
                });
                break;
                
            case 'csv_check':
                onProgress({
                    step: 'csv',
                    message: data.message,
                    progress: 30
                });
                break;
                
            case 'ng_words_found':
                onProgress({
                    step: 'ng_words',
                    message: `${data.words.length}個のNG表現を検出`,
                    progress: 40,
                    data: data.words
                });
                break;
                
            case 'ai_check':
                onProgress({
                    step: 'ai',
                    message: data.message,
                    progress: 60
                });
                break;
                
            case 'complete':
                onProgress({
                    step: 'complete',
                    message: '分析が完了しました',
                    progress: 100
                });
                onComplete(data.result);
                break;
                
            case 'error':
                onError(new Error(data.message));
                break;
        }
    }
    
    /**
     * 通常のAPIにフォールバック
     * @param {Object} checkData - チェックデータ
     * @param {Function} onComplete - 完了コールバック
     * @param {Function} onError - エラーコールバック
     */
    async fallbackToNormalAPI(checkData, onComplete, onError) {
        console.log('通常のAPIにフォールバック');
        
        try {
            const result = await window.yakkiApi.checkText(
                checkData.text,
                checkData.category,
                checkData.type,
                checkData.special_points
            );
            onComplete(result);
        } catch (error) {
            onError(error);
        }
    }
    
    /**
     * 進捗表示UIを更新
     * @param {Object} progress - 進捗情報
     */
    updateProgressUI(progress) {
        const progressContainer = document.getElementById('streaming-progress');
        if (!progressContainer) {
            // 進捗表示コンテナを作成
            const container = document.createElement('div');
            container.id = 'streaming-progress';
            container.className = 'streaming-progress';
            container.innerHTML = `
                <div class="progress-header">
                    <h4>分析中...</h4>
                    <span class="progress-percentage">${progress.progress}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progress.progress}%"></div>
                </div>
                <p class="progress-message">${progress.message}</p>
                <div class="progress-steps"></div>
            `;
            
            const resultArea = document.getElementById('result-area');
            resultArea.insertBefore(container, resultArea.firstChild);
        } else {
            // 既存のコンテナを更新
            progressContainer.querySelector('.progress-percentage').textContent = `${progress.progress}%`;
            progressContainer.querySelector('.progress-fill').style.width = `${progress.progress}%`;
            progressContainer.querySelector('.progress-message').textContent = progress.message;
            
            // ステップ表示を更新
            if (progress.data && progress.step === 'ng_words') {
                const stepsContainer = progressContainer.querySelector('.progress-steps');
                const ngWordsHtml = progress.data.map(word => 
                    `<span class="detected-word">${word.word}</span>`
                ).join('');
                stepsContainer.innerHTML = `<div class="ng-words-preview">検出: ${ngWordsHtml}</div>`;
            }
        }
        
        // 完了時は進捗表示を削除
        if (progress.step === 'complete') {
            setTimeout(() => {
                progressContainer.remove();
            }, 1000);
        }
    }
    
    /**
     * 接続を閉じる
     */
    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

// グローバルに公開
window.streamingClient = new StreamingClient();

console.log('薬機法リスクチェッカー streaming.js 読み込み完了');