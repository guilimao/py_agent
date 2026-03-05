import os
import base64
import mimetypes
from typing import Union, Dict, List, Any


def read_image(image_path: str) -> Dict[str, Any]:
    """
    读取一个图像文件，将其编码为base64格式返回
    
    Args:
        image_path: 图像文件的路径
        
    Returns:
        包含图像信息的字典，格式为:
        {
            "type": "image",
            "data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...",
            "mime_type": "image/jpeg",
            "filename": "example.jpg"
        }
        如果读取失败，返回包含错误信息的字典:
        {
            "type": "error",
            "message": "错误信息"
        }
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(image_path):
            return {
                "type": "error",
                "message": f"图像文件不存在: {image_path}"
            }
        
        # 检查是否为文件
        if not os.path.isfile(image_path):
            return {
                "type": "error",
                "message": f"路径不是文件: {image_path}"
            }
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            # 根据扩展名确定MIME类型
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                '.tiff': 'image/tiff',
                '.svg': 'image/svg+xml'
            }
            mime_type = mime_map.get(ext, 'image/jpeg')
        
        # 检查是否为支持的图像类型
        if not mime_type.startswith('image/'):
            return {
                "type": "error",
                "message": f"不支持的文件类型: {mime_type}，请提供图像文件"
            }
        
        # 读取并编码图像
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            encoded_string = base64.b64encode(image_data).decode('utf-8')
        
        # 构建data URL
        data_url = f"data:{mime_type};base64,{encoded_string}"
        
        # 获取文件名
        filename = os.path.basename(image_path)
        
        return {
            "type": "image",
            "data": data_url,
            "mime_type": mime_type,
            "filename": filename,
            "size": len(image_data)
        }
        
    except Exception as e:
        return {
            "type": "error",
            "message": f"读取图像失败: {str(e)}"
        }


# 工具定义（供LLM识别）
IMAGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_image",
            "description": "读取一个图像文件，输入图像路径，将图像编码为base64格式返回，可用于分析图像内容。支持jpg、jpeg、png、gif、bmp、webp、tiff、svg等格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "图像文件的路径"
                    }
                },
                "required": ["image_path"],
            },
        }
    }
]

# 工具函数映射（供Agent执行）
IMAGE_FUNCTIONS = {
    "read_image": read_image
}
