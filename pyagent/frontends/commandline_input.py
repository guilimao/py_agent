from typing import Tuple
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
import os
import sys
from .image_handler import ImageHandler

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
            prompt_continuation=lambda width, lineno, is_soft_wrap: '> ',
            key_bindings=bindings
        )

        print("\n\033[36m输入内容 (Ctrl+\\ 发送，ENTER换行):\033[0m")
        print("\033[33m提示：可以直接拖拽图像文件到命令行，或输入图像文件路径\033[0m")
        text = session.prompt('> ')

        return text, True

    except KeyboardInterrupt:
        print("\033[2K\r", end='')
        return "", False
    except Exception as e:
        print(f"\n\033[91m输入错误: {e}\033[0m")
        return "", False