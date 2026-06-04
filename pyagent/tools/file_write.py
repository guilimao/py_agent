"""
Windows 平台文件写入工具 —— 创建目录并写入文件，或覆盖已有文件。
仅在 Windows（os.name == 'nt'）下可用。
"""

import os


def write_file(path: str = None, content: str = None):
    """
    在 Windows 上将文本内容写入指定路径。

    - 若目标路径的父目录不存在，自动递归创建到所有中间目录。
    - 若目标文件已存在，覆盖其内容。
    - 若目标文件不存在，创建新文件。
    - 仅在 Windows 平台可用。

    Args:
        path: 目标文件的完整路径。
        content: 要写入的文本内容。

    Returns:
        str: 操作结果，包含额外提示信息（新创建的路径 / 新创建的文件 / 覆盖了已有文件）。
    """
    # ---- 参数校验 ----
    if not path:
        return "[ERROR] 必须提供目标路径（path）"
    if content is None:
        content = ""

    try:
        # 转为绝对路径，避免工作目录歧义
        path = os.path.abspath(path)
        dir_path = os.path.dirname(path)

        hints = []

        # ---- 目录处理 ----
        dir_existed = os.path.isdir(dir_path)
        if not dir_existed:
            os.makedirs(dir_path, exist_ok=True)
            hints.append("新创建的路径")

        # ---- 文件处理 ----
        file_existed = os.path.isfile(path)
        if file_existed:
            hints.append("覆盖了已有文件")
        else:
            hints.append("新创建的文件")

        # ---- 写入 ----
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        hints_str = "；".join(hints)
        return (
            f"[OK] 写入成功：{hints_str}\n"
            f"路径：{path}\n"
            f"内容长度：{len(content)} 字符"
        )

    except PermissionError:
        return f"[ERROR] 写入文件失败：权限不足，无法写入 {path}"
    except OSError as e:
        return f"[ERROR] 写入文件失败：{str(e)}"
    except Exception as e:
        return f"[ERROR] 写入文件失败：未知错误 - {str(e)}"


# ---------------------------------------------------------------------------
# 工具元信息（供 LLM 识别）
# ---------------------------------------------------------------------------

FILE_WRITE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "在 Windows 上将文本内容写入到指定路径。"
                "若目标路径的父目录不存在，自动递归创建所有中间目录。"
                "若目标文件已存在，覆盖其内容。"
                "返回结果中会提示「新创建的路径」「新创建的文件」或「覆盖了已有文件」。"
                "仅限 Windows 平台使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目标文件的完整路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入文件的文本内容",
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
