"""
OpenAI兼容的LLM适配器

适用于大多数OpenAI兼容的LLM提供商，提供统一的接口转换。
"""

from typing import Iterator, Any, Dict, List
import json

from .base import BaseLLMAdapter
from .models import LLMStreamResponse
from .exceptions import LLMException
from ..conversation_manager import StreamEvent
from .converters import StreamEventConverter


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """OpenAI兼容的适配器（适用于大多数提供商）"""
    
    def __init__(self, client: Any, model_name: str):
        """
        初始化OpenAI兼容适配器
        
        Args:
            client: OpenAI兼容的客户端对象
            model_name: 模型名称
        """
        self.client = client
        self.model_name = model_name
    
    def create_chat_completion(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """
        创建聊天完成，将不同SDK的响应转换为统一格式
        
        Args:
            **kwargs: 传递给底层SDK的参数
            
        Returns:
            统一的流式响应迭代器
            
        Raises:
            LLMException: 当LLM调用失败时
        """
        try:
            # 调用底层SDK的流式接口
            stream = self.client.chat.completions.create(**kwargs)
            
            for chunk in stream:
                # 创建统一的响应对象
                unified_response = LLMStreamResponse()
                
                # 处理标准字段
                if hasattr(chunk, 'choices') and chunk.choices:
                    original_choice = chunk.choices[0]
                    
                    # 设置完成原因
                    if hasattr(original_choice, 'finish_reason') and original_choice.finish_reason:
                        unified_response.set_finish_reason(original_choice.finish_reason)
                        unified_response.choices[0].finish_reason = original_choice.finish_reason
                    
                    # 处理delta内容
                    if hasattr(original_choice, 'delta'):
                        original_delta = original_choice.delta
                        
                        # 处理自然语言内容
                        if hasattr(original_delta, 'content') and original_delta.content:
                            unified_response.choices[0].delta.content = original_delta.content
                        
                        # 处理思考内容（reasoning_content）
                        if hasattr(original_delta, 'reasoning_content') and original_delta.reasoning_content:
                            unified_response.choices[0].delta.reasoning_content = original_delta.reasoning_content
                        
                        # 处理工具调用
                        if hasattr(original_delta, 'tool_calls') and original_delta.tool_calls:
                            unified_response.choices[0].delta.tool_calls = original_delta.tool_calls
                
                yield unified_response
                
        except Exception as e:
            # 将底层异常包装为统一异常
            raise LLMException(f"LLM调用失败: {str(e)}") from e
    
    def create_chat_completion_with_events(self, **kwargs) -> Iterator[StreamEvent]:
        """
        创建聊天完成，返回统一的事件流（新接口）
        
        Args:
            **kwargs: 传递给底层适配器的参数
            
        Returns:
            统一的流式事件迭代器
            
        Raises:
            LLMException: 当LLM调用失败时
        """
        try:
            # 调用底层SDK的流式接口
            stream = self.client.chat.completions.create(**kwargs)
            
            for chunk in stream:
                # 使用事件转换器转换chunk为统一事件
                event = StreamEventConverter.convert_openai_chunk(chunk)
                if event:
                    yield event
                
        except Exception as e:
            # 将底层异常包装为统一异常
            raise LLMException(f"LLM调用失败: {str(e)}") from e
        
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        return self.model_name