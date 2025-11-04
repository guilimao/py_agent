"""
流式事件转换器

将不同LLM提供商的响应格式转换为统一的事件流格式。
"""

from typing import Optional, Any, Dict, List
import json

from ..conversation_manager import StreamEvent


class StreamEventConverter:
    """流式事件转换器 - 将不同SDK的响应转换为统一事件"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def convert_openai_chunk(chunk: Any) -> Optional[StreamEvent]:
        """
        转换OpenAI格式的chunk为统一事件
        
        Args:
            chunk: OpenAI格式的响应块
            
        Returns:
            统一的事件对象，如果无法转换则返回None
        """
        
        if not hasattr(chunk, 'choices') or not chunk.choices:
            return None
        
        original_choice = chunk.choices[0]
        
        # 处理完成事件
        if hasattr(original_choice, 'finish_reason') and original_choice.finish_reason:
            return StreamEvent(
                event_type='finish',
                data=original_choice.finish_reason
            )
        
        # 处理delta内容
        if hasattr(original_choice, 'delta'):
            original_delta = original_choice.delta
            
            # 处理思考内容（reasoning_content）
            if hasattr(original_delta, 'reasoning_content') and original_delta.reasoning_content:
                return StreamEvent(
                    event_type='thinking',
                    data=original_delta.reasoning_content
                )
            
            # 处理自然语言内容
            if hasattr(original_delta, 'content') and original_delta.content:
                return StreamEvent(
                    event_type='content',
                    data=original_delta.content
                )
            
            # 处理工具调用
            if hasattr(original_delta, 'tool_calls') and original_delta.tool_calls:
                return StreamEvent(
                    event_type='tool_call',
                    data=original_delta.tool_calls[0] if original_delta.tool_calls else None
                )
        
        return None
    
    @staticmethod
    def convert_anthropic_chunk(chunk: Any) -> Optional[StreamEvent]:
        """
        转换Anthropic格式的chunk为统一事件
        
        Args:
            chunk: Anthropic格式的响应块
            
        Returns:
            统一的事件对象，如果无法转换则返回None
        """
        
        # 处理消息开始事件
        if hasattr(chunk, 'type') and chunk.type == 'message_start':
            # message_start通常包含元数据，这里选择不转换为事件
            return None
        
        # 处理完整的message响应
        if hasattr(chunk, 'type') and chunk.type == 'message':
            if hasattr(chunk, 'content') and chunk.content:
                for block in chunk.content:
                    if hasattr(block, 'type'):
                        if block.type == 'text':
                            return StreamEvent(
                                event_type='content',
                                data=block.text
                            )
                        elif block.type == 'thinking':
                            return StreamEvent(
                                event_type='thinking',
                                data=block.thinking
                            )
                        elif block.type == 'tool_use':
                            tool_call = {
                                'id': block.id,
                                'type': 'function',
                                'function': {
                                    'name': block.name,
                                    'arguments': json.dumps(block.input)
                                }
                            }
                            return StreamEvent(
                                event_type='tool_call',
                                data=tool_call
                            )
            # 处理完成事件
            if hasattr(chunk, 'stop_reason') and chunk.stop_reason:
                return StreamEvent(
                    event_type='finish',
                    data=chunk.stop_reason
                )
        
        # 处理内容块开始事件
        if hasattr(chunk, 'type') and chunk.type == 'content_block_start':
            if hasattr(chunk, 'content_block'):
                if chunk.content_block.type == 'text':
                    return StreamEvent(
                        event_type='content',
                        data=chunk.content_block.text
                    )
                elif chunk.content_block.type == 'tool_use':
                    tool_call = {
                        'id': chunk.content_block.id,
                        'type': 'function',
                        'function': {
                            'name': chunk.content_block.name,
                            'arguments': ''
                        }
                    }
                    return StreamEvent(
                        event_type='tool_call',
                        data=tool_call
                    )
        
        # 处理内容块增量事件
        if hasattr(chunk, 'type') and chunk.type == 'content_block_delta':
            if hasattr(chunk, 'delta'):
                if hasattr(chunk.delta, 'text'):
                    return StreamEvent(
                        event_type='content',
                        data=chunk.delta.text
                    )
                elif hasattr(chunk.delta, 'partial_json'):
                    # 工具调用的JSON片段，需要累积处理
                    tool_call = {
                        'partial_json': chunk.delta.partial_json
                    }
                    return StreamEvent(
                        event_type='tool_call',
                        data=tool_call
                    )
        
        # 处理完成事件
        if hasattr(chunk, 'type') and chunk.type == 'message_stop':
            # 使用实际的停止原因，而不是硬编码的'stop'
            stop_reason = getattr(chunk, 'stop_reason', 'stop') or 'stop'
            return StreamEvent(
                event_type='finish',
                data=stop_reason
            )
        
        return None
    
    @staticmethod
    def convert_generic_chunk(chunk: Any, provider: str) -> Optional[StreamEvent]:
        """
        转换通用格式的chunk为统一事件
        
        Args:
            chunk: 通用格式的响应块
            provider: 提供商名称
            
        Returns:
            统一的事件对象，如果无法转换则返回None
        """
        provider = provider.lower()
        
        if provider == 'openai':
            return StreamEventConverter.convert_openai_chunk(chunk)
        elif provider == 'anthropic':
            return StreamEventConverter.convert_anthropic_chunk(chunk)
        else:
            # 默认使用OpenAI格式转换
            return StreamEventConverter.convert_openai_chunk(chunk)