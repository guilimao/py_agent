"""
LLM适配器的异常定义

定义了LLM适配器模块中使用的各种异常类。
"""


class LLMException(Exception):
    """LLM调用相关的异常基类"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        """
        初始化LLM异常
        
        Args:
            message: 异常消息
            error_code: 错误代码（可选）
            details: 额外的错误详情（可选）
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ProviderNotSupportedException(LLMException):
    """提供商不支持的异常"""
    pass


class AdapterCreationException(LLMException):
    """适配器创建失败的异常"""
    pass


class ResponseConversionException(LLMException):
    """响应转换失败的异常"""
    pass


class ParameterConversionException(LLMException):
    """参数转换失败的异常"""
    pass