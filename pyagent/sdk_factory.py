"""
SDK工厂模块 - 负责创建各种LLM SDK的客户端实例
"""
import importlib
from typing import Any


class SDKFactory:
    """SDK客户端工厂类"""
    
    @staticmethod
    def create_client(sdk_name: str, api_key: str, base_url: str, **kwargs) -> Any:
        """
        根据SDK名称创建对应的客户端实例
        
        Args:
            sdk_name: SDK名称，如 'openai', 'anthropic' 等
            api_key: API密钥
            base_url: 基础URL
            **kwargs: 额外的客户端参数
        
        Returns:
            对应的SDK客户端实例
        
        Raises:
            ImportError: 当所需的SDK模块未安装时
            RuntimeError: 当创建客户端失败时
        """
        sdk_name = sdk_name.lower()
        
        try:
            if sdk_name == 'openai':
                return SDKFactory._create_openai_client(api_key, base_url, **kwargs)
            
            elif sdk_name == 'anthropic':
                return SDKFactory._create_anthropic_client(api_key, base_url, **kwargs)
            
            else:
                # 对于未知的SDK，尝试使用openai兼容模式
                print(f"警告: 未知的SDK类型 '{sdk_name}'，尝试使用OpenAI兼容模式")
                return SDKFactory._create_openai_client(api_key, base_url, **kwargs)
                
        except ImportError as e:
            raise ImportError(f"无法导入所需的SDK模块 '{sdk_name}'，请确保已安装对应的包: {e}")
        except Exception as e:
            raise RuntimeError(f"创建SDK客户端失败: {e}")
    
    @staticmethod
    def _create_openai_client(api_key: str, base_url: str, **kwargs) -> Any:
        """创建OpenAI客户端"""
        openai_module = importlib.import_module('openai')
        return openai_module.OpenAI(
            api_key=api_key, 
            base_url=base_url,
            **kwargs
        )
    
    @staticmethod
    def _create_anthropic_client(api_key: str, base_url: str, **kwargs) -> Any:
        """创建Anthropic客户端"""
        anthropic_module = importlib.import_module('anthropic')
        return anthropic_module.Anthropic(
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    
    @staticmethod
    def is_sdk_available(sdk_name: str) -> bool:
        """
        检查指定的SDK是否可用
        
        Args:
            sdk_name: SDK名称
            
        Returns:
            如果SDK可用返回True，否则返回False
        """
        try:
            sdk_name = sdk_name.lower()
            if sdk_name == 'openai':
                importlib.import_module('openai')
            elif sdk_name == 'anthropic':
                importlib.import_module('anthropic')
            else:
                # 未知的SDK类型，尝试作为openai导入
                importlib.import_module('openai')
            return True
        except ImportError:
            return False