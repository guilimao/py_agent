import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from tools.file_op import *

class TestFileOp(unittest.TestCase):
    def test_read_file(self):
        # 测试 read_file 函数
        content = read_file("example.txt")
        self.assertIsNotNone(content)

    def test_create_file(self):
        # 测试 create_file 函数
        create_file("test_file.txt", "Test content")
        content = read_file("test_file.txt")
        self.assertEqual(content, "Test content")

    def test_delete_file(self):
        # 测试 delete_file 函数
        create_file("temp_file.txt", "Temp content")
        delete_file("temp_file.txt")
        # 验证文件是否被删除
        with self.assertRaises(FileNotFoundError):
            read_file("temp_file.txt")

if __name__ == "__main__":
    unittest.main()