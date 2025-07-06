import os
import json
from typing import List, Dict

# 默认支持的代码/配置文件类型（可扩展）
DEFAULT_FILE_TYPES = {
    "code": [".py", ".js", ".java", ".cpp", ".c", ".ts", ".go", ".php", ".vue", ".tsx", ".bas"],
    "config": [".json", ".yaml", ".yml", ".ini", ".toml", ".env", ".properties", "txt"]
}


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


def _build_directory_tree(
    base_dir: str, 
    file_paths: List[str]
) -> Dict[str, Dict]:
    """
    根据文件路径构建目录树结构（嵌套字典）
    """
    tree = {}
    base_dir = os.path.abspath(base_dir)
    
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
) -> str:
    """
    提取指定目录下的代码/配置文件上下文（返回结构化JSON）
    
    Args:
        directory (str): 目标目录路径
    
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
    
    # 构建目录树结构
    directory_tree = _build_directory_tree(directory, target_files)
    
    # 读取所有文件内容（缓存路径→内容映射）
    content_map = {}
    for file_path in target_files:
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
        "file_contents": content_map
    }
    
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