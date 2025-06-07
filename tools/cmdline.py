import subprocess
from typing import Optional
import chardet
import sys
import os

def execute_command(command: str) -> str:
    """
    执行命令行指令并返回执行结果（支持中文输入/输出）
    """
    try:
        # 检测系统默认编码（Windows中文环境通常是'gbk'）
        system_encoding = sys.getdefaultencoding()
        
        # 转换命令为系统编码（处理中文路径/参数）
        encoded_command = command.encode(system_encoding, errors='replace')
        
        # 特殊处理PowerShell命令
        if command.lower().startswith('powershell'):
            # 添加UTF-8输出编码指令
            ps_command = f"chcp 65001 > nul; {command}; exit $LASTEXITCODE"
            result = subprocess.run(
                ps_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
        else:
            result = subprocess.run(
                encoded_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
        
        # 合并输出流
        combined_output = result.stdout + result.stderr
        
        if not combined_output.strip():
            return f"命令执行成功：{command}"
            
        # 检测输出编码（优先使用系统编码）
        detected_encoding = chardet.detect(combined_output)['encoding']
        final_encoding = detected_encoding if detected_encoding else system_encoding
        
        try:
            decoded_output = combined_output.decode(final_encoding, errors='replace')
        except UnicodeDecodeError:
            # 回退到系统编码
            decoded_output = combined_output.decode(system_encoding, errors='replace')
            
        return decoded_output
    
    except subprocess.CalledProcessError as e:
        error_bytes = e.stderr if e.stderr else b''
        detected_encoding = chardet.detect(error_bytes)['encoding'] or system_encoding
        return f"执行命令时发生错误: {error_bytes.decode(detected_encoding, errors='replace')}"
        
    except Exception as e:
        return f"发生未知错误: {str(e)}"


COMMAND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "执行命令行指令并返回执行结果（支持中文输入/输出，操作系统为windows）",
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