from typing import Tuple
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
import os
import sys
from .image_handler import ImageHandler


def sanitize_unicode(text: str) -> str:
    """
    清理字符串中的 surrogate 字符，防止后续 UTF-8 编码崩溃。

    Windows 控制台 / prompt_toolkit 可能返回包含孤立 surrogate
    （U+D800..U+DFFF）的字符串，这些字符无法被 UTF-8 编码，
    会在 json.dumps / sys.stdout.write / HTTP 请求序列化时引发
    UnicodeEncodeError。

    - 配对的 surrogate 对 → 重组为正确的 Unicode 码点（如 U+2C62B）
    - 孤立的 surrogate → 替换为 U+FFFD（Unicode 替换字符）
    """
    if not text:
        return text
    # 快速路径：不包含 surrogate 的字符串直接返回
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text
    try:
        # surrogatepass 允许 surrogate 通过编码阶段；
        # utf-16 解码时会将配对的代理对自动组合为正确的码点
        return text.encode('utf-16', errors='surrogatepass').decode('utf-16')
    except UnicodeDecodeError:
        # 存在孤立代理（无法配对的 surrogate），回退到 replace 策略
        return text.encode('utf-8', errors='replace').decode('utf-8')


def get_multiline_input() -> Tuple[str, bool]:
    """获取多行用户输入（使用Ctrl+Enter提交）"""
    try:
        # 创建自定义键绑定
        bindings = KeyBindings()

        # 绑定Ctrl+Enter为提交事件
        @bindings.add('c-\\')
        def _handle_ctrl_enter(event):
            event.current_buffer.validate_and_handle()

        # 禁用上下键加载历史记录（覆盖默认行为）
        @bindings.add('up')
        def _ignore_up(event):
            event.current_buffer.cursor_up()

        @bindings.add('down')
        def _ignore_down(event):
            event.current_buffer.cursor_down()

        # 创建多行输入会话
        session = PromptSession(
            multiline=True,
            prompt_continuation=lambda width, lineno, is_soft_wrap: '',
            key_bindings=bindings
        )

        print("\n\033[36m输入内容 (Ctrl+\\ 发送，ENTER换行，拖曳添加图像):\033[0m")
        text = session.prompt('')

        # 清理 surrogate 字符，防止后续 UTF-8/JSON 编码崩溃
        text = sanitize_unicode(text)

        return text, True

    except KeyboardInterrupt:
        print("\033[2K\r", end='')
        return "", False
    except Exception as e:
        print(f"\n\033[91m输入错误: {e}\033[0m")
        return "", False