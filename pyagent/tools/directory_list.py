import os
import json
import fnmatch
from typing import List, Dict, Tuple, Optional, Callable
def _parse_gitignore(gitignore_path: str) -> Callable[[str], bool]:
    """解析.gitignore文件，返回一个函数，判断相对路径是否被忽略
    Args:
        gitignore_path: .gitignore文件的完整路径
    Returns:
        一个函数，接受相对于.gitignore所在目录的文件路径，返回是否被忽略
    """
    patterns = []
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        # 如果无法读取，返回一个始终返回False的函数
        return lambda rel_path: False
    base_dir = os.path.dirname(gitignore_path)
    for line in lines:
        line = line.strip()
        # 忽略空行和注释
        if not line or line.startswith('#'):
            continue
        # 去除行尾的换行符，并处理尾随空格
        pattern = line.rstrip()
        patterns.append(pattern)
    def is_ignored(rel_path: str) -> bool:
        """判断相对路径是否被忽略"""
        # 将路径统一为Unix风格分隔符，便于匹配
        rel_path_unix = rel_path.replace('\\', '/')
        # 始终跳过.git文件夹（如果检测到gitignore文件，表明存在git）
        # 检查路径是否为.git目录或其子目录
        if rel_path_unix == '.git' or rel_path_unix.startswith('.git/') or '/.git/' in rel_path_unix:
            return True
        for pattern in patterns:
            # 简单实现：使用fnmatch进行通配符匹配
            # 注意：fnmatch匹配整个字符串，所以我们需要确保模式与路径匹配
            # .gitignore模式可能包含目录，需要特殊处理
            if fnmatch.fnmatch(rel_path_unix, pattern):
                return True
            # 如果模式以/结尾，表示目录，需要匹配目录下的所有内容
            if pattern.endswith('/'):
                dir_pattern = pattern.rstrip('/')
                if rel_path_unix.startswith(dir_pattern + '/'):
                    return True
                if fnmatch.fnmatch(rel_path_unix, dir_pattern + '/*'):
                    return True
            # 如果模式包含通配符，已经由fnmatch处理
            # 如果没有通配符，可能是具体文件或目录
            elif '/' not in pattern and '/' in rel_path_unix:
                # 模式是文件名，匹配任意层级
                filename = os.path.basename(rel_path_unix)
                if fnmatch.fnmatch(filename, pattern):
                    return True
        return False
    return is_ignored
def _is_hidden_folder(name: str) -> bool:
    """判断是否为隐藏文件夹（以点开头的文件夹）"""
    return name.startswith('.')
def _get_tree_structure(path: str, max_items_per_level: int = 20, max_depth: int = 8, 
                        current_depth: int = 0, should_skip: Optional[Callable[[str, str], bool]] = None,
                        rel_path: str = '.') -> Tuple[List[str], int]:
    """
    递归获取目录的树状结构
    Args:
        path: 当前目录路径
        max_items_per_level: 每层最多显示的项目数
        max_depth: 最大递归深度
        current_depth: 当前深度
        should_skip: 判断文件是否应被忽略的函数（可选），接受两个参数：item_name和rel_path
        rel_path: 当前路径相对于根目录的相对路径
    Returns:
        Tuple[List[str], int]: (当前目录的树状结构行列表, 该目录下显示的总项目数)
    """
    if current_depth >= max_depth:
        return [], 0
    try:
        items = sorted(os.listdir(path))
    except (PermissionError, OSError):
        return [f"[权限错误: 无法访问 {path}]"], 0
    # 分离文件和文件夹，文件夹在前
    dirs = []
    files = []
    for item in items:
        full_path = os.path.join(path, item)
        # 计算相对于根目录的路径
        if rel_path == '.':
            item_rel_path = item
        else:
            item_rel_path = os.path.join(rel_path, item)
        # 检查是否应被忽略
        if should_skip and should_skip(item, item_rel_path):
            continue
        try:
            if os.path.isdir(full_path):
                dirs.append((item, item_rel_path))
            else:
                files.append((item, item_rel_path))
        except (PermissionError, OSError):
            # 跳过无法访问的项目
            continue
    # 排序：文件夹在前，按名称排序
    dirs.sort(key=lambda x: x[0].lower())
    files.sort(key=lambda x: x[0].lower())
    # 计算当前层级显示的项目数（不包括被忽略的）
    total_displayed_items = len(dirs) + len(files)
    # 如果项目太多，需要截断显示
    lines = []
    displayed_items = 0
    truncated = False
    # 优先显示文件夹
    for i, (dir_name, dir_rel_path) in enumerate(dirs):
        if displayed_items >= max_items_per_level:
            truncated = True
            break
        prefix = "├── " if i < len(dirs) - 1 or (i == len(dirs) - 1 and len(files) > 0) else "└── "
        indent = "    " * current_depth
        line = f"{indent}{prefix}{dir_name}/"
        # 检查是否为隐藏文件夹
        if _is_hidden_folder(dir_name):
            # 隐藏文件夹不展开，添加特殊标记
            line += " [隐藏]"
            subdir_lines = []
            subdir_count = 0
        else:
            # 递归获取子目录结构
            subdir_path = os.path.join(path, dir_name)
            subdir_lines, subdir_count = _get_tree_structure(
                subdir_path, max_items_per_level, max_depth, current_depth + 1,
                should_skip, dir_rel_path
            )
            # 如果有子目录或文件，显示计数
            if subdir_count > 0:
                line += f" [{subdir_count}项]"
        lines.append(line)
        lines.extend(subdir_lines)
        displayed_items += 1
    # 显示文件（如果有空间）
    if not truncated:
        for i, (file_name, _) in enumerate(files):
            if displayed_items >= max_items_per_level:
                truncated = True
                break
            # 计算前缀
            if i == len(files) - 1:
                # 如果是最后一个文件
                if len(dirs) > 0:
                    prefix = "└── "
                else:
                    prefix = "└── " if i == len(files) - 1 else "├── "
            else:
                prefix = "├── "
            indent = "    " * current_depth
            lines.append(f"{indent}{prefix}{file_name}")
            displayed_items += 1
    # 添加截断提示
    if truncated:
        remaining = total_displayed_items - displayed_items
        indent = "    " * current_depth
        prefix = "└── " if displayed_items == 0 else "├── "
        lines.append(f"{indent}{prefix}... (还有{remaining}个项未显示)")
    return lines, total_displayed_items
def _truncate_output(lines: List[str], max_chars: int = 2000) -> List[str]:
    """
    截断输出以控制总字符数
    Args:
        lines: 原始输出行列表
        max_chars: 最大字符数
    Returns:
        截断后的行列表
    """
    total_chars = sum(len(line) + 1 for line in lines)  # +1 for newline
    if total_chars <= max_chars:
        return lines
    # 计算需要保留的行数
    result_lines = []
    current_chars = 0
    for line in lines:
        line_with_newline = line + "\n"
        line_length = len(line_with_newline)
        if current_chars + line_length > max_chars - 50:  # 留50字符给截断提示
            break
        result_lines.append(line)
        current_chars += line_length
    # 添加截断提示
    remaining_lines = len(lines) - len(result_lines)
    if remaining_lines > 0:
        result_lines.append(f"... (还有{remaining_lines}行未显示)")
    return result_lines
def list_directory(path: str = ".", depth: int = 0, blacklist: List[str] = None, whitelist: List[str] = None) -> str:
    """
    列出目录的树状结构
    注意：如果目录中存在.gitignore文件，将自动跳过其中指定的文件和目录
    Args:
        path: 要列出的目录路径（默认为当前目录）
        depth: 展开目录的层数，默认值为0，代表全部展开，1代表只展开当前目录下一层，2代表展开两层，以此类推
        blacklist: 黑名单字符串数组，用于排除文件名中含有特定字符的项
        whitelist: 白名单字符串数组，用于仅保留文件名中含有特定字符的项
    Returns:
        目录的树状结构字符串，总输出量控制在2000字符内
    """
    try:
        abs_path = os.path.abspath(path)
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"错误：路径不存在 - {abs_path}"
        # 检查是否为目录
        if not os.path.isdir(abs_path):
            return f"错误：路径不是目录 - {abs_path}"
        # 检查是否存在.gitignore文件
        gitignore_path = os.path.join(abs_path, ".gitignore")
        is_ignored = None
        gitignore_used = False
        if os.path.exists(gitignore_path):
            is_ignored = _parse_gitignore(gitignore_path)
            gitignore_used = True
        # 创建组合的should_skip函数
        def should_skip(item_name: str, rel_path: str) -> bool:
            """判断是否应跳过该项"""
            # 1. 首先检查.gitignore规则
            if is_ignored and is_ignored(rel_path):
                return True
            # 2. 检查黑名单
            if blacklist:
                for pattern in blacklist:
                    if pattern in item_name:
                        return True
            # 3. 检查白名单（如果白名单不为空）
            if whitelist:
                # 如果白名单不为空，但项目名不包含任何白名单字符串，则跳过
                matches_whitelist = False
                for pattern in whitelist:
                    if pattern in item_name:
                        matches_whitelist = True
                        break
                if not matches_whitelist:
                    return True
            return False
        # 获取基本统计信息（考虑所有过滤规则）
        total_dirs = 0
        total_files = 0
        ignored_dirs = 0
        ignored_files = 0
        try:
            for root, dirs, files in os.walk(abs_path):
                # 计算相对于根目录的路径
                rel_root = os.path.relpath(root, abs_path)
                if rel_root == '.':
                    rel_root = ''
                # 过滤被忽略的目录
                filtered_dirs = []
                for dir_name in dirs:
                    if rel_root:
                        dir_rel_path = os.path.join(rel_root, dir_name)
                    else:
                        dir_rel_path = dir_name
                    if should_skip(dir_name, dir_rel_path):
                        ignored_dirs += 1
                    else:
                        filtered_dirs.append(dir_name)
                # 过滤被忽略的文件
                filtered_files = []
                for file_name in files:
                    if rel_root:
                        file_rel_path = os.path.join(rel_root, file_name)
                    else:
                        file_rel_path = file_name
                    if should_skip(file_name, file_rel_path):
                        ignored_files += 1
                    else:
                        filtered_files.append(file_name)
                total_dirs += len(filtered_dirs)
                total_files += len(filtered_files)
                # 修改dirs列表，避免os.walk进入被忽略的目录
                dirs[:] = filtered_dirs
        except (PermissionError, OSError):
            # 部分目录可能无法访问，继续处理
            pass
        # 计算max_depth参数：depth为0时表示无限深度（设置为一个大数）
        # depth > 0时，max_depth = depth + 1，因为current_depth从0开始
        if depth == 0:
            max_depth = 1000  # 视为无限深度
        else:
            max_depth = depth + 1
        # 获取树状结构
        tree_lines, _ = _get_tree_structure(
            abs_path, 
            max_items_per_level=15,
            max_depth=max_depth,
            should_skip=should_skip
        )
        # 截断输出以控制字符数
        tree_lines = _truncate_output(tree_lines, max_chars=1800)  # 留一些空间给标题和统计信息
        # 构建最终输出
        output_parts = [
            f"目录结构: {abs_path}",
            f"统计信息: {total_dirs}个文件夹, {total_files}个文件",
        ]
        # 添加.gitignore信息
        if gitignore_used:
            output_parts.append(f"[gitignore跳过了{ignored_dirs + ignored_files}个项: {ignored_dirs}个文件夹, {ignored_files}个文件]")
        # 添加过滤规则信息
        filter_info = []
        if blacklist:
            filter_info.append(f"黑名单: {blacklist}")
        if whitelist:
            filter_info.append(f"白名单: {whitelist}")
        if filter_info:
            output_parts.append(f"[过滤规则: {'; '.join(filter_info)}]")
        # 添加深度信息（如果depth > 0）
        if depth > 0:
            output_parts.append(f"[展开深度: {depth}层]")
        output_parts.extend([
            "",
            "树状结构:",
            "."
        ])
        # 如果没有树状结构行（空目录）
        if not tree_lines:
            output_parts.append("    [空目录]")
        else:
            output_parts.extend(tree_lines)
        return "\n".join(output_parts)
    except Exception as e:
        return f"列出目录时发生错误: {str(e)}"
# 工具元信息（供LLM识别）
DIRECTORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出目录的树状结构。当同一层级项目过多时，总输出量控制在2000字符内。如果目录中存在.gitignore文件，将自动跳过其中指定的文件和目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的目录路径（默认为当前目录）",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "展开目录的层数，默认值为0，代表全部展开，1代表只展开当前目录下一层，2代表展开两层，以此类推",
                    },
                    "blacklist": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "黑名单，用于排除文件名中含有特定字符的项，可以用来滤除结果中无关的干扰项",
                    },
                    "whitelist": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "白名单，用于仅保留文件名中含有特定字符的项",
                    }
                },
                "required": [],
            },
        }
    }
]
# 工具函数映射（供Agent调用）
DIRECTORY_FUNCTIONS = {
    "list_directory": list_directory
}
