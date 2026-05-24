"""
命令行工具 —— 在全新隔离会话中执行命令，完成后自动销毁。
"""

import os
import subprocess
import time


def _decode_output(data: bytes) -> str:
    """解码命令输出，按操作系统优先级自动检测编码。"""
    if not data:
        return ""

    if os.name == 'nt':
        encodings = ['gbk', 'gb2312', 'utf-8', 'latin-1']
    else:
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']

    for encoding in encodings:
        try:
            return data.decode(encoding, errors='strict')
        except UnicodeDecodeError:
            continue

    return data.decode('latin-1', errors='ignore')


def execute_command(command: str = None, timeout: int = 30) -> str:
    """
    在全新隔离会话中执行一条 shell 命令，完成后自动销毁会话。

    - 每条命令独立运行，不共享状态。
    - 输出不做截断，完整返回。
    - 超时后强制终止并返回已产生的输出。

    Args:
        command: 要执行的 shell 命令。
        timeout: 超时秒数（默认 30）。
    """
    if not command:
        return "❌ 错误：必须提供要执行的命令(command)"

    try:
        start_time = time.time()

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            executable='/bin/bash' if os.name != 'nt' else None,
        )

        try:
            stdout, _ = process.communicate(timeout=timeout)
            output_text = _decode_output(stdout)
            elapsed = int(time.time() - start_time)

            return f"""
📟 终端 - 命令执行完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {command}
⏱️  耗时: {elapsed}秒
📋 输出结果:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 执行状态: 执行完毕
"""

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate()
            output_text = _decode_output(stdout)
            elapsed = int(time.time() - start_time)

            return f"""
📟 终端 - 命令超时
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {command}
⏱️  运行时间: {elapsed}秒 (超时)
📋 当前输出:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 执行状态: 超时终止
"""

    except Exception as e:
        return f"❌ 执行命令时发生错误: {str(e)}"


# ---------------------------------------------------------------------------
# 工具元信息（供 LLM 识别）
# ---------------------------------------------------------------------------

COMMAND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "在命令行终端中执行命令。"
                "每条命令在一个全新的隔离会话中运行，命令结束（或超时）后会话自动销毁。"
                "输出长度不设上限，完整返回所有内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "需要执行的 shell 命令",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "命令超时时间（秒）。超时后会话强制终止并关闭。默认值为 30。",
                        "default": 30,
                    },
                },
                "required": ["command"],
            },
        },
    }
]

# ---------------------------------------------------------------------------
# 工具函数映射（供 Agent 调用）
# ---------------------------------------------------------------------------

COMMAND_FUNCTIONS = {
    "execute_command": execute_command,
}
