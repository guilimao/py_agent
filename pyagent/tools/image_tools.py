import os
import base64
import mimetypes
from typing import Union, Dict, List, Any

# 支持的图像格式扩展名集合
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}

# 扩展名到MIME类型的映射（作为 mimetypes 的补充）
EXT_TO_MIME = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.webp': 'image/webp',
    '.tiff': 'image/tiff',
    '.svg': 'image/svg+xml',
}


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

        # 获取文件扩展名
        ext = os.path.splitext(image_path)[1].lower()

        # 类型检查：首先通过扩展名判断是否为支持的图像格式
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            # 再尝试通过 MIME 类型判断
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                return {
                    "type": "error",
                    "message": f"格式不支持: 文件扩展名 '{ext}' 不是支持的图像格式，支持格式: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
                }

        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = EXT_TO_MIME.get(ext, 'image/jpeg')

        # 双重确认：MIME类型必须是 image/
        if not mime_type.startswith('image/'):
            return {
                "type": "error",
                "message": f"格式不支持: MIME类型 '{mime_type}' 不是图像格式，支持格式: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
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
