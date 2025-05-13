import os
from typing import Optional


BASE_SAFE_DIR = os.path.abspath("./")  # 可以根据需要修改这个路径
if not os.path.exists(BASE_SAFE_DIR):
    os.makedirs(BASE_SAFE_DIR)

def _is_safe_path(path: str) -> bool:
    """检查路径是否在安全目录内"""
    requested_path = os.path.abspath(path)
    common_path = os.path.commonpath([requested_path, BASE_SAFE_DIR])
    return common_path == BASE_SAFE_DIR

def _get_safe_path(path: str) -> Optional[str]:
    """获取安全路径，如果不安全则返回None"""
    if _is_safe_path(path):
        return os.path.abspath(path)
    return None

def read_file(file_name: str) -> str:
    try:
        safe_path = _get_safe_path(file_name)
        if not safe_path:
            return "错误：尝试访问安全目录外的文件"
            
        with open(safe_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "文件不存在"
    except Exception as e:
        return f"读取文件时发生错误: {str(e)}"

def list_directory(directory: str) -> str:
    try:
        safe_path = _get_safe_path(directory)
        if not safe_path:
            return "错误：尝试访问安全目录外的路径"
            
        items = os.listdir(safe_path)
        return "\n".join(items) if items else f"目录{directory}为空"
    except FileNotFoundError:
        return f"目录{directory}不存在"
    except Exception as e:
        return f"列出目录时发生错误: {str(e)}"
    
def create_file(file_name: str, file_content: str) -> str:
    try:
        safe_path = _get_safe_path(file_name)
        if not safe_path:
            return "错误：尝试在安全目录外创建文件"
            
        # 确保目录存在
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'w', encoding='utf-8') as file:
            file.write(file_content)
        return "文件创建成功"
    except Exception as e:
        return f"创建文件时发生错误: {str(e)}"
    
def delete_file(file_path: str) -> str: 
    try:
        safe_path = _get_safe_path(file_path)
        if not safe_path:
            return "错误：尝试删除安全目录外的文件"
            
        os.remove(safe_path)
        return "文件删除成功"
    except FileNotFoundError:
        return f"文件{file_path}不存在"
    except Exception as e:
        return f"删除文件时发生错误: {str(e)}"
    
def create_directory(directory_path: str) -> str:
    try:
        safe_path = _get_safe_path(directory_path)
        if not safe_path:
            return "错误：尝试在安全目录外创建目录"
            
        os.makedirs(safe_path, exist_ok=True)
        return f"目录{directory_path}创建成功"
    except Exception as e:
        return f"目录{directory_path}创建出错：{str(e)}"



FILE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "文件名",
                    },
                },
                "required": ["file_name"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出指定目录下的所有文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目录路径",
                    },
                },
                "required": ["directory"],
            },
            
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "创建一个新文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "文件名",
                    },
                    "file_content": {
                        "type": "string",
                        "description": "文件内容",
                    },
                },
                "required": ["file_name", "file_content"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除一个文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                },
                "required": ["file_path"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "创建一个目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "目录路径",
                    },
                },
                "required": ["directory_path"],
            },
        }
    }

]


FILE_FUNCTIONS = {
    "read_file": read_file,
    "list_directory": list_directory,
    "create_file": create_file,
    "delete_file": delete_file,
    "create_directory": create_directory,
}