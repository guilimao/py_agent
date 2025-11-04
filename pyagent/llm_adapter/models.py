"""
LLM适配器的数据模型

定义了统一的流式响应对象模型，用于标准化不同LLM提供商的响应格式。
"""

from typing import Optional, List, Dict, Any


class LLMStreamResponse:
    """统一的流式响应对象"""
    
    def __init__(self):
        self.choices = [StreamChoice()]
        self.finish_reason = None
    
    def set_finish_reason(self, reason: str):
        """设置完成原因"""
        self.finish_reason = reason


class StreamChoice:
    """流式响应的选择对象"""
    
    def __init__(self):
        self.delta = StreamDelta()
        self.finish_reason = None


class StreamDelta:
    """流式响应的增量对象"""
    
    def __init__(self):
        self.content = ""
        self.reasoning_content = ""
        self.tool_calls = None