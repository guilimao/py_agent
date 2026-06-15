"""
文件读取工具 —— 读取文本文件内容，支持分页和截断。

实现逻辑移植自 pi 框架（@earendil-works/pi-coding-agent）的 read 工具：
- 路径解析：支持 ~ 展开、相对路径、Unicode 空格规范化
- 文本截断：默认最大 2000 行或 50KB（以先到者为准）
- 分页读取：通过 offset（1-indexed）和 limit 参数支持大文件分页
- 截断时自动给出继续读取的提示（offset 建议）
- 支持图片文件检测（通过 MIME 类型），图片以 base64 返回
- 跨平台支持（Linux / macOS / Windows）
"""

import base64
import mimetypes
import os
import unicodedata


# ===========================================================================
# 常量（与 pi 框架一致）
# ===========================================================================

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024  # 50KB

# 支持的图片 MIME 类型
_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


# ===========================================================================
# Unicode 空格规范化（与 pi 框架 UNICODE_SPACES 一致）
# ===========================================================================

_UNICODE_SPACES = (
    "\u00A0"  # NO-BREAK SPACE
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A"
    "\u202F"  # NARROW NO-BREAK SPACE
    "\u205F"  # MEDIUM MATHEMATICAL SPACE
    "\u3000"  # IDEOGRAPHIC SPACE
)
_UNICODE_SPACE_TABLE = str.maketrans(
    dict.fromkeys([ord(c) for c in _UNICODE_SPACES], " ")
)


def _normalize_unicode_spaces(text: str) -> str:
    """将 Unicode 特殊空格统一转换为 ASCII 空格。"""
    return text.translate(_UNICODE_SPACE_TABLE)


# ===========================================================================
# 路径解析
# ===========================================================================

def _resolve_path(file_path: str) -> str:
    """
    解析路径为绝对路径。

    - 展开 ~ 为用户主目录
    - 规范化 Unicode 空格
    - 相对路径基于当前工作目录解析
    - 去除 @ 前缀（某些模型会在路径前加 @）
    """
    if not file_path:
        return file_path

    normalized = file_path.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:]

    # Unicode 空格规范化
    normalized = _normalize_unicode_spaces(normalized)

    # 展开 ~ 并转为绝对路径
    normalized = os.path.expanduser(normalized)
    normalized = os.path.abspath(normalized)

    return normalized


# ===========================================================================
# 字节大小格式化（与 pi 框架 formatSize 一致）
# ===========================================================================

def _format_size(byte_count: int) -> str:
    """将字节数格式化为人类可读的大小字符串。"""
    if byte_count < 1024:
        return f"{byte_count}B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f}KB"
    else:
        return f"{byte_count / (1024 * 1024):.1f}MB"


# ===========================================================================
# 截断逻辑（与 pi 框架 truncateHead 一致）
# ===========================================================================

def _truncate_head(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """
    从头截断内容，保留前 N 行/字节。

    与 pi 框架 truncateHead 行为一致：
    - 以先触发的限制为准（行数限制 或 字节限制）
    - 从不返回不完整的行
    - 如果第一行就超过字节限制，返回空内容并标记 first_line_exceeds_limit

    Returns:
        dict: {
            "content": str,              # 截断后的内容
            "truncated": bool,           # 是否发生了截断
            "truncated_by": str | None,  # "lines" | "bytes" | None
            "total_lines": int,          # 原始总行数
            "total_bytes": int,          # 原始总字节数
            "output_lines": int,         # 输出行数
            "output_bytes": int,         # 输出字节数
            "first_line_exceeds_limit": bool,
            "max_lines": int,
            "max_bytes": int,
        }
    """
    total_bytes = len(content.encode("utf-8"))

    if content == "":
        return {
            "content": content,
            "truncated": False,
            "truncated_by": None,
            "total_lines": 0,
            "total_bytes": 0,
            "output_lines": 0,
            "output_bytes": 0,
            "first_line_exceeds_limit": False,
            "max_lines": max_lines,
            "max_bytes": max_bytes,
        }

    # 按行拆分（保留末尾空行行为：不 strip 最后的 \n）
    lines = content.split("\n")
    # 与 pi 框架一致：如果内容以 \n 结尾，丢弃末尾空元素
    if content.endswith("\n"):
        lines.pop()

    total_lines = len(lines)

    # 检查是否需要截断
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return {
            "content": content,
            "truncated": False,
            "truncated_by": None,
            "total_lines": total_lines,
            "total_bytes": total_bytes,
            "output_lines": total_lines,
            "output_bytes": total_bytes,
            "first_line_exceeds_limit": False,
            "max_lines": max_lines,
            "max_bytes": max_bytes,
        }

    # 检查第一行是否超过字节限制
    first_line_bytes = len(lines[0].encode("utf-8"))
    if first_line_bytes > max_bytes:
        return {
            "content": "",
            "truncated": True,
            "truncated_by": "bytes",
            "total_lines": total_lines,
            "total_bytes": total_bytes,
            "output_lines": 0,
            "output_bytes": 0,
            "first_line_exceeds_limit": True,
            "max_lines": max_lines,
            "max_bytes": max_bytes,
        }

    # 收集能放入限制的完整行
    output_lines_arr = []
    output_bytes_count = 0
    truncated_by = "lines"

    for i, line in enumerate(lines):
        if i >= max_lines:
            truncated_by = "lines"
            break
        # 计算该行的字节数（+1 为换行符，首行不加）
        line_bytes = len(line.encode("utf-8")) + (1 if i > 0 else 0)
        if output_bytes_count + line_bytes > max_bytes:
            truncated_by = "bytes"
            break
        output_lines_arr.append(line)
        output_bytes_count += line_bytes

    if len(output_lines_arr) >= max_lines and output_bytes_count <= max_bytes:
        truncated_by = "lines"

    output_content = "\n".join(output_lines_arr)
    final_output_bytes = len(output_content.encode("utf-8"))

    return {
        "content": output_content,
        "truncated": True,
        "truncated_by": truncated_by,
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "output_lines": len(output_lines_arr),
        "output_bytes": final_output_bytes,
        "first_line_exceeds_limit": False,
        "max_lines": max_lines,
        "max_bytes": max_bytes,
    }


# ===========================================================================
# MIME 类型检测
# ===========================================================================

def _detect_image_mime_type(file_path: str) -> str | None:
    """
    通过文件扩展名检测图片 MIME 类型。

    返回 None 表示非图片文件。
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type in _IMAGE_MIME_TYPES:
        return mime_type
    return None


# ===========================================================================
# 主函数
# ===========================================================================

def read_file(
    path: str = None,
    offset: int = None,
    limit: int = None,
) -> str:
    """
    读取文件内容。支持文本文件和图片（jpg、png、gif、webp）。

    文本输出默认截断为 2000 行或 50KB（以先触发者为准）。
    对大文件请使用 offset/limit 参数分页读取。
    需要完整文件时，继续使用 offset 直到读完为止。

    Args:
        path: 要读取的文件路径（相对或绝对路径）。
        offset: 起始行号（1-indexed），不指定则从第 1 行开始。
        limit: 最大读取行数，不指定则由截断逻辑决定。

    Returns:
        str: 操作结果，包含文件内容或错误信息。
    """
    # ---- 参数校验 ----
    if not path:
        return "[ERROR] read_file: path is required"

    # ---- 路径解析 ----
    absolute_path = _resolve_path(path)

    # ---- 检查文件存在且可读 ----
    if not os.path.isfile(absolute_path):
        return f"[ERROR] read_file: file not found — {path}"
    if not os.access(absolute_path, os.R_OK):
        return f"[ERROR] read_file: permission denied — {path}"

    # ---- 检测图片 MIME 类型 ----
    try:
        mime_type = _detect_image_mime_type(absolute_path)
    except Exception:
        mime_type = None

    if mime_type:
        # ---- 读取图片 ----
        try:
            with open(absolute_path, "rb") as f:
                image_data = f.read()

            image_base64 = base64.b64encode(image_data).decode("ascii")
            file_size = len(image_data)

            result = (
                f"Read image file [{mime_type}]\n"
                f"File: {path}\n"
                f"Size: {_format_size(file_size)}\n"
                f"Base64 data ({len(image_base64)} chars):\n"
                f"{image_base64}"
            )
            return result

        except Exception as e:
            return f"[ERROR] read_file: failed to read image — {e}"

    # ---- 读取文本内容 ----
    try:
        with open(absolute_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except UnicodeDecodeError:
        # 可能是二进制文件，尝试以二进制方式读取
        try:
            with open(absolute_path, "rb") as f:
                binary_data = f.read()
            file_size = len(binary_data)
            return (
                f"[Binary file detected]\n"
                f"File: {path}\n"
                f"Size: {_format_size(file_size)}\n"
                f"[Use appropriate tools for binary files]"
            )
        except Exception as e:
            return f"[ERROR] read_file: failed to read file — {e}"
    except Exception as e:
        return f"[ERROR] read_file: failed to read file — {e}"

    # ---- 拆分为行 ----
    all_lines = raw_content.split("\n")
    if raw_content.endswith("\n"):
        all_lines.pop()

    total_file_lines = len(all_lines)

    # ---- 应用 offset ----
    start_line = max(0, (offset - 1) if offset is not None else 0)
    start_line_display = start_line + 1

    if start_line >= total_file_lines:
        return (
            f"[ERROR] read_file: offset {offset} is beyond end of file "
            f"({total_file_lines} lines total)"
        )

    # ---- 提取选中内容 ----
    if limit is not None:
        end_line = min(start_line + limit, total_file_lines)
        selected_content = "\n".join(all_lines[start_line:end_line])
        user_limited_lines = end_line - start_line
    else:
        selected_content = "\n".join(all_lines[start_line:])
        user_limited_lines = None

    # ---- 应用截断 ----
    truncation = _truncate_head(selected_content)

    if truncation["first_line_exceeds_limit"]:
        first_line_size = _format_size(
            len(all_lines[start_line].encode("utf-8"))
        )
        return (
            f"[Line {start_line_display} is {first_line_size}, "
            f"exceeds {_format_size(DEFAULT_MAX_BYTES)} limit. "
            f"Use bash: sed -n '{start_line_display}p' {path} | "
            f"head -c {DEFAULT_MAX_BYTES}]"
        )

    if truncation["truncated"]:
        output_text = truncation["content"]
        end_line_display = start_line_display + truncation["output_lines"] - 1
        next_offset = end_line_display + 1

        if truncation["truncated_by"] == "lines":
            output_text += (
                f"\n\n[Showing lines {start_line_display}-{end_line_display} "
                f"of {total_file_lines}. Use offset={next_offset} to continue.]"
            )
        else:
            output_text += (
                f"\n\n[Showing lines {start_line_display}-{end_line_display} "
                f"of {total_file_lines} ({_format_size(DEFAULT_MAX_BYTES)} limit). "
                f"Use offset={next_offset} to continue.]"
            )
        return output_text

    # 用户指定的 limit 导致提前结束，但文件还有更多内容
    if (
        user_limited_lines is not None
        and start_line + user_limited_lines < total_file_lines
    ):
        remaining = total_file_lines - (start_line + user_limited_lines)
        next_offset = start_line + user_limited_lines + 1
        output_text = truncation["content"]
        output_text += (
            f"\n\n[{remaining} more lines in file. "
            f"Use offset={next_offset} to continue.]"
        )
        return output_text

    # 无截断、完整返回
    return truncation["content"]


# ===========================================================================
# 工具元信息（供 LLM 识别）
# ===========================================================================

READ_FILE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取文件内容。支持文本文件和图片（jpg、png、gif、webp）。"
                "图片以 base64 编码数据返回。"
                f"对于文本文件，输出截断至 {DEFAULT_MAX_LINES} 行或 "
                f"{DEFAULT_MAX_BYTES // 1024}KB（以先触发者为准）。"
                "对于大文件请使用 offset/limit 分页读取。"
                "需要完整文件时，继续使用 offset 直到读完为止。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径（相对或绝对路径）",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "起始行号（从1开始计数）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大读取行数",
                    },
                },
                "required": ["path"],
            },
        },
    }
]

# ===========================================================================
# 工具函数映射（供 Agent 调用）
# ===========================================================================

READ_FILE_FUNCTIONS = {
    "read_file": read_file,
}
