"""
精确文本替换编辑工具 —— 通过 oldText/newText 对实现文件编辑。

实现方式与 pi 框架的 edit 工具保持一致：
- 支持单次调用中多次替换（edits 数组）
- 精确匹配优先，失败后回退到 Unicode 模糊匹配
- 自动处理 BOM、行尾符（CRLF/LF）
- 检测重叠编辑和重复匹配
- 返回 unified diff 展示变更

模糊匹配安全性：
- 采用"确定性溯源"策略：通过逐步骤位置追踪，将模糊空间中的匹配位置
  精确映射回原始内容，绝不对未编辑区域做任何修改。
- 运行时自检：每次模糊匹配后，回翻译验证（normalize(original_slice) == fuzzy_match），
  若不匹配则拒绝编辑并返回明确错误，确保零误写。
"""

import difflib
import os
import unicodedata


# ===========================================================================
# 行尾符处理
# ===========================================================================

def detect_line_ending(content: str) -> str:
    """检测内容使用的主要行尾符：\r\n 或 \n。

    使用多数投票策略：统计 CRLF 和纯 LF 的出现次数，
    返回占多数的行尾符。若无行尾符，默认返回 \\n。
    """
    crlf_count = content.count("\r\n")
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


# ===========================================================================
# BOM 处理
# ===========================================================================

def strip_bom(content: str) -> tuple:
    """去除 UTF-8 BOM，返回 (bom, text)。"""
    return ("\ufeff", content[1:]) if content.startswith("\ufeff") else ("", content)


# ===========================================================================
# 1:1 字符替换表（模糊匹配中的等长变换）
# ===========================================================================

# 智能单引号 → '
_SMART_SINGLE_MAP = str.maketrans("\u2018\u2019\u201a\u201b", "''''")

# 智能双引号 → "
_SMART_DOUBLE_MAP = str.maketrans("\u201c\u201d\u201e\u201f", '""""')

# 各种破折号/连字符 → -
_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"

# 特殊空格 → 常规空格（不含 \u2002-\u200a，因其在 range 中动态处理）
_SPECIAL_SPACE_MAP = str.maketrans(
    dict.fromkeys([ord(c) for c in "\u00a0\u202f\u205f\u3000"], " ")
)


def _apply_one_to_one_replacements(text: str) -> str:
    """对文本执行所有 1:1 的字符替换（引号、破折号、空格）。"""
    text = text.translate(_SMART_SINGLE_MAP)
    text = text.translate(_SMART_DOUBLE_MAP)
    for ch in _DASH_CHARS:
        text = text.replace(ch, "-")
    text = text.translate(_SPECIAL_SPACE_MAP)
    for code in range(0x2002, 0x200B):
        text = text.replace(chr(code), " ")
    return text


# ===========================================================================
# 确定性溯源：带位置追踪的模糊规范化
# ===========================================================================

def _nfkc_with_trace(text: str) -> tuple:
    """对 text 做 NFKC 规范化，同时返回每个输出字符在原文中的跨度。

    算法：以全字符串 NFKC 结果为基准（ground truth），从左到右贪心地
    匹配原文中尽可能短的子串，使其 NFKC 结果等于当前 full 位置的前缀。

    对于组合字符序列（如 A + ̈ → Ä），算法会通过 lookahead 自动寻找
    正确的原文子串，并将输出字符的跨度标记为覆盖整个子串。

    Returns:
        (nfkc_text, spans): spans[i] = (start_in_original, end_in_original)
    """
    full = unicodedata.normalize("NFKC", text)
    spans = []              # list of (orig_start, orig_end)
    orig_i = 0
    nfkc_i = 0
    text_len = len(text)
    full_len = len(full)

    while orig_i < text_len and nfkc_i < full_len:
        matched = False

        # 贪心：尝试从 orig_i 开始的最短前缀，使其 NFKC 匹配 full 的当前位置
        max_lookahead = min(50, text_len - orig_i)
        for la in range(1, max_lookahead + 1):
            group = text[orig_i:orig_i + la]
            group_nfkc = unicodedata.normalize("NFKC", group)

            if not group_nfkc:
                # 整组被 NFKC 删除（极少数控制字符），跳过
                orig_i += la
                matched = True
                break

            if full.startswith(group_nfkc, nfkc_i):
                # 匹配成功：这 la 个原文字符产生 group_nfkc
                for _ in group_nfkc:
                    spans.append((orig_i, orig_i + la))
                nfkc_i += len(group_nfkc)
                orig_i += la
                matched = True
                break

        if not matched:
            # 理论上不应到达这里（full 就是 text 的 NFKC）
            # 作为最后防线：跳过当前字符，用启发式对齐
            spans.append((orig_i, orig_i + 1))
            nfkc_i += 1
            orig_i += 1

    # 处理 full 末尾可能多出的字符（理论上不应发生）
    last_pos = text_len - 1 if text_len > 0 else 0
    while nfkc_i < full_len:
        spans.append((last_pos, last_pos + 1))
        nfkc_i += 1

    return full, spans


def _strip_trailing_ws_with_trace(
    text: str, spans: list
) -> tuple:
    """删除每行行尾空白，同时更新位置跨度数组。

    关键约束：返回的 spans 必须与返回的 text 逐字符对齐（长度相等），
    否则后续模糊查找时的索引映射会错位。

    Args:
        text: 待处理的文本
        spans: 当前位置跨度列表，spans[i] = (start, end) 在上一级原文中

    Returns:
        (stripped_text, new_spans): 两者长度相等
    """
    result_chars = []
    result_spans = []
    line_chars = []
    line_spans = []

    for i, ch in enumerate(text):
        if ch == "\n":
            # 行尾：去除行尾空白
            strip_pos = len(line_chars)
            while strip_pos > 0 and line_chars[strip_pos - 1] in " \t":
                strip_pos -= 1
            result_chars.extend(line_chars[:strip_pos])
            result_spans.extend(line_spans[:strip_pos])
            # 保留 \n 及其 span
            result_chars.append("\n")
            result_spans.append(spans[i])
            line_chars = []
            line_spans = []
        else:
            line_chars.append(ch)
            line_spans.append(spans[i])

    # 最后一行（无尾随 \n）
    strip_pos = len(line_chars)
    while strip_pos > 0 and line_chars[strip_pos - 1] in " \t":
        strip_pos -= 1
    result_chars.extend(line_chars[:strip_pos])
    result_spans.extend(line_spans[:strip_pos])

    return "".join(result_chars), result_spans


def _fuzzy_normalize_with_trace(lf_text: str) -> tuple:
    """对 LF 规范化的文本执行模糊规范化，同时返回位置溯源。

    要求输入已经是 LF-only（\r\n 和 \r 已转为 \n）。

    规范化管道：
    1. NFKC 规范化（可能改变长度） → 记录 spans
    2. 删除行尾空白（可能改变长度）   → 更新 spans
    3. 1:1 字符替换（长度不变）       → spans 不变

    Returns:
        (fuzzy_text, spans): spans[i] = (start, end) 在原始 lf_text 中
    """
    # Step 1: NFKC（长度可能变化）
    text, spans = _nfkc_with_trace(lf_text)

    # Step 2: 删除行尾空白（长度可能变化）
    text, spans = _strip_trailing_ws_with_trace(text, spans)

    # Step 3: 1:1 字符替换（长度不变，spans 不变）
    text = _apply_one_to_one_replacements(text)

    return text, spans


# ===========================================================================
# 模糊匹配（文本版本，不返回溯源）
# ===========================================================================

def normalize_for_fuzzy_match(text: str) -> str:
    """
    对文本进行渐进式规范化，仅用于模糊匹配时的索引定位。

    注意：此函数的结果**绝不**直接写回文件。它只用于在模糊空间中找到
    oldText 的位置偏移，然后通过 _fuzzy_normalize_with_trace 的 spans
    映射回原始内容进行替换。

    规范化项目：
    - 统一换行符为 LF（处理 \\r\\n 和独立 \\r）
    - NFKC 规范化
    - 去除行尾空白
    - 智能引号 → ASCII 引号
    - Unicode 破折号/连字符 → ASCII 连字符
    - 特殊空格 → 常规空格
    """
    # 先统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 复用带溯源的版本，丢弃 spans
    fuzzy_text, _ = _fuzzy_normalize_with_trace(text)
    return fuzzy_text


# ===========================================================================
# 模糊查找（带回翻译验证）
# ===========================================================================

def fuzzy_find_text(content: str, old_text: str) -> dict:
    """
    在 content 中查找 old_text，先尝试精确匹配，再尝试模糊匹配。

    模糊匹配时，使用确定性溯源将模糊空间中的位置映射回原始位置，
    并通过回翻译验证确保映射正确。

    Args:
        content: LF 规范化后的原始内容
        old_text: LF 规范化后的待查找文本

    Returns:
        dict: {
            "found": bool,
            "index": int,           # 原始内容中的起始位置
            "match_length": int,    # 原始内容中的匹配长度
            "used_fuzzy_match": bool,
        }
    """
    # ---- 精确匹配 ----
    exact_index = content.find(old_text)
    if exact_index != -1:
        return {
            "found": True,
            "index": exact_index,
            "match_length": len(old_text),
            "used_fuzzy_match": False,
        }

    # ---- 模糊匹配 ----
    fuzzy_content, spans = _fuzzy_normalize_with_trace(content)
    fuzzy_old = normalize_for_fuzzy_match(old_text)
    fuzzy_index = fuzzy_content.find(fuzzy_old)

    if fuzzy_index == -1:
        return {
            "found": False,
            "index": -1,
            "match_length": 0,
            "used_fuzzy_match": False,
        }

    fuzzy_end = fuzzy_index + len(fuzzy_old)

    # 边界检查
    if fuzzy_index >= len(spans) or fuzzy_end > len(spans):
        return {
            "found": False,
            "index": -1,
            "match_length": 0,
            "used_fuzzy_match": False,
        }

    # 通过 spans 映射回原始位置
    original_start = spans[fuzzy_index][0]
    original_end = spans[fuzzy_end - 1][1]
    match_length = original_end - original_start

    # ---- 运行时自检（回翻译验证） ----
    original_slice = content[original_start:original_end]
    re_normalized = normalize_for_fuzzy_match(original_slice)

    if re_normalized != fuzzy_old:
        # 溯源失败 —— 绝不静默写入错误内容
        return {
            "found": False,
            "index": -1,
            "match_length": 0,
            "used_fuzzy_match": False,
            "_trace_error": (
                f"模糊匹配定位失败：回翻译验证不通过。\n"
                f"  原文切片: {repr(original_slice[:80])}\n"
                f"  规范化后: {repr(re_normalized[:80])}\n"
                f"  期望匹配: {repr(fuzzy_old[:80])}"
            ),
        }

    return {
        "found": True,
        "index": original_start,
        "match_length": match_length,
        "used_fuzzy_match": True,
    }


def count_occurrences(content: str, old_text: str) -> int:
    """统计 old_text 在 content 中的出现次数（基于模糊匹配）。"""
    fuzzy_content = normalize_for_fuzzy_match(content)
    fuzzy_old_text = normalize_for_fuzzy_match(old_text)
    return fuzzy_content.count(fuzzy_old_text)


# ===========================================================================
# 核心编辑逻辑
# ===========================================================================

def apply_edits_to_normalized_content(
    normalized_content: str,
    edits: list,
    path: str,
) -> tuple:
    """
    对 LF 规范化后的内容应用一组精确文本替换。

    所有编辑均基于同一原始内容（normalized_content）进行匹配，
    然后按逆序应用以保持偏移量稳定。

    模糊匹配只用于定位——实际替换始终在原始内容上进行，
    确保未编辑区域不受任何规范化影响。

    Args:
        normalized_content: LF 规范化后的文件内容
        edits: [{"oldText": ..., "newText": ...}, ...]
        path: 文件路径（用于错误消息）

    Returns:
        (base_content, new_content): 应用编辑前后的内容（均为 LF 规范化）

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
            suffix = (
                f"edits[{i}].oldText 不能为空"
                if len(normalized_edits) > 1
                else "oldText 不能为空"
            )
            raise ValueError(f"编辑 {path} 失败：{suffix}。")

    # ---- 始终以原始内容为基准 ----
    base_content = normalized_content

    # ---- 为每个编辑找到匹配位置 ----
    matched_edits = []
    for i, edit in enumerate(normalized_edits):
        match_result = fuzzy_find_text(base_content, edit["old_text"])

        if not match_result["found"]:
            # 如果是溯源错误，给出更详细的信息
            trace_err = match_result.get("_trace_error", "")
            suffix = (
                f"在 {path} 中找不到 edits[{i}] 的 oldText。"
                if len(normalized_edits) > 1
                else f"在 {path} 中找不到指定的 oldText。"
            )
            detail = f"\n{trace_err}" if trace_err else ""
            raise ValueError(f"{suffix} 请确保文本精确匹配（包括空白和换行）。{detail}")

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

    # 逆序应用编辑（直接在原始内容上）
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


# ===========================================================================
# Diff 生成
# ===========================================================================

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

    for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag == "equal":
            raw_lines = old_lines[i1:i2]

            # 使用 enumerate 索引而非 opcodes.index() 来检测下一段
            has_trailing_change = (
                idx + 1 < len(opcodes) and opcodes[idx + 1][0] != "equal"
            )

            if last_was_change and has_trailing_change:
                if len(raw_lines) <= context_lines * 2:
                    for line in raw_lines:
                        output.append(
                            f" {str(old_line_num).rjust(line_num_width)} {line}"
                        )
                        old_line_num += 1
                        new_line_num += 1
                else:
                    leading = raw_lines[:context_lines]
                    trailing = raw_lines[-context_lines:]
                    skipped = len(raw_lines) - len(leading) - len(trailing)
                    for line in leading:
                        output.append(
                            f" {str(old_line_num).rjust(line_num_width)} {line}"
                        )
                        old_line_num += 1
                        new_line_num += 1
                    output.append(f" {' '.rjust(line_num_width)} ...")
                    old_line_num += skipped
                    new_line_num += skipped
                    for line in trailing:
                        output.append(
                            f" {str(old_line_num).rjust(line_num_width)} {line}"
                        )
                        old_line_num += 1
                        new_line_num += 1
            elif last_was_change:
                shown = raw_lines[:context_lines]
                skipped = len(raw_lines) - len(shown)
                for line in shown:
                    output.append(
                        f" {str(old_line_num).rjust(line_num_width)} {line}"
                    )
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
                    output.append(
                        f" {str(old_line_num).rjust(line_num_width)} {line}"
                    )
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


# ===========================================================================
# 主函数
# ===========================================================================

def edit_file(path: str = None, edits: list = None):
    """
    通过精确文本替换编辑单个文件。

    - 每次调用可包含多个替换（edits 数组）。
    - 每个 edits[].oldText 必须在原文件中唯一且不与其他编辑重叠。
    - 先尝试精确匹配，失败后回退到 Unicode 模糊匹配。
    - 模糊匹配使用确定性溯源 + 回翻译验证，确保零误写。
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


# ===========================================================================
# 工具元信息（供 LLM 识别）
# ===========================================================================

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

# ===========================================================================
# 工具函数映射（供 Agent 调用）
# ===========================================================================

EDIT_FUNCTIONS = {
    "edit_file": edit_file,
}
