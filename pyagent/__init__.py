"""
PyAgent - 一个使用 Python 构建的命令行 LLM 代理示例
"""

__version__ = "1.0.0"
__author__ = "Guilimao"
__email__ = "guilimao@foxmail.com"

# 导出LLM适配器相关类
from .llm_adapter import (
    BaseLLMAdapter,
    OpenAICompatibleAdapter,
    AnthropicAdapter,
    LLMAdapterFactory,
    UnifiedLLMClient,
    LLMStreamResponse,
    LLMException
)

__all__ = [
    "BaseLLMAdapter",
    "OpenAICompatibleAdapter", 
    "AnthropicAdapter",
    "LLMAdapterFactory",
    "UnifiedLLMClient",
    "LLMStreamResponse",
    "LLMException"
]