"""
write_file 工具的综合测试套件。

覆盖场景：
- 基本功能（创建、覆盖、目录自动创建、路径展开）
- 边界情况（空内容、None、Unicode、长文本）
- 错误处理（权限、中断、OS 错误）
- 并发安全（同一文件串行化、不同文件并行）
- 长文本可靠性（1MB、10MB、超长行、特殊字符）

运行方式：
    python -m pytest tests/test_file_write.py -v
    或
    python -m unittest tests.test_file_write -v
"""

import os
import sys
import tempfile
import threading
import time
import unittest

# 确保 pyagent 包可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyagent.tools.file_write import (
    write_file,
    _resolve_path,
    _normalize_unicode_spaces,
    _get_file_lock,
    _with_file_mutation_queue,
)


# ============================================================================
# 测试辅助工具
# ============================================================================

class TempDirMixin:
    """为测试提供临时目录的 mixin。"""

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(prefix="write_file_test_")
        self.temp_root = self._temp_dir.name

    def tearDown(self):
        self._temp_dir.cleanup()

    def temp_path(self, relpath: str) -> str:
        """获取临时目录下的绝对路径。"""
        return os.path.join(self.temp_root, relpath)


class AbortSignal:
    """模拟中断信号对象。"""
    def __init__(self, aborted=False):
        self.aborted = aborted


# ============================================================================
# 路径解析测试
# ============================================================================

class TestResolvePath(unittest.TestCase):

    def test_expand_user_home(self):
        """~ 应展开为用户主目录。"""
        result = _resolve_path("~/test.txt")
        self.assertTrue(result.startswith(os.path.expanduser("~")))
        self.assertTrue(result.endswith("test.txt"))

    def test_relative_to_absolute(self):
        """相对路径应转为基于当前工作目录的绝对路径。"""
        result = _resolve_path("foo/bar.txt")
        self.assertTrue(os.path.isabs(result))
        self.assertTrue(result.endswith(os.path.join("foo", "bar.txt")))

    def test_strip_at_prefix(self):
        """应去除 @ 前缀。"""
        result = _resolve_path("@/home/user/file.txt")
        self.assertFalse("@/" in result)

    def test_unicode_spaces_normalized(self):
        """Unicode 特殊空格应被规范化为普通空格。"""
        result = _resolve_path("foo\u00A0bar.txt")
        self.assertNotIn("\u00A0", result)
        self.assertIn("foo bar.txt", result)

    def test_empty_path_returns_empty(self):
        """空路径应返回空字符串。"""
        self.assertEqual(_resolve_path(""), "")
        self.assertEqual(_resolve_path(None), None)

    def test_preserves_absolute_path(self):
        """已是绝对路径应保持不变（展开 ~ 除外）。"""
        if sys.platform == "win32":
            abs_path = "C:\\absolute\\path.txt"
        else:
            abs_path = "/absolute/path.txt"
        result = _resolve_path(abs_path)
        self.assertEqual(os.path.normpath(result), os.path.normpath(os.path.abspath(abs_path)))


class TestNormalizeUnicodeSpaces(unittest.TestCase):

    def test_no_break_space(self):
        self.assertEqual(_normalize_unicode_spaces("hello\u00A0world"), "hello world")

    def test_ideographic_space(self):
        self.assertEqual(_normalize_unicode_spaces("hello\u3000world"), "hello world")

    def test_multiple_unicode_spaces(self):
        text = "a\u2000b\u2001c\u2002d"
        result = _normalize_unicode_spaces(text)
        self.assertEqual(result, "a b c d")

    def test_no_change_for_normal_text(self):
        text = "hello world"
        self.assertEqual(_normalize_unicode_spaces(text), text)


# ============================================================================
# 文件锁和队列测试
# ============================================================================

class TestFileLocks(unittest.TestCase):

    def test_same_path_same_lock(self):
        """同一路径应返回相同的锁对象。"""
        lock1 = _get_file_lock("/tmp/test.txt")
        lock2 = _get_file_lock("/tmp/test.txt")
        self.assertIs(lock1, lock2)

    def test_different_paths_different_locks(self):
        """不同路径应返回不同的锁对象。"""
        lock1 = _get_file_lock("/tmp/a.txt")
        lock2 = _get_file_lock("/tmp/b.txt")
        self.assertIsNot(lock1, lock2)

    def test_lock_is_actual_lock(self):
        """返回的对象应为 threading.Lock 实例。"""
        lock = _get_file_lock("/tmp/test.txt")
        self.assertIsInstance(lock, threading.Lock)
        self.assertTrue(lock.acquire(blocking=False))
        lock.release()


class TestFileMutationQueue(unittest.TestCase):

    def test_executes_function_and_returns_result(self):
        """应执行传入的函数并返回其结果。"""
        result = _with_file_mutation_queue("/tmp/test.txt", lambda: 42)
        self.assertEqual(result, 42)

    def test_checks_signal_before_execution(self):
        """如果信号已标记为中断，应抛出 InterruptedError。"""
        signal = AbortSignal(aborted=True)
        with self.assertRaises(InterruptedError):
            _with_file_mutation_queue("/tmp/test.txt", lambda: "ok", signal)

    def test_passes_when_signal_not_aborted(self):
        """信号未中断时应正常执行。"""
        signal = AbortSignal(aborted=False)
        result = _with_file_mutation_queue("/tmp/test.txt", lambda: "ok", signal)
        self.assertEqual(result, "ok")


# ============================================================================
# 基本功能测试（需要临时目录）
# ============================================================================

class TestWriteFileBasic(TempDirMixin, unittest.TestCase):

    def test_write_new_file(self):
        """写入一个不存在的文件应成功创建。"""
        path = self.temp_path("new_file.txt")
        result = write_file(path=path, content="Hello, World!")
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Hello, World!")

    def test_overwrite_existing_file(self):
        """覆盖已存在的文件。"""
        path = self.temp_path("existing.txt")
        # 先创建文件
        write_file(path=path, content="original")
        # 再覆盖
        result = write_file(path=path, content="overwritten")
        self.assertIn("Successfully wrote", result)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "overwritten")

    def test_create_parent_directories(self):
        """如果父目录不存在，应自动递归创建。"""
        path = self.temp_path("a/b/c/d/file.txt")
        result = write_file(path=path, content="nested")
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.isdir(self.temp_path("a/b/c/d")))

    def test_write_empty_content(self):
        """写入空字符串应创建空文件。"""
        path = self.temp_path("empty.txt")
        result = write_file(path=path, content="")
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.path.getsize(path), 0)

    def test_write_none_content_defaults_to_empty(self):
        """content=None 应默认为空字符串。"""
        path = self.temp_path("none_content.txt")
        result = write_file(path=path, content=None)
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.path.getsize(path), 0)

    def test_expand_tilde(self):
        """路径中的 ~ 应被展开。"""
        # 使用 expanduser 手动展开，确认行为一致
        path = "~/pyagent_test_expand_tilde_temp.txt"
        result = write_file(path=path, content="tilde test")
        self.assertIn("Successfully wrote", result)
        expanded = os.path.expanduser(path)
        self.assertTrue(os.path.isfile(expanded))
        # 清理
        os.remove(expanded)

    def test_unicode_content(self):
        """应正确写入 Unicode 内容。"""
        path = self.temp_path("unicode.txt")
        content = "你好世界 🌍\nこんにちは\n🎉 Unicode test: àéîöü"
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_byte_count_in_result(self):
        """返回消息应包含正确的字节数。"""
        path = self.temp_path("count.txt")
        content = "你好"  # 6 bytes in UTF-8
        result = write_file(path=path, content=content)
        self.assertIn("6 bytes", result)

    def test_relative_path(self):
        """相对路径应能正常工作。"""
        orig_cwd = os.getcwd()
        try:
            os.chdir(self.temp_root)
            result = write_file(path="relative.txt", content="relative")
            self.assertIn("Successfully wrote", result)
            self.assertTrue(os.path.isfile(os.path.join(self.temp_root, "relative.txt")))
        finally:
            os.chdir(orig_cwd)


# ============================================================================
# 错误处理测试
# ============================================================================

class TestWriteFileErrors(TempDirMixin, unittest.TestCase):

    def test_missing_path_returns_error(self):
        """缺少 path 参数应返回错误。"""
        result = write_file(path=None, content="test")
        self.assertIn("[ERROR] write_file: path is required", result)

    def test_empty_path_returns_error(self):
        """空字符串 path 应返回错误。"""
        result = write_file(path="", content="test")
        self.assertIn("[ERROR] write_file: path is required", result)

    def test_permission_error_readonly_directory(self):
        """写入只读目录下的文件应返回权限错误。"""
        if sys.platform == "win32":
            self.skipTest("Windows 权限模型不同，单独测试")

        # 创建只读目录
        ro_dir = self.temp_path("readonly_dir")
        os.makedirs(ro_dir)
        os.chmod(ro_dir, 0o444)  # 只读

        try:
            path = os.path.join(ro_dir, "test.txt")
            result = write_file(path=path, content="test")
            self.assertIn("permission denied", result.lower())
        finally:
            os.chmod(ro_dir, 0o755)

    def test_interrupted_signal(self):
        """中断信号应导致操作中止。"""
        signal = AbortSignal(aborted=True)
        path = self.temp_path("aborted.txt")
        result = write_file(path=path, content="test", signal=signal)
        self.assertIn("[ERROR] write_file: operation aborted", result)
        self.assertFalse(os.path.isfile(path))

    def test_os_error_is_captured(self):
        """OSError 应被捕获并返回错误消息。"""
        # 尝试写入一个路径中包含空字符的文件（在 POSIX 上会触发 OSError）
        # 但跨平台，我们使用一个非常长的路径
        very_long_name = "x" * 300
        path = self.temp_path(very_long_name)
        result = write_file(path=path, content="test")
        # Windows 路径限制较严，POSIX 更宽松，所以检查两种情况
        if "[ERROR]" in result:
            self.assertTrue(
                "write_file:" in result or "write_file" in result
            )


# ============================================================================
# 并发安全测试
# ============================================================================

class TestWriteFileConcurrency(TempDirMixin, unittest.TestCase):

    def test_concurrent_writes_to_same_file_serialized(self):
        """并发写入同一文件应串行化，不会出现数据损坏。"""
        path = self.temp_path("concurrent_same.txt")
        thread_count = 10
        results = []
        errors = []

        def writer(idx):
            try:
                content = f"thread-{idx}\n"
                # 每个线程写入后稍作停顿，增加交错概率
                time.sleep(0.001 * (idx % 3))
                r = write_file(path=path, content=content)
                results.append((idx, r))
            except Exception as e:
                errors.append((idx, str(e)))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")

        # 验证文件存在且内容完整（最后写入者胜出）
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.startswith("thread-"))
        self.assertTrue(content.endswith("\n"))

    def test_concurrent_writes_to_different_files_parallel(self):
        """并发写入不同文件应并行进行。"""
        thread_count = 10
        results = []
        errors = []
        start_barrier = threading.Barrier(thread_count)

        def writer(idx):
            try:
                path = self.temp_path(f"concurrent_diff_{idx}.txt")
                start_barrier.wait()  # 确保所有线程同时开始
                r = write_file(path=path, content=f"content-{idx}")
                results.append((idx, r))
            except Exception as e:
                errors.append((idx, str(e)))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(results), thread_count)

        # 验证所有文件都正确创建
        for i in range(thread_count):
            path = self.temp_path(f"concurrent_diff_{i}.txt")
            self.assertTrue(os.path.isfile(path))
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), f"content-{i}")


# ============================================================================
# 长文本可靠性测试
# ============================================================================

class TestWriteFileLongContent(TempDirMixin, unittest.TestCase):
    """重点测试长文本写入的可靠性。"""

    # ---------- 中等长度 ----------

    def test_write_100kb_text(self):
        """写入 100KB 文本。"""
        path = self.temp_path("100kb.txt")
        content = "A" * 100_000
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(len(actual), 100_000)
        self.assertEqual(actual, content)

    def test_write_1mb_text(self):
        """写入 1MB 文本。"""
        path = self.temp_path("1mb.txt")
        # 使用可读的重复模式，而非单一字符
        pattern = "The quick brown fox jumps over the lazy dog. 敏捷的棕色狐狸跳过懒狗。\n"
        content = pattern * (1_024 * 1024 // len(pattern))
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(len(actual), len(content))
        self.assertEqual(actual, content)

    def test_write_10mb_text(self):
        """写入 10MB 文本 —— 真正的压力测试。

        使用纯 ASCII 字母（无换行符）以避免 Windows 文本模式 \n → \r\n
        转换干扰字节级验证。
        """
        path = self.temp_path("10mb.txt")
        # 使用纯字母字符，无换行符，确保跨平台字节一致
        chunk = "abcdefghij"  # 10 bytes
        content = chunk * (10 * 1024 * 1024 // len(chunk))

        start = time.time()
        result = write_file(path=path, content=content)
        elapsed = time.time() - start

        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))

        # 验证文件大小（纯 ASCII，无换行符，字节数应精确匹配）
        file_size = os.path.getsize(path)
        expected_size = len(content.encode("utf-8"))
        self.assertEqual(file_size, expected_size,
                         f"Size mismatch: {file_size} vs {expected_size}")
        self.assertGreaterEqual(file_size, 10 * 1024 * 1024)

        # 以二进制模式验证内容采样
        content_bytes = content.encode("utf-8")
        with open(path, "rb") as f:
            # 验证开头
            self.assertEqual(f.read(100), content_bytes[:100])
            # 验证中间
            mid = len(content_bytes) // 2 - 50
            f.seek(mid)
            self.assertEqual(f.read(100), content_bytes[mid:mid + 100])
            # 验证结尾
            f.seek(-100, os.SEEK_END)
            self.assertEqual(f.read(100), content_bytes[-100:])

        print(f"\n10MB write took {elapsed:.3f}s ({file_size / 1024 / 1024:.1f} MB on disk)")

    def test_write_50mb_text(self):
        """写入 50MB 文本 —— 极限压力测试。

        注意：此测试耗时较长，默认跳过。设置 WRITE_FILE_HEAVY=1 环境变量来启用。
        """
        if not os.environ.get("WRITE_FILE_HEAVY"):
            self.skipTest("设置 WRITE_FILE_HEAVY=1 环境变量来启用 50MB 压力测试")

        path = self.temp_path("50mb.txt")
        line = "0123456789" * 10 + "\n"  # 101 chars
        content = line * (50 * 1024 * 1024 // len(line))

        start = time.time()
        result = write_file(path=path, content=content)
        elapsed = time.time() - start

        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        file_size = os.path.getsize(path)
        self.assertEqual(file_size, len(content.encode("utf-8")))
        print(f"\n50MB write took {elapsed:.3f}s ({file_size / 1024 / 1024:.1f} MB)")

    # ---------- 超长行 ----------

    def test_single_very_long_line(self):
        """写入只有一行的超长文本（不包含换行符）。"""
        path = self.temp_path("long_line.txt")
        content = "X" * 1_000_000  # 1MB 单行
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(len(actual), 1_000_000)
        self.assertEqual(actual, content)
        # 确认只有一行
        self.assertNotIn("\n", actual)

    def test_single_line_10mb(self):
        """写入 10MB 单行文本。"""
        if not os.environ.get("WRITE_FILE_HEAVY"):
            self.skipTest("设置 WRITE_FILE_HEAVY=1 环境变量来启用 10MB 单行测试")

        path = self.temp_path("long_line_10mb.txt")
        content = "Y" * (10 * 1024 * 1024)
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.path.getsize(path), len(content.encode("utf-8")))

    # ---------- 特殊字符组合 ----------

    def test_all_unicode_planes(self):
        """写入包含多个 Unicode 平面的内容。"""
        path = self.temp_path("unicode_planes.txt")
        # BMP、补充多语言平面、补充表意文字平面等
        content = (
            "BMP: \u0041\u00E9\u4E16\u754C\n"          # A, é, 世界
            "SMP: \U0001F600\U0001F4A9\U0001F3B5\n"     # 😀💩🎵
            "SIP: \U00020000\U00020001\n"               # CJK Extension B
            "SSP: \U000E0001\n"                         # Language Tag
            "Combining: A\u0308\u0302\u0327\n"          # Ä with circumflex and cedilla
            "RTL: \u05D0\u05D1\u05D2\n"                # Hebrew
            "Zero-width: x\u200Bx\u200Cx\u200Dx\n"      # zero-width spaces
        )
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        with open(path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(actual, content)

    def test_binary_like_control_characters(self):
        """写入包含控制字符的文本（除 \0 外）。

        注意：write_file 在文本模式下写入，Windows 上 \n → \r\n。
        因此通过二进制模式读取来验证精确内容。
        """
        path = self.temp_path("control_chars.txt")
        # 包含各类控制字符（避免 \r\n 组合，因为文本模式会转换）
        parts = [
            "start\n",
            "\t tab",
            "\x01\x02\x03 SOH STX ETX",
            "\x1b ESC",
            "\x7f DEL",
            "end\n",
        ]
        content = "".join(parts)
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        # 以二进制模式读取，验证核心数据存在
        with open(path, "rb") as f:
            raw = f.read()
        # 验证关键控制字符以原始字节形式存在
        self.assertIn(b"\x01\x02\x03", raw)
        self.assertIn(b"SOH STX ETX", raw)
        self.assertIn(b"\x1b", raw)
        self.assertIn(b"ESC", raw)
        self.assertIn(b"\x7f", raw)
        self.assertIn(b"DEL", raw)
        self.assertIn(b"start", raw)
        self.assertIn(b"end", raw)

    def test_null_character_in_content(self):
        """写入包含 NUL (\0) 字符的内容。

        Python 字符串可以包含 \0，但某些文件操作可能受影响。
        """
        path = self.temp_path("null_char.txt")
        content = "before\0after"
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        # 读取回来确认
        with open(path, "rb") as f:
            raw = f.read()
        self.assertIn(b"\x00", raw)

    # ---------- 换行符多样性 ----------

    def test_mixed_line_endings(self):
        """写入包含混合换行符的文本。

        注意：当前 write_file 使用文本模式（无 newline=''），
        在 Windows 上 \n 会被转译为 \r\n。因此通过二进制模式
        验证写入确实完成了，同时记录平台行为差异。
        """
        path = self.temp_path("mixed_endings.txt")
        content = "LF\nCRLF\r\nCR\rMixed\nAgain\r\nDone\n"
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)

        # 二进制验证：文件不为空且可读
        with open(path, "rb") as f:
            raw = f.read()
        self.assertGreater(len(raw), 0)
        # 验证核心文本片段存在
        self.assertIn(b"LF", raw)
        self.assertIn(b"CRLF", raw)
        self.assertIn(b"Mixed", raw)
        self.assertIn(b"Again", raw)
        self.assertIn(b"Done", raw)

        # 记录平台行为
        if sys.platform == "win32":
            print(f"\n[INFO] Windows text-mode: \\n in content is translated to \\r\\n on disk")

    def test_windows_style_line_endings(self):
        """写入纯 CRLF 换行符的文本。

        以二进制模式验证写入，避免文本模式读取时的换行符转换。
        """
        path = self.temp_path("crlf.txt")
        lines = ["line1", "line2", "line3", "line4", "line5"]
        content = "\r\n".join(lines)
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        # 二进制读取验证
        with open(path, "rb") as f:
            raw = f.read()
        # 验证所有行都存在
        for line in lines:
            self.assertIn(line.encode("utf-8"), raw)
        # 验证 CRLF 分隔符存在
        self.assertIn(b"\r\n", raw)
        # 验证没有孤立的 \r（即 \r 后总跟 \n 或 \r 之前已是 \n 清况下的 CR）
        # 在 Windows 文本模式下，\n 会被转译，所以可能有额外的 \r
        # 这里仅验证核心内容完整性
        self.assertEqual(raw.split(b"\n")[-1], b"line5")

    # ---------- 大量行 ----------

    def test_many_small_lines(self):
        """写入大量短行。"""
        path = self.temp_path("many_lines.txt")
        lines = [f"line_{i:06d}" for i in range(100_000)]
        content = "\n".join(lines)
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        with open(path, "r", encoding="utf-8") as f:
            actual_lines = f.read().splitlines()
        self.assertEqual(len(actual_lines), 100_000)
        self.assertEqual(actual_lines[0], "line_000000")
        self.assertEqual(actual_lines[-1], "line_099999")

    # ---------- 边界条件 ----------

    def test_exactly_one_byte(self):
        """恰好一个字节的内容。"""
        path = self.temp_path("one_byte.txt")
        result = write_file(path=path, content="A")
        self.assertIn("1 bytes", result)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "A")

    def test_multibyte_boundary(self):
        """内容长度在 UTF-8 多字节边界处。"""
        path = self.temp_path("boundary.txt")
        # 刚好跨越多种宽度字符边界
        content = "a" * 4095 + "世" + "a" * 4095  # 8191 chars
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_whitespace_only(self):
        """仅有空白字符的内容。

        以二进制模式验证核心特征（空格、制表符、换行符的存在性）。
        """
        path = self.temp_path("whitespace.txt")
        content = " " * 10000 + "\n" + "\t" * 5000 + "\n" + "\r\n" * 1000
        result = write_file(path=path, content=content)
        self.assertIn("Successfully wrote", result)
        with open(path, "rb") as f:
            raw = f.read()
        # 验证数量级正确
        self.assertGreater(len(raw), 16000)
        # 验证存在空格和制表符
        self.assertIn(b" ", raw)
        self.assertIn(b"\t", raw)
        # 存在换行符
        self.assertIn(b"\n", raw)


# ============================================================================
# 工具元信息测试
# ============================================================================

class TestWriteFileToolMetadata(unittest.TestCase):

    def test_tool_schema_is_valid(self):
        """工具元信息应包含必要字段。"""
        from pyagent.tools.file_write import FILE_WRITE_TOOLS

        self.assertIsInstance(FILE_WRITE_TOOLS, list)
        self.assertGreater(len(FILE_WRITE_TOOLS), 0)

        tool = FILE_WRITE_TOOLS[0]
        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["function"]["name"], "write_file")
        self.assertIn("description", tool["function"])
        self.assertIn("parameters", tool["function"])

        params = tool["function"]["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertIn("path", params["properties"])
        self.assertIn("content", params["properties"])
        self.assertEqual(params["required"], ["path", "content"])

    def test_function_mapping(self):
        """工具函数映射应正确指向 write_file。"""
        from pyagent.tools.file_write import FILE_WRITE_FUNCTIONS

        self.assertIn("write_file", FILE_WRITE_FUNCTIONS)
        self.assertIs(FILE_WRITE_FUNCTIONS["write_file"], write_file)


# ============================================================================
# 回归测试：确保不会破坏现有行为
# ============================================================================

class TestWriteFileRegression(TempDirMixin, unittest.TestCase):

    def test_result_format_consistency(self):
        """成功结果的格式应保持一致（以 'Successfully wrote' 开头）。"""
        path = self.temp_path("format.txt")
        result = write_file(path=path, content="test")
        self.assertTrue(result.startswith("Successfully wrote"))

    def test_error_format_consistency(self):
        """错误结果的格式应保持一致（以 '[ERROR]' 开头）。"""
        result = write_file(path=None, content="test")
        self.assertTrue(result.startswith("[ERROR]"))

    def test_write_idempotent(self):
        """重复写入相同内容应是幂等的。"""
        path = self.temp_path("idempotent.txt")
        content = "same content"
        r1 = write_file(path=path, content=content)
        r2 = write_file(path=path, content=content)
        self.assertEqual(r1, r2)  # 同样的路径，同样的字节数
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_overwrite_larger_with_smaller(self):
        """用较小内容覆盖较大文件应正确截断。"""
        path = self.temp_path("shrink.txt")
        large = "X" * 10000
        small = "Y"
        write_file(path=path, content=large)
        write_file(path=path, content=small)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), small)
        self.assertEqual(os.path.getsize(path), 1)

    def test_overwrite_smaller_with_larger(self):
        """用较大内容覆盖较小文件。"""
        path = self.temp_path("grow.txt")
        small = "a"
        large = "B" * 100000
        write_file(path=path, content=small)
        write_file(path=path, content=large)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), large)

    def test_unicode_path(self):
        """路径中包含 Unicode 字符。"""
        path = self.temp_path("中文目录/файл.txt")
        result = write_file(path=path, content="unicode path test")
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.isfile(path))


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    unittest.main()
