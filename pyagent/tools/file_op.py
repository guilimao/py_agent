import os
import json
import re
import fnmatch
from typing import Union, Dict, List, Optional, Callable
import chardet
# 默认支持的文件扩展名
DEFAULT_EXTENSIONS = {
    '.py', '.js', '.java', '.cpp', '.c', '.ts', '.go', '.php', '.vue', '.tsx',
    '.json', '.yaml', '.yml', '.ini', '.toml', '.env', '.properties', '.txt',
    '.html', '.css', '.xml', '.sql', '.sh', '.bat', '.md', '.rst'
}
def _get_all_files(directory: str) -> List[str]:
    """获取目录下所有符合扩展名的文件"""
    target_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext in DEFAULT_EXTENSIONS:
                target_files.append(file_path)
    return sorted(target_files)
def _read_file_with_encoding(file_path: str) -> str:
    """使用chardet检测编码并读取文件内容"""
    try:
        # 首先读取二进制数据用于编码检测
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        # 使用chardet检测编码
        detection = chardet.detect(raw_data)
        encoding = detection['encoding'] or 'gbk'
        # 使用检测到的编码解码文件内容
        try:
            content = raw_data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            # 如果检测的编码失败，尝试常见编码
            for alt_encoding in ['utf-8', 'gbk', 'gb2312']:
                try:
                    content = raw_data.decode(alt_encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content = raw_data.decode('gbk', errors='ignore')
        return content
    except Exception as e:
        return f"[读取文件失败: {str(e)}]"
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
def read_file(file_names: Union[str, List[str]]) -> str:
    """
    读取一个或多个文件的内容，或提取目录下的代码文件
    Args:
        file_names: 文件路径（字符串）或文件路径列表
    Returns:
        文件内容字符串，如果是多个文件则返回合并的内容
        格式：<文件路径>\n文件内容
    """
    # 如果输入是单个字符串，转换为列表
    if isinstance(file_names, str):
        file_list = [file_names]
    else:
        file_list = file_names
    results = []
    for file_name in file_list:
        try:
            abs_path = os.path.abspath(file_name)
            # 检查路径是否存在
            if not os.path.exists(abs_path):
                results.append(f"{abs_path}\n路径不存在")
                continue
            # 判断是目录还是文件
            if os.path.isdir(abs_path):
                # 处理目录 - 提取该目录下所有符合格式的文件
                files = _get_all_files(abs_path)
                if not files:
                    results.append(f"{abs_path}\n[警告：目录中未找到符合扩展名的文件]")
                    continue
                # 构建目录结构信息
                dir_result_parts = [f"目录: {abs_path}\n", "目录结构:"]
                base_dir = abs_path
                for file_path in files:
                    rel_path = os.path.relpath(file_path, base_dir)
                    dir_result_parts.append(f"  {rel_path}")
                dir_result_parts.append("")  # 空行分隔
                # 读取并添加所有文件内容
                all_contents = []
                total_chars = 0
                exceeds_limit = False
                
                for file_path in files:
                    rel_path = os.path.relpath(file_path, base_dir)
                    content = _read_file_with_encoding(file_path)
                    all_contents.append((rel_path, content))
                    total_chars += len(content)
                    if total_chars > 10000:
                        exceeds_limit = True
                
                if exceeds_limit:
                    # 如果超过限制，添加警告信息，不显示文件内容
                    dir_result_parts.append("[警告：目录内容总字符数超过10000字符（共{}字符），内容长度过长，请只读取需要的具体文件]".format(total_chars))
                else:
                    # 未超过限制，正常添加所有内容
                    for rel_path, content in all_contents:
                        dir_result_parts.extend([
                            f"<{rel_path}>",
                            content,
                            ""
                        ])
                results.append("\n".join(dir_result_parts).rstrip())
            elif os.path.isfile(abs_path):
                # 处理单个文件 - 使用原逻辑
                content = _read_file_with_encoding(abs_path)
                result = f"{abs_path}\n{content}"
                results.append(result.strip())
            else:
                results.append(f"{abs_path}\n路径既不是文件也不是目录")
        except Exception as e:
            results.append(f"{os.path.abspath(file_name)}\n处理时发生错误: {str(e)}")
    # 如果是单个路径，直接返回结果；如果是多个路径，合并结果
    if len(file_list) == 1:
        return results[0] if results else "没有路径被处理"
    else:
        return "\n\n" + "="*50 + "\n".join(results)
def create_file(file_name: str, file_content: Union[str, Dict, List], backup: bool = False) -> str:
    try:
        abs_path = os.path.abspath(file_name)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # 备份逻辑
        backup_path = None
        if backup and os.path.exists(abs_path):
            backup_path = abs_path + ".backup"
            # 如果备份文件已存在，删除它
            if os.path.exists(backup_path):
                os.remove(backup_path)
            # 复制原文件到备份文件
            import shutil
            shutil.copy2(abs_path, backup_path)
        
        # 处理JSON对象或数组，转换为格式化字符串
        if isinstance(file_content, (Dict, List)):
            file_content_str = json.dumps(file_content, ensure_ascii=False, indent=2)
        else:
            file_content_str = str(file_content)
        
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(file_content_str)
        
        # 构建结果信息
        result = f"文件已成功创建/更新: {abs_path}"
        if backup_path:
            result += f"\n已创建备份文件: {backup_path}"
        return result
    except json.JSONDecodeError as e:
        return f"JSON序列化错误：无法将内容转换为JSON字符串 - {str(e)}"
    except Exception as e:
        return f"创建/修改文件时发生错误：{str(e)}"
def find(
    search_path: str,
    file_name: Optional[str] = None,
    content: Optional[str] = None
) -> str:
    """
    在指定路径下查找文件或文件内容
    Args:
        search_path (str): 要查找的目录路径
        file_name (Optional[str]): 文件名正则表达式，用于匹配文件名
        content (Optional[str]): 内容正则表达式，用于匹配文件内容
    Returns:
        符合匹配条件的文件路径列表
    """
    try:
        abs_path = os.path.abspath(search_path)
        # 检查路径是否存在
        if not os.path.exists(abs_path):
            return f"查找失败：路径不存在 - {abs_path}"
        if not os.path.isdir(abs_path):
            return f"查找失败：路径不是目录 - {abs_path}"
        # 检查是否存在.gitignore文件
        gitignore_path = os.path.join(abs_path, '.gitignore')
        is_ignored = None
        if os.path.exists(gitignore_path):
            is_ignored = _parse_gitignore(gitignore_path)
        # 编译正则表达式（如果提供）
        file_name_pattern = re.compile(file_name) if file_name else None
        content_pattern = re.compile(content) if content else None
        matching_files = []
        ignored_count = 0
        # 遍历目录
        for root, _, files in os.walk(abs_path):
            for file in files:
                file_path = os.path.join(root, file)
                # 计算相对于搜索目录的路径
                rel_path = os.path.relpath(file_path, abs_path)
                # 检查是否被.gitignore忽略
                if is_ignored and is_ignored(rel_path):
                    ignored_count += 1
                    continue
                # 检查文件名是否匹配
                if file_name_pattern:
                    if not file_name_pattern.search(rel_path):
                        continue
                # 如果需要匹配内容
                if content_pattern:
                    file_content = _read_file_with_encoding(file_path)
                    # 跳过读取失败的文件
                    if file_content.startswith("[") and "读取文件失败" in file_content:
                        continue
                    if not content_pattern.search(file_content):
                        continue
                # 如果通过了所有条件，添加到结果
                matching_files.append(file_path)
        # 构建结果字符串
        if not matching_files:
            result_msg = f"在 {abs_path} 中未找到匹配的文件"
            if ignored_count > 0:
                result_msg += f"\n[gitignore忽略了{ignored_count}个文件]"
            return result_msg
        # 处理输出限制
        # 如果只有一个结果，完整输出
        if len(matching_files) == 1:
            result_lines = [f"在 {abs_path} 中找到 1 个匹配文件:"]
            for file_path in sorted(matching_files):
                result_lines.append(f"  {file_path}")
            result_text = "\n".join(result_lines)
        else:
            # 如果有多个结果，检查总长度
            # 首先构建完整的输出
            result_lines = [f"在 {abs_path} 中找到 {len(matching_files)} 个匹配文件:"]
            for file_path in sorted(matching_files):
                result_lines.append(f"  {file_path}")
            full_output = "\n".join(result_lines)
            # 如果总长度小于等于1000个字符，返回完整输出
            if len(full_output) <= 1000:
                result_text = full_output
            else:
                # 如果超过1000个字符，需要截断
                # 先计算标题行长度（包括换行符）
                title_line = result_lines[0] + "\n"
                title_length = len(title_line)
                # 计算剩余可用长度
                remaining_length = 1000 - title_length - 50  # 留50个字符给省略信息
                # 收集部分文件
                displayed_files = []
                current_length = 0
                for i, file_path in enumerate(sorted(matching_files)):
                    file_line = f"  {file_path}\n"
                    line_length = len(file_line)
                    # 如果添加这一行会超过限制，停止添加
                    if current_length + line_length > remaining_length:
                        # 检查是否至少显示了一个文件
                        if not displayed_files:
                            # 如果连一个文件都显示不了，至少显示第一个
                            displayed_files.append(file_line.rstrip())
                            truncated = True
                        else:
                            truncated = True
                        break
                    displayed_files.append(file_line.rstrip())
                    current_length += line_length
                    truncated = False
                # 构建最终输出
                output_lines = [f"在 {abs_path} 中找到 {len(matching_files)} 个匹配文件:"]
                output_lines.extend(displayed_files)
                # 添加省略信息
                if truncated:
                    displayed_count = len(displayed_files)
                    output_lines.append(f"  ... (仅显示前{displayed_count}个文件，共{len(matching_files)}个)")
                result_text = "\n".join(output_lines)
        # 添加.gitignore忽略统计信息
        if ignored_count > 0:
            result_text += f"\n[gitignore忽略了{ignored_count}个文件]"
        return result_text
    except re.error as e:
        return f"查找失败：正则表达式错误 - {str(e)}"
    except Exception as e:
        return f"查找失败：{str(e)}"
def replace(
    file_path: str,
    replacements: list,
) -> str:
    """在文件中查找并替换文本内容
    Args:
    - file_path (str) [Required]: 要操作的文件路径
    - replacements (list) [Required]: 包含替换规则的JSON数组，每个对象包含search和replacement属性
    """
    try:
        abs_path = os.path.abspath(file_path)
        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return "替换失败：文件不存在"
        # 读取文件内容
        content = _read_file_with_encoding(abs_path)
        if content.startswith("[") and "读取文件失败" in content:
            return f"替换失败：无法读取文件 - {content}"
    except Exception as e:
        return f"替换失败：读取文件时发生异常 - {str(e)}"
    results = []
    new_content = content
    replacement_made = False
    try:
        # 处理每个替换规则
        for replacement in replacements:
            search_text = replacement.get('search', '')
            replacement_text = replacement.get('replacement', '')
            if not search_text:
                results.append("替换失败：search属性不能为空")
                continue
            # 检查原始内容中是否包含搜索文本
            # 支持不同换行符的匹配
            if search_text in new_content:
                # 直接替换
                new_content = new_content.replace(search_text, replacement_text)
                replacement_made = True
                results.append(f"替换成功：'{search_text[:30]}{'...' if len(search_text) > 30 else ''}'")
            else:
                # 尝试将搜索文本的换行符从 \n 改为 \r\n
                search_text_crlf = search_text.replace('\n', '\r\n')
                if search_text_crlf in new_content:
                    # 检查目标文件使用的是哪种换行符
                    if '\r\n' in content:
                        # 文件中主要使用 CRLF，保持风格一致
                        replacement_text_crlf = replacement_text.replace('\n', '\r\n')
                        new_content = new_content.replace(search_text_crlf, replacement_text_crlf)
                    else:
                        # 文件中主要使用 LF
                        new_content = new_content.replace(search_text_crlf, replacement_text)
                    replacement_made = True
                    results.append(f"替换成功'{search_text[:30]}{'...' if len(search_text) > 30 else ''}'")
                else:
                    # 使用正则表达式尝试更灵活的匹配
                    # 将搜索文本转义为正则表达式（正确处理括号等特殊字符）
                    # 先转义所有特殊字符，然后为换行符添加灵活性
                    escaped_text = re.escape(search_text)
                    # 将 \r 和 \n 的转义序列替换为可匹配不同换行符的模式
                    search_pattern = escaped_text.replace('\\r', '(\\r?)?').replace('\\n', '\\r?\\n')
                    if re.search(search_pattern, new_content, re.MULTILINE):
                        # 使用不同换行符格式进行替换
                        for src_nl, dst_nl in [('\n', '\n'), ('\r\n', '\n'), ('\n', '\r\n'), ('\r\n', '\r\n')]:
                            search_variant = search_text.replace('\r\n', '\n').replace('\n', src_nl)
                            if search_variant in new_content:
                                replacement_variant = replacement_text.replace('\r\n', '\n').replace('\n', dst_nl)
                                new_content = new_content.replace(search_variant, replacement_variant)
                                replacement_made = True
                                results.append(f"替换成功：'{search_text[:30]}{'...' if len(search_text) > 30 else ''}'")
                                break
                        if not replacement_made:
                            results.append(f"替换失败：找不到对应文本 '{search_text[:30]}{'...' if len(search_text) > 30 else ''}'")
                    else:
                        results.append(f"替换失败：找不到对应文本 '{search_text[:30]}{'...' if len(search_text) > 30 else ''}'")
        # 写回文件（仅当有修改时）
        if replacement_made:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                f.write(new_content)
        else:
            return "没有任何替换操作执行"
        return "\n".join(results) if results else "替换完成"
    except Exception as e:
        return f"替换失败：{str(e)}"
FILE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取一个或多个文本类型文件，或提取整个目录下的文本类型文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_names": {
                        "type": ["string", "array"],
                        "description": "要读取的所有文本类型文件的路径，也可以是含有文件的目录路径",
                    }
                },
                "required": ["file_names"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "创建新文件或更新现有文件内容。当backup为True时，如果目标文件已存在，将在同目录下创建.backup后缀的备份文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "目标文件路径",
                    },
                    "file_content": {
                        "type": ["string", "object"],
                        "description": "文件内容",
                    },
                    "backup": {
                        "type": "boolean",
                        "description": "是否创建备份文件，默认为False",
                        "default": False
                    }
                },
                "required": ["file_name", "file_content"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find",
            "description": "在指定路径下按文件名或文件内容查找文件。支持正则表达式匹配文件名和内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_path": {
                        "type": "string",
                        "description": "要查找的目录路径",
                    },
                    "file_name": {
                        "type": "string",
                        "description": "文件名正则表达式，用于匹配文件名（可选）",
                    },
                    "content": {
                        "type": "string",
                        "description": "内容正则表达式，用于匹配文件内容（可选）",
                    }
                },
                "required": ["search_path"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace",
            "description": "在文件中查找并替换文本内容，可以在replacement前后附带一些原始文本，作为插入编辑使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                    "replacements": {
                        "type": "array",
                        "description": "包含替换规则的JSON数组，每个对象包含search和replacement属性",
                        "items": {
                            "type": "object",
                            "properties": {
                                "search": {"type": "string", "description": "要查找的文本"},
                                "replacement": {"type": "string", "description": "要替换成的文本"}
                            },
                            "required": ["search", "replacement"]
                        }
                    }
                },
                "required": ["file_path", "replacements"],
            },
        }
    }
]
FILE_FUNCTIONS = {
    "read_file": read_file,
    "create_file": create_file,
    "replace": replace,
    "find": find
}
