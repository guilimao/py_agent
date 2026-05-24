"""
命令行工具 —— 在全新隔离会话中执行命令，完成后自动销毁。

当命令输出超过 MAX_RETURN_CHARS 时，返回结构化溢出信号（type: "overflow"），
由 Agent 层负责创建托管临时文件并管理其生命周期。
"""

import os
import subprocess
import time

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 单次返回内容的最大字符数，超出部分触发溢出转储
MAX_RETURN_CHARS = 100000


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


def execute_command(command: str = None, timeout: int = 30):
    """
    在全新隔离会话中执行一条 shell 命令，完成后自动销毁会话。

    - 每条命令独立运行，不共享状态。
    - 输出不做截断，完整返回。
    - 超时后强制终止并返回已产生的输出。
    - 当输出超过 100,000 字符时，将完整内容保存到临时文件，
      返回文件路径及按需读取命令提示。

    Args:
        command: 要执行的 shell 命令。
        timeout: 超时秒数（默认 30）。

    Returns:
        - str: 命令执行结果（未超过长度限制）
        - dict: {"type": "overflow", "content": ..., "url": ..., "title": ...,
                  "source_type": "命令输出"}
          内容过长时的溢出信号，由 Agent 层处理
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

            result = f"""
📟 终端 - 命令执行完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {command}
⏱️  耗时: {elapsed}秒
📋 输出结果:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 执行状态: 执行完毕
"""
            return _check_overflow(result, command)

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate()
            output_text = _decode_output(stdout)
            elapsed = int(time.time() - start_time)

            result = f"""
📟 终端 - 命令超时
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {command}
⏱️  运行时间: {elapsed}秒 (超时)
📋 当前输出:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 执行状态: 超时终止
"""
            return _check_overflow(result, command)

    except Exception as e:
        return f"❌ 执行命令时发生错误: {str(e)}"


# ---------------------------------------------------------------------------
# 溢出检查
# ---------------------------------------------------------------------------

def _check_overflow(content: str, command: str, max_chars: int = MAX_RETURN_CHARS):
    """检查命令输出是否超过长度限制。

    Returns:
        - str: 内容未超限，原样返回
        - dict: 溢出信号，交由 Agent 层处理
    """
    if len(content) > max_chars:
        return {
            "type": "overflow",
            "content": content,
            "source_type": "命令输出",
            "url": "",
            "title": f"命令: {command}",
        }
    return content


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
                "当输出超过 100,000 字符时，自动保存到临时文件并返回路径，"
                "可使用 cat/head/tail/grep/less 等命令按需读取。"
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
