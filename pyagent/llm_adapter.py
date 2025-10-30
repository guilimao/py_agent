"""
LLM适配器模块 - 为不同提供商的SDK提供统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, Optional
import json
from .sdk_factory import SDKFactory


class LLMStreamResponse:
    """统一的流式响应对象"""
    
    def __init__(self):
        self.choices = [StreamChoice()]
        self.finish_reason = None
    
    def set_finish_reason(self, reason: str):
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


class BaseLLMAdapter(ABC):
    """LLM适配器基类"""
    
    @abstractmethod
    def create_chat_completion(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """创建聊天完成，返回统一的流式响应"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        pass


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """OpenAI兼容的适配器（适用于大多数提供商）"""
    
    def __init__(self, client, model_name: str):
        self.client = client
        self.model_name = model_name
    
    def create_chat_completion(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """创建聊天完成，将不同SDK的响应转换为统一格式"""
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
    
    def get_model_name(self) -> str:
        return self.model_name


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Claude适配器（示例，用于展示如何适配不同接口）"""
    
    def __init__(self, client, model_name: str):
        self.client = client
        self.model_name = model_name
    
    def create_chat_completion(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """将Anthropic的接口转换为统一格式"""
        # 转换消息格式（如果需要）
        messages = kwargs.get('messages', [])
        
        # 调用Anthropic的API
        try:
            # 这里需要根据Anthropic的实际API进行调整
            # 示例代码，实际需要根据具体SDK实现
            response = self.client.messages.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                max_tokens=kwargs.get('max_tokens', 4000)
            )
            
            for chunk in response:
                unified_response = LLMStreamResponse()
                
                # 根据Anthropic的响应格式进行转换
                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    unified_response.choices[0].delta.content = chunk.delta.text
                
                if hasattr(chunk, 'type') and chunk.type == 'message_stop':
                    unified_response.set_finish_reason('stop')
                
                yield unified_response
                
        except Exception as e:
            raise LLMException(f"Anthropic LLM调用失败: {str(e)}") from e
    
    def get_model_name(self) -> str:
        return self.model_name


class LLMException(Exception):
    """LLM调用相关的异常"""
    pass


class LLMAdapterFactory:
    """LLM适配器工厂类"""
    
    @staticmethod
    def create_adapter(provider: str, client: Any = None, model_name: str = None, 
                      sdk_name: str = None, api_key: str = None, base_url: str = None, 
                      **client_kwargs) -> BaseLLMAdapter:
        """
        根据提供商和SDK类型创建相应的适配器
        
        Args:
            provider: 提供商名称（如 'openai', 'doubao', 'deepseek' 等）
            client: 底层SDK客户端对象（如果提供，则直接使用）
            model_name: 模型名称（可选，如果client为None则需要提供）
            sdk_name: SDK名称（如 'openai', 'anthropic' 等），如果为None则根据提供商名称推断
            api_key: API密钥（可选，如果client为None则需要提供）
            base_url: 基础URL（可选，如果client为None则需要提供）
            **client_kwargs: 额外的客户端参数
        
        Returns:
            相应的适配器实例
        """
        provider = provider.lower()
        
        # 如果未提供client，则需要创建它
        if client is None:
            if not all([sdk_name, api_key, base_url, model_name]):
                raise ValueError("如果未提供client，则必须提供sdk_name, api_key, base_url, model_name")
            client = SDKFactory.create_client(sdk_name, api_key, base_url, **client_kwargs)
        
        # 如果未提供sdk_name，则根据提供商名称推断
        if sdk_name is None:
            if provider == 'anthropic':
                sdk_name = 'anthropic'
            else:
                sdk_name = 'openai'  # 默认使用openai兼容模式
        else:
            sdk_name = sdk_name.lower()
        
        # 根据SDK类型选择适配器
        if sdk_name == 'anthropic':
            return AnthropicAdapter(client, model_name)
        
        elif sdk_name == 'openai':
            return OpenAICompatibleAdapter(client, model_name)
        
        # 默认使用OpenAI兼容模式
        else:
            print(f"警告: 未知的SDK类型 '{sdk_name}'，使用OpenAI兼容模式")
            return OpenAICompatibleAdapter(client, model_name)


class UnifiedLLMClient:
    """统一的LLM客户端，对外提供一致的接口"""
    
    def __init__(self, adapter: BaseLLMAdapter):
        self.adapter = adapter
    
    def chat_completions_create(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """
        创建聊天完成（统一接口）
        
        Args:
            **kwargs: 传递给底层适配器的参数
        
        Returns:
            统一的流式响应迭代器
        """
        # 确保使用正确的模型名称
        if 'model' not in kwargs:
            kwargs['model'] = self.adapter.get_model_name()
        
        return self.adapter.create_chat_completion(**kwargs)
    
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        return self.adapter.get_model_name()