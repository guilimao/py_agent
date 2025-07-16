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
    force_read: bool = False
) -> str:
    """
    提取指定目录下的代码/配置文件上下文（返回结构化JSON）
    
    Args:
        directory (str): 目标目录路径
        force_read (bool): 是否强制读取所有文件，忽略大小和行数限制
    
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
    
    # 检查文件限制
    filtered_files = []
    files_to_read = []
    
    for file_path in target_files:
        check_result = _check_file_constraints(file_path)
        
        if check_result.get("error"):
            # 读取文件出错，标记为已过滤
            filtered_files.append({
                "file_path": file_path,
                "reason": "read_error",
                "error": check_result["error"]
            })
        elif not force_read and check_result["exceeds_limits"]:
            # 超过限制且未启用强制读取模式
            filtered_files.append({
                "file_path": file_path,
                "reason": "size_limit",
                "line_count": check_result["line_count"],
                "file_size_kb": check_result["file_size_kb"],
                "limits": {
                    "max_lines": MAX_LINES,
                    "max_file_size_kb": MAX_FILE_SIZE_KB
                }
            })
        else:
            # 可以读取的文件
            files_to_read.append(file_path)
    
    # 构建目录树结构
    directory_tree = _build_directory_tree(directory, files_to_read, filtered_files)
    
    # 读取所有文件内容（缓存路径→内容映射）
    content_map = {}
    for file_path in files_to_read:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content_map[file_path] = f.read()
        except Exception as e:
            content_map[file_path] = f"[读取失败：{str(e)}]"
    
    # 生成最终JSON结果
    result = {
        "status": "success",
        "repository_path": os.path.abspath(directory),
        "directory_tree": directory_tree,
        "file_contents": content_map,
        "summary": {
            "total_files_found": len(target_files),
            "files_read": len(files_to_read),
            "files_filtered": len(filtered_files),
            "force_read_enabled": force_read
        }
    }
    
    # 如果有文件被过滤，添加警报信息
    if filtered_files and not force_read:
        alerts = []
        for filtered in filtered_files:
            if filtered["reason"] == "size_limit":
                alerts.append(
                    f"⚠️ 文件 {os.path.basename(filtered['file_path'])} "
                    f"({filtered['line_count']}行, {filtered['file_size_kb']}KB) "
                    f"超过限制 (>{MAX_LINES}行 或 >{MAX_FILE_SIZE_KB}KB)，已跳过。"
                    f"使用 force_read=True 强制读取。"
                )
            elif filtered["reason"] == "read_error":
                alerts.append(
                    f"❌ 文件 {os.path.basename(filtered['file_path'])} 读取失败: {filtered['error']}"
                )
        result["alerts"] = alerts
    
    # 使用json.dumps确保格式正确，处理特殊字符
    return json.dumps(result, ensure_ascii=False, indent=2)


# 工具元信息（供LLM识别）
CODE_CONTEXT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_code_context",
            "description": "提取指定文件夹中的文件，返回带目录结构的JSON（包含文件内容）",
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