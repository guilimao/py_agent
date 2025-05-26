import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from tools.cmdline import *

class TestCmdline(unittest.TestCase):
    def test_execute_command(self):
        # 测试 execute_command 函数
        result = execute_command("echo Hello")
        self.assertIn("Hello", result)

if __name__ == "__main__":
    unittest.main()