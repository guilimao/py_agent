"""
LLM适配器模块 - 为不同提供商的SDK提供统一接口

该模块提供了统一的LLM接口，支持多种提供商（OpenAI、Anthropic等）和不同的SDK。
主要功能：
- 统一的流式响应格式
- 多种LLM提供商适配器
- 事件驱动的响应处理
- 适配器工厂模式
"""

from .models import LLMStreamResponse, StreamChoice, StreamDelta
from .base import BaseLLMAdapter
from .openai_adapter import OpenAICompatibleAdapter
from .anthropic_adapter import AnthropicAdapter
from .exceptions import LLMException
from .converters import StreamEventConverter
from .factory import LLMAdapterFactory
from .client import UnifiedLLMClient

__all__ = [
    'LLMStreamResponse',
    'StreamChoice', 
    'StreamDelta',
    'BaseLLMAdapter',
    'OpenAICompatibleAdapter',
    'AnthropicAdapter',
    'LLMException',
    'StreamEventConverter',
    'LLMAdapterFactory',
    'UnifiedLLMClient'
]