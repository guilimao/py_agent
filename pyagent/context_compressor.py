import json
from typing import List, Dict, Any


class ContextCompressor:
    """上下文压缩器占位符，不再执行压缩功能"""
    
    def __init__(self, keep_recent_rounds: int = 10):
        """
        初始化压缩器（现为占位符）
        :param keep_recent_rounds: 保留最近几轮的完整信息（参数保留但不再使用）
        """
        self.keep_recent_rounds = keep_recent_rounds
    
    def compress_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        不再压缩对话上下文，直接返回原始消息
        """
        return messages
    
    def get_compression_stats(self, original_messages: List[Dict[str, Any]], 
                            compressed_messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """获取压缩统计信息（始终返回无压缩数据）"""
        return {
            "original_length": 0,
            "compressed_length": 0,
            "saved_chars": 0,
            "compression_ratio": 0.0
        }