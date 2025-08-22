#!/bin/bash

# 薬機法リスクチェッカー サーバー停止スクリプト

echo "============================================================"
echo "薬機法リスクチェッカー サーバー停止中..."
echo "============================================================"

# プロジェクトルートディレクトリに移動（settingディレクトリからプロジェクトルートへ）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# PIDファイルから停止
if [ -f "backend.pid" ]; then
    BACKEND_PID=$(cat backend.pid)
    echo "バックエンドサーバー停止中 (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || true
    rm -f backend.pid
fi

if [ -f "frontend.pid" ]; then
    FRONTEND_PID=$(cat frontend.pid)
    echo "フロントエンドサーバー停止中 (PID: $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null || true
    rm -f frontend.pid
fi

# 念のため、プロセス名で検索して停止
echo "残存プロセスを確認・停止中..."
pkill -f "python3 app.py" 2>/dev/null || true
pkill -f "python3 -m http.server" 2>/dev/null || true

sleep 2

# 停止確認
echo "サーバー停止確認中..."
if pgrep -f "python3 app.py" > /dev/null; then
    echo "⚠️  バックエンドサーバーがまだ動作中です"
else
    echo "✅ バックエンドサーバー停止完了"
fi

if pgrep -f "python3 -m http.server" > /dev/null; then
    echo "⚠️  フロントエンドサーバーがまだ動作中です"
else
    echo "✅ フロントエンドサーバー停止完了"
fi

# ログファイルをクリーンアップ
if [ -f "backend.log" ]; then
    echo "バックエンドログファイルを保存: backend.log.$(date +%Y%m%d_%H%M%S)"
    mv backend.log "backend.log.$(date +%Y%m%d_%H%M%S)"
fi

if [ -f "frontend.log" ]; then
    echo "フロントエンドログファイルを保存: frontend.log.$(date +%Y%m%d_%H%M%S)"
    mv frontend.log "frontend.log.$(date +%Y%m%d_%H%M%S)"
fi

echo "============================================================"
echo "🛑 薬機法リスクチェッカー 停止完了"
echo "============================================================"