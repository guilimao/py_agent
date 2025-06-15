import os
import re
import difflib
import json
from typing import Union, Dict, List


def read_file(file_name: str) -> str:
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "文件不存在"
    except Exception as e:
        return f"读取文件时发生错误: {str(e)}"


def create_file(file_name: str, file_content: Union[str, Dict, List]) -> str:
    try:
        abs_path = os.path.abspath(file_name)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # 处理JSON对象或数组，转换为格式化字符串
        if isinstance(file_content, (Dict, List)):
            file_content_str = json.dumps(file_content, ensure_ascii=False, indent=0)
        else:
            file_content_str = str(file_content)
        
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(file_content_str)
        
        return f"文件{abs_path}创建/修改成功！内容已写入。"
    except json.JSONDecodeError as e:
        return f"JSON序列化错误：无法将内容转换为JSON字符串 - {str(e)}"
    except Exception as e:
        return f"创建/修改文件时发生错误：{str(e)}"
    
def find_replace(
    file_path: str,
    find_text: str,
    replace_text: str,
    use_regex: bool = False,
    preserve_indent: bool = False,
    ignore_indent: bool = False,
    case_sensitive: bool = True
) -> str:
    """查找file_path中与find_text匹配的内容并替换为replace_text，支持多种优化选项

    Args:
    - file_path (str) [Required]: 要操作的文件路径
    - find_text (str) [Required]: 需要查找的文本内容（支持正则表达式）
    - replace_text (str) [Required]: 要替换成的文本内容（正则模式下支持捕获组引用）
    - use_regex (bool): 是否使用正则表达式匹配（默认False）
    - preserve_indent (bool): 是否保留原匹配行的缩进格式（仅对行级匹配有效，默认False）
    - ignore_indent (bool): 是否忽略缩进差异（匹配时去除两边空白，默认False）
    - case_sensitive (bool): 是否区分大小写（默认True）
    """
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"错误：文件不存在 - {file_path}"
    except Exception as e:
        return f"错误：读取文件时发生异常 - {str(e)}"
    
    try:
        matched_times = 0
        new_content = content
        
        # 处理缩进忽略需求
        if ignore_indent:
            find_text_stripped = find_text.strip()
            if not find_text_stripped:
                return "错误：find_text去除缩进后为空"
            # 使用正则匹配行内容（去除缩进）
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(rf'^(\s*){re.escape(find_text_stripped)}(\s*)$', flags=flags | re.MULTILINE)
            # 替换时保留原行的缩进和行尾空白
            replace_func = lambda m: f'{m.group(1)}{replace_text.strip()}{m.group(2)}'
            new_content = pattern.sub(replace_func, content)
            matched_times = len(pattern.findall(content))
        
        # 处理正则表达式需求
        elif use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            if preserve_indent:
                # 匹配行首缩进+目标文本，保留缩进
                pattern = re.compile(rf'(^\s*){find_text}', flags=flags | re.MULTILINE)
                replace_func = lambda m: f'{m.group(1)}{replace_text}'
                new_content = pattern.sub(replace_func, content)
            else:
                pattern = re.compile(find_text, flags=flags)
                new_content = pattern.sub(replace_text, content)
            matched_times = len(pattern.findall(content))
        
        # 普通字符串替换（保留原逻辑）
        else:
            if not case_sensitive:
                find_text_lower = find_text.lower()
                content_lower = content.lower()
                matched_times = content_lower.count(find_text_lower)
                if matched_times > 0:
                    new_content = ''
                    idx = 0
                    while idx < len(content):
                        pos = content_lower.find(find_text_lower, idx)
                        if pos == -1:
                            new_content += content[idx:]
                            break
                        new_content += content[idx:pos] + replace_text
                        idx = pos + len(find_text)
                else:
                    new_content = content
            else:
                matched_times = content.count(find_text)
                new_content = content.replace(find_text, replace_text)
        
        # 写回文件（仅当有修改时）
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        
        # 生成返回信息
        options_msg = f"使用选项：\n- 正则表达式：{'是' if use_regex else '否'}\n- 保留缩进：{'是' if preserve_indent else '否'}\n- 忽略缩进：{'是' if ignore_indent else '否'}\n- 区分大小写：{'是' if case_sensitive else '否'}"
        
        if matched_times == 0:
            # 查找近似匹配的行
            def find_approximate():
                if use_regex:
                    return []
                lines = content.split('\n')
                approx = []
                for line in lines:
                    # 处理忽略缩进
                    line_processed = line.strip() if ignore_indent else line
                    # 处理大小写
                    if not case_sensitive:
                        line_processed = line_processed.lower()
                        find_processed = find_text.lower()
                    else:
                        find_processed = find_text
                    # 计算相似性
                    if not find_processed:
                        continue
                    similarity = difflib.SequenceMatcher(None, line_processed, find_processed).ratio()
                    if similarity > 0.7:
                        approx.append(line)
                return approx[:3]  # 取前3个最相似的
            
            approx_lines = find_approximate()
            approx_msg = "\n近似匹配的行（相似性>70%）：\n" + "\n".join([f"- {line}" for line in approx_lines]) if approx_lines else "\n未找到近似匹配的行"
            return f"结果：未找到与find_text匹配的内容。\n{options_msg}{approx_msg}"
        else:
            return f"结果：成功在文件{file_path}中完成替换，共替换{matched_times}处。\n{options_msg}"
    
    except re.error as e:
        return f"错误：正则表达式语法错误 - {str(e)}"
    except Exception as e:
        return f"错误：查找替换时发生异常 - {str(e)}"


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
            "name": "create_file",
            "description": "创建新文件或更新现有文件内容。支持直接传入JSON对象/数组（会自动格式化写入）或字符串。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "目标文件的路径（含文件名）",
                    },
                    "file_content": {
                        "type": ["string", "object", "array"],
                        "description": "文件内容：可以是字符串（直接写入）、JSON对象/数组（自动格式化）",
                    },
                },
                "required": ["file_name", "file_content"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_replace",
            "description": "查找文件中指定文本并替换为新文本，支持正则表达式、缩进处理等优化选项",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "要操作的文件路径",
                    },
                    "find_text": {
                        "type": "string",
                        "description": "需要查找的文本内容（支持正则表达式）",
                    },
                    "replace_text": {
                        "type": "string",
                        "description": "要替换成的文本内容（正则模式下支持捕获组引用）",
                    },
                    "use_regex": {
                        "type": "boolean",
                        "description": "是否使用正则表达式匹配（默认False）",
                        "default": False
                    },
                    "preserve_indent": {
                        "type": "boolean",
                        "description": "是否保留原匹配行的缩进格式（仅对行级匹配有效，默认False）",
                        "default": False
                    },
                    "ignore_indent": {
                        "type": "boolean",
                        "description": "是否忽略缩进差异（匹配时去除两边空白，默认False）",
                        "default": False
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "是否区分大小写（默认True）",
                        "default": True
                    }
                },
                "required": ["file_path", "find_text", "replace_text"],
            },
        }
    }
]


FILE_FUNCTIONS = {
    "read_file": read_file,
    "create_file": create_file,
    "find_replace": find_replace
}