"""
LLM适配器工厂

根据提供商和SDK类型创建相应的适配器实例。
"""

from typing import Any, Dict, Optional

from .base import BaseLLMAdapter
from .openai_adapter import OpenAICompatibleAdapter
from .anthropic_adapter import AnthropicAdapter
from .exceptions import AdapterCreationException, ProviderNotSupportedException
from ..sdk_factory import SDKFactory


class LLMAdapterFactory:
    """LLM适配器工厂类"""
    
    # SDK到适配器的映射
    SDK_TO_ADAPTER = {
        'openai': OpenAICompatibleAdapter,
        'anthropic': AnthropicAdapter,
    }
    
    @staticmethod
    def create_adapter(
        provider: str,
        client: Any = None,
        model_name: str = None,
        sdk_name: str = None,
        api_key: str = None,
        base_url: str = None,
        **client_kwargs
    ) -> BaseLLMAdapter:
        """
        根据SDK类型创建相应的适配器
        
        Args:
            provider: 提供商名称（用于信息展示）
            client: 底层SDK客户端对象（如果提供，则直接使用）
            model_name: 模型名称（可选，如果client为None则需要提供）
            sdk_name: SDK名称（如 'openai', 'anthropic' 等），如果为None则默认为openai
            api_key: API密钥（可选，如果client为None则需要提供）
            base_url: 基础URL（可选，如果client为None则需要提供）
            **client_kwargs: 额外的客户端参数
            
        Returns:
            相应的适配器实例
            
        Raises:
            AdapterCreationException: 当适配器创建失败时
        """
        # 如果未提供client，则需要创建它
        if client is None:
            required_params = [sdk_name, api_key, base_url, model_name]
            if not all(required_params):
                missing_params = [
                    param for param, value in zip(
                        ['sdk_name', 'api_key', 'base_url', 'model_name'],
                        required_params
                    ) if not value
                ]
                raise AdapterCreationException(
                    f"如果未提供client，则必须提供: {', '.join(missing_params)}",
                    error_code="MISSING_REQUIRED_PARAMS",
                    details={"missing_params": missing_params}
                )
            
            try:
                client = SDKFactory.create_client(sdk_name, api_key, base_url, **client_kwargs)
            except Exception as e:
                raise AdapterCreationException(
                    f"创建SDK客户端失败: {str(e)}",
                    error_code="SDK_CREATION_FAILED",
                    details={"sdk_name": sdk_name, "error": str(e)}
                ) from e
        
        # 如果未提供sdk_name，则默认为openai
        if sdk_name is None:
            sdk_name = 'openai'
        else:
            sdk_name = sdk_name.lower()
        
        # 根据SDK类型选择适配器
        try:
            if sdk_name == 'anthropic':
                return AnthropicAdapter(client, model_name)
            elif sdk_name == 'openai':
                return OpenAICompatibleAdapter(client, model_name)
            else:
                # 默认使用OpenAI兼容模式
                print(f"警告: 未知的SDK类型 '{sdk_name}'，使用OpenAI兼容模式")
                return OpenAICompatibleAdapter(client, model_name)
        except Exception as e:
            raise AdapterCreationException(
                f"创建适配器失败: {str(e)}",
                error_code="ADAPTER_CREATION_FAILED",
                details={"sdk_name": sdk_name, "model_name": model_name, "error": str(e)}
            ) from e
    
    @staticmethod
    def get_supported_providers() -> Dict[str, type]:
        """
        获取支持的提供商列表
        
        Returns:
            SDK名称到适配器类的映射字典
        """
        return LLMAdapterFactory.SDK_TO_ADAPTER.copy()
    
    @staticmethod
    def is_provider_supported(provider: str) -> bool:
        """
        检查提供商是否受支持
        
        Args:
            provider: 提供商名称
            
        Returns:
            如果支持返回True，否则返回False
        """
        # 现在支持所有提供商，只要使用支持的SDK类型
        return True