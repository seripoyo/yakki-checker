#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
セキュリティテストスクリプト
.envファイルへの不正アクセスをテスト
"""

import os
import sys
import requests
import time
from urllib.parse import urljoin

def test_security(base_url="http://localhost:5000"):
    """
    セキュリティテストを実行
    """
    print("=" * 60)
    print("セキュリティテスト開始")
    print("=" * 60)
    
    test_results = []
    
    # テストケース1: 直接的な.envファイルアクセス
    test_cases = [
        {
            "name": ".envファイル直接アクセス",
            "paths": [
                "/.env",
                "/setting/backend/.env",
                "/backend/.env",
                "/.env.local",
                "/.env.production",
            ]
        },
        {
            "name": "ディレクトリトラバーサル攻撃",
            "paths": [
                "/../.env",
                "/../../.env",
                "/%2e%2e/.env",
                "/%2e%2e%2f.env",
                "/..%2f.env",
                "/setting/backend/../../../.env",
            ]
        },
        {
            "name": "URLエンコード攻撃",
            "paths": [
                "/%2e%65%6e%76",  # .env
                "/.%65%6e%76",    # .env
                "/setting/backend/%2e%65%6e%76",
            ]
        },
        {
            "name": "その他のセキュリティファイル",
            "paths": [
                "/.git/config",
                "/.gitignore",
                "/.htaccess",
                "/.htpasswd",
                "/config.ini",
                "/settings.py",
                "/secrets.json",
            ]
        }
    ]
    
    for test_group in test_cases:
        print(f"\n[テスト] {test_group['name']}")
        print("-" * 40)
        
        for path in test_group["paths"]:
            try:
                url = urljoin(base_url, path)
                response = requests.get(url, timeout=5)
                
                # ステータスコードをチェック
                if response.status_code in [403, 404]:
                    status = "✅ 保護されています"
                    result = "PASS"
                elif response.status_code == 200:
                    # レスポンス内容をチェック
                    content = response.text.lower()
                    if 'claude_api_key' in content or 'api_key' in content:
                        status = "❌ 危険: 環境変数が露出しています！"
                        result = "FAIL"
                    else:
                        status = "⚠️ 警告: アクセス可能ですが、機密情報は含まれていません"
                        result = "WARN"
                else:
                    status = f"⚠️ 予期しないステータス: {response.status_code}"
                    result = "WARN"
                
                print(f"  {path:<40} -> {status}")
                test_results.append({
                    "path": path,
                    "status_code": response.status_code,
                    "result": result
                })
                
            except requests.exceptions.RequestException as e:
                print(f"  {path:<40} -> ⚠️ リクエストエラー: {e}")
                test_results.append({
                    "path": path,
                    "status_code": None,
                    "result": "ERROR"
                })
            
            # サーバーに負荷をかけないよう少し待つ
            time.sleep(0.1)
    
    # APIエンドポイントのテスト
    print(f"\n[テスト] APIエンドポイントセキュリティ")
    print("-" * 40)
    
    # 不正なパラメータでのAPIアクセス
    api_test_cases = [
        {
            "endpoint": "/api/check",
            "method": "POST",
            "data": {
                "text": "../.env",
                "type": "キャッチコピー",
                "category": "化粧品"
            }
        },
        {
            "endpoint": "/api/check",
            "method": "POST",
            "data": {
                "text": "テスト",
                "type": "../../../../.env",
                "category": "化粧品"
            }
        }
    ]
    
    for test in api_test_cases:
        try:
            url = urljoin(base_url, test["endpoint"])
            response = requests.post(
                url,
                json=test["data"],
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code in [400, 403]:
                status = "✅ 不正な入力を拒否しました"
                result = "PASS"
            else:
                status = f"⚠️ ステータス: {response.status_code}"
                result = "WARN"
            
            print(f"  {test['endpoint']} (data: {test['data']['text'][:20]}...) -> {status}")
            
        except Exception as e:
            print(f"  {test['endpoint']} -> ⚠️ エラー: {e}")
    
    # 結果のサマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    pass_count = sum(1 for r in test_results if r["result"] == "PASS")
    fail_count = sum(1 for r in test_results if r["result"] == "FAIL")
    warn_count = sum(1 for r in test_results if r["result"] == "WARN")
    error_count = sum(1 for r in test_results if r["result"] == "ERROR")
    
    print(f"✅ PASS: {pass_count}")
    print(f"❌ FAIL: {fail_count}")
    print(f"⚠️ WARN: {warn_count}")
    print(f"🔧 ERROR: {error_count}")
    
    if fail_count > 0:
        print("\n⚠️ 重要: セキュリティ問題が検出されました！")
        print("環境変数ファイルが外部からアクセス可能な状態です。")
        print("至急、セキュリティ設定を確認してください。")
        return False
    else:
        print("\n✅ すべてのセキュリティテストに合格しました。")
        print("環境変数ファイルは適切に保護されています。")
        return True

if __name__ == "__main__":
    # コマンドライン引数でURLを指定可能
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    # テスト実行
    success = test_security(base_url)
    
    # 終了コード
    sys.exit(0 if success else 1)