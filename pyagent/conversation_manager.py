"""
对话管理器 - 统一处理对话状态和消息管理
"""
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class MessageRole(Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """统一的消息格式"""
    role: MessageRole
    content: Optional[str] = None
    content_parts: Optional[List[Dict[str, Any]]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    thinking: Optional[str] = None
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，适配不同SDK"""
        result = {"role": self.role.value}
        
        if self.content_parts:
            result["content"] = self.content_parts
        elif self.content is not None:
            result["content"] = self.content
        
        if self.thinking:
            result["thinking"] = self.thinking
        
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        
        if self.timestamp:
            result["timestamp"] = self.timestamp
            
        return result


@dataclass
class StreamEvent:
    """流式事件"""
    event_type: str  # 'content', 'thinking', 'tool_call', 'finish'
    data: Any
    metadata: Optional[Dict[str, Any]] = None


class ConversationManager:
    """对话管理器 - 统一管理对话状态"""
    
    def __init__(self, system_prompt: str):
        self.messages: List[Message] = []
        self.system_prompt = system_prompt
        self._add_system_message(system_prompt)
    
    def _add_system_message(self, content: str):
        """添加系统消息"""
        self.messages.append(Message(role=MessageRole.SYSTEM, content=content, timestamp=datetime.now().isoformat()))
    
    def add_user_message(self, content: str, content_parts: Optional[List[Dict[str, Any]]] = None):
        """添加用户消息"""
        if content_parts:
            self.messages.append(Message(role=MessageRole.USER, content_parts=content_parts, timestamp=datetime.now().isoformat()))
        else:
            self.messages.append(Message(role=MessageRole.USER, content=content, timestamp=datetime.now().isoformat()))
    
    def add_assistant_message(self, content: str, thinking: Optional[str] = None, 
                            tool_calls: Optional[List[Dict[str, Any]]] = None):
        """添加助手消息"""
        self.messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            timestamp=datetime.now().isoformat()
        ))
    
    def add_tool_result(self, tool_call_id: str, content: str):
        """添加工具结果"""
        self.messages.append(Message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            timestamp=datetime.now().isoformat()
        ))
    
    def get_messages_for_sdk(self) -> List[Dict[str, Any]]:
        """获取适配SDK的消息格式"""
        return [msg.to_dict() for msg in self.messages]
    
    def get_last_message(self) -> Optional[Dict[str, Any]]:
        """获取最后一条消息（用于增量保存）"""
        if not self.messages:
            return None
        return self.messages[-1].to_dict()
    
    def get_system_message(self) -> Optional[Dict[str, Any]]:
        """获取系统消息（用于确保系统提示被保存）"""
        if not self.messages:
            return None
        # 系统消息总是在第一位
        if self.messages[0].role == MessageRole.SYSTEM:
            return self.messages[0].to_dict()
        return None
    
    def get_last_n_messages(self, n: int) -> List[Dict[str, Any]]:
        """获取最后n条消息（用于增量保存）"""
        if not self.messages:
            return []
        start_index = max(0, len(self.messages) - n)
        return [msg.to_dict() for msg in self.messages[start_index:]]
    
    def get_recent_messages(self, count: int) -> List[Message]:
        """获取最近的n条消息"""
        return self.messages[-count:] if len(self.messages) > count else self.messages
    
    def compress_context(self, keep_recent_rounds: int) -> List[Dict[str, Any]]:
        """压缩上下文，保留最近的对话轮次"""
        if keep_recent_rounds <= 0:
            return self.get_messages_for_sdk()
        
        # 保留系统消息和最近的对话轮次
        system_msg = self.messages[0]  # 系统消息总是在第一位
        recent_messages = self.get_recent_messages(keep_recent_rounds * 2)  # 每轮包含用户和助手消息
        
        # 确保系统消息在开头
        compressed = [system_msg]
        
        # 添加不重复的消息
        for msg in recent_messages:
            if msg not in compressed:
                compressed.append(msg)
        
        # 转换为SDK格式
        return [msg.to_dict() for msg in compressed]
    
    def clear(self):
        """清空对话历史（保留系统消息）"""
        self.messages = [self.messages[0]]  # 只保留系统消息
    
    def get_stats(self) -> Dict[str, Any]:
        """获取对话统计信息"""
        return {
            "total_messages": len(self.messages),
            "user_messages": len([m for m in self.messages if m.role == MessageRole.USER]),
            "assistant_messages": len([m for m in self.messages if m.role == MessageRole.ASSISTANT]),
            "tool_messages": len([m for m in self.messages if m.role == MessageRole.TOOL])
        }


class StreamResponseHandler:
    """流式响应处理器 - 统一处理不同SDK的流式响应"""
    
    def __init__(self, frontend):
        self.frontend = frontend
        self.full_content = ""
        self.full_thinking = ""
        self.tool_calls_cache = {}
        self.has_received_thinking = False
        self.finish_reason = None
    
    def handle_stream_event(self, event: StreamEvent):
        """处理流式事件"""
        if event.event_type == "thinking":
            if not self.has_received_thinking:
                self.has_received_thinking = True
            thinking_content = event.data
            self.full_thinking += thinking_content
            self.frontend.output('thinking', thinking_content)
            
        elif event.event_type == "content":
            content = event.data
            self.full_content += content
            self.frontend.output('content', content)
            
        elif event.event_type == "tool_call":
            tool_chunk = event.data
            self._handle_tool_call_chunk(tool_chunk)
            
        elif event.event_type == "finish":
            self.finish_reason = event.data
            self.frontend.output('end', f"\n[Stream结束] 完成原因: {event.data}")
    
    def _handle_tool_call_chunk(self, tool_chunk):
        """处理工具调用块"""
        # 获取工具调用的索引，处理字典和对象两种情况
        if isinstance(tool_chunk, dict):
            tool_index = tool_chunk.get('index', 0)
            tool_id = tool_chunk.get('id', '')
            function_name = tool_chunk.get('function', {}).get('name', '')
            function_args = tool_chunk.get('function', {}).get('arguments', '')
        else:
            # 处理对象格式（如OpenAI的tool call格式）
            tool_index = getattr(tool_chunk, 'index', 0)
            tool_id = getattr(tool_chunk, 'id', '')
            function_name = getattr(getattr(tool_chunk, 'function', None), 'name', '') if hasattr(tool_chunk, 'function') else ''
            function_args = getattr(getattr(tool_chunk, 'function', None), 'arguments', '') if hasattr(tool_chunk, 'function') else ''
        
        if tool_index not in self.tool_calls_cache:
            self.tool_calls_cache[tool_index] = {
                'id': '',
                'function': {'name': '', 'arguments': ''}
            }
            # 首次检测到工具调用时提示
            if function_name:
                self.frontend.output('tool_call', function_name)
        
        # 更新工具ID、名称、参数
        if tool_id:
            self.tool_calls_cache[tool_index]['id'] = tool_id
        if function_name:
            self.tool_calls_cache[tool_index]['function']['name'] = function_name
        if function_args:
            self.tool_calls_cache[tool_index]['function']['arguments'] += function_args
            # 显示参数接收进度（每50字符一个点）
            if len(self.tool_calls_cache[tool_index]['function']['arguments']) % 50 == 0:
                self.frontend.output('tool_progress', ".")
    
    def get_result(self) -> Dict[str, Any]:
        """获取处理结果"""
        return {
            "content": self.full_content,
            "thinking": self.full_thinking,
            "tool_calls": self._get_tool_calls_list(),
            "finish_reason": self.finish_reason,
            "has_content": bool(self.full_content),
            "has_thinking": bool(self.full_thinking),
            "has_tool_calls": bool(self.tool_calls_cache)
        }
    
    def _get_tool_calls_list(self) -> Optional[List[Dict[str, Any]]]:
        """获取工具调用列表"""
        if not self.tool_calls_cache:
            return None
        
        return [
            {
                'id': tool_call['id'],
                'type': 'function',
                'function': {
                    'name': tool_call['function']['name'],
                    'arguments': tool_call['function']['arguments']
                }
            } for tool_call in self.tool_calls_cache.values()
        ]