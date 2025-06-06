import os
import subprocess
from typing import List, Dict, Optional
from .file_op import _is_safe_path  # 复用现有安全检查函数

# 默认支持的代码/配置文件类型（可扩展）
DEFAULT_FILE_TYPES = {
    "code": [".py", ".js", ".java", ".cpp", ".c", ".ts", ".go", ".php", ".vue", ".tsx"],
    "config": [".json", ".yaml", ".yml", ".ini", ".toml", ".env", ".properties"]
}


def _get_git_tracked_files(directory: str) -> List[str]:
    """
    获取指定目录（Git仓库）中被跟踪的文件列表
    """
    try:
        # 执行 git ls-files 命令，获取所有被跟踪的文件（相对路径）
        result = subprocess.run(
            ["git", "-C", directory, "ls-files"],  # -C 参数指定Git仓库目录
            capture_output=True,
            text=True,
            check=True
        )
        # 按行分割输出，过滤空行
        tracked_files = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        # 转换为绝对路径
        return [os.path.join(directory, file) for file in tracked_files]
    except subprocess.CalledProcessError as e:
        # 处理非Git仓库或命令错误（如目录不是仓库）
        if "not a git repository" in e.stderr:
            return []  # 非Git仓库，返回空列表
        else:
            raise  # 其他错误向上抛出


def _get_target_files(
    directory: str, 
    file_types: Optional[Dict[str, List[str]]] = None
) -> List[str]:
    """
    先通过Git获取被跟踪的文件，再筛选符合类型的代码/配置文件
    """
    target_files = []
    file_types = file_types or DEFAULT_FILE_TYPES
    valid_extensions = [ext for exts in file_types.values() for ext in exts]

    # 步骤1：获取Git跟踪的文件（绝对路径）
    tracked_files = _get_git_tracked_files(directory)
    if not tracked_files:
        # 非Git仓库时，回退到原逻辑（遍历目录）
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                if ext in valid_extensions:
                    target_files.append(file_path)
        return target_files

    # 步骤2：从Git跟踪的文件中筛选符合类型的文件
    for file_path in tracked_files:
        ext = os.path.splitext(file_path)[1].lower()
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


def _tree_to_text(
    tree: Dict, 
    prefix: str = "", 
    is_last: bool = True, 
    content_map: Dict[str, str] = {}
) -> str:
    """
    将目录树字典转换为带缩进的树状文本格式
    """
    text = ""
    items = list(tree.items())
    for i, (name, value) in enumerate(items):
        is_last_item = (i == len(items) - 1)
        line_prefix = prefix + ("└── " if is_last else "├── ") if prefix else ""
        if isinstance(value, dict):  # 目录节点
            text += f"{line_prefix}{name}/\n"
            new_prefix = prefix + ("    " if is_last else "│   ")
            text += _tree_to_text(value, new_prefix, is_last_item, content_map)
        else:  # 文件节点（value为文件路径，从content_map获取内容）
            content = content_map.get(value, "[内容读取失败]")
            text += f"{line_prefix}{name}\\n"
            # 缩进4格展示文件内容（模拟代码块）
            content_lines = [f"    {line}" for line in content.split("\n")]
            text += "\n".join(content_lines) + "\n"
    return text


def extract_code_context(
    directory: str, 
    file_types: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    提取指定Git仓库中被跟踪的代码/配置文件上下文（带目录结构）
    
    Args:
        directory (str): 目标Git仓库目录路径（需在安全目录内）
        file_types (Dict[str, List[str]]): 可选，自定义文件类型（如 {"code": [".py"], "config": [".json"]}）
    
    Returns:
        str: 目录结构+文件内容的文本（树状格式）
    """
    # 安全检查
    if not _is_safe_path(directory):
        return "错误：目标目录位于安全目录外"
    
    # 检查目录是否存在
    if not os.path.isdir(directory):
        return f"错误：目录 {directory} 不存在"
    
    # 筛选目标文件（优先使用Git跟踪的文件）
    target_files = _get_target_files(directory, file_types)
    if not target_files:
        # 检查是否为Git仓库：若Git跟踪文件为空且非仓库，提示可能原因
        tracked_files = _get_git_tracked_files(directory)
        if not tracked_files:
            return f"提示：目录 {directory} 下未找到代码/配置文件（或非Git仓库）"
        else:
            return f"提示：Git仓库 {directory} 中未找到符合类型的代码/配置文件"
    
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
    
    # 生成最终文本（含目录结构和文件内容）
    result = f"目录结构及文件内容（Git仓库: {os.path.abspath(directory)}）:\n"
    result += _tree_to_text(directory_tree, content_map=content_map)
    return result


# 工具元信息（供LLM识别）
CODE_CONTEXT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_code_context",
            "description": "提取指定Git仓库中被跟踪的代码文件（如.py、.js等）和配置文件（如.json、.yaml等）的上下文，返回带目录结构的文本（包含文件内容）",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目标Git仓库目录路径（需在项目安全目录内）",
                    },
                    "file_types": {
                        "type": "object",
                        "description": "可选，自定义文件类型（如 {'code': ['.py'], 'config': ['.json']}），默认包含常见代码和配置类型",
                        "properties": {
                            "code": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "代码文件扩展名列表（如['.py', '.js']）"
                            },
                            "config": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "配置文件扩展名列表（如['.json', '.yaml']）"
                            }
                        }
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
