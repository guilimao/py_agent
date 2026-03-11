import os
import re
from typing import List, Optional, Dict, Tuple, Union, Pattern
from dataclasses import dataclass, field


@dataclass
class Node:
    id: int
    name: str
    suffix: str
    is_file: bool
    size: int
    depth: int
    parent_id: int
    children_ids: List[int] = field(default_factory=list)


def translate_gitignore_to_regex(pattern: str) -> Pattern:
    """将 .gitignore 模式转换为正则表达式。
    
    支持的 .gitignore 特性：
    - * 匹配任意数量的非斜杠字符
    - ? 匹配单个非斜杠字符
    - **/ 匹配零个或多个目录
    - /** 匹配目录内所有内容
    - [abc] 字符类
    - [!abc] 否定字符类
    - 以 / 开头的模式匹配项目根目录
    """
    # 去除末尾的空格和 /，但保留前导 /
    pattern = pattern.rstrip('/').rstrip()
    
    # 如果模式为空，返回不匹配任何内容的正则
    if not pattern:
        return re.compile(r'(?!x)x')
    
    # 标记是否以 / 开头（匹配根目录）
    anchored = pattern.startswith('/')
    if anchored:
        pattern = pattern[1:]
    
    i = 0
    result = []
    length = len(pattern)
    
    while i < length:
        c = pattern[i]
        
        if c == '*':
            # 检查是否是 **
            if i + 1 < length and pattern[i + 1] == '*':
                # ** 的情况
                if i + 2 < length and pattern[i + 2] == '/':
                    # **/ 匹配零个或多个目录
                    result.append('(?:.*/)?')
                    i += 3
                elif i + 2 >= length:
                    # ** 在末尾，匹配任意内容
                    result.append('.*')
                    i += 2
                else:
                    # ** 后面不是 /，作为普通 *
                    result.append('[^/]*')
                    i += 2
            else:
                # 单个 * 匹配非斜杠字符
                result.append('[^/]*')
                i += 1
                
        elif c == '?':
            # ? 匹配单个非斜杠字符
            result.append('[^/]')
            i += 1
            
        elif c == '[':
            # 字符类
            j = i + 1
            if j < length and pattern[j] == '!':
                # [!abc] -> [^abc]
                j += 1
                negate = True
            else:
                negate = False
            
            # 找到字符类的结束
            class_content = []
            while j < length and pattern[j] != ']':
                if pattern[j] == '\\' and j + 1 < length:
                    j += 1
                class_content.append(pattern[j])
                j += 1
            
            if j < length:
                # 有效的字符类
                char_class = ''.join(class_content)
                if negate:
                    result.append(f'[^{re.escape(char_class)}]')
                else:
                    result.append(f'[{re.escape(char_class)}]')
                i = j + 1
            else:
                # 未闭合的字符类，当作普通 [
                result.append(re.escape(c))
                i += 1
                
        elif c == '\\':
            # 转义字符
            if i + 1 < length:
                result.append(re.escape(pattern[i + 1]))
                i += 2
            else:
                result.append(re.escape(c))
                i += 1
                
        else:
            # 普通字符
            result.append(re.escape(c))
            i += 1
    
    regex_pattern = ''.join(result)
    
    # 处理锚定模式
    if anchored:
        regex_pattern = '^' + regex_pattern
    else:
        # 非锚定模式可以匹配路径的任意部分
        regex_pattern = '(^|/)' + regex_pattern
    
    # 匹配结尾：可以匹配文件/目录本身，或者目录下的内容
    regex_pattern = regex_pattern + '(/|$)'
    
    try:
        return re.compile(regex_pattern)
    except re.error:
        # 如果正则编译失败，返回一个不匹配任何内容的模式
        return re.compile(r'(?!x)x')


def list_directory(path: str = ".", depth: int = 0,
                   blacklist: Optional[List[str]] = None,
                   whitelist: Optional[List[str]] = None) -> str:
    # 参数初始化
    abs_path = os.path.abspath(path)
    # 默认黑名单包含 .git 文件夹，但如果用户传入了黑名单参数则使用用户传入的
    if blacklist is None:
        blacklist = ['.git']
    whitelist = whitelist or []

    # 解析.gitignore
    gitignore_path = os.path.join(abs_path, ".gitignore")
    if os.path.exists(gitignore_path) and os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if line.startswith('!'):
                        # 白名单条目（否定模式）：移除开头的 !
                        whitelist.append(line[1:])
                    else:
                        # 黑名单条目（普通模式）
                        blacklist.append(line)

    # 广度优先扫描构建节点
    nodes: Dict[int, Node] = {}
    root = Node(id=1, name=abs_path, suffix='', is_file=False,
                size=0, depth=0, parent_id=0, children_ids=[])
    nodes[1] = root
    next_id = 2
    queue = [root]

    while queue:
        current = queue.pop(0)
        if depth > 0 and current.depth >= depth:
            continue
        current_abs = current.name if current.depth == 0 else os.path.join(abs_path, *get_relative_parts(nodes, current.id))
        if not os.path.isdir(current_abs):
            continue
        try:
            items = sorted(os.listdir(current_abs))
        except (PermissionError, OSError):
            continue
        for item in items:
            item_path = os.path.join(current_abs, item)
            is_file = os.path.isfile(item_path)
            if is_file:
                name_part, suffix_part = os.path.splitext(item)
                suffix_part = suffix_part[1:] if suffix_part else ''
                try:
                    size = os.path.getsize(item_path)
                except:
                    size = 0
            else:
                name_part, suffix_part, size = item, '', 0
            node = Node(id=next_id, name=name_part, suffix=suffix_part,
                        is_file=is_file, size=size, depth=current.depth + 1,
                        parent_id=current.id, children_ids=[])
            nodes[next_id] = node
            current.children_ids.append(next_id)
            queue.append(node)
            next_id += 1

    # 编译白名单为正则表达式
    whitelist_patterns = [translate_gitignore_to_regex(w) for w in whitelist]
    
    # 白名单过滤
    if whitelist_patterns:
        file_nodes = [n for n in nodes.values() if n.is_file]
        for fn in file_nodes:
            full_name = fn.name + ('.' + fn.suffix if fn.suffix else '')
            # 获取相对路径用于匹配
            relative_path = '/'.join(get_relative_parts(nodes, fn.id))
            # 检查是否匹配任意白名单模式（匹配文件名或相对路径）
            is_whitelisted = any(
                pattern.search(full_name) or pattern.search(relative_path)
                for pattern in whitelist_patterns
            )
            if not is_whitelisted:
                del nodes[fn.id]
                if fn.parent_id in nodes:
                    nodes[fn.parent_id].children_ids.remove(fn.id)
        dir_ids = sorted([n.id for n in nodes.values() if not n.is_file], reverse=True)
        for did in dir_ids:
            if did == 1:
                continue
            node = nodes[did]
            full_name = node.name
            relative_path = '/'.join(get_relative_parts(nodes, did))
            is_whitelisted = any(
                pattern.search(full_name) or pattern.search(relative_path)
                for pattern in whitelist_patterns
            )
            if not is_whitelisted and not node.children_ids:
                del nodes[did]
                if node.parent_id in nodes:
                    nodes[node.parent_id].children_ids.remove(did)

    # 编译黑名单为正则表达式
    blacklist_patterns = [translate_gitignore_to_regex(b) for b in blacklist]
    
    # 黑名单过滤
    if blacklist_patterns:
        to_remove = set()
        queue = [1]
        while queue:
            curr_id = queue.pop(0)
            if curr_id not in nodes:
                continue
            curr = nodes[curr_id]
            full_name = curr.name + ('.' + curr.suffix if curr.suffix else '')
            relative_path = '/'.join(get_relative_parts(nodes, curr_id))
            # 检查是否匹配任意黑名单模式（匹配文件名或相对路径）
            is_blacklisted = any(
                pattern.search(full_name) or pattern.search(relative_path)
                for pattern in blacklist_patterns
            )
            if is_blacklisted:
                to_remove.add(curr_id)
            else:
                queue.extend(curr.children_ids)
        for rid in sorted(to_remove, reverse=True):
            if rid in nodes:
                node = nodes[rid]
                if node.parent_id in nodes:
                    nodes[node.parent_id].children_ids.remove(rid)
                del nodes[rid]

    # 深度调整（字符量检查）
    effective_depth = depth if depth > 0 else max((n.depth for n in nodes.values()), default=0)
    while effective_depth > 0:
        total_chars = sum(len(n.name) + len(n.suffix) + (1 if n.suffix else 0) for n in nodes.values() if n.depth <= effective_depth)
        if total_chars <= 2000:
            break
        effective_depth -= 1

    # 按有效深度过滤节点
    filtered_nodes = {nid: n for nid, n in nodes.items() if n.depth <= effective_depth}
    for n in filtered_nodes.values():
        n.children_ids = [cid for cid in n.children_ids if cid in filtered_nodes]

    # 构建树状输出
    lines = []
    def build_tree(node_id: int, prefix: str = "", is_last: bool = True):
        if node_id not in filtered_nodes:
            return
        node = filtered_nodes[node_id]
        display_name = node.name
        if node.suffix:
            display_name += "." + node.suffix
        connector = "└── " if is_last else "├── "
        if node_id == 1:
            lines.append(display_name)
        else:
            lines.append(prefix + connector + display_name)
        children = [filtered_nodes[cid] for cid in node.children_ids if cid in filtered_nodes]
        children.sort(key=lambda x: (not x.is_file, x.name.lower()))
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            extension = "    " if is_last else "│   "
            build_tree(child.id, prefix + extension, is_last_child)

    build_tree(1)
    return "\n".join(lines)


def get_relative_parts(nodes: Dict[int, Node], node_id: int) -> List[str]:
    parts = []
    curr = nodes.get(node_id)
    while curr and curr.parent_id != 0:
        name = curr.name
        if curr.suffix:
            name += "." + curr.suffix
        parts.append(name)
        curr = nodes.get(curr.parent_id)
    return list(reversed(parts))


# 工具定义
DIRECTORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出目录的树状结构。当同一层级项目过多时，总输出量控制在2000字符内。默认会自动跳过 .git 文件夹。如果目录中存在.gitignore文件，将自动跳过其中指定的文件和目录。",
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

DIRECTORY_FUNCTIONS = {
    "list_directory": list_directory
}
