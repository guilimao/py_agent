# frontends/commandline.py
"""
命令行前端实现
"""
import sys
from typing import Tuple
from .base import FrontendInterface

class CommandlineFrontend(FrontendInterface):
    """
    命令行前端实现类
    """
    def __init__(self):
        self.thinking_mode = False
        
    def get_input(self) -> Tuple[str, bool]:
        """
        获取命令行用户输入
        """
        try:
            line = input("\n用户输入：").strip()
            return line, True
        except (EOFError, KeyboardInterrupt):
            return "", False
    
    def output(self, message_type: str, content: str, **kwargs) -> None:
        """
        根据消息类型输出到控制台
        """
        # 思考过程 - 灰色
        if message_type == "thinking":
            if not self.thinking_mode:
                print("\n\033[90m思考过程：")
                self.thinking_mode = True
            sys.stdout.write(content)
            sys.stdout.flush()
        
        # 自然语言内容 - 默认颜色
        elif message_type == "content":
            if self.thinking_mode:
                print("\033[0m")  # 结束思考模式
                self.thinking_mode = False
            sys.stdout.write(content)
            sys.stdout.flush()
        
        # 工具调用 - 蓝色
        elif message_type == "tool_call":
            print(f"\n\033[94m检测到工具调用：{content}\033[0m")
        
        # 工具结果 - 绿色
        elif message_type == "tool_result":
            print(f"\n\033[92m{content}\033[0m")
            if "result" in kwargs:
                print(f"\033[90m工具返回结果：{kwargs['result']}\033[0m")
        
        # 错误信息 - 红色
        elif message_type == "error":
            print(f"\n\033[91m{content}\033[0m")
        
        # 常规信息
        elif message_type == "info":
            print(content)
        
        # 默认输出
        else:
            print(content)
    
    def end_session(self) -> None:
        """结束会话时重置终端颜色"""
        print("\033[0m")  # 确保重置终端颜色