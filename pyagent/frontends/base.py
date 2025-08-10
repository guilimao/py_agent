# frontends/base.py
"""
前端基础接口定义
"""

class FrontendInterface:
    """
    前端抽象基类，定义适配不同前端所需的接口
    """
    def get_input(self) -> tuple[str, bool]:
        """
        获取用户输入
        
        Returns:
            tuple: (用户输入内容, 是否有有效输入)
        """
        raise NotImplementedError
    
    def output(self, message_type: str, content: str, **kwargs) -> None:
        """
        输出内容到前端
        
        Args:
            message_type: 消息类型（如 'thinking', 'content', 'tool_call', 'end'）
            content: 要输出的内容
            kwargs: 其他类型相关参数
        """
        raise NotImplementedError
    
    def start_session(self) -> None:
        """开始一个新的会话"""
        pass
    
    def end_session(self) -> None:
        """结束当前会话"""
        pass