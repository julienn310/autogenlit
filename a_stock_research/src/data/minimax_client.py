"""MiniMax API客户端 - 适配AutoGen框架"""

import requests
import json
from typing import Dict, List, Optional, Any


class MiniMaxClient:
    """MiniMax API客户端，兼容OpenAI API格式"""

    def __init__(self, api_key: str, base_url: str = "https://api.minimax.chat/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "abab6.5s-chat",
        temperature: float = 0.1,
        max_tokens: int = 8000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用MiniMax聊天完成接口

        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant/system", "content": "..."}]
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            响应字典
        """
        url = f"{self.base_url}/text/chatcompletion_v2"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        payload.update(kwargs)

        response = requests.post(url, headers=self.headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()

    def create_autogen_config(self, model: str = "MiniMax-M2.7") -> Dict:
        """
        创建兼容AutoGen的LLM配置

        Returns:
            AutoGen可用的config_list配置
        """
        return {
            "config_list": [
                {
                    "model": model,
                    "api_type": "openai",
                    "base_url": self.base_url,
                    "api_key": self.api_key,
                    "price": [0, 0],  # MiniMax不收费
                }
            ],
            "temperature": 0.1,
            "max_tokens": 8000,
            "timeout": 120
        }


def create_minimax_client(api_key: str) -> MiniMaxClient:
    """工厂函数：创建MiniMax客户端"""
    return MiniMaxClient(api_key)