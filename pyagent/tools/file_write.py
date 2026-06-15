"""
文件写入工具 —— 创建目录并写入文件，或覆盖已有文件。

实现逻辑移植自 pi 框架（@earendil-works/pi-coding-agent）的 write 工具：
- 路径解析：支持 ~ 展开、相对路径、Unicode 空格规范化
- 自动递归创建父目录
- 文件变更队列：同一文件的写入操作串行化，避免竞态条件
- 支持写入中断检查
- 跨平台支持（Linux / macOS / Windows）
"""

import os
import threading
import unicodedata


# ---------------------------------------------------------------------------
# 路径解析工具（移植自 pi 框架 path-utils / paths）
# ---------------------------------------------------------------------------

# Unicode 空格字符集合（与 pi 框架 UNICODE_SPACES 一致）
_UNICODE_SPACES = (
    "\u00A0"  # NO-BREAK SPACE
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A"  # EN QUAD ~ HAIR SPACE
    "\u202F"  # NARROW NO-BREAK SPACE
    "\u205F"  # MEDIUM MATHEMATICAL SPACE
    "\u3000"  # IDEOGRAPHIC SPACE
)
_UNICODE_SPACE_TABLE = str.maketrans(dict.fromkeys([ord(c) for c in _UNICODE_SPACES], " "))


def _normalize_unicode_spaces(text: str) -> str:
    """将 Unicode 特殊空格统一转换为 ASCII 空格。"""
    return text.translate(_UNICODE_SPACE_TABLE)


def _resolve_path(file_path: str) -> str:
    """
    解析路径为绝对路径。

    移植自 pi 框架的 resolveToCwd / resolvePath：
    - 展开 ~ 为用户主目录
    - 规范化 Unicode 空格
    - 相对路径基于当前工作目录解析
    - 去除 @ 前缀（pi 框架特有行为，用于模型提示）
    """
    if not file_path:
        return file_path

    # 去除 @ 前缀（某些模型会在路径前加 @）
    normalized = file_path.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:]

    # Unicode 空格规范化
    normalized = _normalize_unicode_spaces(normalized)

    # 展开 ~ 并转为绝对路径
    normalized = os.path.expanduser(normalized)
    normalized = os.path.abspath(normalized)

    return normalized


# ---------------------------------------------------------------------------
# 文件变更队列（移植自 pi 框架 file-mutation-queue）
# ---------------------------------------------------------------------------

# 全局锁字典：每个文件路径对应一个锁，确保同一文件的写入串行化
_file_locks: dict[str, threading.Lock] = {}
_file_locks_guard = threading.Lock()


def _get_file_lock(file_path: str) -> threading.Lock:
    """获取指定文件路径的专属锁（线程安全）。"""
    with _file_locks_guard:
        if file_path not in _file_locks:
            _file_locks[file_path] = threading.Lock()
        return _file_locks[file_path]


def _with_file_mutation_queue(file_path: str, fn, signal=None):
    """
    在文件级队列中执行写入操作，确保同一文件的并发写入串行化。

    移植自 pi 框架的 withFileMutationQueue：同一文件的操作排队执行，
    不同文件的操作并行执行。
    """
    lock = _get_file_lock(file_path)
    with lock:
        # 写入前检查中断信号
        if signal is not None and hasattr(signal, "aborted") and signal.aborted:
            raise InterruptedError("Operation aborted")
        return fn()


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def write_file(path: str = None, content: str = None, signal=None):
    """
    将文本内容写入指定路径。

    - 若目标路径的父目录不存在，自动递归创建所有中间目录。
    - 若目标文件已存在，覆盖其内容。
    - 若目标文件不存在，创建新文件。
    - 跨平台支持（Linux / macOS / Windows）。

    Args:
        path: 目标文件的路径（相对或绝对路径，支持 ~ 展开）。
        content: 要写入的文本内容。
        signal: 可选的取消信号对象，需包含 aborted 属性。

    Returns:
        str: 操作结果。
    """
    # ---- 参数校验 ----
    if not path:
        return "[ERROR] write_file: path is required"
    if content is None:
        content = ""

    # ---- 路径解析 ----
    absolute_path = _resolve_path(path)
    dir_path = os.path.dirname(absolute_path)

    def _do_write():
        """实际写入操作。"""
        # 递归创建父目录
        os.makedirs(dir_path, exist_ok=True)

        # 写入文件
        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(content)

        byte_count = len(content.encode("utf-8"))
        return f"Successfully wrote {byte_count} bytes to {path}"

    try:
        return _with_file_mutation_queue(absolute_path, _do_write, signal)

    except InterruptedError:
        return "[ERROR] write_file: operation aborted"
    except PermissionError:
        return f"[ERROR] write_file: permission denied — {path}"
    except OSError as e:
        return f"[ERROR] write_file: {e}"
    except Exception as e:
        return f"[ERROR] write_file: unexpected error — {e}"


# ---------------------------------------------------------------------------
# 工具元信息（供 LLM 识别）
# ---------------------------------------------------------------------------

FILE_WRITE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "将内容写入文件。若文件不存在则创建，"
                "若已存在则覆盖。自动创建父目录。"
                "支持 ~ 展开和相对路径。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径（相对或绝对路径）",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入文件的内容",
                    },
                },
                "required": ["path", "content"],
            },
        },
    }
]

# ---------------------------------------------------------------------------
# 工具函数映射（供 Agent 调用）
# ---------------------------------------------------------------------------

FILE_WRITE_FUNCTIONS = {
    "write_file": write_file,
}
