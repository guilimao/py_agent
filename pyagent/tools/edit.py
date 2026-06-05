"""
精确文本替换编辑工具 —— 通过 oldText/newText 对实现文件编辑。

实现方式与 pi 框架的 edit 工具保持一致：
- 支持单次调用中多次替换（edits 数组）
- 精确匹配优先，失败后回退到 Unicode 模糊匹配
- 自动处理 BOM、行尾符（CRLF/LF）
- 检测重叠编辑和重复匹配
- 返回 unified diff 展示变更
"""

import difflib
import os
import unicodedata


# ---------------------------------------------------------------------------
# 行尾符处理
# ---------------------------------------------------------------------------

def detect_line_ending(content: str) -> str:
    """检测内容使用的主要行尾符：\r\n 或 \n。

    使用多数投票策略：统计 CRLF 和纯 LF 的出现次数，
    返回占多数的行尾符。若无行尾符，默认返回 \n。
    """
    crlf_count = content.count("\r\n")
    # 纯 LF：总 LF 数减去 CRLF 中的 LF
    lf_count = content.count("\n") - crlf_count
    if crlf_count == 0 and lf_count == 0:
        return "\n"
    return "\r\n" if crlf_count >= lf_count else "\n"


def normalize_to_lf(text: str) -> str:
    """将所有行尾符统一为 LF。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def restore_line_endings(text: str, ending: str) -> str:
    """将 LF 恢复为原始行尾符。"""
    return text.replace("\n", ending) if ending == "\r\n" else text


# ---------------------------------------------------------------------------
# BOM 处理
# ---------------------------------------------------------------------------

def strip_bom(content: str) -> tuple:
    """去除 UTF-8 BOM，返回 (bom, text)。"""
    return ("\ufeff", content[1:]) if content.startswith("\ufeff") else ("", content)


# ---------------------------------------------------------------------------
# 模糊匹配（Unicode 规范化）
# ---------------------------------------------------------------------------

def normalize_for_fuzzy_match(text: str) -> str:
    """
    对文本进行渐进式规范化，仅用于模糊匹配时的索引定位。

    注意：此函数的结果**绝不**直接写回文件。它只用于在模糊空间中找到
    oldText 的位置偏移，然后映射回原始内容进行替换。

    规范化项目：
    - 统一换行符为 LF（处理 \r\n 和独立 \r）
    - NFKC 规范化
    - 去除行尾空白
    - 智能引号 → ASCII 引号
    - Unicode 破折号/连字符 → ASCII 连字符
    - 特殊空格 → 常规空格
    """
    # 先统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    # 去除行尾空白
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # 智能单引号 → '
    text = text.translate(str.maketrans(
        "\u2018\u2019\u201a\u201b", "''''"
    ))
    # 智能双引号 → "
    text = text.translate(str.maketrans(
        "\u201c\u201d\u201e\u201f", '""""'
    ))
    # 各种破折号/连字符 → -
    for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
        text = text.replace(ch, "-")
    # 特殊空格 → 常规空格
    for ch in "\u00a0\u202f\u205f\u3000":
        text = text.replace(ch, " ")
    # U+2002–U+200A 各种空格
    for code in range(0x2002, 0x200B):
        text = text.replace(chr(code), " ")
    return text


def fuzzy_find_text(content: str, old_text: str) -> dict:
    """
    在 content 中查找 old_text，先尝试精确匹配，再尝试模糊匹配。

    Returns:
        dict: {
            "found": bool,
            "index": int,
            "match_length": int,
            "used_fuzzy_match": bool,
            "content_for_replacement": str,  # 用于替换的内容（模糊匹配时已规范化）
        }
    """
    # 精确匹配
    exact_index = content.find(old_text)
    if exact_index != -1:
        return {
            "found": True,
            "index": exact_index,
            "match_length": len(old_text),
            "used_fuzzy_match": False,
            "content_for_replacement": content,
        }

    # 模糊匹配
    fuzzy_content = normalize_for_fuzzy_match(content)
    fuzzy_old_text = normalize_for_fuzzy_match(old_text)
    fuzzy_index = fuzzy_content.find(fuzzy_old_text)

    if fuzzy_index == -1:
        return {
            "found": False,
            "index": -1,
            "match_length": 0,
            "used_fuzzy_match": False,
            "content_for_replacement": content,
        }

    return {
        "found": True,
        "index": fuzzy_index,
        "match_length": len(fuzzy_old_text),
        "used_fuzzy_match": True,
        "content_for_replacement": fuzzy_content,
    }


def count_occurrences(content: str, old_text: str) -> int:
    """统计 old_text 在 content 中的出现次数（基于模糊匹配）。"""
    fuzzy_content = normalize_for_fuzzy_match(content)
    fuzzy_old_text = normalize_for_fuzzy_match(old_text)
    return fuzzy_content.count(fuzzy_old_text)


# ---------------------------------------------------------------------------
# 核心编辑逻辑
# ---------------------------------------------------------------------------

def apply_edits_to_normalized_content(
    normalized_content: str,
    edits: list,
    path: str,
) -> tuple:
    """
    对 LF 规范化后的内容应用一组精确文本替换。

    所有编辑均基于同一原始内容进行匹配，然后按逆序应用以保持偏移量稳定。

    Args:
        normalized_content: LF 规范化后的文件内容
        edits: [{"oldText": ..., "newText": ...}, ...]
        path: 文件路径（用于错误消息）

    Returns:
        (base_content, new_content): 应用编辑前后的内容

    Raises:
        ValueError: 匹配失败、重复匹配或编辑重叠时
    """
    # 规范化编辑
    normalized_edits = [
        {
            "old_text": normalize_to_lf(e["oldText"]),
            "new_text": normalize_to_lf(e["newText"]),
        }
        for e in edits
    ]

    # 验证 oldText 非空
    for i, edit in enumerate(normalized_edits):
        if len(edit["old_text"]) == 0:
            suffix = f"edits[{i}].oldText 不能为空" if len(normalized_edits) > 1 else "oldText 不能为空"
            raise ValueError(f"编辑 {path} 失败：{suffix}。")

    # 初始匹配
    initial_matches = [
        fuzzy_find_text(normalized_content, e["old_text"])
        for e in normalized_edits
    ]

    # 如果有任何编辑需要模糊匹配，则在模糊规范化空间中操作
    base_content = (
        normalize_for_fuzzy_match(normalized_content)
        if any(m["used_fuzzy_match"] for m in initial_matches)
        else normalized_content
    )

    # 为每个编辑找到匹配位置
    matched_edits = []
    for i, edit in enumerate(normalized_edits):
        match_result = fuzzy_find_text(base_content, edit["old_text"])

        if not match_result["found"]:
            suffix = (
                f"在 {path} 中找不到 edits[{i}] 的 oldText。"
                if len(normalized_edits) > 1
                else f"在 {path} 中找不到指定的 oldText。"
            )
            raise ValueError(f"{suffix} 请确保文本精确匹配（包括空白和换行）。")

        occurrences = count_occurrences(base_content, edit["old_text"])
        if occurrences > 1:
            suffix = (
                f"edits[{i}] 的 oldText 在 {path} 中匹配到 {occurrences} 处。"
                if len(normalized_edits) > 1
                else f"oldText 在 {path} 中匹配到 {occurrences} 处。"
            )
            raise ValueError(f"{suffix} 请提供更多上下文使其唯一。")

        matched_edits.append({
            "edit_index": i,
            "match_index": match_result["index"],
            "match_length": match_result["match_length"],
            "new_text": edit["new_text"],
        })

    # 按匹配位置排序，检测重叠
    matched_edits.sort(key=lambda e: e["match_index"])
    for i in range(1, len(matched_edits)):
        prev = matched_edits[i - 1]
        curr = matched_edits[i]
        if prev["match_index"] + prev["match_length"] > curr["match_index"]:
            raise ValueError(
                f"edits[{prev['edit_index']}] 和 edits[{curr['edit_index']}] "
                f"在 {path} 中存在重叠。请合并为一次编辑或选择不相交的区域。"
            )

    # 逆序应用编辑
    new_content = base_content
    for edit in reversed(matched_edits):
        new_content = (
            new_content[:edit["match_index"]]
            + edit["new_text"]
            + new_content[edit["match_index"] + edit["match_length"]:]
        )

    if base_content == new_content:
        suffix = (
            "所有替换均未产生实际变更。"
            if len(normalized_edits) > 1
            else "替换未产生实际变更。"
        )
        raise ValueError(f"编辑 {path} 失败：{suffix}")

    return base_content, new_content


# ---------------------------------------------------------------------------
# Diff 生成
# ---------------------------------------------------------------------------

def generate_unified_patch(
    path: str,
    old_content: str,
    new_content: str,
    context_lines: int = 4,
) -> str:
    """生成标准 unified diff 补丁。"""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=path,
        tofile=path,
        n=context_lines,
    )
    return "".join(diff)


def generate_diff_string(
    old_content: str,
    new_content: str,
    context_lines: int = 4,
) -> dict:
    """
    生成带行号的展示用 diff 字符串。

    Returns:
        {"diff": str, "first_changed_line": int | None}
    """
    old_lines = old_content.split("\n")
    new_lines = new_content.split("\n")

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = matcher.get_opcodes()

    output = []
    max_line_num = max(len(old_lines), len(new_lines))
    line_num_width = len(str(max_line_num))

    old_line_num = 1
    new_line_num = 1
    last_was_change = False
    first_changed_line = None

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            raw_lines = old_lines[i1:i2]
            next_is_change = any(
                op[0] != "equal"
                for op in opcodes[opcodes.index((tag, i1, i2, j1, j2)) + 1:]
                if opcodes.index((tag, i1, i2, j1, j2)) + 1 < len(opcodes)
            )
            # 简化：检查下一个 opcode 是否为 change
            idx = opcodes.index((tag, i1, i2, j1, j2))
            has_trailing_change = idx + 1 < len(opcodes) and opcodes[idx + 1][0] != "equal"

            if last_was_change and has_trailing_change:
                if len(raw_lines) <= context_lines * 2:
                    for line in raw_lines:
                        output.append(f" {str(old_line_num).rjust(line_num_width)} {line}")
                        old_line_num += 1
                        new_line_num += 1
                else:
                    leading = raw_lines[:context_lines]
                    trailing = raw_lines[-context_lines:]
                    skipped = len(raw_lines) - len(leading) - len(trailing)
                    for line in leading:
                        output.append(f" {str(old_line_num).rjust(line_num_width)} {line}")
                        old_line_num += 1
                        new_line_num += 1
                    output.append(f" {' '.rjust(line_num_width)} ...")
                    old_line_num += skipped
                    new_line_num += skipped
                    for line in trailing:
                        output.append(f" {str(old_line_num).rjust(line_num_width)} {line}")
                        old_line_num += 1
                        new_line_num += 1
            elif last_was_change:
                shown = raw_lines[:context_lines]
                skipped = len(raw_lines) - len(shown)
                for line in shown:
                    output.append(f" {str(old_line_num).rjust(line_num_width)} {line}")
                    old_line_num += 1
                    new_line_num += 1
                if skipped > 0:
                    output.append(f" {' '.rjust(line_num_width)} ...")
                    old_line_num += skipped
                    new_line_num += skipped
            elif has_trailing_change:
                skipped = max(0, len(raw_lines) - context_lines)
                if skipped > 0:
                    output.append(f" {' '.rjust(line_num_width)} ...")
                    old_line_num += skipped
                    new_line_num += skipped
                for line in raw_lines[skipped:]:
                    output.append(f" {str(old_line_num).rjust(line_num_width)} {line}")
                    old_line_num += 1
                    new_line_num += 1
            else:
                old_line_num += len(raw_lines)
                new_line_num += len(raw_lines)

            last_was_change = False

        elif tag in ("replace", "delete"):
            if first_changed_line is None:
                first_changed_line = new_line_num

            for line in old_lines[i1:i2]:
                output.append(f"-{str(old_line_num).rjust(line_num_width)} {line}")
                old_line_num += 1

            if tag == "replace":
                for line in new_lines[j1:j2]:
                    output.append(f"+{str(new_line_num).rjust(line_num_width)} {line}")
                    new_line_num += 1

            last_was_change = True

        elif tag == "insert":
            if first_changed_line is None:
                first_changed_line = new_line_num

            for line in new_lines[j1:j2]:
                output.append(f"+{str(new_line_num).rjust(line_num_width)} {line}")
                new_line_num += 1

            last_was_change = True

    return {
        "diff": "\n".join(output),
        "first_changed_line": first_changed_line,
    }


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def edit_file(path: str = None, edits: list = None):
    """
    通过精确文本替换编辑单个文件。

    - 每次调用可包含多个替换（edits 数组）。
    - 每个 edits[].oldText 必须在原文件中唯一且不与其他编辑重叠。
    - 先尝试精确匹配，失败后回退到 Unicode 模糊匹配。
    - 自动处理 BOM 和行尾符差异。
    - 返回变更摘要和 unified diff。

    Args:
        path: 要编辑的文件路径（相对或绝对路径）。
        edits: 替换列表，每项为 {"oldText": str, "newText": str}。

    Returns:
        str: 操作结果，包含替换数量和 diff 展示。
    """
    # ---- 参数校验 ----
    if not path:
        return "[ERROR] 必须提供目标路径（path）"

    if not edits or not isinstance(edits, list) or len(edits) == 0:
        return "[ERROR] edits 必须为非空数组，每项包含 oldText 和 newText"

    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            return f"[ERROR] edits[{i}] 必须是对象，包含 oldText 和 newText"
        if "oldText" not in edit or "newText" not in edit:
            return f"[ERROR] edits[{i}] 缺少 oldText 或 newText"
        if not isinstance(edit["oldText"], str) or not isinstance(edit["newText"], str):
            return f"[ERROR] edits[{i}] 的 oldText 和 newText 必须为字符串"

    try:
        # 转为绝对路径
        path = os.path.abspath(path)

        # 检查文件是否存在且可读写
        if not os.path.isfile(path):
            return f"[ERROR] 无法编辑 {path}：文件不存在"
        if not os.access(path, os.R_OK | os.W_OK):
            return f"[ERROR] 无法编辑 {path}：权限不足"

        # 读取文件
        with open(path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # 去除 BOM
        bom, content = strip_bom(raw_content)

        # 检测原始行尾符
        original_ending = detect_line_ending(content)

        # 统一为 LF
        normalized_content = normalize_to_lf(content)

        # 应用编辑
        base_content, new_content = apply_edits_to_normalized_content(
            normalized_content, edits, path
        )

        # 恢复行尾符并加回 BOM
        final_content = bom + restore_line_endings(new_content, original_ending)

        # 写入文件
        with open(path, "w", encoding="utf-8") as f:
            f.write(final_content)

        # 生成 diff
        diff_result = generate_diff_string(base_content, new_content)
        patch = generate_unified_patch(path, base_content, new_content)

        # 构建返回结果
        edit_count = len(edits)
        summary = (
            f"[OK] 在 {path} 中成功替换了 {edit_count} 处内容。\n\n"
            f"--- 变更预览 ---\n"
            f"{diff_result['diff']}\n"
            f"--- 补丁 ---\n"
            f"{patch}"
        )

        return summary

    except ValueError as e:
        return f"[ERROR] {str(e)}"
    except PermissionError:
        return f"[ERROR] 写入文件失败：权限不足，无法写入 {path}"
    except OSError as e:
        return f"[ERROR] 文件操作失败：{str(e)}"
    except Exception as e:
        return f"[ERROR] 编辑文件失败：未知错误 - {str(e)}"


# ---------------------------------------------------------------------------
# 工具元信息（供 LLM 识别）
# ---------------------------------------------------------------------------

EDIT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "通过精确文本替换编辑单个文件。每次调用可包含多个替换（edits 数组）。"
                "每个 edits[].oldText 必须在原文件中唯一且不与其他编辑重叠。"
                "先尝试精确匹配，失败后自动回退到 Unicode 模糊匹配"
                "（智能处理引号、破折号、空格等字符差异）。"
                "自动处理 BOM 和行尾符（CRLF/LF）差异。"
                "如果两个变更影响同一代码块或相邻行，请合并为一次编辑，"
                "不要发出重叠编辑。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的文件路径（相对或绝对路径）",
                    },
                    "edits": {
                        "type": "array",
                        "description": (
                            "一个或多个目标替换。每个编辑基于原始文件（而非增量）进行匹配。"
                            "不要包含重叠或嵌套编辑。"
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "oldText": {
                                    "type": "string",
                                    "description": (
                                        "要替换的精确文本。必须在原文件中唯一，"
                                        "且不与同次调用中其他 edits[].oldText 重叠。"
                                    ),
                                },
                                "newText": {
                                    "type": "string",
                                    "description": "替换后的文本。",
                                },
                            },
                            "required": ["oldText", "newText"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        },
    }
]

# ---------------------------------------------------------------------------
# 工具函数映射（供 Agent 调用）
# ---------------------------------------------------------------------------

EDIT_FUNCTIONS = {
    "edit_file": edit_file,
}
