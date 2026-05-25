"""
LLM 适配器 —— 基于 OpenAI Chat Completion API。

提供 UnifiedLLMClient，直接使用 openai SDK 进行流式聊天完成，
将响应转换为统一的 StreamEvent 流。
"""

from .client import UnifiedLLMClient

__all__ = ["UnifiedLLMClient"]
