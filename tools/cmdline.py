import subprocess
from typing import Optional
import chardet  # 新添加的chardet库

def execute_command(command: str) -> str:
    """
    执行命令行指令并返回执行结果（无报错时若输出为空会返回成功提示）
    """
    try:
        # 关键修改：将text=True改为text=False，获取字节流
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=False,  # 改为字节流模式
            check=True
        )
        
        # 检测stdout编码（优先使用stdout，若为空则检测stderr）
        if result.stdout:
            detected_encoding = chardet.detect(result.stdout)['encoding'] or 'utf-8'
            stdout = result.stdout.decode(detected_encoding, errors='replace')
        else:
            detected_encoding = 'utf-8'
            stdout = ''

        # 处理stderr（如果有错误）
        if result.stderr:
            stderr = result.stderr.decode(detected_encoding, errors='replace')
        else:
            stderr = ''

        # 输出结果处理
        if not stdout.strip() and not stderr.strip():
            return f"命令执行成功：{command}"
        return stdout + stderr  # 合并标准输出和错误输出

    except subprocess.CalledProcessError as e:
        # 检测错误输出的编码
        error_bytes = e.stderr if isinstance(e.stderr, bytes) else b''
        detected_encoding = chardet.detect(error_bytes)['encoding'] or 'utf-8'
        error_output = error_bytes.decode(detected_encoding, errors='replace')
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
