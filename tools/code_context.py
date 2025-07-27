import os
import json
from typing import List, Dict, Optional

# 默认支持的代码/配置文件类型（可扩展）
DEFAULT_FILE_TYPES = {
    "code": [".py", ".js", ".java", ".cpp", ".c", ".ts", ".go", ".php", ".vue", ".tsx", ".bas"],
    "config": [".json", ".yaml", ".yml", ".ini", ".toml", ".env", ".properties", ".txt"]
}

# 过滤阈值
MAX_LINES = 1000
MAX_FILE_SIZE_KB = 50


def _get_target_files(directory: str) -> List[str]:
    """
    获取目录中所有符合类型的代码/配置文件（忽略Git状态）
    """
    target_files = []
    file_types = DEFAULT_FILE_TYPES
    valid_extensions = [ext for exts in file_types.values() for ext in exts]
    
    # 直接遍历所有目录文件
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                target_files.append(file_path)
                
    return target_files


def _check_file_constraints(file_path: str) -> Dict[str, any]:
    """
    检查文件是否超过指定的行数和大小限制
    
    Args:
        file_path (str): 文件路径
    
    Returns:
        Dict: 包含检查结果和文件信息
    """
    try:
        # 获取文件大小
        file_size_bytes = os.path.getsize(file_path)
        file_size_kb = file_size_bytes / 1024
        
        # 获取文件行数
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                line_count = len(lines)
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试其他编码
            with open(file_path, 'r', encoding='latin-1') as f:
                lines = f.readlines()
                line_count = len(lines)
        
        # 检查是否超过限制
        exceeds_limits = line_count > MAX_LINES or file_size_kb > MAX_FILE_SIZE_KB
        
        return {
            "exceeds_limits": exceeds_limits,
            "line_count": line_count,
            "file_size_kb": round(file_size_kb, 2),
            "file_path": file_path
        }
    except Exception as e:
        return {
            "exceeds_limits": True,
            "error": str(e),
            "file_path": file_path
        }


def _build_directory_tree(
    base_dir: str, 
    file_paths: List[str],
    filtered_files: List[Dict[str, any]] = None
) -> Dict[str, Dict]:
    """
    根据文件路径构建目录树结构（嵌套字典）
    
    Args:
        base_dir (str): 基础目录
        file_paths (List[str]): 文件路径列表
        filtered_files (List[Dict], optional): 被过滤的文件信息列表
    """
    tree = {}
    base_dir = os.path.abspath(base_dir)
    
    # 添加被过滤的文件信息到目录树
    if filtered_files:
        tree["_filtered_files"] = filtered_files
    
    for file_path in file_paths:
        rel_path = os.path.relpath(file_path, base_dir)
        parts = rel_path.split(os.sep)
        current = tree
        for part in parts[:-1]:  # 处理目录部分
            if part not in current:
                current[part] = {}
            current = current[part]
        # 处理文件部分（存储文件路径）
        current[parts[-1]] = file_path
    return tree


def extract_code_context(
    directory: str,
    force_read: bool = False,
    specific_files: List[str] = None
) -> str:
    """
    提取指定目录下的代码/配置文件上下文（返回结构化JSON）
    
    两步式安全提取：
    1. 第一遍运行时（specific_files=None）：仅返回目录结构和文件大小信息
    2. 第二遍运行时（指定specific_files）：只读取指定的具体文件内容
    
    Args:
        directory (str): 目标目录路径
        force_read (bool): 是否强制读取所有文件，忽略大小和行数限制
        specific_files (List[str], optional): 要具体读取的文件路径列表
    
    Returns:
        str: 包含目录结构和文件内容的JSON字符串
    """
    
    # 检查目录是否存在
    if not os.path.isdir(directory):
        return json.dumps({
            "status": "error",
            "message": f"目录 {directory} 不存在"
        }, ensure_ascii=False)
    
    # 获取所有目标文件
    target_files = _get_target_files(directory)
    
    if not target_files:
        return json.dumps({
            "status": "warning",
            "message": f"目录 {directory} 中未找到符合类型的代码/配置文件"
        }, ensure_ascii=False)
    
    # 第一步：如果未指定具体文件，仅返回目录结构和文件信息
    if specific_files is None:
        file_info_list = []
        for file_path in target_files:
            check_result = _check_file_constraints(file_path)
            file_info = {
                "file_path": file_path,
                "relative_path": os.path.relpath(file_path, directory)
            }
            
            if check_result.get("error"):
                file_info.update({
                    "status": "error",
                    "error": check_result["error"]
                })
            else:
                file_info.update({
                    "status": "ok",
                    "line_count": check_result["line_count"],
                    "file_size_kb": check_result["file_size_kb"],
                    "exceeds_limits": check_result["exceeds_limits"]
                })
            
            file_info_list.append(file_info)
        
        # 构建目录树结构（仅包含文件路径，不包含内容）
        directory_tree = _build_directory_tree(directory, target_files)
        
        result = {
            "status": "directory_listing",
            "message": "第一步完成：目录结构和文件信息已列出。如需读取具体文件内容，请指定 specific_files 参数。",
            "repository_path": os.path.abspath(directory),
            "directory_tree": directory_tree,
            "file_info": file_info_list,
            "summary": {
                "total_files_found": len(target_files),
                "mode": "directory_listing"
            }
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    # 第二步：读取指定的具体文件内容
    files_to_read = []
    invalid_files = []
    
    # 验证指定的文件是否在目标目录中
    abs_directory = os.path.abspath(directory)
    for file_path in specific_files:
        abs_file_path = os.path.abspath(file_path)
        
        # 检查文件是否存在
        if not os.path.isfile(abs_file_path):
            invalid_files.append({
                "file_path": file_path,
                "error": "文件不存在"
            })
            continue
            
        # 检查文件是否在目标目录内
        if not abs_file_path.startswith(abs_directory):
            invalid_files.append({
                "file_path": file_path,
                "error": "文件不在指定目录范围内"
            })
            continue
            
        # 检查文件类型是否符合要求
        ext = os.path.splitext(abs_file_path)[1].lower()
        valid_extensions = [ext for exts in DEFAULT_FILE_TYPES.values() for ext in exts]
        if ext not in valid_extensions:
            invalid_files.append({
                "file_path": file_path,
                "error": f"文件类型 {ext} 不在支持的类型列表中"
            })
            continue
            
        files_to_read.append(abs_file_path)
    
    # 读取指定文件的内容
    content_map = {}
    read_errors = []
    
    for file_path in files_to_read:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content_map[file_path] = f.read()
        except Exception as e:
            content_map[file_path] = f"[读取失败：{str(e)}]"
            read_errors.append({
                "file_path": file_path,
                "error": str(e)
            })
    
    # 构建结果
    result = {
        "status": "content_loaded",
        "message": "第二步完成：指定文件内容已加载",
        "repository_path": abs_directory,
        "file_contents": content_map,
        "summary": {
            "requested_files": len(specific_files),
            "valid_files": len(files_to_read),
            "invalid_files": len(invalid_files),
            "read_errors": len(read_errors),
            "mode": "content_loading"
        }
    }
    
    if invalid_files:
        result["invalid_files"] = invalid_files
    if read_errors:
        result["read_errors"] = read_errors
    
    # 使用json.dumps确保格式正确，处理特殊字符
    return json.dumps(result, ensure_ascii=False, indent=2)


# 工具元信息（供LLM识别）
CODE_CONTEXT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_code_context",
            "description": "提取指定路径下的代码库：第一步获取目录结构，第二步读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目标目录路径",
                    },
                    "force_read": {
                        "type": "boolean",
                        "description": "是否强制读取所有文件，忽略大小和行数限制",
                        "default": False
                    },
                    "specific_files": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "要具体读取的文件路径列表（从第一步获取的列表中选择）",
                        "default": None
                    }
                },
                "required": ["directory"],
            },
        }
    }
]


# 工具函数映射（供Agent调用）
CODE_CONTEXT_FUNCTIONS = {
    "extract_code_context": extract_code_context
}