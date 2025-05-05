
def get_current_weather(location: str, unit: str = "celsius") -> str:
    """获取当前天气情况"""
    return f"{location}的天气是22度{unit}"

def get_stock_price(stock_symbol: str) -> str:
    """获取股票当前价格"""
    return f"{stock_symbol}的当前价格是$150.75"

def read_file(file_name: str):
    try:
        with open(file_name, 'r',encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "文件不存在"
    except Exception as e:
        return f"读取文件时发生错误: {str(e)}"

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
    }
]

# 工具名称到函数的映射
TOOL_FUNCTIONS = {
    "get_current_weather": get_current_weather,
    "get_stock_price": get_stock_price,
    "read_file": read_file,
}