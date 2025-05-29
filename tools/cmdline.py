import subprocess
from typing import Optional

def execute_command(command: str) -> str:
    """
    执行命令行指令并返回执行结果（无报错时若输出为空会返回成功提示）
    """
    try:
        # 将编码从gbk改为utf-8，适配Git等工具的UTF-8输出
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',  # 关键修改点
            check=True
        )
        if not result.stdout.strip():
            return f"命令执行成功：{command}"
        return result.stdout
    except subprocess.CalledProcessError as e:
        # 错误输出使用utf-8解码
        error_output = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr
        return f"执行命令时发生错误: {error_output}"
    except Exception as e:
        return f"发生未知错误: {str(e)}"

COMMAND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "执行命令行指令并返回执行结果（多行命令最好以文件形式执行，操作系统为windows）",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令行指令",
                    },
                },
                "required": ["command"],
            },
        }
    }
]

COMMAND_FUNCTIONS = {
    "execute_command": execute_command
}
