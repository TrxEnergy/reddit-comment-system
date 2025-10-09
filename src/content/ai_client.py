"""
M4内容工厂 - AI客户端
提供统一的AI生成接口，支持OpenAI和Anthropic
"""

import asyncio
from typing import List, Optional
from abc import ABC, abstractmethod

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class BaseAIClient(ABC):
    """AI客户端抽象基类"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.9,
        max_tokens: int = 500,
        n: int = 1
    ) -> List[str]:
        """
        生成文本

        Args:
            prompt: 提示词
            temperature: 生成温度
            max_tokens: 最大token数
            n: 生成数量

        Returns:
            生成的文本列表
        """
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI客户端"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        初始化OpenAI客户端

        Args:
            api_key: API密钥
            model: 模型名称
        """
        self.api_key = api_key
        self.model = model

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            raise

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.9,
        max_tokens: int = 500,
        n: int = 1
    ) -> List[str]:
        """生成文本（OpenAI）"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful Reddit community member."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                n=n
            )

            results = [choice.message.content for choice in response.choices]

            logger.debug(
                "OpenAI generation completed",
                model=self.model,
                variants=len(results)
            )

            return results

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise


class AnthropicClient(BaseAIClient):
    """Anthropic客户端"""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        初始化Anthropic客户端

        Args:
            api_key: API密钥
            model: 模型名称
        """
        self.api_key = api_key
        self.model = model

        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=api_key)
        except ImportError:
            logger.error("anthropic package not installed. Run: pip install anthropic")
            raise

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.9,
        max_tokens: int = 500,
        n: int = 1
    ) -> List[str]:
        """生成文本（Anthropic）"""
        results = []

        try:
            # Anthropic不支持n参数，需要多次调用
            for _ in range(n):
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                text = response.content[0].text
                results.append(text)

            logger.debug(
                "Anthropic generation completed",
                model=self.model,
                variants=len(results)
            )

            return results

        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise


class AIClient:
    """
    统一AI客户端
    根据配置自动选择OpenAI或Anthropic
    """

    def __init__(self):
        """从配置初始化AI客户端"""
        provider = settings.ai.provider.lower()
        api_key = settings.ai.api_key
        model = settings.ai.model

        if provider == "openai":
            self.client = OpenAIClient(api_key, model)
        elif provider == "anthropic":
            self.client = AnthropicClient(api_key, model)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        logger.info(f"Initialized AI client: {provider} ({model})")

    async def generate_with_retry(
        self,
        prompt: str,
        temperature: float = 0.9,
        max_tokens: int = 500,
        n: int = 1,
        max_retries: int = 2,
        timeout: int = 15
    ) -> List[str]:
        """
        生成文本（含重试和超时）

        Args:
            prompt: 提示词
            temperature: 生成温度
            max_tokens: 最大token数
            n: 生成数量
            max_retries: 最大重试次数
            timeout: 超时时间（秒）

        Returns:
            生成的文本列表

        Raises:
            Exception: 重试耗尽后仍失败
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # 使用asyncio.wait_for添加超时控制
                results = await asyncio.wait_for(
                    self.client.generate(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        n=n
                    ),
                    timeout=timeout
                )

                return results

            except asyncio.TimeoutError:
                last_error = "Timeout"
                logger.warning(
                    f"AI generation timeout (attempt {attempt + 1}/{max_retries + 1})"
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"AI generation failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )

            # 重试前等待
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # 指数退避

        # 重试耗尽
        raise Exception(f"AI generation failed after {max_retries + 1} attempts: {last_error}")

    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        n: int = 1
    ) -> List[str]:
        """
        生成文本（使用配置默认值）

        Args:
            prompt: 提示词
            temperature: 生成温度（可选，使用配置默认值）
            max_tokens: 最大token数（可选，使用配置默认值）
            n: 生成数量

        Returns:
            生成的文本列表
        """
        temp = temperature if temperature is not None else settings.ai.temperature
        tokens = max_tokens if max_tokens is not None else settings.ai.max_tokens

        return await self.generate_with_retry(
            prompt=prompt,
            temperature=temp,
            max_tokens=tokens,
            n=n
        )
