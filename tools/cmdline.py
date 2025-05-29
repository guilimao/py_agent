import subprocess
from typing import Optional

def execute_command(command: str) -> str:
    """
    执行命令行指令并返回执行结果（无报错时若输出为空会返回成功提示）
    """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            return f"命令执行成功：{command}"
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"执行命令时发生错误: {e.stderr}"
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
