"""
命令行工具 —— 在全新隔离会话中执行命令，完成后自动销毁。

移植并增强自 pi 框架（@earendil-works/pi-coding-agent）的 bash 工具：
- 双维度输出截断：行数限制（默认 2000 行）+ 字节限制（默认 50KB），先到先截
- 流式输出累加器：滚动缓冲区 + 自动临时文件落盘
- 渐进式展示：保留输出末尾（tail），适合查看命令错误和最终结果
- 更好的错误处理：区分退出码、超时、中断
- 跨平台支持：Windows（Git Bash）/ Linux / macOS
"""

import os
import random
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 单次返回内容的最大行数
DEFAULT_MAX_LINES = 2000
# 单次返回内容的最大字节数
DEFAULT_MAX_BYTES = 50 * 1024  # 50KB

# Git Bash 候选路径（Windows）
GIT_BASH_CANDIDATES = (
    os.path.join(os.environ.get("ProgramW6432", r"C:\Program Files"), "Git", "bin", "bash.exe"),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Git", "bin", "bash.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Git", "bin", "bash.exe"),
    os.path.join(os.environ.get("LocalAppData", ""), "Programs", "Git", "bin", "bash.exe"),
)

# 进程树跟踪（用于跨平台清理）
_tracked_pids: set[int] = set()
_tracked_pids_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 截断工具（移植自 pi 框架 truncate.js）
# ---------------------------------------------------------------------------

def _split_lines_for_counting(content: str) -> list:
    """将内容按行拆分，末尾空行不计。"""
    if len(content) == 0:
        return []
    lines = content.split("\n")
    if content.endswith("\n"):
        lines.pop()
    return lines


def format_size(byte_count: int) -> str:
    """将字节数格式化为人类可读的大小字符串。"""
    if byte_count < 1024:
        return f"{byte_count}B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f}KB"
    else:
        return f"{byte_count / (1024 * 1024):.1f}MB"


def _truncate_string_to_bytes_from_end(text: str, max_bytes: int) -> str:
    """从末尾截断字符串到指定字节数，正确处理 UTF-8 多字节字符。"""
    buf = text.encode("utf-8")
    if len(buf) <= max_bytes:
        return text
    start = len(buf) - max_bytes
    # 找到合法的 UTF-8 字符边界
    while start < len(buf) and (buf[start] & 0xC0) == 0x80:
        start += 1
    return buf[start:].decode("utf-8")


def truncate_tail(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """
    从末尾保留内容（保留最后 N 行/字节），适合命令输出。

    如果最后一行的字节数超过限制，可能返回部分行。

    Returns:
        dict: {
            "content": str,          # 截断后的内容
            "truncated": bool,       # 是否被截断
            "truncated_by": str|None, # "lines" / "bytes" / None
            "total_lines": int,
            "total_bytes": int,
            "output_lines": int,
            "output_bytes": int,
            "last_line_partial": bool,
            "max_lines": int,
            "max_bytes": int,
        }
    """
    total_bytes = len(content.encode("utf-8"))
    lines = _split_lines_for_counting(content)
    total_lines = len(lines)

    # 无需截断
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return {
            "content": content,
            "truncated": False,
            "truncated_by": None,
            "total_lines": total_lines,
            "total_bytes": total_bytes,
            "output_lines": total_lines,
            "output_bytes": total_bytes,
            "last_line_partial": False,
            "max_lines": max_lines,
            "max_bytes": max_bytes,
        }

    # 从末尾向前收集
    output_lines_list = []
    output_bytes_count = 0
    truncated_by = "lines"
    last_line_partial = False

    for i in range(len(lines) - 1, -1, -1):
        if len(output_lines_list) >= max_lines:
            break

        line = lines[i]
        line_bytes = len(line.encode("utf-8")) + (1 if output_lines_list else 0)

        if output_bytes_count + line_bytes > max_bytes:
            truncated_by = "bytes"
            # 边界情况：还没有添加任何行，且此行超过字节限制
            if len(output_lines_list) == 0:
                truncated_line = _truncate_string_to_bytes_from_end(line, max_bytes)
                output_lines_list.insert(0, truncated_line)
                output_bytes_count = len(truncated_line.encode("utf-8"))
                last_line_partial = True
            break

        output_lines_list.insert(0, line)
        output_bytes_count += line_bytes

    if len(output_lines_list) >= max_lines and output_bytes_count <= max_bytes:
        truncated_by = "lines"

    output_content = "\n".join(output_lines_list)
    final_bytes = len(output_content.encode("utf-8"))

    return {
        "content": output_content,
        "truncated": True,
        "truncated_by": truncated_by,
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "output_lines": len(output_lines_list),
        "output_bytes": final_bytes,
        "last_line_partial": last_line_partial,
        "max_lines": max_lines,
        "max_bytes": max_bytes,
    }


# ---------------------------------------------------------------------------
# 输出累加器（移植自 pi 框架 OutputAccumulator）
# ---------------------------------------------------------------------------

class OutputAccumulator:
    """
    增量式跟踪流式输出，保持有界内存占用。

    - 使用流式 UTF-8 解码器追加解码块
    - 仅保留解码后的尾部用于展示快照
    - 当完整输出需要保留时，打开临时文件
    """

    def __init__(
        self,
        max_lines: int = DEFAULT_MAX_LINES,
        max_bytes: int = DEFAULT_MAX_BYTES,
        temp_file_prefix: str = "pi-cmd",
    ):
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        self.max_rolling_bytes = max(max_bytes * 2, 1)
        self.temp_file_prefix = temp_file_prefix

        self._raw_chunks: list[bytes] = []
        self._tail_text = ""
        self._tail_bytes = 0
        self._tail_starts_at_line_boundary = True

        self.total_raw_bytes = 0
        self.total_decoded_bytes = 0
        self.completed_lines = 0
        self.total_lines = 0
        self.current_line_bytes = 0
        self.has_open_line = False
        self.finished = False

        self.temp_file_path: str | None = None
        self._temp_file_handle = None
        # UTF-8 流式解码器状态
        self._decoder_state: list[bytes] = []

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def append(self, data: bytes) -> None:
        """追加原始字节数据。"""
        if self.finished:
            raise RuntimeError("Cannot append to a finished OutputAccumulator")

        self.total_raw_bytes += len(data)

        # 流式解码
        decoded = self._stream_decode(data)
        if decoded:
            self._append_decoded_text(decoded)

        # 超过阈值时写入临时文件
        if self._temp_file_handle is not None or self._should_use_temp_file():
            self._ensure_temp_file()
            self._temp_file_handle.write(data)
        elif len(data) > 0:
            self._raw_chunks.append(data)

    def finish(self) -> None:
        """完成输出，刷新解码器缓冲区。"""
        if self.finished:
            return
        self.finished = True

        # 刷新流式解码器
        remainder = b"".join(self._decoder_state)
        if remainder:
            try:
                decoded = remainder.decode("utf-8")
            except UnicodeDecodeError:
                decoded = remainder.decode("utf-8", errors="replace")
            if decoded:
                self._append_decoded_text(decoded)
            self._decoder_state.clear()

        if self._should_use_temp_file():
            self._ensure_temp_file()

    def snapshot(self, persist_if_truncated: bool = False) -> dict:
        """获取当前输出快照。"""
        tail_truncation = truncate_tail(
            self._get_snapshot_text(),
            max_lines=self.max_lines,
            max_bytes=self.max_bytes,
        )

        truncated = (
            self.total_lines > self.max_lines
            or self.total_decoded_bytes > self.max_bytes
        )
        truncated_by = (
            tail_truncation["truncated_by"]
            if truncated
            else None
        )
        if truncated and truncated_by is None:
            truncated_by = (
                "bytes" if self.total_decoded_bytes > self.max_bytes else "lines"
            )

        truncation_info = {
            **tail_truncation,
            "truncated": truncated,
            "truncated_by": truncated_by,
            "total_lines": self.total_lines,
            "total_bytes": self.total_decoded_bytes,
            "max_lines": self.max_lines,
            "max_bytes": self.max_bytes,
        }

        if persist_if_truncated and truncation_info["truncated"]:
            self._ensure_temp_file()

        return {
            "content": truncation_info["content"],
            "truncation": truncation_info,
            "full_output_path": self.temp_file_path,
        }

    def close_temp_file(self) -> None:
        """关闭临时文件（如有）。"""
        if self._temp_file_handle is None:
            return
        try:
            self._temp_file_handle.close()
        except Exception:
            pass
        self._temp_file_handle = None

    def get_last_line_bytes(self) -> int:
        """返回当前最后一行的字节数。"""
        return self.current_line_bytes

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _stream_decode(self, data: bytes) -> str:
        """流式 UTF-8 解码，正确处理多字节字符边界。"""
        self._decoder_state.append(data)
        raw = b"".join(self._decoder_state)
        # 尝试完整解码，如果失败则保留最后几个字节（可能是截断的多字节字符）
        for trim in range(4):
            try:
                result = raw.decode("utf-8") if trim == 0 else raw[: -(trim)].decode("utf-8")
                # 只保留未解码的尾部
                self._decoder_state = [raw[-(trim):]] if trim > 0 else []
                return result
            except UnicodeDecodeError:
                continue
        # 最终回退
        self._decoder_state = []
        return raw.decode("utf-8", errors="replace")

    def _append_decoded_text(self, text: str) -> None:
        """追加已解码文本。"""
        if len(text) == 0:
            return

        byte_count = len(text.encode("utf-8"))
        self.total_decoded_bytes += byte_count
        self._tail_text += text
        self._tail_bytes += byte_count

        # 滚动缓冲区超出上限时裁剪
        if self._tail_bytes > self.max_rolling_bytes * 2:
            self._trim_tail()

        # 统计行
        newlines = text.count("\n")
        last_newline = text.rfind("\n")

        if newlines == 0:
            self.current_line_bytes += byte_count
            self.has_open_line = True
        else:
            self.completed_lines += newlines
            tail = text[last_newline + 1:]
            self.current_line_bytes = len(tail.encode("utf-8"))
            self.has_open_line = len(tail) > 0

        self.total_lines = self.completed_lines + (1 if self.has_open_line else 0)

    def _trim_tail(self) -> None:
        """裁剪滚动缓冲区到上限。"""
        buf = self._tail_text.encode("utf-8")
        if len(buf) <= self.max_rolling_bytes:
            self._tail_bytes = len(buf)
            return

        start = len(buf) - self.max_rolling_bytes
        # 找到 UTF-8 字符边界
        while start < len(buf) and (buf[start] & 0xC0) == 0x80:
            start += 1

        self._tail_starts_at_line_boundary = (
            start == 0
            and self._tail_starts_at_line_boundary
            or (start > 0 and buf[start - 1] == 0x0A)
        )
        self._tail_text = buf[start:].decode("utf-8")
        self._tail_bytes = len(self._tail_text.encode("utf-8"))

    def _get_snapshot_text(self) -> str:
        """获取用于截断快照的文本（从行边界开始）。"""
        if self._tail_starts_at_line_boundary:
            return self._tail_text
        first_newline = self._tail_text.find("\n")
        if first_newline == -1:
            return self._tail_text
        return self._tail_text[first_newline + 1:]

    def _should_use_temp_file(self) -> bool:
        """判断是否需要使用临时文件。"""
        return (
            self.total_raw_bytes > self.max_bytes
            or self.total_decoded_bytes > self.max_bytes
            or self.total_lines > self.max_lines
        )

    def _ensure_temp_file(self) -> None:
        """确保临时文件已创建。"""
        if self.temp_file_path is not None:
            return

        tmp_dir = tempfile.gettempdir()
        random_id = format(random.getrandbits(64), "016x")
        self.temp_file_path = os.path.join(
            tmp_dir, f"{self.temp_file_prefix}-{random_id}.log"
        )
        self._temp_file_handle = open(self.temp_file_path, "wb")

        # 将已积累的原始块写入临时文件
        for chunk in self._raw_chunks:
            self._temp_file_handle.write(chunk)
        self._raw_chunks.clear()


# ---------------------------------------------------------------------------
# 平台检测与 Shell 解析
# ---------------------------------------------------------------------------

def _decode_output(data: bytes) -> str:
    """解码命令输出，按操作系统优先级自动检测编码。"""
    if not data:
        return ""

    if os.name == "nt":
        encodings = ["utf-8", "gbk", "gb2312", "utf-16-le", "latin-1"]
    else:
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]

    for encoding in encodings:
        try:
            return data.decode(encoding, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue

    return data.decode("latin-1", errors="ignore")


def _find_git_bash() -> str:
    """查找 Windows 上的 Git Bash 可执行文件。"""
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


def _get_shell_env() -> dict:
    """获取 shell 环境变量（继承当前进程环境）。"""
    env = os.environ.copy()
    # 确保基本 PATH 设置
    return env


def _build_command(command: str) -> dict:
    """
    构造平台对应的子进程参数。

    Returns:
        dict with keys: args, stdout, stderr, creationflags (win), shell (unix),
                        executable (unix), start_new_session (unix)
    """
    if os.name == "nt":
        git_bash = _find_git_bash()
        return {
            "args": [git_bash, "-lc", command],
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        }

    return {
        "args": command,
        "shell": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "executable": "/bin/bash",
        "start_new_session": True,
    }


def _track_child_pid(pid: int) -> None:
    """注册子进程 PID 以便清理。"""
    with _tracked_pids_lock:
        _tracked_pids.add(pid)


def _untrack_child_pid(pid: int) -> None:
    """取消注册子进程 PID。"""
    with _tracked_pids_lock:
        _tracked_pids.discard(pid)


def _kill_process_tree(pid: int) -> None:
    """
    终止进程及其所有子进程（跨平台）。

    移植自 pi 框架的 killProcessTree。
    """
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 命令执行（移植自 pi 框架 executeBashWithOperations）
# ---------------------------------------------------------------------------

def execute_command(command: str = None, timeout: int = None):
    """
    在全新隔离会话中执行一条 shell 命令，完成后自动销毁。

    特性（移植自 pi 框架）：
    - 每条命令独立运行，不共享状态。
    - 输出保留末尾（tail）：最多 2000 行或 50KB，先到先截。
    - 截断时自动将完整输出保存到临时文件，返回文件路径。
    - 超时后强制终止并返回已产生的输出。
    - 跨平台支持：Windows 使用 Git Bash，Linux/macOS 使用 /bin/bash。

    Args:
        command: 要执行的 shell 命令。
        timeout: 超时秒数（可选，默认无超时限制）。

    Returns:
        str: 命令执行结果。若输出被截断，包含临时文件路径供后续读取。
    """
    if not command:
        return "❌ 错误：必须提供要执行的命令(command)"

    child_process = None
    output = OutputAccumulator(temp_file_prefix="pi-cmd")
    cancelled = False
    timed_out = False
    timeout_handle = None

    try:
        start_time = time.time()
        spawn_kwargs = _build_command(command)

        # 检查工作目录
        cwd = os.getcwd()
        if not os.path.isdir(cwd):
            return f"❌ 错误：当前工作目录不存在：{cwd}\n无法执行命令。"

        # 添加公共参数
        spawn_kwargs["cwd"] = cwd
        spawn_kwargs["env"] = _get_shell_env()

        child_process = subprocess.Popen(**spawn_kwargs)

        if child_process.pid:
            _track_child_pid(child_process.pid)

        # ------------------------------------------------------------------
        # 超时处理（仅当 timeout 明确指定时生效）
        # ------------------------------------------------------------------
        if timeout is not None and timeout > 0:
            def _on_timeout():
                nonlocal timed_out
                timed_out = True
                if child_process and child_process.pid:
                    _kill_process_tree(child_process.pid)

            timeout_handle = threading.Timer(timeout, _on_timeout)
            timeout_handle.start()

        # ------------------------------------------------------------------
        # 流式读取 stdout 和 stderr
        # ------------------------------------------------------------------

        def _read_stream(stream, is_stderr: bool):
            """读取输出流并追加到累加器。"""
            try:
                for chunk in iter(lambda: stream.read(4096), b""):
                    if chunk:
                        output.append(chunk)
            except Exception:
                pass

        # 使用线程并发读取 stdout 和 stderr
        stdout_thread = threading.Thread(
            target=_read_stream,
            args=(child_process.stdout, False),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_read_stream,
            args=(child_process.stderr, True),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        # 等待进程结束
        child_process.wait()

        # 等待读取线程结束
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        if timeout_handle:
            timeout_handle.cancel()

        output.finish()
        snapshot = output.snapshot(persist_if_truncated=True)
        output.close_temp_file()

        elapsed = int(time.time() - start_time)

        # ------------------------------------------------------------------
        # 构建结果
        # ------------------------------------------------------------------
        return _format_result(
            snapshot=snapshot,
            command=command,
            elapsed=elapsed,
            exit_code=child_process.returncode,
            cancelled=False,
            timed_out=timed_out,
        )

    except FileNotFoundError as e:
        if timeout_handle:
            timeout_handle.cancel()
        output.finish()
        output.close_temp_file()
        return f"❌ 执行命令时发生错误: {str(e)}"

    except Exception as e:
        if timeout_handle:
            timeout_handle.cancel()
        output.finish()
        snapshot = output.snapshot(persist_if_truncated=True)
        output.close_temp_file()

        elapsed = int(time.time() - start_time) if "start_time" in dir() else 0

        if timed_out:
            return _format_result(
                snapshot=snapshot,
                command=command,
                elapsed=elapsed,
                exit_code=None,
                cancelled=False,
                timed_out=True,
                timeout_seconds=timeout,
            )

        return f"❌ 执行命令时发生错误: {str(e)}"

    finally:
        if timeout_handle:
            timeout_handle.cancel()

        if child_process is not None:
            if child_process.pid:
                _untrack_child_pid(child_process.pid)

            # 确保子进程已终止
            if child_process.poll() is None:
                _kill_process_tree(child_process.pid)

            # 关闭流
            for stream in (child_process.stdout, child_process.stderr):
                if stream:
                    try:
                        stream.close()
                    except Exception:
                        pass


def _format_result(
    snapshot: dict,
    command: str,
    elapsed: int,
    exit_code: int | None,
    cancelled: bool,
    timed_out: bool,
    timeout_seconds: int | None = None,
) -> str:
    """
    格式化命令执行结果为展示字符串。

    移植自 pi 框架的 formatOutput / 结果渲染逻辑。
    """
    truncation = snapshot["truncation"]
    full_output_path = snapshot["full_output_path"]
    output_text = snapshot["content"] or "(无输出)"

    lines = []

    # 标题行
    if cancelled:
        lines.append("📟 终端 - 命令已取消")
    elif timed_out:
        lines.append("📟 终端 - 命令超时")
    else:
        lines.append("📟 终端 - 命令执行完成")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 命令信息
    lines.append(f"💻 执行命令: {command}")
    lines.append(f"⏱️  耗时: {elapsed}秒" + (" (超时)" if timed_out else ""))

    # 输出
    lines.append("📋 输出结果:")
    lines.append(output_text)

    # 截断信息
    if truncation["truncated"]:
        total_lines = truncation["total_lines"]
        output_lines = truncation["output_lines"]
        truncated_by = truncation["truncated_by"]

        truncation_parts = []
        if full_output_path:
            truncation_parts.append(f"完整输出: {full_output_path}")

        if truncated_by == "lines":
            truncation_parts.append(
                f"已截断: 显示第 {total_lines - output_lines + 1}-{total_lines} 行"
                f"（共 {total_lines} 行）"
            )
        else:
            if truncation["last_line_partial"]:
                last_line_size = format_size(
                    len(output_text.split("\n")[-1].encode("utf-8"))
                    if output_text
                    else 0
                )
                truncation_parts.append(
                    f"已截断: 显示 {output_lines} 行 "
                    f"（限制 {format_size(truncation['max_bytes'])}）"
                )
            else:
                truncation_parts.append(
                    f"已截断: 显示 {output_lines} 行 "
                    f"（限制 {format_size(truncation['max_bytes'])}）"
                )

        if truncation_parts:
            lines.append(f"\n[{'；'.join(truncation_parts)}]")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 状态行
    if cancelled:
        lines.append("📊 执行状态: 已取消")
    elif timed_out:
        lines.append(f"📊 执行状态: 超时终止（{timeout_seconds}秒）")
    elif exit_code is not None and exit_code != 0:
        lines.append(f"📊 执行状态: 命令以退出码 {exit_code} 结束")
    else:
        lines.append("📊 执行状态: 执行完毕")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 工具元信息（供 LLM 识别）
# ---------------------------------------------------------------------------

def _get_shell_name() -> str:
    """获取当前平台实际使用的 shell 名称。"""
    if os.name == "nt":
        try:
            return f"Git Bash ({_find_git_bash()})"
        except FileNotFoundError:
            return "Git Bash (bash.exe)"
    return "/bin/bash"


def _build_command_description() -> str:
    """根据当前操作系统构建命令行工具的描述。"""
    shell_name = _get_shell_name()

    base = (
        f"在当前操作系统（{os.name}）的命令行终端中执行 shell 命令。"
        f"shell名称：{shell_name}。"
        "每条命令在一个全新的隔离会话中运行，命令结束（或超时）后会话自动销毁。"
        f"输出截断至最后 {DEFAULT_MAX_LINES} 行或 {DEFAULT_MAX_BYTES // 1024}KB（先到先截）。"
        "若输出被截断，完整内容保存到临时文件，路径在结果中显示，"
        "可使用 cat/head/tail/grep/less 等命令按需读取。"
    )

    if os.name == "nt":
        base += (
            "注意：当前命令行存在长度限制（约 8191 字符）。"
            "如果命令过长，请拆分为多次短命令分步执行。"
        )

    return base


COMMAND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": _build_command_description(),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "需要执行的 shell 命令",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": (
                            "命令超时时间（秒）。超时后会话强制终止并返回已产生的输出。"
                            "默认不设超时。仅在预期命令可能长时间运行时指定。"
                        ),
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
