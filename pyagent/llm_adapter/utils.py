"""
LLM适配器工具函数

提供各种实用的工具函数，用于参数转换、格式验证等。
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse


def validate_openai_messages(messages: List[Dict[str, Any]]) -> bool:
    """
    验证OpenAI格式的消息列表
    
    Args:
        messages: 消息列表
        
    Returns:
        如果格式有效返回True，否则返回False
    """
    if not isinstance(messages, list):
        return False
    
    for message in messages:
        if not isinstance(message, dict):
            return False
        
        # 检查必需字段
        if 'role' not in message or 'content' not in message:
            return False
        
        # 验证role字段
        if message['role'] not in ['system', 'user', 'assistant', 'tool']:
            return False
        
        # 验证content字段
        content = message['content']
        if content is None:
            continue
        
        if isinstance(content, str):
            continue
        elif isinstance(content, list):
            # 处理多模态内容
            for part in content:
                if not isinstance(part, dict):
                    return False
                if 'type' not in part:
                    return False
                if part['type'] not in ['text', 'image_url']:
                    return False
        else:
            return False
    
    return True


def convert_image_url_to_base64(image_url: str) -> Optional[Dict[str, str]]:
    """
    将图像URL转换为base64格式
    
    Args:
        image_url: 图像URL，可以是data URL或普通URL
        
    Returns:
        包含media_type和base64数据的字典，如果转换失败返回None
    """
    # 处理data URL
    if image_url.startswith('data:image'):
        match = re.match(r'data:image/(\w+);base64,(.+)', image_url)
        if match:
            return {
                'media_type': f"image/{match.group(1)}",
                'base64_data': match.group(2)
            }
    
    # TODO: 处理普通URL（需要下载图像并转换为base64）
    # 目前只支持data URL格式
    return None


def extract_model_info(model_name: str) -> Dict[str, str]:
    """
    从模型名称中提取信息
    
    Args:
        model_name: 模型名称
        
    Returns:
        包含模型信息的字典
    """
    model_name = model_name.lower()
    
    # 提供商识别
    provider = 'unknown'
    if 'gpt' in model_name or 'openai' in model_name:
        provider = 'openai'
    elif 'claude' in model_name or 'anthropic' in model_name:
        provider = 'anthropic'
    elif 'deepseek' in model_name:
        provider = 'deepseek'
    elif 'moonshot' in model_name:
        provider = 'moonshot'
    elif 'glm' in model_name or 'zhipu' in model_name:
        provider = 'zhipu'
    
    # 模型类型识别
    model_type = 'unknown'
    if 'gpt-4' in model_name:
        model_type = 'gpt-4'
    elif 'gpt-3.5' in model_name:
        model_type = 'gpt-3.5'
    elif 'claude-3' in model_name:
        model_type = 'claude-3'
    elif 'claude-2' in model_name:
        model_type = 'claude-2'
    
    return {
        'provider': provider,
        'model_type': model_type,
        'original_name': model_name
    }


def validate_tool_definitions(tools: List[Dict[str, Any]]) -> bool:
    """
    验证工具定义格式
    
    Args:
        tools: 工具定义列表
        
    Returns:
        如果格式有效返回True，否则返回False
    """
    if not isinstance(tools, list):
        return False
    
    for tool in tools:
        if not isinstance(tool, dict):
            return False
        
        # 检查必需字段
        if 'type' not in tool or tool['type'] != 'function':
            return False
        
        if 'function' not in tool:
            return False
        
        function_def = tool['function']
        if not isinstance(function_def, dict):
            return False
        
        # 检查函数定义字段
        required_fields = ['name', 'description', 'parameters']
        for field in required_fields:
            if field not in function_def:
                return False
        
        # 验证参数定义
        parameters = function_def['parameters']
        if not isinstance(parameters, dict):
            return False
        
        if 'type' not in parameters or parameters['type'] != 'object':
            return False
        
        if 'properties' not in parameters:
            return False
    
    return True


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全的JSON解析
    
    Args:
        text: JSON字符串
        default: 解析失败时的默认值
        
    Returns:
        解析后的对象，如果解析失败返回默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀字符串
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_error_message(error: Exception, include_traceback: bool = False) -> str:
    """
    格式化错误消息
    
    Args:
        error: 异常对象
        include_traceback: 是否包含堆栈跟踪
        
    Returns:
        格式化的错误消息
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    if include_traceback:
        import traceback
        tb = traceback.format_exc()
        return f"{error_type}: {error_message}\n\n堆栈跟踪:\n{tb}"
    
    return f"{error_type}: {error_message}"