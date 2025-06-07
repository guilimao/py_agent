import os


def read_file(file_name: str) -> str:
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "文件不存在"
    except Exception as e:
        return f"读取文件时发生错误: {str(e)}"


def create_file(file_name: str, file_content: str) -> str:
    try:
        abs_path = os.path.abspath(file_name)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(file_content)
        return "文件创建/修改成功！"
    except Exception as e:
        return f"创建文件时发生错误: {str(e)}"
    


def find_replace(file_path: str, find_text: str, replace_text: str) -> str:
    """查找file_path中与find_text相同的部分，将其替换为replace_text，并保存

    Args:
    - file_path (str) [Required]: 要操作的文件路径
    - find_text (str) [Required]: 需要查找的文本内容
    - replace_text (str) [Required]: 要替换成的文本内容
    """
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 执行替换（全局替换）
        new_content = content.replace(find_text, replace_text)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return f"成功在文件{file_path}中完成替换，共替换{content.count(find_text)}处"
    except Exception as e:
        return f"查找替换时发生错误: {str(e)}"


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
            "description": "创建新文件，或更新文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "文件名",
                    },
                    "file_content": {
                        "type": "string",
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
                        "description": "要操作的文件路径",
                    },
                    "find_text": {
                        "type": "string",
                        "description": "需要查找的文本内容",
                    },
                    "replace_text": {
                        "type": "string",
                        "description": "要替换成的文本内容",
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