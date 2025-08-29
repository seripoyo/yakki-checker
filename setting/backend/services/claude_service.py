# リファクタリング: app.pyからClaude API関連機能を分離
# 変更内容: Claude APIの呼び出し、レスポンス処理、非同期化準備を独立したサービスクラスに移動
"""
Claude APIサービスモジュール
Anthropic Claude APIとの通信とレスポンス処理を管理
"""

import json
import re
import logging
import anthropic
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio

from config import Config

logger = logging.getLogger(__name__)

class ClaudeService:
    """Claude APIサービスクラス"""
    
    def __init__(self):
        self.client = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialize_client()
    
    def _initialize_client(self):
        """Claude APIクライアントを初期化"""
        try:
            if Config.CLAUDE_API_KEY:
                self.client = anthropic.Anthropic(
                    api_key=Config.CLAUDE_API_KEY
                )
                logger.info("Claude APIクライアント初期化完了")
            else:
                logger.warning("Claude APIキーが設定されていません")
        except Exception as e:
            logger.error(f"Claude APIクライアント初期化失敗: {e}")
    
    def is_available(self) -> bool:
        """Claude APIが利用可能かチェック"""
        return self.client is not None
    
    def call_api(self, system_prompt: str, user_prompt: str, 
                 model: str = None, max_tokens: int = None, 
                 temperature: float = None) -> Dict[str, Any]:
        """
        Claude APIを呼び出す
        
        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            model: 使用するモデル（デフォルト：設定値）
            max_tokens: 最大トークン数（デフォルト：設定値）
            temperature: 温度パラメータ（デフォルト：設定値）
        
        Returns:
            APIレスポンス辞書
        """
        if not self.client:
            raise Exception("Claude APIクライアントが初期化されていません")
        
        # パラメータのデフォルト値設定
        model = model or Config.CLAUDE_MODEL
        max_tokens = max_tokens or Config.CLAUDE_MAX_TOKENS
        temperature = temperature if temperature is not None else Config.CLAUDE_TEMPERATURE
        
        try:
            logger.info(f"Claude API呼び出し開始 - Model: {model}")
            
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": user_prompt
                }]
            )
            
            response_text = response.content[0].text.strip()
            logger.info(f"Claude API応答受信: {len(response_text)} characters")
            
            return {
                'text': response_text,
                'model': model,
                'usage': getattr(response, 'usage', None)
            }
            
        except anthropic.APIError as e:
            logger.error(f"Claude API エラー: {str(e)}")
            
            # 認証エラーの場合のフォールバック
            if self._is_auth_error(e):
                logger.warning("認証エラー - フォールバックモデルで再試行")
                return self._call_fallback_model(system_prompt, user_prompt)
            
            # モデル未対応の場合のフォールバック
            if self._is_model_error(e):
                logger.warning("モデルエラー - フォールバックモデルで再試行")
                return self._call_fallback_model(system_prompt, user_prompt)
            
            raise
    
    def _is_auth_error(self, error: anthropic.APIError) -> bool:
        """認証エラーかチェック"""
        error_str = str(error).lower()
        return any(phrase in error_str for phrase in [
            "authentication_error", "invalid x-api-key", "401"
        ])
    
    def _is_model_error(self, error: anthropic.APIError) -> bool:
        """モデルエラーかチェック"""
        error_str = str(error).lower()
        return any(phrase in error_str for phrase in [
            "model_not_found", "does not exist", "invalid model"
        ])
    
    def _call_fallback_model(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """フォールバックモデルでAPI呼び出し"""
        fallback_model = "claude-3-5-sonnet-20241022"
        
        try:
            response = self.client.messages.create(
                model=fallback_model,
                max_tokens=Config.CLAUDE_MAX_TOKENS,
                temperature=Config.CLAUDE_TEMPERATURE,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": user_prompt
                }]
            )
            
            response_text = response.content[0].text.strip()
            logger.info(f"フォールバック成功: {len(response_text)} characters")
            
            return {
                'text': response_text,
                'model': fallback_model,
                'usage': getattr(response, 'usage', None),
                'is_fallback': True
            }
            
        except Exception as e:
            logger.error(f"フォールバック呼び出しも失敗: {e}")
            raise
    
    async def call_api_async(self, system_prompt: str, user_prompt: str, 
                           **kwargs) -> Dict[str, Any]:
        """
        非同期でClaude APIを呼び出す
        
        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            **kwargs: その他のパラメータ
        
        Returns:
            APIレスポンス辞書
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.call_api, 
            system_prompt, 
            user_prompt, 
            kwargs.get('model'),
            kwargs.get('max_tokens'),
            kwargs.get('temperature')
        )
    
    def parse_response(self, response_text: str, original_text: str = "") -> Optional[Dict[str, Any]]:
        """
        Claude APIレスポンスを堅牢にJSON解析する
        
        Args:
            response_text: Claude APIからの応答テキスト
            original_text: 元のテキスト（フォールバック用）
        
        Returns:
            解析されたJSON辞書またはNone
        """
        try:
            # コードブロックを除去
            cleaned_text = self._clean_response_text(response_text)
            
            # JSONの解析を段階的に試行
            for parser in [
                self._parse_json_direct,
                self._parse_json_with_repair,
                self._parse_json_with_regex,
                self._parse_partial_data
            ]:
                try:
                    result = parser(cleaned_text)
                    if result and self._validate_response_structure(result):
                        return result
                except Exception as e:
                    logger.debug(f"パーサー {parser.__name__} 失敗: {e}")
                    continue
            
            logger.error("全てのJSONパーサーが失敗しました")
            return None
            
        except Exception as e:
            logger.error(f"レスポンス解析で予期しないエラー: {e}")
            return None
    
    def _clean_response_text(self, text: str) -> str:
        """レスポンステキストをクリーンアップ"""
        # コードブロックを除去
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        elif text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
        
        # 不要な改行とスペースを整理
        text = re.sub(r'\n\s*\n', '\n', text)
        text = text.strip()
        
        return text
    
    def _parse_json_direct(self, text: str) -> Optional[Dict[str, Any]]:
        """直接的なJSON解析"""
        return json.loads(text)
    
    def _parse_json_with_repair(self, text: str) -> Optional[Dict[str, Any]]:
        """JSON修復後の解析"""
        repaired = self._repair_json(text)
        return json.loads(repaired)
    
    def _parse_json_with_regex(self, text: str) -> Optional[Dict[str, Any]]:
        """正規表現を使用したJSON抽出と解析"""
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    
    def _parse_partial_data(self, text: str) -> Optional[Dict[str, Any]]:
        """部分的なデータの抽出"""
        # 最低限の構造を持つJSONを作成
        risk_level = self._extract_risk_level(text)
        issues = self._extract_issues(text)
        
        if risk_level or issues:
            return {
                "overall_risk": risk_level or "中",
                "risk_counts": {"total": len(issues), "high": 0, "medium": 0, "low": 0},
                "issues": issues,
                "rewritten_texts": {
                    "conservative": {"text": "", "explanation": ""},
                    "balanced": {"text": "", "explanation": ""},
                    "appealing": {"text": "", "explanation": ""}
                }
            }
        
        return None
    
    def _repair_json(self, text: str) -> str:
        """JSONの一般的な問題を修復"""
        # 未閉じの文字列を修正
        text = self._fix_unclosed_strings(text)
        
        # 不正なカンマを修正
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        
        # 二重引用符の問題を修正
        text = re.sub(r'""([^"]*?)""', r'"\1"', text)
        
        return text
    
    def _fix_unclosed_strings(self, text: str) -> str:
        """未閉じの文字列を修正"""
        lines = text.split('\n')
        fixed_lines = []
        
        for line in lines:
            # 未閉じの文字列を検出して修正
            quote_count = line.count('"')
            if quote_count % 2 == 1 and not line.strip().endswith('"'):
                line += '"'
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _extract_risk_level(self, text: str) -> Optional[str]:
        """テキストからリスクレベルを抽出"""
        risk_patterns = [
            r'"overall_risk":\s*"([^"]+)"',
            r'リスクレベル[：:]\s*([高中低])',
            r'総合リスク[：:]\s*([高中低])'
        ]
        
        for pattern in risk_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_issues(self, text: str) -> list:
        """テキストから問題点を抽出"""
        # 簡易的な問題抽出
        issues = []
        issue_patterns = [
            r'"fragment":\s*"([^"]+)"',
            r'"reason":\s*"([^"]+)"'
        ]
        
        # より高度な抽出ロジックをここに実装
        return issues
    
    def _validate_response_structure(self, response: Dict[str, Any]) -> bool:
        """レスポンス構造の妥当性をチェック"""
        required_keys = ['overall_risk', 'risk_counts', 'issues', 'rewritten_texts']
        return all(key in response for key in required_keys)
    
    def create_demo_response(self, text: str, text_type: str, 
                           category: str, special_points: str = "") -> Dict[str, Any]:
        """デモ用のレスポンスを生成（Claude API未利用時）"""
        return {
            "overall_risk": "低",
            "risk_counts": {"total": 0, "high": 0, "medium": 0, "low": 0},
            "issues": [],
            "rewritten_texts": {
                "conservative": {
                    "text": f"【デモモード】{text}",
                    "explanation": "Claude APIが利用できないため、デモレスポンスを表示しています。"
                },
                "balanced": {
                    "text": f"【デモモード】{text}",
                    "explanation": "Claude APIが利用できないため、デモレスポンスを表示しています。"
                },
                "appealing": {
                    "text": f"【デモモード】{text}",
                    "explanation": "Claude APIが利用できないため、デモレスポンスを表示しています。"
                }
            },
            "is_demo": True
        }