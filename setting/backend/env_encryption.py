#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
環境変数の暗号化とセキュアな管理
"""

import os
import base64
import json
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

logger = logging.getLogger(__name__)

class SecureEnvManager:
    """
    環境変数の暗号化と管理を行うクラス
    """
    
    def __init__(self, master_key=None):
        """
        初期化
        master_key: 暗号化用のマスターキー（省略時は環境変数から取得）
        """
        if master_key:
            self.master_key = master_key
        else:
            # 環境変数からマスターキーを取得
            self.master_key = os.getenv('MASTER_KEY', self._generate_default_key())
        
        self.cipher = self._create_cipher()
        self.encrypted_vars = {}
        
    def _generate_default_key(self):
        """
        デフォルトのマスターキーを生成（本番環境では使用しないこと）
        """
        logger.warning("デフォルトのマスターキーを使用しています。本番環境では独自のキーを設定してください。")
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def _create_cipher(self):
        """
        暗号化オブジェクトを作成
        """
        # マスターキーからFernet用のキーを導出
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'yakki-checker-salt',  # 本番環境では動的なsaltを使用
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def encrypt_value(self, value):
        """
        値を暗号化
        """
        if not value:
            return None
        
        try:
            encrypted = self.cipher.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"暗号化エラー: {e}")
            return None
    
    def decrypt_value(self, encrypted_value):
        """
        暗号化された値を復号化
        """
        if not encrypted_value:
            return None
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"復号化エラー: {e}")
            return None
    
    def load_encrypted_env(self, filepath='.env.encrypted'):
        """
        暗号化された環境変数ファイルを読み込む
        """
        if not os.path.exists(filepath):
            logger.warning(f"暗号化された環境変数ファイルが見つかりません: {filepath}")
            return {}
        
        try:
            with open(filepath, 'r') as f:
                encrypted_data = json.load(f)
            
            decrypted_data = {}
            for key, encrypted_value in encrypted_data.items():
                decrypted_value = self.decrypt_value(encrypted_value)
                if decrypted_value:
                    decrypted_data[key] = decrypted_value
                    # 環境変数として設定
                    os.environ[key] = decrypted_value
            
            logger.info(f"暗号化された環境変数を読み込みました: {len(decrypted_data)}個")
            return decrypted_data
        
        except Exception as e:
            logger.error(f"暗号化された環境変数の読み込みエラー: {e}")
            return {}
    
    def save_encrypted_env(self, env_dict, filepath='.env.encrypted'):
        """
        環境変数を暗号化して保存
        """
        try:
            encrypted_data = {}
            for key, value in env_dict.items():
                encrypted_value = self.encrypt_value(value)
                if encrypted_value:
                    encrypted_data[key] = encrypted_value
            
            with open(filepath, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            # ファイル権限を600に設定
            os.chmod(filepath, 0o600)
            
            logger.info(f"環境変数を暗号化して保存しました: {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"環境変数の保存エラー: {e}")
            return False
    
    def convert_env_to_encrypted(self, env_filepath='.env', encrypted_filepath='.env.encrypted'):
        """
        既存の.envファイルを暗号化形式に変換
        """
        if not os.path.exists(env_filepath):
            logger.error(f".envファイルが見つかりません: {env_filepath}")
            return False
        
        try:
            env_dict = {}
            with open(env_filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_dict[key.strip()] = value.strip()
            
            # 暗号化して保存
            if self.save_encrypted_env(env_dict, encrypted_filepath):
                logger.info("環境変数を暗号化形式に変換しました")
                
                # 元の.envファイルを削除（オプション）
                # os.remove(env_filepath)
                # logger.info(f"元の.envファイルを削除しました: {env_filepath}")
                
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"環境変数の変換エラー: {e}")
            return False
    
    def get_secure_env(self, key, default=None):
        """
        セキュアに環境変数を取得
        """
        # まず通常の環境変数から取得
        value = os.getenv(key)
        
        # なければ暗号化された環境変数から取得
        if not value and key in self.encrypted_vars:
            value = self.encrypted_vars.get(key)
        
        # それでもなければデフォルト値を返す
        return value if value else default
    
    def validate_api_key(self, api_key):
        """
        APIキーの検証（ハッシュ比較）
        """
        if not api_key:
            return False
        
        # 保存されているハッシュと比較
        valid_key_hash = os.getenv('API_KEY_HASH')
        if not valid_key_hash:
            logger.warning("APIキーハッシュが設定されていません")
            return False
        
        # 提供されたキーをハッシュ化
        provided_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # タイミング攻撃対策として、セキュアな比較を実行
        import hmac
        return hmac.compare_digest(provided_hash, valid_key_hash)

# シングルトンインスタンス
_secure_env_manager = None

def get_secure_env_manager():
    """
    SecureEnvManagerのシングルトンインスタンスを取得
    """
    global _secure_env_manager
    if _secure_env_manager is None:
        _secure_env_manager = SecureEnvManager()
        # 暗号化された環境変数を自動的に読み込む
        _secure_env_manager.load_encrypted_env()
    return _secure_env_manager

# 便利な関数
def secure_getenv(key, default=None):
    """
    セキュアに環境変数を取得する便利関数
    """
    manager = get_secure_env_manager()
    return manager.get_secure_env(key, default)