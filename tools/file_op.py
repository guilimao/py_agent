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
) -> str:
    """查找file_path中与find_text匹配的内容并替换为replace_text

    Args:
    - file_path (str) [Required]: 要操作的文件路径
    - find_text (str) [Required]: 需要查找的文本内容
    - replace_text (str) [Required]: 要替换成的文本内容

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
        

        if matched_times == 0:
            return f"结果：工具内部错误，请换用create_file工具进行操作。"
        else:
            return f"结果：成功在文件{file_path}中完成替换，共替换{matched_times}处。\n"
    
    except Exception as e:
        return f"错误：工具内部错误，请换用create_file工具进行操作。 - {str(e)}"


FILE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "文件路径",
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
            "description": "创建新文件或更新现有文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "目标文件路径",
                    },
                    "file_content": {
                        "type": ["string", "object", "array"],
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