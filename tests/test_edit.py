"""
edit_file 工具的综合测试套件。

覆盖场景：
- 底层溯源函数（NFKC trace、行尾空白 strip trace）
- fuzzy_find_text（精确匹配、模糊匹配、自检失败）
- apply_edits_to_normalized_content（基本、模糊、错误处理）
- edit_file 集成测试（文件往返、BOM、行尾符）
- 回归测试：模糊匹配不损坏未编辑区域

运行方式：
    python -m pytest tests/test_edit.py -v
"""

import os
import sys
import tempfile
import unicodedata
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyagent.tools.edit import (
    _nfkc_with_trace,
    _strip_trailing_ws_with_trace,
    _fuzzy_normalize_with_trace,
    _apply_one_to_one_replacements,
    fuzzy_find_text,
    normalize_for_fuzzy_match,
    count_occurrences,
    apply_edits_to_normalized_content,
    edit_file,
    detect_line_ending,
    normalize_to_lf,
    restore_line_endings,
    strip_bom,
    generate_diff_string,
    generate_unified_patch,
    EDIT_TOOLS,
    EDIT_FUNCTIONS,
)


# ============================================================================
# 辅助工具
# ============================================================================

class TempDirMixin:
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(prefix="edit_test_")
        self.temp_root = self._temp_dir.name

    def tearDown(self):
        self._temp_dir.cleanup()

    def temp_path(self, relpath: str) -> str:
        return os.path.join(self.temp_root, relpath)


# ============================================================================
# 行尾符 / BOM 基础测试
# ============================================================================

class TestLineEndingDetection(unittest.TestCase):
    def test_crlf_dominant(self):
        self.assertEqual(detect_line_ending("a\r\nb\r\nc"), "\r\n")

    def test_lf_dominant(self):
        self.assertEqual(detect_line_ending("a\nb\nc\r\nd"), "\n")

    def test_empty_defaults_to_lf(self):
        self.assertEqual(detect_line_ending(""), "\n")

    def test_no_newlines_defaults_to_lf(self):
        self.assertEqual(detect_line_ending("hello world"), "\n")


class TestNormalizeToLf(unittest.TestCase):
    def test_crlf_converted(self):
        self.assertEqual(normalize_to_lf("a\r\nb"), "a\nb")

    def test_cr_converted(self):
        self.assertEqual(normalize_to_lf("a\rb"), "a\nb")

    def test_mixed(self):
        self.assertEqual(normalize_to_lf("a\r\nb\rc\nd"), "a\nb\nc\nd")


class TestRestoreLineEndings(unittest.TestCase):
    def test_restore_crlf(self):
        self.assertEqual(restore_line_endings("a\nb", "\r\n"), "a\r\nb")

    def test_restore_lf_unchanged(self):
        self.assertEqual(restore_line_endings("a\nb", "\n"), "a\nb")


class TestBomHandling(unittest.TestCase):
    def test_strip_bom(self):
        bom, text = strip_bom("\ufeffhello")
        self.assertEqual(bom, "\ufeff")
        self.assertEqual(text, "hello")

    def test_no_bom(self):
        bom, text = strip_bom("hello")
        self.assertEqual(bom, "")
        self.assertEqual(text, "hello")


# ============================================================================
# _nfkc_with_trace 测试
# ============================================================================

class TestNfkcWithTrace(unittest.TestCase):
    def test_ascii_identity(self):
        text = "hello world"
        result, spans = _nfkc_with_trace(text)
        self.assertEqual(result, text)
        self.assertEqual(len(spans), len(text))
        for i, s in enumerate(spans):
            self.assertEqual(s, (i, i + 1))

    def test_ligature_expansion(self):
        """ﬁ (U+FB01) → fi，1 字符变成 2 字符"""
        text = "\ufb01le"
        result, spans = _nfkc_with_trace(text)
        self.assertEqual(result, "file")
        self.assertEqual(len(spans), 4)
        # 两个输出字符 'f' 和 'i' 都追溯到同一个输入位置 0
        self.assertEqual(spans[0], (0, 1))
        self.assertEqual(spans[1], (0, 1))
        self.assertEqual(spans[2], (1, 2))
        self.assertEqual(spans[3], (2, 3))

    def test_combining_contraction(self):
        """A + combining diaeresis → Ä，2 字符变成 1 字符"""
        text = "A\u0308"
        result, spans = _nfkc_with_trace(text)
        expected = unicodedata.normalize("NFKC", text)
        self.assertEqual(result, expected)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0], (0, 2))

    def test_mixed_content(self):
        """混合普通字符和特殊字符"""
        text = "café\ufb01n"  # café + ﬁ + n
        result, spans = _nfkc_with_trace(text)
        full_nfkc = unicodedata.normalize("NFKC", text)
        self.assertEqual(result, full_nfkc)
        self.assertEqual(len(spans), len(result),
                         f"spans length {len(spans)} != result length {len(result)}")

    def test_all_spans_monotonic(self):
        """spans 中 start 位置应单调不降"""
        text = "A\u0308\ufb01\u2014test"
        result, spans = _nfkc_with_trace(text)
        for i in range(1, len(spans)):
            self.assertGreaterEqual(spans[i][0], spans[i - 1][0])

    def test_empty_string(self):
        result, spans = _nfkc_with_trace("")
        self.assertEqual(result, "")
        self.assertEqual(spans, [])

    def test_newline_preserved(self):
        result, spans = _nfkc_with_trace("a\nb")
        self.assertIn("\n", result)

    def test_cjk_compatibility(self):
        """CJK 兼容字符如 ㌔ (U+3314) 被 NFKC 展开"""
        text = "\u3314"
        result, _ = _nfkc_with_trace(text)
        self.assertGreater(len(result), 1)  # Should expand


# ============================================================================
# _strip_trailing_ws_with_trace 测试
# ============================================================================

class TestStripTrailingWsWithTrace(unittest.TestCase):
    def _make_spans(self, text):
        return [(i, i + 1) for i in range(len(text))]

    def test_no_trailing_ws(self):
        text = "hello\nworld"
        spans_in = self._make_spans(text)
        result, spans_out = _strip_trailing_ws_with_trace(text, spans_in)
        self.assertEqual(result, text)
        self.assertEqual(len(spans_out), len(result))

    def test_trailing_spaces(self):
        text = "hello   \nworld"
        spans_in = self._make_spans(text)
        result, spans_out = _strip_trailing_ws_with_trace(text, spans_in)
        self.assertEqual(result, "hello\nworld")

    def test_trailing_tabs(self):
        text = "hello\t\t\nworld"
        spans_in = self._make_spans(text)
        result, spans_out = _strip_trailing_ws_with_trace(text, spans_in)
        self.assertEqual(result, "hello\nworld")

    def test_newline_spans_preserved(self):
        """\\n 的 span 必须保留，确保 spans 与 text 长度对齐"""
        text = "a\nb\n"
        spans_in = self._make_spans(text)
        result, spans_out = _strip_trailing_ws_with_trace(text, spans_in)
        self.assertEqual(len(spans_out), len(result),
                         "spans must be same length as result text")
        # 两个 \n 的 span 应该保留
        newline_indices = [i for i, ch in enumerate(result) if ch == "\n"]
        self.assertEqual(len(newline_indices), 2)

    def test_last_line_trailing_ws(self):
        """最后一行（无换行符）的行尾空白也应删除"""
        text = "hello\nworld   "
        spans_in = self._make_spans(text)
        result, spans_out = _strip_trailing_ws_with_trace(text, spans_in)
        self.assertEqual(result, "hello\nworld")


# ============================================================================
# _fuzzy_normalize_with_trace 测试
# ============================================================================

class TestFuzzyNormalizeWithTrace(unittest.TestCase):
    def test_length_invariant(self):
        """返回的 text 和 spans 长度必须相等"""
        for content in [
            "hello world",
            "\ufb01le",
            "A\u0308",
            "\u201cquote\u201d",
            "\u2014dash\u2014",
            "a\u00a0b",  # non-breaking space
        ]:
            with self.subTest(content=repr(content)):
                text, spans = _fuzzy_normalize_with_trace(content)
                self.assertEqual(len(text), len(spans),
                                 f"Length mismatch: text={len(text)}, spans={len(spans)}")

    def test_smart_quotes_replaced(self):
        text, _ = _fuzzy_normalize_with_trace("\u201cHello\u201d")
        self.assertNotIn("\u201c", text)
        self.assertNotIn("\u201d", text)
        self.assertIn('"', text)

    def test_em_dash_replaced(self):
        text, _ = _fuzzy_normalize_with_trace("a\u2014b")
        self.assertNotIn("\u2014", text)
        self.assertIn("-", text)

    def test_special_spaces_replaced(self):
        text, _ = _fuzzy_normalize_with_trace("a\u3000b")
        self.assertNotIn("\u3000", text)
        self.assertIn(" ", text)

    def test_monotonic_spans(self):
        content = "\u201cA\u0308\ufb01\u2014test\u201d"
        _, spans = _fuzzy_normalize_with_trace(content)
        for i in range(1, len(spans)):
            self.assertGreaterEqual(spans[i][0], spans[i - 1][0],
                                    f"Spans not monotonic at {i}")


# ============================================================================
# _apply_one_to_one_replacements 测试
# ============================================================================

class TestOneToOneReplacements(unittest.TestCase):
    def test_smart_single_quotes(self):
        result = _apply_one_to_one_replacements("\u2018test\u2019")
        self.assertEqual(result, "'test'")

    def test_smart_double_quotes(self):
        result = _apply_one_to_one_replacements("\u201ctest\u201d")
        self.assertEqual(result, '"test"')

    def test_various_dashes(self):
        for dash in ["\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"]:
            result = _apply_one_to_one_replacements(f"a{dash}b")
            self.assertEqual(result, "a-b", f"Failed for U+{ord(dash):04X}")

    def test_special_spaces(self):
        for sp in ["\u00a0", "\u202f", "\u205f", "\u3000"]:
            result = _apply_one_to_one_replacements(f"a{sp}b")
            self.assertEqual(result, "a b", f"Failed for U+{ord(sp):04X}")

    def test_en_quad_to_hair_space(self):
        for code in range(0x2002, 0x200B):
            result = _apply_one_to_one_replacements(f"a{chr(code)}b")
            self.assertEqual(result, "a b", f"Failed for U+{code:04X}")

    def test_ascii_unchanged(self):
        result = _apply_one_to_one_replacements("hello world")
        self.assertEqual(result, "hello world")


# ============================================================================
# fuzzy_find_text 测试
# ============================================================================

class TestFuzzyFindText(unittest.TestCase):
    def test_exact_match(self):
        r = fuzzy_find_text("hello world", "world")
        self.assertTrue(r["found"])
        self.assertFalse(r["used_fuzzy_match"])
        self.assertEqual(r["index"], 6)
        self.assertEqual(r["match_length"], 5)

    def test_exact_match_not_found(self):
        r = fuzzy_find_text("hello world", "xyz")
        self.assertFalse(r["found"])

    def test_fuzzy_dash(self):
        r = fuzzy_find_text("hello\u2014world", "hello-world")
        self.assertTrue(r["found"])
        self.assertTrue(r["used_fuzzy_match"])

    def test_fuzzy_smart_quotes(self):
        r = fuzzy_find_text("\u201chello\u201d", '"hello"')
        self.assertTrue(r["found"])
        self.assertTrue(r["used_fuzzy_match"])

    def test_fuzzy_ligature(self):
        r = fuzzy_find_text("\ufb01le", "file")
        self.assertTrue(r["found"])
        self.assertTrue(r["used_fuzzy_match"])

    def test_fuzzy_combining(self):
        """Ä (precomposed) matching A + combining diaeresis"""
        r = fuzzy_find_text("\u00c4nder", "Ander")  # Ä → A in NFKC? No, Ä stays Ä.
        # Actually, NFKC doesn't decompose Ä. Let's do the reverse:
        r = fuzzy_find_text("A\u0308nder", "\u00c4nder")
        self.assertTrue(r["found"])
        self.assertTrue(r["used_fuzzy_match"])

    def test_self_check_passes(self):
        """验证自检：规范化(原文切片) == 模糊匹配文本"""
        content = "\u201cHello\u2014World\u201d"
        r = fuzzy_find_text(content, '"Hello-World"')
        self.assertTrue(r["found"])
        original_slice = content[r["index"]:r["index"] + r["match_length"]]
        re_norm = normalize_for_fuzzy_match(original_slice)
        self.assertEqual(re_norm, normalize_for_fuzzy_match('"Hello-World"'))

    def test_no_false_positive_on_close_match(self):
        """确保不会错匹配"""
        r = fuzzy_find_text("something completely different", "target")
        self.assertFalse(r["found"])


# ============================================================================
# count_occurrences 测试
# ============================================================================

class TestCountOccurrences(unittest.TestCase):
    def test_single(self):
        self.assertEqual(count_occurrences("hello", "hello"), 1)

    def test_multiple(self):
        self.assertEqual(count_occurrences("x x x", "x"), 3)

    def test_zero(self):
        self.assertEqual(count_occurrences("abc", "xyz"), 0)

    def test_fuzzy_count(self):
        """模糊空间中的计数"""
        self.assertEqual(count_occurrences("\u2014 \u2014", "-"), 2)


# ============================================================================
# apply_edits_to_normalized_content 测试
# ============================================================================

class TestApplyEditsBasic(unittest.TestCase):
    def test_single_exact_edit(self):
        base, new = apply_edits_to_normalized_content(
            "hello world",
            [{"oldText": "world", "newText": "there"}],
            "test.txt",
        )
        self.assertEqual(new, "hello there")

    def test_multiple_edits(self):
        base, new = apply_edits_to_normalized_content(
            "a b c d",
            [
                {"oldText": "a", "newText": "1"},
                {"oldText": "c", "newText": "3"},
            ],
            "test.txt",
        )
        self.assertEqual(new, "1 b 3 d")

    def test_empty_oldtext_rejected(self):
        with self.assertRaises(ValueError):
            apply_edits_to_normalized_content("test", [{"oldText": "", "newText": "x"}], "t")

    def test_non_unique_rejected(self):
        with self.assertRaises(ValueError):
            apply_edits_to_normalized_content("x x", [{"oldText": "x", "newText": "y"}], "t")

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            apply_edits_to_normalized_content(
                "abcdef",
                [
                    {"oldText": "abc", "newText": "1"},
                    {"oldText": "bcd", "newText": "2"},
                ],
                "t",
            )

    def test_no_change_rejected(self):
        with self.assertRaises(ValueError):
            apply_edits_to_normalized_content("abc", [{"oldText": "abc", "newText": "abc"}], "t")

    def test_base_content_unchanged(self):
        """编辑后 base 仍然是原始内容"""
        original = "hello world"
        base, new = apply_edits_to_normalized_content(
            original, [{"oldText": "world", "newText": "there"}], "t"
        )
        self.assertEqual(base, original)


class TestApplyEditsFuzzy(unittest.TestCase):
    """核心回归测试：模糊匹配不损坏未编辑区域"""

    def test_ligatures_preserved_outside_edit(self):
        """Bug 回归：文件中的连字不应被 NFKC 破坏"""
        content = "keep\u2014\ufb01\nedit\u2014target\nkeep\u2014\ufb01\n"
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "edit-target", "newText": "CHANGED"}],
            "t",
        )
        # 未编辑的连字必须保留
        self.assertEqual(new.count("\ufb01"), 2)
        self.assertEqual(new.count("\u2014"), 2)

    def test_smart_quotes_preserved_outside_edit(self):
        content = 'say \u201cHello\u2014World\u201d please'
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "Hello-World", "newText": "Hi"}],
            "t",
        )
        # 外围的智能引号必须保留
        self.assertIn("\u201c", new)
        self.assertIn("\u201d", new)
        # 但编辑区域内的 em dash 应被替换掉
        self.assertEqual(new, 'say \u201cHi\u201d please')

    def test_trailing_whitespace_preserved_outside_edit(self):
        content = "hello   \nworld\n"
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "world", "newText": "EARTH"}],
            "t",
        )
        self.assertEqual(new, "hello   \nEARTH\n")

    def test_fuzzy_on_simple_match_still_exact(self):
        """当精确匹配可用时，不触发模糊路径"""
        content = "hello world"
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "world", "newText": "there"}],
            "t",
        )
        self.assertEqual(new, "hello there")

    def test_complex_unicode_file(self):
        """模拟真实代码文件，包含多种 Unicode 字符"""
        content = (
            '\ufb01le_name = "\u201cvalue\u201d"  # \u2014 comment\n'
            'print(\ufb01le_name)\n'
        )
        # 使用足够唯一的 oldText，确保只匹配第一个 ﬁle_name
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": 'file_name = "', "newText": 'filename = "'}],
            "t",
        )
        self.assertTrue(new.startswith("filename = \""))
        self.assertIn("\u201c", new)  # 智能引号保留
        self.assertIn("\u201d", new)
        self.assertIn("\u2014", new)  # em dash 保留
        self.assertEqual(new.count("\ufb01"), 1)  # print 中的连字保留


# ============================================================================
# generate_diff_string 测试
# ============================================================================

class TestGenerateDiffString(unittest.TestCase):
    def test_simple_change(self):
        result = generate_diff_string("hello\nworld\n", "hello\nthere\n")
        self.assertIn("-", result["diff"])
        self.assertIn("+", result["diff"])
        self.assertIsNotNone(result["first_changed_line"])

    def test_no_change_identical(self):
        """相同内容不会产生 diff"""
        result = generate_diff_string("same", "same")
        # 相同时没有 + 或 - 行
        self.assertNotIn("+", result["diff"])
        self.assertNotIn("-", result["diff"])

    def test_insert_only(self):
        result = generate_diff_string("line1\nline3\n", "line1\nline2\nline3\n")
        self.assertIn("+", result["diff"])

    def test_delete_only(self):
        result = generate_diff_string("line1\nline2\nline3\n", "line1\nline3\n")
        self.assertIn("-", result["diff"])


# ============================================================================
# edit_file 集成测试
# ============================================================================

class TestEditFileIntegration(TempDirMixin, unittest.TestCase):
    def test_basic_edit_to_disk(self):
        path = self.temp_path("basic.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hello world")

        result = edit_file(path, [{"oldText": "world", "newText": "there"}])
        self.assertTrue(result.startswith("[OK]"))

        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello there")

    def test_fuzzy_edit_preserves_unicode_on_disk(self):
        """最关键回归测试：磁盘上的 Unicode 不被损坏"""
        path = self.temp_path("unicode.txt")
        original = "keep\u2014\ufb01\nedit\u2014target\nkeep\u2014\ufb01\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)

        result = edit_file(path, [{"oldText": "edit-target", "newText": "CHANGED"}])
        self.assertTrue(result.startswith("[OK]"))

        with open(path, "r", encoding="utf-8") as f:
            after = f.read()

        self.assertIn("CHANGED", after)
        self.assertEqual(after.count("\ufb01"), 2)
        self.assertEqual(after.count("\u2014"), 2)

    def test_bom_preserved(self):
        path = self.temp_path("bom.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\ufeffhello world")

        result = edit_file(path, [{"oldText": "world", "newText": "there"}])
        self.assertTrue(result.startswith("[OK]"))

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.startswith("\ufeff"))
        self.assertIn("there", content)

    def test_crlf_preserved(self):
        path = self.temp_path("crlf.txt")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("line1\r\nline2\r\nline3\r\n")

        result = edit_file(path, [{"oldText": "line2", "newText": "LINE2"}])
        self.assertTrue(result.startswith("[OK]"))

        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        self.assertIn("\r\n", content)
        self.assertIn("LINE2", content)

    def test_file_not_found(self):
        result = edit_file("/nonexistent/path.txt", [{"oldText": "x", "newText": "y"}])
        self.assertTrue(result.startswith("[ERROR]"))
        self.assertIn("不存在", result)

    def test_missing_parameters(self):
        result = edit_file(None, [{"oldText": "x", "newText": "y"}])
        self.assertTrue(result.startswith("[ERROR]"))

        result = edit_file("test.txt", None)
        self.assertTrue(result.startswith("[ERROR]"))

        result = edit_file("test.txt", [])
        self.assertTrue(result.startswith("[ERROR]"))

    def test_multiple_edits_to_disk(self):
        path = self.temp_path("multi.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("alpha beta gamma")

        result = edit_file(path, [
            {"oldText": "alpha", "newText": "first"},
            {"oldText": "gamma", "newText": "third"},
        ])
        self.assertTrue(result.startswith("[OK]"))

        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "first beta third")


# ============================================================================
# 工具元信息测试
# ============================================================================

class TestEditToolMetadata(unittest.TestCase):
    def test_tool_schema_is_valid(self):
        self.assertIsInstance(EDIT_TOOLS, list)
        self.assertGreater(len(EDIT_TOOLS), 0)
        tool = EDIT_TOOLS[0]
        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["function"]["name"], "edit_file")
        self.assertIn("description", tool["function"])
        self.assertIn("parameters", tool["function"])

        params = tool["function"]["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("path", params["properties"])
        self.assertIn("edits", params["properties"])
        self.assertEqual(params["required"], ["path", "edits"])

    def test_function_mapping(self):
        self.assertIn("edit_file", EDIT_FUNCTIONS)
        self.assertIs(EDIT_FUNCTIONS["edit_file"], edit_file)


# ============================================================================
# 回归测试：模糊匹配不损坏未编辑区域（多场景）
# ============================================================================

class TestFuzzyEditRegression(unittest.TestCase):
    """验证所有模糊规范化变换都不会泄漏到未编辑区域"""

    UNICODE_MARKERS = [
        ("\ufb01", "NFKC ligature ﬁ"),
        ("\u201c", "smart left double quote"),
        ("\u201d", "smart right double quote"),
        ("\u2018", "smart left single quote"),
        ("\u2019", "smart right single quote"),
        ("\u2014", "em dash"),
        ("\u2013", "en dash"),
        ("\u00a0", "non-breaking space"),
        ("\u3000", "ideographic space"),
    ]

    def test_markers_survive_outside_edit_region(self):
        """所有 Unicode 标记字符在编辑区域外必须保留"""
        for char, desc in self.UNICODE_MARKERS:
            with self.subTest(char=desc):
                # 构建：前后各放一个标记字符，中间是可编辑目标
                content = f"before{char} TARGET after{char}"
                base, new = apply_edits_to_normalized_content(
                    content,
                    [{"oldText": "TARGET", "newText": "REPLACED"}],
                    "t",
                )
                self.assertIn(char, new, f"{desc} ({repr(char)}) was corrupted!")
                self.assertEqual(new.count(char), 2,
                                 f"{desc} count mismatch: expected 2, got {new.count(char)}")

    def test_ascii_vs_unicode_dash_separation(self):
        """编辑 ASCII 连字符的区域不应影响 Unicode 破折号"""
        content = "\u2014 keep \u2014\nedit-me\n\u2014 keep \u2014\n"
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "edit-me", "newText": "CHANGED"}],
            "t",
        )
        self.assertEqual(new.count("\u2014"), 4)


# ============================================================================
# 压力测试
# ============================================================================

class TestEditStress(TempDirMixin, unittest.TestCase):
    def test_many_unicode_markers(self):
        """文件中散布大量 Unicode 标记字符"""
        markers = "\ufb01\u201c\u201d\u2014\u2013\u00a0\u3000"
        content = ""
        for i in range(100):
            content += f"line{i}: {markers} target{i} {markers}\n"

        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "target50", "newText": "REPLACED50"}],
            "t",
        )
        # 所有 marker 字符总数应保持不变（只有一个 target 被替换）
        for ch in markers:
            self.assertEqual(new.count(ch), content.count(ch),
                             f"Marker {repr(ch)} count changed!")

    def test_deeply_nested_unicode(self):
        """层层嵌套的 Unicode 结构"""
        content = (
            "\ufb01(\u201c\u2014\u2018\u3000\u2019\u2014\u201d)\ufb01\n"
            "EDIT_HERE\n"
            "\ufb01(\u201c\u2014\u2018\u3000\u2019\u2014\u201d)\ufb01\n"
        )
        base, new = apply_edits_to_normalized_content(
            content,
            [{"oldText": "EDIT_HERE", "newText": "DONE"}],
            "t",
        )
        # 上下两行必须完全一致（除编辑行）
        lines = new.split("\n")
        self.assertEqual(lines[0], lines[2])


if __name__ == "__main__":
    unittest.main()
