import subprocess
import unittest
from unittest.mock import MagicMock, patch

from pyagent.tools import cmdline


class CmdlineTests(unittest.TestCase):
    def test_build_command_uses_git_bash_on_windows(self):
        with patch.object(cmdline.os, "name", "nt"), patch.object(
            cmdline, "_find_git_bash", return_value=r"C:\Program Files\Git\bin\bash.exe"
        ):
            popen_kwargs = cmdline._build_command("echo hello")

        self.assertEqual(
            popen_kwargs["args"],
            [r"C:\Program Files\Git\bin\bash.exe", "-lc", "echo hello"],
        )
        self.assertEqual(
            popen_kwargs["creationflags"],
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    def test_execute_command_returns_error_when_git_bash_missing(self):
        with patch.object(cmdline.os, "name", "nt"), patch.object(
            cmdline, "_find_git_bash", side_effect=FileNotFoundError("missing git bash")
        ):
            result = cmdline.execute_command("echo hello")

        self.assertIn("missing git bash", result)

    def test_execute_command_basic_execution(self):
        """基本命令执行测试。"""
        result = cmdline.execute_command("echo hello")
        self.assertIsInstance(result, str)
        self.assertIn("hello", result)
        self.assertIn("终端", result)
        self.assertIn("执行完毕", result)

    def test_execute_command_with_timeout(self):
        """超时测试：长时间命令应被终止。"""
        result = cmdline.execute_command("sleep 10", timeout=1)
        self.assertIsInstance(result, str)
        self.assertIn("超时", result)

    def test_truncate_tail_no_truncation_needed(self):
        """内容在限制内时不应截断。"""
        content = "line1\nline2\nline3"
        result = cmdline.truncate_tail(content, max_lines=100, max_bytes=50000)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["content"], content)

    def test_truncate_tail_by_lines(self):
        """行数超限时应截断并保留尾部。"""
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = cmdline.truncate_tail(content, max_lines=10, max_bytes=50000)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "lines")
        self.assertEqual(result["output_lines"], 10)
        # 应该保留最后10行
        self.assertIn("line 90", result["content"])
        self.assertIn("line 99", result["content"])

    def test_truncate_tail_by_bytes(self):
        """字节数超限时应截断。"""
        content = "x" * 100000  # 约 100KB
        result = cmdline.truncate_tail(content, max_lines=2000, max_bytes=1000)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncated_by"], "bytes")

    def test_format_size(self):
        """字节格式化测试。"""
        self.assertEqual(cmdline.format_size(100), "100B")
        self.assertEqual(cmdline.format_size(2048), "2.0KB")
        self.assertEqual(cmdline.format_size(1024 * 1024), "1.0MB")

    def test_output_accumulator_basic(self):
        """输出累加器基本功能测试。"""
        acc = cmdline.OutputAccumulator(max_lines=1000, max_bytes=50000)
        acc.append(b"Hello World\n")
        acc.append(b"Second line\n")
        acc.finish()

        snapshot = acc.snapshot()
        self.assertIn("Hello World", snapshot["content"])
        self.assertIn("Second line", snapshot["content"])
        self.assertFalse(snapshot["truncation"]["truncated"])
        acc.close_temp_file()

    def test_output_accumulator_truncation(self):
        """输出累加器截断测试。"""
        acc = cmdline.OutputAccumulator(max_lines=10, max_bytes=50000)
        for i in range(100):
            acc.append(f"line {i:04d}\n".encode())
        acc.finish()

        snapshot = acc.snapshot()
        self.assertTrue(snapshot["truncation"]["truncated"])
        self.assertEqual(snapshot["truncation"]["output_lines"], 10)
        acc.close_temp_file()

    def test_output_accumulator_temp_file(self):
        """输出累加器临时文件测试。"""
        acc = cmdline.OutputAccumulator(max_lines=10, max_bytes=500)
        # 写入足够多的数据触发临时文件
        for i in range(200):
            acc.append(f"line {i:04d} with some extra padding\n".encode())
        acc.finish()

        snapshot = acc.snapshot(persist_if_truncated=True)
        self.assertTrue(snapshot["truncation"]["truncated"])
        self.assertIsNotNone(snapshot["full_output_path"])
        self.assertIsNotNone(acc.temp_file_path)

        import os
        self.assertTrue(os.path.exists(acc.temp_file_path))
        acc.close_temp_file()
        # 清理
        if acc.temp_file_path and os.path.exists(acc.temp_file_path):
            os.unlink(acc.temp_file_path)


if __name__ == "__main__":
    unittest.main()
