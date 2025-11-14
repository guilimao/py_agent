import os
import json
from typing import Union, Dict, List


def read_file(file_names: Union[str, List[str]]) -> str:
    """
    读取一个或多个文件的内容
    
    Args:
        file_names: 文件路径（字符串）或文件路径列表
    
    Returns:
        文件内容字符串，如果是多个文件则返回合并的内容
        格式：<文件路径>\n文件内容
    """
    # 如果输入是单个文件路径字符串，转换为列表
    if isinstance(file_names, str):
        file_list = [file_names]
    else:
        file_list = file_names
    
    results = []
    
    for file_name in file_list:
        try:
            abs_path = os.path.abspath(file_name)
            
            # 检查文件是否存在
            if not os.path.exists(abs_path):
                results.append(f"{abs_path}\n文件不存在")
                continue
            
            # 检查是否是文件（而非目录）
            if not os.path.isfile(abs_path):
                results.append(f"{abs_path}\n路径指向的不是文件")
                continue
            
            # 获取文件信息
            file_size = os.path.getsize(abs_path)
            file_stat = os.stat(abs_path)
            
            # 读取文件内容 - 修复编码问题
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    lines_list = file.readlines()
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试GBK编码（适用于中文Windows系统）
                try:
                    with open(file_name, 'r', encoding='gbk') as file:
                        lines_list = file.readlines()
                except UnicodeDecodeError:
                    # 如果GBK也失败，使用错误处理模式
                    with open(file_name, 'r', encoding='utf-8', errors='replace') as file:
                        lines_list = file.readlines()
            
            # 计算总行数
            total_lines = len(lines_list)
            
            # 处理空文件情况
            if total_lines == 0:
                results.append(f"{abs_path}\n文件为空")
                continue
            
            content = ''.join(lines_list)
            result = f"{abs_path}\n{content}"
            
            results.append(result.strip())
            
        except FileNotFoundError:
            results.append(f"{os.path.abspath(file_name)}\n文件不存在")
        except UnicodeDecodeError as e:
            results.append(f"{os.path.abspath(file_name)}\n文件编码错误：无法以UTF-8编码读取文件 - {str(e)}")
        except PermissionError as e:
            results.append(f"{os.path.abspath(file_name)}\n权限错误：无法读取文件 - {str(e)}")
        except Exception as e:
            results.append(f"{os.path.abspath(file_name)}\n读取文件时发生错误: {str(e)}")
    
    # 如果是单个文件，直接返回结果；如果是多个文件，合并结果
    if len(file_list) == 1:
        return results[0] if results else "没有文件被处理"
    else:
        return "\n\n" + "="*50 + "\n\n".join(results)


def create_file(file_name: str, file_content: Union[str, Dict, List]) -> str:
    try:
        abs_path = os.path.abspath(file_name)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # 处理JSON对象或数组，转换为格式化字符串
        if isinstance(file_content, (Dict, List)):
            file_content_str = json.dumps(file_content, ensure_ascii=False, indent=2)
        else:
            file_content_str = str(file_content)
        
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(file_content_str)
        
        result = f"{abs_path}\n{file_content_str}"
        return result.strip()
    except json.JSONDecodeError as e:
        return f"JSON序列化错误：无法将内容转换为JSON字符串 - {str(e)}"
    except Exception as e:
        return f"创建/修改文件时发生错误：{str(e)}"
    
def find_replace(
    file_path: str,
    find_text: str,
    replace_text: str,
) -> str:
    """查找file_path中与find_text匹配的内容并替换为replace_text

    Args:
    - file_path (str) [Required]: 要操作的文件路径
    - find_text (str) [Required]: 需要查找的文本内容
    - replace_text (str) [Required]: 要替换成的文本内容

    """
    try:
        abs_path = os.path.abspath(file_path)
        
        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return f"❌ 文件不存在：{abs_path}"
        
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 如果UTF-8失败，尝试GBK编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
    except FileNotFoundError:
        return f"{os.path.abspath(file_path)}\n文件不存在"
    except Exception as e:
        return f"{os.path.abspath(file_path)}\n错误：读取文件时发生异常 - {str(e)}"
    
    try:
        matched_times = 0
        new_content = content

        # 使用更精确的匹配方式
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

        # 写回文件（仅当有修改时）
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return f"{abs_path}\n<查找内容>\n{find_text}\n<更新内容>\n{replace_text}"
        else:
            return f"{abs_path}\n未找到匹配内容\n查找文本：{find_text}"
    
    except Exception as e:
        return f"❌ 替换操作失败：{str(e)}"


FILE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取一个或多个文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_names": {
                        "type": ["string", "array"],
                        "description": "文件路径（字符串）或多个文件路径列表",
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
            "description": "创建新文件或更新现有文件内容。",
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
                },
                "required": ["file_name", "file_content"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_replace",
            "description": "查找文件中指定文本并替换为新文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                    "find_text": {
                        "type": "string",
                        "description": "需查找的文本内容",
                    },
                    "replace_text": {
                        "type": "string",
                        "description": "替换成的文本内容",
                    },
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