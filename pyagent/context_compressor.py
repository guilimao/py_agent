import json
from typing import List, Dict, Any


class ContextCompressor:
    """上下文压缩器，用于压缩对话历史以节省token"""
    
    def __init__(self, keep_recent_rounds: int = 10):
        """
        初始化压缩器
        :param keep_recent_rounds: 保留最近几轮的完整信息
        """
        self.keep_recent_rounds = keep_recent_rounds
    
    def compress_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        压缩对话上下文
        1. 将十轮之前的工具调用记录的参数信息改为"略"
        2. 将十轮之前工具调用的结果信息缩短，只保留前100个字符
        """
        if len(messages) <= 10:
            return messages
        
        # 分离系统消息和用户对话消息
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        conversation_messages = [msg for msg in messages if msg.get("role") != "system"]
        
        if len(conversation_messages) <= 10:
            return messages
        
        compressed_messages = system_messages.copy()
        
        # 分析对话轮次（只针对用户消息）
        round_boundaries = self._identify_rounds(conversation_messages)
        
        # 处理对话消息
        for i, msg in enumerate(conversation_messages):
            # 确定当前消息属于哪一轮
            round_index = self._get_round_index(i, round_boundaries)
            
            # 保留最近keep_recent_rounds轮的完整信息
            if round_index >= len(round_boundaries) - self.keep_recent_rounds - 1:
                compressed_messages.append(msg)
            else:
                # 压缩旧轮次的信息
                compressed_msg = self._compress_message(msg)
                compressed_messages.append(compressed_msg)
        
        return compressed_messages
    
    def _identify_rounds(self, messages: List[Dict[str, Any]]) -> List[int]:
        """识别对话轮次的边界"""
        boundaries = [0]  # 从第一条消息开始
        
        for i, msg in enumerate(messages[1:], 1):
            # 当遇到新的user消息时，认为是新一轮的开始
            if msg.get("role") == "user" and i > 0:
                boundaries.append(i)
        
        # 添加最后一条消息的边界
        if boundaries[-1] < len(messages):
            boundaries.append(len(messages))
            
        return boundaries
    
    def _get_round_index(self, msg_index: int, boundaries: List[int]) -> int:
        """获取消息所在的轮次索引"""
        for i in range(len(boundaries) - 1):
            if boundaries[i] <= msg_index < boundaries[i + 1]:
                return i
        return len(boundaries) - 1
    
    def _compress_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """压缩单条消息"""
        compressed = msg.copy()
        
        # 处理工具调用消息
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            compressed["tool_calls"] = self._compress_tool_calls(msg["tool_calls"])
        
        # 处理工具返回结果消息
        elif msg.get("role") == "tool" and msg.get("content"):
            content = msg["content"]
            if isinstance(content, str):
                if len(content) > 100:
                    compressed["content"] = content[:100] + "..."
            elif isinstance(content, list):
                # 处理content为列表的情况
                compressed_content = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text = item["text"]
                        if len(text) > 100:
                            item["text"] = text[:100] + "..."
                    compressed_content.append(item)
                compressed["content"] = compressed_content
        
        # 处理思考内容（可选压缩）
        if msg.get("thinking") and len(msg["thinking"]) > 200:
            compressed["thinking"] = msg["thinking"][:200] + "..."
        
        return compressed
    
    def _compress_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """压缩工具调用信息"""
        compressed_calls = []
        
        for tool_call in tool_calls:
            compressed_call = tool_call.copy()
            
            if "function" in tool_call:
                function_info = tool_call["function"].copy()
                # 将参数信息改为"略"
                function_info["arguments"] = "略"
                compressed_call["function"] = function_info
            
            compressed_calls.append(compressed_call)
        
        return compressed_calls
    
    def get_compression_stats(self, original_messages: List[Dict[str, Any]], 
                            compressed_messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """获取压缩统计信息"""
        original_str = json.dumps(original_messages, ensure_ascii=False)
        compressed_str = json.dumps(compressed_messages, ensure_ascii=False)
        
        return {
            "original_length": len(original_str),
            "compressed_length": len(compressed_str),
            "saved_chars": len(original_str) - len(compressed_str),
            "compression_ratio": round((len(original_str) - len(compressed_str)) / len(original_str) * 100, 2)
        }