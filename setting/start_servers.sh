#!/bin/bash

# 薬機法リスクチェッカー サーバー起動スクリプト
# フロントエンドとバックエンドを同時に起動

echo "============================================================"
echo "薬機法リスクチェッカー サーバー起動中..."
echo "============================================================"

# プロジェクトルートディレクトリを取得（settingディレクトリからプロジェクトルートへ）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 既存のサーバープロセスを停止
echo "既存のサーバープロセスを確認・停止中..."
pkill -f "python3 -m http.server" 2>/dev/null || true
pkill -f "python3 app.py" 2>/dev/null || true
sleep 2

echo "1. バックエンドサーバー起動中..."
cd setting/backend

# 環境変数の確認
if [ ! -f ".env" ]; then
    echo "❌ .envファイルが見つかりません"
    echo "backend/.env.example を backend/.env にコピーして設定してください"
    exit 1
fi

# バックエンドをバックグラウンドで起動
nohup python3 app.py > ../../backend.log 2>&1 &
BACKEND_PID=$!
echo "   バックエンド PID: $BACKEND_PID"

# バックエンドの起動確認（最大30秒待機）
echo "   バックエンド起動確認中..."
for i in {1..30}; do
    if curl -s http://localhost:5000/ > /dev/null 2>&1; then
        echo "   ✅ バックエンドサーバー起動完了: http://localhost:5000"
        break
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "2. フロントエンドサーバー起動中..."
cd ../setting/frontend

# フロントエンドをバックグラウンドで起動
nohup python3 -m http.server 8080 > ../../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   フロントエンド PID: $FRONTEND_PID"

# フロントエンドの起動確認（最大10秒待機）
echo "   フロントエンド起動確認中..."
for i in {1..10}; do
    if curl -s http://localhost:8080/ > /dev/null 2>&1; then
        echo "   ✅ フロントエンドサーバー起動完了: http://localhost:8080"
        break
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "============================================================"
echo "🎉 薬機法リスクチェッカー 起動完了!"
echo "============================================================"
echo "📱 フロントエンド: http://localhost:8080"
echo "🔧 バックエンド:   http://localhost:5000"
echo ""
echo "📊 サーバー状況:"
echo "   バックエンド PID: $BACKEND_PID"
echo "   フロントエンド PID: $FRONTEND_PID"
echo ""
echo "📋 使用方法:"
echo "   1. ブラウザで http://localhost:8080 にアクセス"
echo "   2. 薬機法チェック機能を試す"
echo "   3. ガイド機能を確認"
echo ""
echo "🛑 サーバー停止方法:"
echo "   ./stop_servers.sh を実行"
echo "   または: pkill -f 'python3 app.py' && pkill -f 'python3 -m http.server'"
echo ""
echo "📝 ログ確認:"
echo "   バックエンド: tail -f backend.log"
echo "   フロントエンド: tail -f frontend.log"
echo "============================================================"

# PIDs をファイルに保存（停止用）
echo "$BACKEND_PID" > ../../backend.pid
echo "$FRONTEND_PID" > ../../frontend.pid

echo "サーバーがバックグラウンドで動作中です。"
echo "ターミナルを閉じてもサーバーは継続動作します。"