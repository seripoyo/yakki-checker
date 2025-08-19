# リファクタリング: app.pyから薬機法チェックロジックを分離
# 変更内容: プロンプト生成、NG表現チェック、レスポンス処理を独立したサービスクラスに移動
"""
薬機法チェッカーサービスモジュール
薬機法違反チェック、プロンプト生成、結果処理のメインロジック
"""

import re
import json
import logging
import hashlib
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple

from services.claude_service import ClaudeService
from services.data_service import DataService
from models.data_models import CheckCache
from utils.cache import CacheManager
from config import Config

logger = logging.getLogger(__name__)

class YakkiChecker:
    """薬機法チェッカーメインサービス"""
    
    def __init__(self):
        self.claude_service = ClaudeService()
        self.data_service = DataService()
        self.check_cache = CheckCache(
            max_size=Config.CACHE_MAX_SIZE,
            ttl=Config.CACHE_TTL
        )
        
        # プリプロセシング用NG表現パターン
        self.ng_patterns = self._generate_ng_patterns()
    
    def check_text(self, text: str, text_type: str, category: str, 
                   special_points: str = '', medical_approval: bool = False) -> Dict[str, Any]:
        """
        薬機法チェックのメイン処理
        
        Args:
            text: チェック対象テキスト
            text_type: 文章の種類
            category: 商品カテゴリ
            special_points: 特に訴求したいポイント
            medical_approval: 医薬品・医療機器承認
        
        Returns:
            チェック結果辞書
        """
        try:
            # キャッシュチェック
            cache_key = self.check_cache.get_cache_key(
                text, category, text_type, special_points, medical_approval
            )
            
            cached_result = self.check_cache.get(cache_key)
            if cached_result:
                cached_result['response_time'] = 0.1  # キャッシュヒット時の応答時間
                cached_result['from_cache'] = True
                return cached_result
            
            # プリプロセシング（基本的なNG表現チェック）
            preprocessing_issues = self._check_ng_expressions_in_text(text)
            
            # Claude APIが利用可能かチェック
            if not self.claude_service.is_available():
                logger.warning("Claude APIが利用できません - プリプロセシング結果またはデモ応答を返します")
                if preprocessing_issues:
                    result = self._create_preprocessing_fallback_response(text, preprocessing_issues)
                else:
                    result = self.claude_service.create_demo_response(text, text_type, category, special_points)
            else:
                # Claude APIで詳細チェック
                result = self._call_claude_api_check(
                    text, text_type, category, special_points, medical_approval
                )
            
            # 結果をキャッシュに保存
            self.check_cache.set(cache_key, result)
            result['from_cache'] = False
            
            return result
            
        except Exception as e:
            logger.error(f"薬機法チェック処理でエラー: {e}")
            return self._create_fallback_response(text, f"チェック処理エラー: {str(e)}")
    
    def _call_claude_api_check(self, text: str, text_type: str, category: str, 
                              special_points: str, medical_approval: bool) -> Dict[str, Any]:
        """Claude APIを使用した詳細チェック"""
        try:
            # プロンプト生成
            system_prompt = self._create_system_prompt()
            user_prompt = self._create_user_prompt(
                text, text_type, category, special_points, medical_approval
            )
            
            # Claude API呼び出し
            api_response = self.claude_service.call_api(system_prompt, user_prompt)
            response_text = api_response['text']
            
            # レスポンス解析
            result = self.claude_service.parse_response(response_text, text)
            
            if result is None:
                logger.error("Claude APIレスポンスの解析に失敗")
                return self._create_fallback_response(text, "APIレスポンスの解析に失敗しました")
            
            # 結果の後処理
            result = self._post_process_result(result, api_response.get('model'))
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API チェック処理でエラー: {e}")
            return self._create_fallback_response(text, f"API呼び出しエラー: {str(e)}")
    
    def _create_system_prompt(self) -> str:
        """システムプロンプトを生成"""
        return '''あなたは薬機法の専門家です。与えられたテキストを薬機法の観点から詳細に分析し、問題点を特定して改善案を提案してください。

**重要な判定基準:**
1. 効果効能の表現（医薬品的効果の示唆）
2. 安全性に関する表現
3. 最大級の表現（最高、絶対など）
4. 即効性・永続性の表現
5. 医学的・科学的根拠の明示

**出力形式:**
必ずJSON形式で以下の構造を返してください：

```json
{
  "overall_risk": "高|中|低",
  "risk_counts": {
    "total": 検出総数,
    "high": 高リスク数,
    "medium": 中リスク数,
    "low": 低リスク数
  },
  "issues": [
    {
      "fragment": "問題のある表現",
      "reason": "抵触する理由の詳細説明",
      "risk_level": "高|中|低",
      "suggestions": ["代替案1", "代替案2", "代替案3"]
    }
  ],
  "rewritten_texts": {
    "conservative": {
      "text": "保守的なリライト文",
      "explanation": "この版が薬機法的に安全な理由"
    },
    "balanced": {
      "text": "バランス版リライト文",
      "explanation": "安全性と訴求力のバランスについて"
    },
    "appealing": {
      "text": "訴求力重視版リライト文",
      "explanation": "法的リスクを最小限にした理由"
    }
  }
}
```'''
    
    def _create_user_prompt(self, text: str, text_type: str, category: str, 
                           special_points: str, medical_approval: bool) -> str:
        """ユーザープロンプトを生成"""
        # データファイルの内容を取得
        all_data_content = self.data_service.load_all_data_files()
        rule_content = self.data_service.load_rule_file(text_type)
        
        # カテゴリ別ガイダンス
        category_guidance = self.data_service.get_category_guidance(category)
        text_type_guidance = self.data_service.get_text_type_guidance(text_type)
        
        prompt = f"""以下のテキストを薬機法の観点から詳細に分析してください。

**チェック対象テキスト:**
{text}

**商品カテゴリ:** {category}
**文章の種類:** {text_type}
**特に訴求したいポイント:** {special_points or 'なし'}
**医薬品・医療機器承認:** {'あり' if medical_approval else 'なし'}

**カテゴリ別ガイダンス:**
{category_guidance}

**文章種類別ガイダンス:**
{text_type_guidance}

**参考データ:**
{all_data_content}

**文章種類別ルール:**
{rule_content}

**分析要求:**
1. 薬機法違反の可能性がある表現を特定
2. 各問題のリスクレベル（高・中・低）を判定
3. 問題となる理由を具体的に説明
4. 代替表現を3つずつ提案
5. 3パターンのリライト案を作成（保守的・バランス・訴求力重視）

必ずJSON形式で回答してください。"""
        
        return prompt
    
    def _generate_ng_patterns(self) -> List[Dict[str, Any]]:
        """NG表現のパターンを生成"""
        try:
            ng_data = self.data_service.load_ng_expressions()
            if ng_data is None or ng_data.empty:
                return []
            
            patterns = []
            for _, row in ng_data.iterrows():
                if '表現' in row and pd.notna(row['表現']):
                    patterns.append({
                        'pattern': row['表現'],
                        'reason': row.get('理由', ''),
                        'risk_level': row.get('リスクレベル', '中'),
                        'alternative': row.get('代替表現', '')
                    })
            
            logger.info(f"NG表現パターン生成完了: {len(patterns)}件")
            return patterns
            
        except Exception as e:
            logger.error(f"NG表現パターン生成エラー: {e}")
            return []
    
    def _check_ng_expressions_in_text(self, text: str) -> List[Dict[str, Any]]:
        """テキスト内のNG表現をチェック"""
        issues = []
        
        try:
            for pattern_info in self.ng_patterns:
                pattern = pattern_info['pattern']
                
                # 正規表現として使用可能かチェック
                try:
                    matches = re.finditer(re.escape(pattern), text, re.IGNORECASE)
                    for match in matches:
                        issues.append({
                            'fragment': match.group(),
                            'reason': pattern_info['reason'],
                            'risk_level': pattern_info['risk_level'],
                            'suggestions': [pattern_info['alternative']] if pattern_info['alternative'] else [],
                            'start': match.start(),
                            'end': match.end()
                        })
                except re.error:
                    # 正規表現エラーの場合は単純な文字列検索
                    if pattern.lower() in text.lower():
                        issues.append({
                            'fragment': pattern,
                            'reason': pattern_info['reason'],
                            'risk_level': pattern_info['risk_level'],
                            'suggestions': [pattern_info['alternative']] if pattern_info['alternative'] else []
                        })
            
            if issues:
                logger.info(f"プリプロセシングで{len(issues)}件の問題を検出")
            
            return issues
            
        except Exception as e:
            logger.error(f"NG表現チェックエラー: {e}")
            return []
    
    def _post_process_result(self, result: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        """結果の後処理"""
        try:
            # モデル情報を追加
            if model:
                result['model_used'] = model
            
            # 統計情報の整合性チェック
            if 'issues' in result and 'risk_counts' in result:
                issues = result['issues']
                actual_counts = {'high': 0, 'medium': 0, 'low': 0}
                
                for issue in issues:
                    risk_level = issue.get('risk_level', '中')
                    if risk_level == '高':
                        actual_counts['high'] += 1
                    elif risk_level == '中':
                        actual_counts['medium'] += 1
                    elif risk_level == '低':
                        actual_counts['low'] += 1
                
                # 統計情報を修正
                result['risk_counts'] = {
                    'total': len(issues),
                    'high': actual_counts['high'],
                    'medium': actual_counts['medium'],
                    'low': actual_counts['low']
                }
            
            return result
            
        except Exception as e:
            logger.error(f"結果後処理エラー: {e}")
            return result
    
    def _create_preprocessing_fallback_response(self, text: str, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """プリプロセシング結果をベースにしたフォールバック応答"""
        risk_counts = {'high': 0, 'medium': 0, 'low': 0}
        
        for issue in issues:
            risk_level = issue.get('risk_level', '中')
            if risk_level == '高':
                risk_counts['high'] += 1
            elif risk_level == '中':
                risk_counts['medium'] += 1
            else:
                risk_counts['low'] += 1
        
        # 総合リスクレベルの判定
        if risk_counts['high'] > 0:
            overall_risk = '高'
        elif risk_counts['medium'] > 0:
            overall_risk = '中'
        else:
            overall_risk = '低'
        
        return {
            "overall_risk": overall_risk,
            "risk_counts": {
                "total": len(issues),
                "high": risk_counts['high'],
                "medium": risk_counts['medium'],
                "low": risk_counts['low']
            },
            "issues": issues,
            "rewritten_texts": {
                "conservative": {
                    "text": text,
                    "explanation": "プリプロセシング結果のため、詳細なリライトは提供されません。"
                },
                "balanced": {
                    "text": text,
                    "explanation": "プリプロセシング結果のため、詳細なリライトは提供されません。"
                },
                "appealing": {
                    "text": text,
                    "explanation": "プリプロセシング結果のため、詳細なリライトは提供されません。"
                }
            },
            "is_preprocessing": True
        }
    
    def _create_fallback_response(self, text: str, error_message: str) -> Dict[str, Any]:
        """エラー時のフォールバック応答"""
        return {
            "overall_risk": "不明",
            "risk_counts": {"total": 0, "high": 0, "medium": 0, "low": 0},
            "issues": [],
            "rewritten_texts": {
                "conservative": {
                    "text": text,
                    "explanation": f"チェック処理中にエラーが発生しました: {error_message}"
                },
                "balanced": {
                    "text": text,
                    "explanation": f"チェック処理中にエラーが発生しました: {error_message}"
                },
                "appealing": {
                    "text": text,
                    "explanation": f"チェック処理中にエラーが発生しました: {error_message}"
                }
            },
            "error": error_message,
            "is_fallback": True
        }
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self.check_cache.clear()
        self.data_service.invalidate_cache()
        logger.info("全キャッシュをクリアしました")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        return {
            'check_cache': {
                'hit_rate': self.check_cache.get_hit_rate(),
                'size': len(self.check_cache.cache),
                'max_size': self.check_cache.max_size
            },
            'data_service': self.data_service.get_cache_status(),
            'claude_service_available': self.claude_service.is_available()
        }