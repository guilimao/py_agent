import os
import json
from typing import Optional, List
import shutil

# 从配置文件读取安全目录列表（支持多个安全目录）
def _get_allowed_directories() -> List[str]:
    """读取允许的安全目录列表（从config/allowed_directories.json）"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "allowed_directories.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            allowed_dirs = json.load(f)  # 格式应为["/dir1", "/dir2", ...]
            # 转换为绝对路径（避免相对路径问题）
            return [os.path.abspath(dir_path) for dir_path in allowed_dirs]
    except FileNotFoundError:
        return [os.path.abspath("./")]  # 配置文件不存在时默认允许当前目录
    except json.JSONDecodeError:
        return [os.path.abspath("./")]  # 配置文件格式错误时默认允许当前目录
    except Exception as e:
        return [os.path.abspath("./")]  # 其他异常时默认允许当前目录

ALLOWED_DIRECTORIES = _get_allowed_directories()  # 全局安全目录列表

def _is_safe_path(path: str) -> bool:
    """检查路径是否在任意一个安全目录内"""
    requested_path = os.path.abspath(path)
    # 遍历所有允许的安全目录，检查是否存在包含关系
    for safe_dir in ALLOWED_DIRECTORIES:
        safe_dir_abs = os.path.abspath(safe_dir)
        common_path = os.path.commonpath([requested_path, safe_dir_abs])
        if common_path == safe_dir_abs:
            return True
    return False

# 以下工具函数的安全检查逻辑已更新（基于多目录校验）
def read_file(file_name: str) -> str:
    try:
        if not _is_safe_path(file_name):
            return "错误：尝试访问安全目录外的文件"
            
        with open(os.path.abspath(file_name), 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "文件不存在"
    except Exception as e:
        return f"读取文件时发生错误: {str(e)}"

def list_directory(directory: str) -> str:
    try:
        if not _is_safe_path(directory):
            return "错误：尝试访问安全目录外的路径"
            
        items = os.listdir(os.path.abspath(directory))
        return "\n".join(items) if items else f"目录{directory}为空"
    except FileNotFoundError:
        return f"目录{directory}不存在"
    except Exception as e:
        return f"列出目录时发生错误: {str(e)}"
    
def create_file(file_name: str, file_content: str) -> str:
    try:
        if not _is_safe_path(file_name):
            return "错误：尝试在安全目录外创建文件"
            
        # 确保目录存在
        abs_path = os.path.abspath(file_name)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(file_content)
        return "文件创建成功"
    except Exception as e:
        return f"创建文件时发生错误: {str(e)}"
    
def delete_file(file_path: str) -> str: 
    try:
        if not _is_safe_path(file_path):
            return "错误：尝试删除安全目录外的文件"
            
        os.remove(os.path.abspath(file_path))
        return "文件删除成功"
    except FileNotFoundError:
        return f"文件{file_path}不存在"
    except Exception as e:
        return f"删除文件时发生错误: {str(e)}"
    
def create_directory(directory_path: str) -> str:
    try:
        if not _is_safe_path(directory_path):
            return "错误：尝试在安全目录外创建目录"
            
        abs_path = os.path.abspath(directory_path)
        os.makedirs(abs_path, exist_ok=True)
        return f"目录{directory_path}创建成功"
    except Exception as e:
        return f"目录{directory_path}创建出错：{str(e)}"
    
def copy_file_or_directory(source_path: str, destination_path: str) -> str:
    try:
        # 检查源路径和目标路径是否都在安全目录内
        if not _is_safe_path(source_path) or not _is_safe_path(destination_path):
            return "错误：源路径或目标路径位于安全目录外"

        source_abs = os.path.abspath(source_path)
        dest_abs = os.path.abspath(destination_path)

        if os.path.isdir(source_abs):
            shutil.copytree(source_abs, dest_abs)
        else:
            shutil.copy2(source_abs, dest_abs)

        return f"成功将 {source_path} 复制到 {destination_path}"

    except FileNotFoundError:
        return f"错误：源路径 {source_path} 未找到"
    except PermissionError:
        return f"错误：权限不足，无法访问或写入路径 {destination_path}"
    except FileExistsError:
        return f"错误：目标路径 {destination_path} 已存在"
    except Exception as e:
        return f"复制文件/目录时出错: {str(e)}"

FILE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容（建议先在目录下查看文件的完整名称）",
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
            "description": "创建新文件，或更新文件内容",
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
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file_or_directory",
            "description": "复制文件或整个目录到指定位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "源文件或目录路径",
                    },
                    "destination_path": {
                        "type": "string",
                        "description": "目标路径",
                    }
                },
                "required": ["source_path", "destination_path"],
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
    "copy_file_or_directory": copy_file_or_directory
}