"""
LLM 客户端模块 - 支持 DeepSeek 和其他 LLM API

功能：
- 多模型支持
- 重试机制
- Token 统计和费用估算
"""

import os
import time
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMResponse:
    """LLM 响应结构"""

    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str


class DeepSeekClient:
    """DeepSeek API 客户端"""

    BASE_URL = "https://api.deepseek.com/v1"

    # 模型定价 (每百万 token，单位：元)
    PRICING = {
        "deepseek-chat": {"input": 1.0, "output": 2.0},
        "deepseek-reasoner": {"input": 4.0, "output": 16.0},
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 统计
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

    def chat(
        self,
        prompt: str,
        system_prompt: str = "你是一个专业的内容创作助手。",
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        retry_times: int = 3,
        retry_delay: float = 2.0,
    ) -> LLMResponse:
        """
        调用 DeepSeek Chat API

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            model: 模型名称 (deepseek-chat / deepseek-reasoner)
            temperature: 温度参数 (0-2)
            max_tokens: 最大输出 token 数
            retry_times: 重试次数
            retry_delay: 重试间隔（秒）

        Returns:
            LLMResponse 对象
        """
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_error = None
        for attempt in range(retry_times):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        f"{self.BASE_URL}/chat/completions",
                        headers=self.headers,
                        json=payload,
                    )
                    response.raise_for_status()

                result = response.json()
                choice = result["choices"][0]
                usage = result.get("usage", {})

                # 更新统计
                self.total_input_tokens += usage.get("prompt_tokens", 0)
                self.total_output_tokens += usage.get("completion_tokens", 0)
                self.total_requests += 1

                return LLMResponse(
                    content=choice["message"]["content"],
                    model=model,
                    usage=usage,
                    finish_reason=choice.get("finish_reason", "unknown"),
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    # Rate limit，等待更长时间
                    wait_time = retry_delay * (attempt + 1) * 2
                    print(f"  [!] Rate limit，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                elif e.response.status_code >= 500:
                    # 服务器错误，重试
                    print(f"  [!] 服务器错误，{retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    raise
            except Exception as e:
                last_error = e
                if attempt < retry_times - 1:
                    print(f"  [!] 请求失败: {e}，{retry_delay} 秒后重试...")
                    time.sleep(retry_delay)

        raise last_error or Exception("请求失败")

    def chat_simple(
        self, prompt: str, system_prompt: str = "你是一个专业的内容创作助手。"
    ) -> str:
        """简化版调用，只返回内容字符串"""
        response = self.chat(prompt, system_prompt)
        return response.content

    def get_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_cny": self._calculate_cost(),
        }

    def _calculate_cost(self, model: str = "deepseek-chat") -> float:
        """计算估算费用（元）"""
        pricing = self.PRICING.get(model, self.PRICING["deepseek-chat"])
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 4)

    def reset_stats(self):
        """重置统计"""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0


# 全局客户端实例
_default_client: Optional[DeepSeekClient] = None


def get_client() -> DeepSeekClient:
    """获取全局客户端实例"""
    global _default_client
    if _default_client is None:
        _default_client = DeepSeekClient()
    return _default_client


def generate_content(
    prompt: str, system_prompt: str = "你是一个专业的内容创作助手。"
) -> str:
    """快速生成内容（兼容旧接口）"""
    client = get_client()
    return client.chat_simple(prompt, system_prompt)


if __name__ == "__main__":
    # 测试
    print("=== DeepSeek API 测试 ===\n")

    try:
        client = DeepSeekClient()

        # 简单测试
        response = client.chat("你好，请用一句话介绍你自己。")
        print("回复:", response.content)
        print(f"模型: {response.model}")
        print(f"Token 使用: {response.usage}")

        # 打印统计
        print("\n统计:", client.get_stats())

    except ValueError as e:
        print(f"配置错误: {e}")
    except Exception as e:
        print(f"测试失败: {e}")
