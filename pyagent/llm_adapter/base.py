"""
LLM适配器基类

定义了所有LLM适配器必须实现的抽象接口，确保不同提供商的适配器具有一致的行为。
"""

from abc import ABC, abstractmethod
from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import LLMStreamResponse
    from ..conversation_manager import StreamEvent


class BaseLLMAdapter(ABC):
    """LLM适配器基类"""
    
    @abstractmethod
    def create_chat_completion(self, **kwargs) -> Iterator['LLMStreamResponse']:
        """
        创建聊天完成，返回统一的流式响应
        
        Args:
            **kwargs: 传递给底层SDK的参数
            
        Returns:
            统一的流式响应迭代器
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """
        获取当前使用的模型名称
        
        Returns:
            模型名称字符串
        """
        pass
    
    def create_chat_completion_with_events(self, **kwargs) -> Iterator['StreamEvent']:
        """
        创建聊天完成，返回统一的事件流（可选实现）
        
        默认实现将流式响应转换为事件流。子类可以重写此方法以提供更优化的实现。
        
        Args:
            **kwargs: 传递给底层适配器的参数
            
        Returns:
            统一的流式事件迭代器
        """
        from .models import LLMStreamResponse
        from ..conversation_manager import StreamEvent
        
        for response in self.create_chat_completion(**kwargs):
            # 处理思考内容
            if (hasattr(response.choices[0].delta, 'reasoning_content') and 
                response.choices[0].delta.reasoning_content):
                yield StreamEvent(
                    event_type='thinking',
                    data=response.choices[0].delta.reasoning_content
                )
            
            # 处理自然语言内容
            if response.choices[0].delta.content:
                yield StreamEvent(
                    event_type='content',
                    data=response.choices[0].delta.content
                )
            
            # 处理工具调用
            if (hasattr(response.choices[0].delta, 'tool_calls') and 
                response.choices[0].delta.tool_calls):
                for tool_call in response.choices[0].delta.tool_calls:
                    yield StreamEvent(
                        event_type='tool_call',
                        data=tool_call
                    )
            
            # 处理完成事件
            if response.finish_reason:
                yield StreamEvent(
                    event_type='finish',
                    data=response.finish_reason
                )