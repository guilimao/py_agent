"""
命令行工具 —— 在全新隔离会话中执行命令，完成后自动销毁。

当命令输出超过 MAX_RETURN_CHARS 时，返回结构化溢出信号（type: "overflow"），
由 Agent 层负责创建托管临时文件并管理其生命周期。
"""

import os
import shutil
import signal
import subprocess
import time

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 单次返回内容的最大字符数，超出部分触发溢出转储
MAX_RETURN_CHARS = 100000

GIT_BASH_CANDIDATES = (
    os.path.join(os.environ.get("ProgramW6432", r"C:\Program Files"), "Git", "bin", "bash.exe"),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Git", "bin", "bash.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Git", "bin", "bash.exe"),
    os.path.join(os.environ.get("LocalAppData", ""), "Programs", "Git", "bin", "bash.exe"),
)


def _decode_output(data: bytes) -> str:
    """解码命令输出，按操作系统优先级自动检测编码。"""
    if not data:
        return ""

    if os.name == 'nt':
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16-le', 'latin-1']
    else:
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']

    for encoding in encodings:
        try:
            return data.decode(encoding, errors='strict')
        except UnicodeDecodeError:
            continue

    return data.decode('latin-1', errors='ignore')


def _find_git_bash() -> str:
    """查找 Windows 上的 Git Bash 可执行文件，不提供 PowerShell/cmd 回退。"""
    env_path = os.environ.get("GIT_BASH_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    which_path = shutil.which("bash.exe")
    if which_path and "git" in which_path.lower():
        return which_path

    for candidate in GIT_BASH_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        "未找到 Git Bash。请先安装 Git for Windows，或设置 GIT_BASH_PATH 指向 bash.exe。"
    )


def _build_command(command: str):
    """构造平台对应的子进程参数。"""
    if os.name == 'nt':
        git_bash = _find_git_bash()
        return {
            "args": [git_bash, "-lc", command],
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        }

    return {
        "args": command,
        "shell": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "executable": '/bin/bash',
        "start_new_session": True,
    }


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """终止命令进程及其子进程，避免遗留孤儿进程。"""
    if process.poll() is not None:
        return

    try:
        if os.name == 'nt':
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _collect_process_output(
    process: subprocess.Popen,
    command: str,
    timeout: int,
    start_time: float,
):
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
        _terminate_process_tree(process)
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

    process = None
    try:
        start_time = time.time()
        process = subprocess.Popen(**_build_command(command))
        return _collect_process_output(process, command, timeout, start_time)
    except FileNotFoundError as e:
        return f"❌ 执行命令时发生错误: {str(e)}"
    except Exception as e:
        return f"❌ 执行命令时发生错误: {str(e)}"
    finally:
        if process is not None:
            _terminate_process_tree(process)
            stdout = getattr(process, "stdout", None)
            if stdout is not None:
                try:
                    stdout.close()
                except Exception:
                    pass


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
