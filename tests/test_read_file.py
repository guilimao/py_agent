"""
read_file 工具的综合测试套件。

覆盖场景：
- 底层函数：路径解析、Unicode 空格规范化、大小格式化
- _truncate_head（截断逻辑：行/字节限制、第一行超限、边界条件）
- read_file 集成测试（文本文件、二进制、错误处理）
- offset / limit 分页读取
- 截断提示信息（offset 建议）
- 工具元信息

运行方式：
    python -m pytest tests/test_read_file.py -v
    或
    python -m unittest tests.test_read_file -v
"""

import os
import sys
import tempfile
import unittest

# 确保 pyagent 包可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyagent.tools.read_file import (
    _normalize_unicode_spaces,
    _resolve_path,
    _format_size,
    _truncate_head,
    read_file,
    DEFAULT_MAX_LINES,
    DEFAULT_MAX_BYTES,
    READ_FILE_TOOLS,
    READ_FILE_FUNCTIONS,
)


# ============================================================================
# 测试辅助工具
# ============================================================================

class TempDirMixin:
    """为测试提供临时目录的 mixin。"""

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(prefix="read_file_test_")
        self.temp_root = self._temp_dir.name

    def tearDown(self):
        self._temp_dir.cleanup()

    def temp_path(self, relpath: str) -> str:
        """获取临时目录下的绝对路径。"""
        return os.path.join(self.temp_root, relpath)


# ============================================================================
# _normalize_unicode_spaces 测试
# ============================================================================

class TestNormalizeUnicodeSpaces(unittest.TestCase):

    def test_no_break_space(self):
        self.assertEqual(_normalize_unicode_spaces("hello\u00A0world"), "hello world")

    def test_ideographic_space(self):
        self.assertEqual(_normalize_unicode_spaces("hello\u3000world"), "hello world")

    def test_en_quad_to_hair_space(self):
        """U+2000..U+200A 范围的各种空间字符"""
        for code in range(0x2000, 0x200B):
            with self.subTest(code=f"U+{code:04X}"):
                result = _normalize_unicode_spaces(f"a{chr(code)}b")
                self.assertEqual(result, "a b")

    def test_narrow_no_break_space(self):
        self.assertEqual(_normalize_unicode_spaces("a\u202Fb"), "a b")

    def test_medium_mathematical_space(self):
        self.assertEqual(_normalize_unicode_spaces("a\u205Fb"), "a b")

    def test_mixed_unicode_spaces(self):
        text = "a\u00A0b\u2000c\u3000d\u202Fe"
        result = _normalize_unicode_spaces(text)
        self.assertEqual(result, "a b c d e")

    def test_no_change_for_normal_text(self):
        text = "hello world\ttab\nnewline"
        self.assertEqual(_normalize_unicode_spaces(text), text)

    def test_empty_string(self):
        self.assertEqual(_normalize_unicode_spaces(""), "")


# ============================================================================
# _resolve_path 测试
# ============================================================================

class TestResolvePath(unittest.TestCase):

    def test_expand_user_home(self):
        """~ 应展开为用户主目录。"""
        result = _resolve_path("~/test.txt")
        self.assertTrue(result.startswith(os.path.expanduser("~")))
        self.assertTrue(result.endswith("test.txt"))

    def test_relative_to_absolute(self):
        """相对路径应转为绝对路径。"""
        result = _resolve_path("foo/bar.txt")
        self.assertTrue(os.path.isabs(result))
        self.assertTrue(result.endswith(os.path.join("foo", "bar.txt")))

    def test_strip_at_prefix(self):
        """应去除 @ 前缀。"""
        result = _resolve_path("@/home/user/file.txt")
        self.assertFalse("@/" in result)

    def test_unicode_spaces_normalized(self):
        """路径中的 Unicode 空格应被规范化。"""
        result = _resolve_path("foo\u00A0bar.txt")
        self.assertNotIn("\u00A0", result)
        self.assertIn("foo bar.txt", result)

    def test_empty_path_returns_empty(self):
        self.assertEqual(_resolve_path(""), "")
        self.assertEqual(_resolve_path(None), None)

    def test_absolute_path_preserved(self):
        """已是绝对路径应保持不变（展开 ~ 除外）。"""
        if sys.platform == "win32":
            abs_path = "C:\\absolute\\path.txt"
        else:
            abs_path = "/absolute/path.txt"
        result = _resolve_path(abs_path)
        self.assertEqual(os.path.normpath(result), os.path.normpath(os.path.abspath(abs_path)))

    def test_strips_surrounding_whitespace(self):
        result = _resolve_path("  /some/path  ")
        self.assertTrue(os.path.isabs(result))


# ============================================================================
# _format_size 测试
# ============================================================================

class TestFormatSize(unittest.TestCase):

    def test_bytes_range(self):
        self.assertEqual(_format_size(0), "0B")
        self.assertEqual(_format_size(1), "1B")
        self.assertEqual(_format_size(1023), "1023B")

    def test_kb_range(self):
        self.assertEqual(_format_size(1024), "1.0KB")
        self.assertEqual(_format_size(1536), "1.5KB")
        self.assertEqual(_format_size(1024 * 1024 - 1), f"{(1024 * 1024 - 1) / 1024:.1f}KB")

    def test_mb_range(self):
        self.assertEqual(_format_size(1024 * 1024), "1.0MB")
        self.assertEqual(_format_size(10 * 1024 * 1024), "10.0MB")
        self.assertEqual(_format_size(1536 * 1024), "1.5MB")

    def test_large_values(self):
        size = 100 * 1024 * 1024  # 100 MB
        result = _format_size(size)
        self.assertIn("MB", result)


# ==============================================
# _truncate_head 测试
# ============================================================================

class TestTruncateHead(unittest.TestCase):

    # ---------- 无需截断的情况 ----------

    def test_empty_content(self):
        result = _truncate_head("")
        self.assertFalse(result["truncated"])
        self.assertEqual(result["content"], "")
        self.assertEqual(result["total_lines"], 0)
        self.assertEqual(result["total_bytes"], 0)
        self.assertEqual(result["output_lines"], 0)
        self.assertEqual(result["output_bytes"], 0)
        self.assertFalse(result["first_line_exceeds_limit"])
        self.assertIsNone(result["truncated_by"])

    def test_small_content_no_truncation(self):
        content = "hello world"
        result = _truncate_head(content)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["content"], content)
        self.assertIsNone(result["truncated_by"])

    # ---------- 按行数截断 ----------

    def test_truncate_by_lines(self):
        """超过 max_lines 但不超过 max_bytes"""
        lines = ["line " + str(i) for i in range(10)]
        content = "\n".join(lines)
        result = _truncate_head(content, max_lines=5, max_bytes=DEFAULT_MAX_BYTES)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "lines")
        self.assertEqual(result["output_lines"], 5)
        self.assertEqual(result["total_lines"], 10)

    # ---------- 按字节数截断 ----------

    def test_truncate_by_bytes(self):
        """不超过 max_lines 但超过 max_bytes"""
        # 每条长 ~100 字节，限制 200 字节 → 约 2 条
        long_line = "x" * 100
        lines = [long_line] * 10
        content = "\n".join(lines)
        result = _truncate_head(content, max_lines=100, max_bytes=250)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "bytes")
        # 200 字节限制，100 字节第一行 + 101 字节第二行 = 201 > 250 → 第二行可以放
        # 100 + 101 + 101 = 302 > 250 → 第三行不行
        self.assertEqual(result["output_lines"], 2)

    # ---------- 第一行超限 ----------

    def test_first_line_exceeds_bytes_limit(self):
        """第一行本身就超过字节限制"""
        long_line = "x" * 1000
        result = _truncate_head(long_line, max_lines=100, max_bytes=500)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "bytes")
        self.assertTrue(result["first_line_exceeds_limit"])
        self.assertEqual(result["content"], "")
        self.assertEqual(result["output_lines"], 0)

    def test_first_line_exceeds_but_within_default(self):
        """第一行超出自定义限制但未超出默认限制时"""
        # 默认限制 50KB，一行 500 字节
        line = "x" * 600
        result = _truncate_head(line, max_lines=10, max_bytes=500)
        self.assertTrue(result["first_line_exceeds_limit"])

    # ---------- 多行中字节截断 ----------

    def test_bytes_truncation_preserves_lines(self):
        """字节截断不应把一行切成两半"""
        lines = ["aaa", "bbb", "ccc"]
        content = "\n".join(lines)
        # 总字节：aaa(3) + \n(1) + bbb(3) + \n(1) = 8 → 限制 5 → 只保留第一行
        result = _truncate_head(content, max_lines=100, max_bytes=5)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "bytes")
        self.assertEqual(result["output_lines"], 1)
        self.assertEqual(result["content"], "aaa")

    def test_bytes_exactly_at_boundary(self):
        """字节数恰好等于限制时不应截断"""
        content = "abcde"  # 5 bytes
        result = _truncate_head(content, max_lines=100, max_bytes=5)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["content"], content)

    # ---------- 行数恰好等于限制 ----------

    def test_lines_exactly_at_limit(self):
        lines = ["a", "b", "c", "d", "e"]
        content = "\n".join(lines)
        result = _truncate_head(content, max_lines=5, max_bytes=DEFAULT_MAX_BYTES)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["total_lines"], 5)

    # ---------- 以 \n 结尾 ----------

    def test_trailing_newline_handling(self):
        """以 \n 结尾的内容，末尾空行不计入行数"""
        content = "line1\nline2\n"
        result = _truncate_head(content, max_lines=10, max_bytes=DEFAULT_MAX_BYTES)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["total_lines"], 2)
        self.assertEqual(result["content"], content)

    # ---------- 单行内容 ----------

    def test_single_line(self):
        content = "just one line"
        result = _truncate_head(content)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["total_lines"], 1)

    # ---------- 中文字符 ----------

    def test_chinese_characters_bytes(self):
        """中文字符每字符 3 字节（UTF-8），正确计算字节限制"""
        line = "你好世界"  # 12 bytes
        lines = [line] * 10
        content = "\n".join(lines)
        result = _truncate_head(content, max_lines=100, max_bytes=30)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "bytes")
        self.assertEqual(result["output_lines"], 2)
        # 第一行: 12 bytes, 第二行: 12 + 1(\n) = 13 → 12+13=25 ≤ 30
        # 第三行: +13 = 38 > 30 → 停
        self.assertEqual(result["content"], f"{line}\n{line}")

    # ---------- 默认限制 ----------

    def test_default_limits_in_result(self):
        result = _truncate_head("test")
        self.assertEqual(result["max_lines"], DEFAULT_MAX_LINES)
        self.assertEqual(result["max_bytes"], DEFAULT_MAX_BYTES)

    # ---------- 边界回归 ----------

    def test_bytes_one_less_than_needed(self):
        """字节数刚好少 1 不足以包含下一行"""
        line = "abc"  # 3 bytes
        # 第一行: 3 bytes, 第二行: 3 + 1(\n) = 4
        # 总 3+4=7, 限制 6 → 只保留第一行
        result = _truncate_head(f"{line}\n{line}", max_lines=100, max_bytes=6)
        self.assertEqual(result["output_lines"], 1)

    def test_bytes_one_more_than_needed(self):
        """字节数刚好多 1 可以包含下一行"""
        line = "abc"
        result = _truncate_head(f"{line}\n{line}", max_lines=100, max_bytes=7)
        self.assertEqual(result["output_lines"], 2)
        self.assertFalse(result["truncated"])


# ============================================================================
# read_file 集成测试
# ============================================================================

class TestReadFileBasic(TempDirMixin, unittest.TestCase):

    def test_read_simple_text_file(self):
        """读取一个简单的文本文件。"""
        path = self.temp_path("simple.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hello world")

        result = read_file(path=path)
        self.assertIn("hello world", result)
        self.assertNotIn("[ERROR]", result)

    def test_read_unicode_content(self):
        """读取包含 Unicode 内容的文件。"""
        path = self.temp_path("unicode.txt")
        content = "你好世界 🌍\nこんにちは\n🎉 àéîöü"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        result = read_file(path=path)
        self.assertIn("你好世界", result)
        self.assertIn("🌍", result)
        self.assertIn("🎉", result)

    def test_read_multiline_file(self):
        """读取多行文件。"""
        path = self.temp_path("multiline.txt")
        lines = [f"line_{i}" for i in range(50)]
        content = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        result = read_file(path=path)
        for i in range(50):
            self.assertIn(f"line_{i}", result)

    def test_read_empty_file(self):
        """读取空文件。"""
        path = self.temp_path("empty.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("")

        result = read_file(path=path)
        self.assertEqual(result, "")


class TestReadFileErrors(TempDirMixin, unittest.TestCase):

    def test_missing_path(self):
        result = read_file(path=None)
        self.assertIn("[ERROR]", result)
        self.assertIn("path is required", result)

    def test_empty_path(self):
        result = read_file(path="")
        self.assertIn("[ERROR]", result)
        self.assertIn("path is required", result)

    def test_file_not_found(self):
        result = read_file(path="/nonexistent/file_that_does_not_exist.txt")
        self.assertIn("[ERROR]", result)
        self.assertIn("file not found", result)

    def test_offset_beyond_end(self):
        """offset 超出文件行数时应报错。"""
        path = self.temp_path("short.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("only 3 lines\nsecond\nthird\n")

        result = read_file(path=path, offset=100)
        self.assertIn("[ERROR]", result)
        self.assertIn("beyond end of file", result)


class TestReadFileWithOffset(TempDirMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        path = self.temp_path("numbered.txt")
        lines = [f"line_{i:04d}" for i in range(100)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.numbered_path = path

    def test_offset_from_middle(self):
        """从第 50 行开始读取。"""
        result = read_file(path=self.numbered_path, offset=50)
        self.assertIn("line_0049", result)  # 第 50 行（1-indexed → 0-indexed: 49）
        self.assertNotIn("line_0000", result)

    def test_offset_with_limit(self):
        """使用 offset + limit 精确控制读取范围。"""
        result = read_file(path=self.numbered_path, offset=10, limit=5)
        # 提取纯内容行（排除末尾的 "more lines" 提示）
        content_part = result.split("\n\n[")[0]
        lines = content_part.strip().split("\n")
        # 应该只有 5 行
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "line_0009")  # offset=10 → 第 10 行 = index 9
        self.assertEqual(lines[4], "line_0013")

    def test_offset_limit_shows_more_hint(self):
        """limit 截断后应显示剩余行提示。"""
        path = self.temp_path("more_hint.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join([f"line_{i}" for i in range(20)]))

        result = read_file(path=path, offset=1, limit=10)
        self.assertIn("more lines in file", result)
        self.assertIn("offset=11", result)

    def test_offset_exactly_at_last_line(self):
        """offset 恰好指向最后一行。"""
        result = read_file(path=self.numbered_path, offset=100)
        self.assertEqual(result.strip(), "line_0099")

    def test_offset_zero_treated_as_one(self):
        """offset=0 应被当作从第一行开始。"""
        result = read_file(path=self.numbered_path, offset=0)
        self.assertIn("line_0000", result)


class TestReadFileTruncation(TempDirMixin, unittest.TestCase):

    def test_large_file_truncation_message(self):
        """大文件应有截断提示。"""
        path = self.temp_path("large.txt")
        lines = [f"line_{i:06d}" for i in range(3000)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        result = read_file(path=path)
        self.assertIn("Showing lines", result)
        self.assertIn("offset=", result)

    def test_truncation_shows_correct_line_range(self):
        """截断提示应显示正确的行范围。"""
        path = self.temp_path("trunc_range.txt")
        lines = [f"line_{i}" for i in range(2500)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        result = read_file(path=path)
        # 默认 max_lines=2000
        self.assertIn("lines 1-2000", result)
        self.assertIn("offset=2001", result)

    def test_first_line_exceeds_limit(self):
        """第一行超过 50KB 限制时给出提示。"""
        path = self.temp_path("huge_first_line.txt")
        huge_line = "x" * (DEFAULT_MAX_BYTES + 100)
        with open(path, "w", encoding="utf-8") as f:
            f.write(huge_line)

        result = read_file(path=path)
        self.assertIn("exceeds", result)
        self.assertIn("sed", result)

    def test_truncation_offset_continues(self):
        """截断后使用提示的 offset 可以继续读取。"""
        path = self.temp_path("continue.txt")
        lines = [f"line_{i:04d}" for i in range(2500)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # 第一次读取
        r1 = read_file(path=path)
        self.assertIn("lines 1-2000", r1)
        self.assertIn("line_1999", r1)
        self.assertNotIn("line_2000", r1)

        # 使用 offset 继续读取
        r2 = read_file(path=path, offset=2001)
        self.assertIn("line_2000", r2)
        self.assertIn("line_2499", r2)


class TestReadFileBinary(TempDirMixin, unittest.TestCase):

    def test_binary_file_detected(self):
        """二进制文件应被检测并给出提示。"""
        path = self.temp_path("binary.bin")
        with open(path, "wb") as f:
            f.write(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc")

        result = read_file(path=path)
        self.assertIn("Binary file detected", result)

    def test_utf16_file_detected_as_binary(self):
        """UTF-16 编码文件无法以 UTF-8 解码，应视为二进制。"""
        path = self.temp_path("utf16.txt")
        with open(path, "w", encoding="utf-16") as f:
            f.write("hello world")

        result = read_file(path=path)
        self.assertIn("Binary file detected", result)


class TestReadFileEdgeCases(TempDirMixin, unittest.TestCase):

    def test_tilde_expansion(self):
        """路径中的 ~ 应被展开。"""
        path = "~/pyagent_read_test_temp.txt"
        expanded = os.path.expanduser(path)
        try:
            with open(expanded, "w", encoding="utf-8") as f:
                f.write("tilde test")
            result = read_file(path=path)
            self.assertIn("tilde test", result)
        finally:
            if os.path.exists(expanded):
                os.remove(expanded)

    def test_at_prefix_path(self):
        """@ 前缀应被去除。"""
        path = self.temp_path("at_prefix.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("content")

        result = read_file(path="@" + path)
        self.assertIn("content", result)

    def test_unicode_path(self):
        """路径中包含 Unicode 字符。"""
        path = self.temp_path("中文目录/файл.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("unicode path test")

        result = read_file(path=path)
        self.assertIn("unicode path test", result)

    def test_trailing_newlines(self):
        """末尾多个换行符的处理。"""
        path = self.temp_path("trailing_nl.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1\nline2\n\n\n")

        result = read_file(path=path)
        # 应该保留换行（末尾空行被去掉后内容应包含 \n）
        self.assertIn("line1", result)
        self.assertIn("line2", result)

    def test_crlf_file(self):
        """CRLF 换行符的文件。"""
        path = self.temp_path("crlf.txt")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("line1\r\nline2\r\nline3\r\n")

        result = read_file(path=path)
        self.assertIn("line1", result)
        self.assertIn("line2", result)
        self.assertIn("line3", result)


# ============================================================================
# 工具元信息测试
# ============================================================================

class TestReadFileToolMetadata(unittest.TestCase):

    def test_tool_schema_is_valid(self):
        self.assertIsInstance(READ_FILE_TOOLS, list)
        self.assertGreater(len(READ_FILE_TOOLS), 0)

        tool = READ_FILE_TOOLS[0]
        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["function"]["name"], "read_file")
        self.assertIn("description", tool["function"])
        self.assertIn("parameters", tool["function"])

        params = tool["function"]["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("path", params["properties"])
        self.assertIn("offset", params["properties"])
        self.assertIn("limit", params["properties"])
        self.assertEqual(params["required"], ["path"])

    def test_function_mapping(self):
        self.assertIn("read_file", READ_FILE_FUNCTIONS)
        self.assertIs(READ_FILE_FUNCTIONS["read_file"], read_file)


# ============================================================================
# 边界回归测试
# ============================================================================

class TestReadFileRegression(TempDirMixin, unittest.TestCase):

    def test_very_long_line_in_middle(self):
        """超长行在文件中间时，截断应正确处理。"""
        path = self.temp_path("long_mid.txt")
        lines = []
        for i in range(50):
            lines.append(f"short line {i}")
        lines.append("x" * (DEFAULT_MAX_BYTES + 10))  # 超长行
        for i in range(50, 100):
            lines.append(f"short line {i}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # 从超长行之前开始读
        result = read_file(path=path, offset=51, limit=1)
        self.assertIn("exceeds", result)

    def test_exact_max_bytes_boundary(self):
        """内容字节数恰好等于 DEFAULT_MAX_BYTES 时不应截断。"""
        path = self.temp_path("exact_boundary.txt")
        # 构造恰好 50KB 的内容
        content = "a" * DEFAULT_MAX_BYTES
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        result = read_file(path=path)
        self.assertNotIn("[ERROR]", result)
        self.assertNotIn("Showing lines", result)
        self.assertNotIn("offset=", result)

    def test_near_max_lines_boundary(self):
        """行数接近 DEFAULT_MAX_LINES 时的行为。"""
        path = self.temp_path("near_boundary.txt")
        lines = [f"line_{i}" for i in range(DEFAULT_MAX_LINES - 1)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        result = read_file(path=path)
        self.assertNotIn("Showing lines", result)

    def test_very_many_short_lines(self):
        """大量非常短的行。"""
        path = self.temp_path("many_short.txt")
        lines = ["x"] * 5000
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        result = read_file(path=path)
        self.assertIn("lines 1-2000", result)
        self.assertIn("offset=2001", result)

    def test_limit_exceeds_file(self):
        """limit 大于文件行数时应返回全部内容。"""
        path = self.temp_path("limit_exceed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1\nline2\nline3\n")

        result = read_file(path=path, limit=100)
        self.assertNotIn("[ERROR]", result)
        self.assertNotIn("more lines", result)
        self.assertEqual(result.strip(), "line1\nline2\nline3")

    def test_precise_byte_count_in_truncation(self):
        """截断消息中的字节数信息应准确。"""
        path = self.temp_path("precise_trunc.txt")
        # 每行 ~100 字节，共 2500 行
        line = "x" * 100
        lines = [f"{line}{i:04d}" for i in range(2500)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        result = read_file(path=path)
        # 截断消息中包含 50.0KB 限制（_format_size 格式化结果）
        self.assertIn("50.0KB limit", result)


if __name__ == "__main__":
    unittest.main()
