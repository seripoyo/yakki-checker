# リファクタリング: app.pyからデータ読み込み・管理機能を分離
# 変更内容: ファイル読み込み、データ変換、キャッシュ管理を独立したサービスクラスに移動
"""
データサービスモジュール
薬機法データファイルの読み込み、キャッシュ管理、フォーマット変換を担当
"""

import os
import csv
import json
import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from functools import lru_cache

from config import Config
from models.data_models import DataCache
from utils.cache import CacheManager

logger = logging.getLogger(__name__)

class DataService:
    """データ管理サービスクラス"""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.data_cache = DataCache()
        self.base_dir = os.path.dirname(__file__)
        self.data_dir = os.path.join(self.base_dir, '..', Config.DATA_DIR)
        self.rule_dir = os.path.join(self.base_dir, '..', Config.RULE_DIR)
        
        # ファイル監視の設定
        self._setup_file_watching()
    
    def _setup_file_watching(self):
        """ファイル監視を設定"""
        try:
            self.data_cache.start_file_watcher()
        except Exception as e:
            logger.error(f"ファイル監視の設定に失敗: {e}")
    
    def load_ng_expressions(self) -> Optional[pd.DataFrame]:
        """NG表現CSVファイルを読み込み"""
        cache_key = "ng_expressions_data"
        cached_data = self.cache_manager.get('data_files', cache_key)
        
        if cached_data is not None:
            return cached_data
        
        try:
            csv_file_path = os.path.join(self.data_dir, 'ng_expressions.csv')
            if not os.path.exists(csv_file_path):
                logger.warning(f"NG表現CSVファイルが見つかりません: {csv_file_path}")
                return self._create_default_ng_data()
            
            data = self._read_csv_file(csv_file_path)
            self.cache_manager.set('data_files', cache_key, data)
            
            logger.info(f"NG表現データ読み込み完了: {len(data)}件")
            return data
            
        except Exception as e:
            logger.error(f"NG表現データの読み込みに失敗: {e}")
            return self._create_default_ng_data()
    
    def _read_csv_file(self, file_path: str) -> pd.DataFrame:
        """CSVファイルを読み込む"""
        try:
            # 複数のエンコーディングを試行
            encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    data = pd.read_csv(file_path, encoding=encoding)
                    logger.debug(f"CSVファイル読み込み成功: {encoding}")
                    return data
                except UnicodeDecodeError:
                    continue
            
            # 全て失敗した場合はエラーをraise
            raise ValueError(f"CSVファイルの読み込みに失敗: {file_path}")
            
        except Exception as e:
            logger.error(f"CSVファイル読み込みエラー: {e}")
            raise
    
    def _create_default_ng_data(self) -> pd.DataFrame:
        """デフォルトのNG表現データを作成"""
        default_data = [
            {"表現": "即効性", "理由": "効果の即時性を示唆", "リスクレベル": "高", "代替表現": "お手入れ"},
            {"表現": "完治", "理由": "医学的治療効果", "リスクレベル": "高", "代替表現": "お手入れ"},
            {"表現": "美白", "理由": "薬用化粧品以外では使用不可", "リスクレベル": "中", "代替表現": "透明感"}
        ]
        
        logger.info("デフォルトNG表現データを作成しました")
        return pd.DataFrame(default_data)
    
    def load_all_data_files(self) -> str:
        """全データファイルを読み込んでテキスト結合"""
        return self.data_cache.get_cached_data_content(self._load_all_data_files_direct)
    
    def _load_all_data_files_direct(self) -> str:
        """データファイルを直接読み込み（キャッシュバイパス）"""
        try:
            all_content = []
            
            # マークダウンファイルを読み込み
            md_files = ['law1.md', 'law2.md', 'ng.md', '美容・健康関連機器.md', '医療機器.md']
            
            for filename in md_files:
                file_path = os.path.join(self.data_dir, filename)
                if os.path.exists(file_path):
                    content = self._read_text_file(file_path)
                    all_content.append(f"=== {filename} ===\n{content}\n")
            
            # CSVファイルの内容を追加
            ng_data = self.load_ng_expressions()
            if ng_data is not None:
                csv_content = self._format_csv_for_prompt(ng_data)
                all_content.append(f"=== NG表現データ ===\n{csv_content}\n")
            
            result = "\n".join(all_content)
            logger.info(f"全データファイル読み込み完了: {len(result)}文字")
            
            return result
            
        except Exception as e:
            logger.error(f"データファイル読み込みエラー: {e}")
            return ""
    
    def _read_text_file(self, file_path: str) -> str:
        """テキストファイルを読み込む"""
        try:
            # 複数のエンコーディングを試行
            encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            raise ValueError(f"テキストファイルの読み込みに失敗: {file_path}")
            
        except Exception as e:
            logger.error(f"テキストファイル読み込みエラー: {e}")
            return ""
    
    def _format_csv_for_prompt(self, df: pd.DataFrame) -> str:
        """CSVデータをプロンプト用にフォーマット"""
        if df.empty:
            return "NG表現データはありません。"
        
        try:
            formatted_rows = []
            for _, row in df.iterrows():
                row_text = " | ".join([f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])])
                formatted_rows.append(row_text)
            
            return "\n".join(formatted_rows)
            
        except Exception as e:
            logger.error(f"CSV フォーマットエラー: {e}")
            return "CSVデータの処理中にエラーが発生しました。"
    
    def load_rule_file(self, text_type: str) -> str:
        """文章種類に対応するルールファイルを読み込み"""
        return self.data_cache.get_cached_rule_content(text_type, self._load_rule_file_direct)
    
    def _load_rule_file_direct(self, text_type: str) -> str:
        """ルールファイルを直接読み込み（キャッシュバイパス）"""
        try:
            # ルールファイルのマッピング
            rule_file_mapping = {
                'キャッチコピー': 'キャッチコピー.md',
                'LP見出し・タイトル': 'LP見出し・タイトル.md',
                '商品説明文・広告文・通常テキスト': '商品説明文.md',
                'お客様の声': 'お客様の声.md'
            }
            
            filename = rule_file_mapping.get(text_type)
            if not filename:
                logger.warning(f"未知の文章種類: {text_type}")
                return ""
            
            file_path = os.path.join(self.rule_dir, filename)
            if not os.path.exists(file_path):
                logger.warning(f"ルールファイルが見つかりません: {file_path}")
                return ""
            
            content = self._read_text_file(file_path)
            logger.info(f"ルールファイル読み込み完了: {filename}")
            
            return content
            
        except Exception as e:
            logger.error(f"ルールファイル読み込みエラー: {e}")
            return ""
    
    @lru_cache(maxsize=32)
    def get_category_guidance(self, category: str) -> str:
        """商品カテゴリ別のガイダンスを取得"""
        guidance_map = {
            "化粧品": "一般化粧品として、効果効能の表現に特に注意が必要です。",
            "薬用化粧品": "医薬部外品として承認された効果効能のみ表現可能です。",
            "医薬部外品": "承認された効果効能の範囲内での表現が必要です。",
            "サプリメント・健康食品": "健康食品として、医薬品的な効果表現は禁止されています。",
            "美容機器・健康器具・その他": "機器の分類に応じた適切な表現が必要です。"
        }
        
        return guidance_map.get(category, "適切な薬機法表現を心がけてください。")
    
    @lru_cache(maxsize=32)
    def get_text_type_guidance(self, text_type: str) -> str:
        """文章種類別のガイダンスを取得"""
        guidance_map = {
            "キャッチコピー": "短く印象的でありながら、誇大表現を避ける必要があります。",
            "LP見出し・タイトル": "注目を集めつつ、薬機法に準拠した表現が重要です。",
            "商品説明文・広告文・通常テキスト": "詳細な説明において、客観的で根拠のある表現を心がけてください。",
            "お客様の声": "個人の感想として、効果を断定しない表現が必要です。"
        }
        
        return guidance_map.get(text_type, "薬機法に準拠した適切な表現を使用してください。")
    
    def invalidate_cache(self, cache_type: str = "all"):
        """キャッシュを無効化"""
        if cache_type == "all":
            self.cache_manager.invalidate()
            self.data_cache.invalidate_cache()
        elif cache_type == "data":
            self.cache_manager.invalidate('data_files')
            self.data_cache.invalidate_cache('data')
        elif cache_type == "rule":
            self.cache_manager.invalidate('rule_files')
            self.data_cache.invalidate_cache('rule')
        
        logger.info(f"キャッシュ無効化完了: {cache_type}")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        return {
            'cache_manager_stats': self.cache_manager.get_stats(),
            'file_watcher_status': 'active' if self.data_cache.observer else 'inactive',
            'data_dir': self.data_dir,
            'rule_dir': self.rule_dir
        }