"""
统一的LLM客户端

对外提供一致的LLM接口，隐藏底层不同提供商的差异。
"""

from typing import Iterator, Any, Dict, Optional

from .base import BaseLLMAdapter
from .models import LLMStreamResponse
from ..conversation_manager import StreamEvent


class UnifiedLLMClient:
    """统一的LLM客户端，对外提供一致的接口"""
    
    def __init__(self, adapter: BaseLLMAdapter):
        """
        初始化统一LLM客户端
        
        Args:
            adapter: LLM适配器实例
        """
        if not isinstance(adapter, BaseLLMAdapter):
            raise TypeError(f"adapter必须是BaseLLMAdapter的子类，当前类型: {type(adapter)}")
        
        self.adapter = adapter
    
    def chat_completions_create(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """
        创建聊天完成（统一接口）
        
        这是与OpenAI API兼容的接口，返回统一的流式响应格式。
        
        Args:
            **kwargs: 传递给底层适配器的参数，支持以下主要参数：
                - model: 模型名称（如果未提供，使用适配器的默认模型）
                - messages: 消息列表
                - stream: 是否流式输出（默认True）
                - max_tokens: 最大token数
                - temperature: 温度参数
                - tools: 工具定义列表
                - tool_choice: 工具选择策略
                
        Returns:
            统一的流式响应迭代器
            
        Raises:
            ValueError: 当参数无效时
            Exception: 当底层适配器调用失败时
        """
        # 确保使用正确的模型名称
        if 'model' not in kwargs:
            kwargs['model'] = self.adapter.get_model_name()
        
        # 验证必要参数
        if 'messages' not in kwargs:
            raise ValueError("必须提供'messages'参数")
        
        # 设置默认的流式参数
        if 'stream' not in kwargs:
            kwargs['stream'] = True
        
        return self.adapter.create_chat_completion(**kwargs)
    
    def chat_completions_create_with_events(self, **kwargs) -> Iterator[StreamEvent]:
        """
        创建聊天完成，返回统一的事件流（新接口）
        
        这是新的事件驱动接口，将响应转换为统一的事件流，
        便于处理不同类型的内容（文本、思考、工具调用等）。
        
        Args:
            **kwargs: 传递给底层适配器的参数，支持以下主要参数：
                - model: 模型名称（如果未提供，使用适配器的默认模型）
                - messages: 消息列表
                - stream: 是否流式输出（默认True）
                - max_tokens: 最大token数
                - temperature: 温度参数
                - tools: 工具定义列表
                - tool_choice: 工具选择策略
                
        Returns:
            统一的流式事件迭代器
            
        Raises:
            ValueError: 当参数无效时
            Exception: 当底层适配器调用失败时
        """
        # 确保使用正确的模型名称
        if 'model' not in kwargs:
            kwargs['model'] = self.adapter.get_model_name()
        
        # 验证必要参数
        if 'messages' not in kwargs:
            raise ValueError("必须提供'messages'参数")
        
        # 设置默认的流式参数
        if 'stream' not in kwargs:
            kwargs['stream'] = True
        
        return self.adapter.create_chat_completion_with_events(**kwargs)
    
    def get_model_name(self) -> str:
        """
        获取当前使用的模型名称
        
        Returns:
            模型名称字符串
        """
        return self.adapter.get_model_name()
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """
        获取适配器信息
        
        Returns:
            包含适配器信息的字典
        """
        return {
            'adapter_type': type(self.adapter).__name__,
            'model_name': self.get_model_name(),
            'provider': getattr(self.adapter, 'provider', 'unknown')
        }