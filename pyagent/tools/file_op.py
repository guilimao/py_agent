import os
import json
from typing import Union, Dict, List


def read_file(file_names: Union[str, List[str]], start_line: int = None, end_line: int = None) -> str:
    """
    读取一个或多个文件的内容
    
    Args:
        file_names: 文件路径（字符串）或文件路径列表
        start_line: 开始行号（可选，从1开始）
        end_line: 结束行号（可选，从1开始）
    
    Returns:
        文件内容字符串，如果是多个文件则返回合并的内容
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
                results.append(f"❌ 文件不存在：{abs_path}")
                continue
            
            # 检查是否是文件（而非目录）
            if not os.path.isfile(abs_path):
                results.append(f"❌ 路径指向的不是文件：{abs_path}")
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
                results.append(f"✅ 文件读取成功，但文件为空！\n📁 文件路径：{abs_path}\n📊 文件大小：{file_size} 字节\n📝 行数：0 行")
                continue
            
            # 处理行范围参数
            if start_line is not None or end_line is not None:
                # 处理负索引和边界情况
                if start_line is None:
                    start_line = 1
                elif start_line < 0:
                    start_line = max(1, total_lines + start_line + 1)
                else:
                    start_line = max(1, min(start_line, total_lines))
                    
                if end_line is None:
                    end_line = total_lines
                elif end_line < 0:
                    end_line = max(1, total_lines + end_line + 1)
                else:
                    end_line = max(1, min(end_line, total_lines))
                
                # 确保start_line <= end_line
                if start_line > end_line:
                    start_line, end_line = end_line, start_line
                
                # 提取指定范围的行
                selected_lines = lines_list[start_line-1:end_line]
                content = ''.join(selected_lines)
                actual_lines = len(selected_lines)
                
                result = f"""
✅ 文件读取成功！
📁 文件路径：{abs_path}
📊 文件大小：{file_size} 字节
📝 总行数：{total_lines} 行
📖 读取范围：第{start_line}行到第{end_line}行 (共{actual_lines}行)
📄 文件内容：
{content}
"""
            else:
                content = ''.join(lines_list)
                result = f"""
✅ 文件读取成功！
📁 文件路径：{abs_path}
📊 文件大小：{file_size} 字节
📝 行数：{total_lines} 行
📄 文件内容：
{content}
"""
            
            results.append(result.strip())
            
        except FileNotFoundError:
            results.append(f"❌ 文件不存在：{os.path.abspath(file_name)}")
        except UnicodeDecodeError as e:
            results.append(f"❌ 文件编码错误：无法以UTF-8编码读取文件 - {str(e)}")
        except PermissionError as e:
            results.append(f"❌ 权限错误：无法读取文件 - {str(e)}")
        except Exception as e:
            results.append(f"❌ 读取文件时发生错误: {str(e)}")
    
    # 如果是单个文件，直接返回结果；如果是多个文件，合并结果
    if len(file_list) == 1:
        return results[0] if results else "❌ 没有文件被处理"
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
        
        # 检查文件是否已存在
        file_exists = os.path.exists(abs_path)
        
        # 获取文件大小
        original_size = 0
        if file_exists:
            original_size = os.path.getsize(abs_path)
        
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(file_content_str)
        
        # 获取新文件大小
        new_size = os.path.getsize(abs_path)
        
        # 生成详细的反馈信息
        action = "修改" if file_exists else "创建"
        status = "成功"
        
        # 文件内容摘要（前200字符）
        content_preview = file_content_str[:200]
        if len(file_content_str) > 200:
            content_preview += "..."
        
        # 返回详细的确认信息
        result = f"""
✅ 文件{action}{status}！
📁 文件路径：{abs_path}
🔍 操作类型：{'覆盖现有文件' if file_exists else '新建文件'}
📊 文件大小：{new_size} 字节 (原大小：{original_size} 字节)
📝 内容摘要：
{content_preview}

文件已成功写入磁盘。
"""
        return result.strip()
    except json.JSONDecodeError as e:
        return f"❌ JSON序列化错误：无法将内容转换为JSON字符串 - {str(e)}"
    except Exception as e:
        return f"❌ 创建/修改文件时发生错误：{str(e)}"
    
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
        return f"❌ 文件不存在：{file_path}"
    except Exception as e:
        return f"❌ 错误：读取文件时发生异常 - {str(e)}"
    
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
            
            # 获取文件信息
            file_size = os.path.getsize(abs_path)
            lines = new_content.count('\n') + 1 if new_content else 0
            
            return f"""
✅ 替换操作成功完成！
📁 文件路径：{abs_path}
🔍 查找文本："{find_text}"
🔄 替换文本："{replace_text}"
📊 替换次数：{matched_times} 处
📏 文件大小：{file_size} 字节
📝 总行数：{lines} 行

文件已成功更新并保存到磁盘。
""".strip()
        else:
            return f"""
⚠️ 未找到匹配内容
📁 文件路径：{abs_path}
🔍 查找文本："{find_text}"
❓ 建议：未找到匹配的文本，请检查查找内容是否正确，或使用create_file工具直接修改文件。
""".strip()
    
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
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "开始行号（可选，从1开始）",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "结束行号（可选，从1开始）",
                    },
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