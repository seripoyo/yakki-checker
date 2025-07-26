#!/usr/bin/env python3
"""
Claude APIキー設定用スクリプト
"""

import os
import sys

def set_api_key():
    """新しいAPIキーを.envファイルに設定"""
    
    # APIキーの入力を求める
    print("=" * 60)
    print("Claude API キー設定")
    print("=" * 60)
    print("新しいClaude APIキーを入力してください:")
    print("(Anthropic Console: https://console.anthropic.com/ で取得)")
    print()
    
    api_key = input("Claude API Key: ").strip()
    
    if not api_key:
        print("❌ APIキーが入力されていません。")
        return False
    
    if not api_key.startswith('sk-ant-'):
        print("❌ 有効なClaude APIキーの形式ではありません。")
        print("   正しい形式: sk-ant-api03-xxxxxxxx")
        return False
    
    # .envファイルの更新
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    
    try:
        # 既存の.envファイルを読み込み
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # APIキーの行を更新
        updated_lines = []
        found_api_key = False
        
        for line in lines:
            if line.startswith('CLAUDE_API_KEY='):
                updated_lines.append(f'CLAUDE_API_KEY={api_key}\n')
                found_api_key = True
            else:
                updated_lines.append(line)
        
        # APIキーの行が見つからない場合は追加
        if not found_api_key:
            updated_lines.append(f'CLAUDE_API_KEY={api_key}\n')
        
        # .envファイルに書き込み
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        print("✅ APIキーが正常に設定されました。")
        print("🔄 バックエンドを再起動してください。")
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return False

if __name__ == "__main__":
    set_api_key()