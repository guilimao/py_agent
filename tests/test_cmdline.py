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

    def test_timeout_kills_process_tree_on_windows(self):
        process = MagicMock()
        process.pid = 4321
        process.poll.side_effect = [None, 0]
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="cmd", timeout=1),
            (b"partial output", None),
        ]
        process.stdout = MagicMock()

        with patch.object(cmdline.os, "name", "nt"), patch.object(
            cmdline, "_build_command", return_value={"args": ["bash.exe", "-lc", "sleep 5"]}
        ), patch.object(cmdline.subprocess, "Popen", return_value=process), patch.object(
            cmdline.subprocess, "run"
        ) as run_mock:
            result = cmdline.execute_command("sleep 5", timeout=1)

        self.assertIn("命令超时", result)
        run_mock.assert_called_once_with(
            ["taskkill", "/F", "/T", "/PID", "4321"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        process.stdout.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
