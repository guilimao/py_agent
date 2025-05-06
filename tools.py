import os

def read_file(file_name: str) -> str:
    try:
        with open(file_name, 'r',encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "文件不存在"
    except Exception as e:
        return f"读取文件时发生错误: {str(e)}"

def list_directory(directory:str)->str:
    try:
        items = os.listdir(directory)
        return "\n".join(items) if items else f"目录{directory}为空"
    except FileNotFoundError:
        return f"目录{directory}不存在"
    except Exception as e:
        return f"列出目录时发生错误: {str(e)}"
    
def create_file(file_name: str, file_content: str) -> str:
    try:
        with open(file_name, 'w',encoding='utf-8') as file:
            file.write(file_content)
        return "文件创建成功"
    except Exception as e:
        return f"创建文件时发生错误: {str(e)}"
    
def delete_file(file_path: str) -> str: 
    try:
        os.remove(file_path)
        return "文件删除成功"
    except FileNotFoundError:
        return f"文件{file_path}不存在"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定位置的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市或地区名称",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位",
                    },
                },
                "required": ["location"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "获取指定股票的当前价格",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_symbol": {
                        "type": "string",
                        "description": "股票代码，例如AAPL",
                    },
                },
                "required": ["stock_symbol"],
            },
        }
    },
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
            "name": "list_directory",
            "description": "列出指定目录下的所有文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目录路径",
                    },
                },
                "required": ["directory"],
            },
            
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "创建一个新文件",
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
            "name": "delete_file",
            "description": "删除一个文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                },
                "required": ["file_path"],
            },
        }
    }

]

# 工具名称到函数的映射
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_directory": list_directory,
    "create_file": create_file,
    "delete_file": delete_file,
}