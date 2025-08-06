# frontends/commandline.py
"""
命令行前端实现
"""
import sys
from typing import Tuple
from .base import FrontendInterface
from .commandline_input import get_multiline_input

class CommandlineFrontend(FrontendInterface):
    """
    命令行前端实现类
    """
    def __init__(self):
        self.thinking_mode = False
        
    def get_input(self) -> Tuple[str, bool]:
        """
        获取多行用户输入
        """
        return get_multiline_input()
    
    def output(self, message_type: str, content: str, **kwargs) -> None:
        """
        根据消息类型输出到控制台
        """
        # 思考过程 - 灰色
        if message_type == "thinking":
            if not self.thinking_mode:
                print("\n\033[90m思考过程：", end="")
                self.thinking_mode = True
            sys.stdout.write(content)
            sys.stdout.flush()
        
        # 自然语言内容 - 默认颜色
        elif message_type == "content":
            if self.thinking_mode:
                print("\n\033[0m", end="")  # 结束思考模式
                self.thinking_mode = False
            sys.stdout.write(content)
            sys.stdout.flush()
        
        # 工具调用 - 蓝色
        elif message_type == "tool_call":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\n\033[94m检测到工具调用：{content}\033[0m")
        
        # 工具调用进度 - 黄色
        elif message_type == "tool_progress":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            sys.stdout.write('\033[93m' + content + '\033[0m')
            sys.stdout.flush()
        
        # 工具结果 - 绿色
        elif message_type == "tool_result":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\n\033[92m{content}\033[0m")
            if "result" in kwargs:
                print(f"\033[90m工具返回结果：{kwargs['result']}\033[0m")
        
        # 错误信息 - 红色
        elif message_type == "error":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\n\033[91m{content}\033[0m")
        
        # 用户输入token信息 - 品红色
        elif message_type == "user_input_tokens":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\n\033[95m{content}\033[0m\n")
        
        # 轮次token统计 - 品红色
        elif message_type == "round_tokens":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\n\n\033[95m{content}\033[0m")
        
        # 总token统计摘要 - 品红色
        elif message_type == "token_summary":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\033[95m{content}\033[0m")
        
        # 结束信息 - 品红色
        elif message_type == "end":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(f"\n\033[95m{content}\033[0m")
        
        # 常规信息
        elif message_type == "info":
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            # 为token信息添加特殊格式
            if "tokens:" in content or "token" in content.lower():
                print(f"\n\033[96m{content}\033[0m")  # 青色高亮显示token信息
            else:
                print(content)
        
        # 默认输出
        else:
            if self.thinking_mode:
                print("\033[0m", end="")  # 确保重置颜色
                self.thinking_mode = False
            print(content)
    
    def end_session(self) -> None:
        """结束会话时重置终端颜色"""
        if self.thinking_mode:
            print("\033[0m", end="")  # 确保重置颜色
            self.thinking_mode = False
        print("\033[0m")  # 确保重置终端颜色