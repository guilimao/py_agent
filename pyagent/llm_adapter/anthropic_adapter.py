"""
Anthropic Claude LLM适配器
专门处理Anthropic Claude模型的适配器
"""
from typing import Iterator, Any, Dict, List, Optional
import json
import re
from .base import BaseLLMAdapter
from .models import LLMStreamResponse
from .exceptions import LLMException
from ..conversation_manager import StreamEvent
class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Claude适配器 - 专注于流式响应"""
    def __init__(self, client: Any, model_name: str):
        """
        初始化Anthropic适配器
        Args:
            client: Anthropic客户端对象
            model_name: 模型名称
        """
        self.client = client
        self.model_name = model_name
    def create_chat_completion(self, **kwargs) -> Iterator[LLMStreamResponse]:
        """
        将Anthropic的接口转换为统一格式 - 仅支持流式响应
        Args:
            **kwargs: OpenAI格式的参数
        Returns:
            统一的流式响应迭代器
        Raises:
            LLMException: 当LLM调用失败时
        """
        try:
            # 转换OpenAI格式为Anthropic格式
            anthropic_params = self._convert_openai_to_anthropic(kwargs)
            # 强制使用流式模式
            anthropic_params['stream'] = True
            # 调用Anthropic API - 仅支持流式
            response = self.client.messages.create(**anthropic_params)
            # 处理流式响应并转换为统一格式
            for unified_response in self._process_streaming_response(response):
                yield unified_response
        except Exception as e:
            raise LLMException(f"Anthropic LLM调用失败: {str(e)}") from e
    def create_chat_completion_with_events(self, **kwargs) -> Iterator[StreamEvent]:
        """
        创建聊天完成，返回统一的事件流
        Args:
            **kwargs: OpenAI格式的参数
        Returns:
            统一的流式事件迭代器
        Raises:
            LLMException: 当LLM调用失败时
        """
        try:
            # 转换OpenAI格式为Anthropic格式
            anthropic_params = self._convert_openai_to_anthropic(kwargs)
            # 强制使用流式模式
            anthropic_params['stream'] = True
            # 调用Anthropic API - 仅支持流式
            response = self.client.messages.create(**anthropic_params)
            # 处理响应并转换为事件流
            for event in self._process_streaming_events(response):
                yield event
        except Exception as e:
            raise LLMException(f"Anthropic LLM调用失败: {str(e)}") from e
    def _convert_openai_to_anthropic(self, openai_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        将OpenAI格式参数转换为Anthropic格式
        Args:
            openai_params: OpenAI格式的参数字典
        Returns:
            Anthropic格式的参数字典
        """
        anthropic_params = {}
        # 基本参数
        anthropic_params['model'] = openai_params.get('model', self.model_name)
        anthropic_params['max_tokens'] = openai_params.get('max_tokens', 4096)
        # 转换消息格式
        messages = openai_params.get('messages', [])
        anthropic_messages = []
        system_prompt = None
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content')
            if role == 'system':
                system_prompt = content
            elif role == 'user':
                if isinstance(content, list):
                    # 处理多模态内容
                    anthropic_content = []
                    for part in content:
                        if part.get('type') == 'text':
                            anthropic_content.append({"type": "text", "text": part.get('text', '')})
                        elif part.get('type') == 'image_url':
                            image_url = part.get('image_url', {}).get('url', '')
                            if image_url.startswith('data:image'):
                                # 处理base64图像
                                match = re.match(r'data:image/(\w+);base64,(.+)', image_url)
                                if match:
                                    media_type = match.group(1)
                                    base64_data = match.group(2)
                                    anthropic_content.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": f"image/{media_type}",
                                            "data": base64_data
                                        }
                                    })
                    anthropic_messages.append({"role": "user", "content": anthropic_content})
                else:
                    anthropic_messages.append({"role": "user", "content": content})
            elif role == 'assistant':
                anthropic_messages.append({"role": "assistant", "content": content})
            elif role == 'tool':
                # 转换工具结果为Anthropic格式
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg.get('tool_call_id', ''),
                    "content": str(content) if content else ""
                }
                anthropic_messages.append({"role": "user", "content": [tool_result]})
        anthropic_params['messages'] = anthropic_messages
        # 设置系统提示
        if system_prompt:
            anthropic_params['system'] = system_prompt
        # 转换工具定义
        if 'tools' in openai_params:
            anthropic_params['tools'] = self._convert_openai_tools_to_anthropic(openai_params['tools'])
        # 注意：流式参数由调用者控制，这里不强制设置
        return anthropic_params
    def _convert_openai_tools_to_anthropic(self, openai_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将OpenAI格式的工具定义转换为Anthropic格式
        Args:
            openai_tools: OpenAI格式的工具列表
        Returns:
            Anthropic格式的工具列表
        """
        anthropic_tools = []
        for tool in openai_tools:
            if tool.get('type') == 'function':
                function_def = tool.get('function', {})
                anthropic_tool = {
                    'name': function_def.get('name'),
                    'description': function_def.get('description', ''),
                    'input_schema': function_def.get('parameters', {})
                }
                anthropic_tools.append(anthropic_tool)
        return anthropic_tools
    def _process_streaming_response(self, response) -> Iterator[LLMStreamResponse]:
        """
        处理Anthropic流式响应并转换为统一格式
        Args:
            response: Anthropic的流式响应对象
        Returns:
            统一的流式响应迭代器
        """
        current_tool_call = None
        tool_call_index = 0  # 跟踪工具调用索引
        for chunk in response:
            unified_response = LLMStreamResponse()
            if hasattr(chunk, 'type'):
                if chunk.type == 'message_start':
                    # message_start包含模型信息，可以记录但不生成响应内容
                    continue
                elif chunk.type == 'content_block_start':
                    if hasattr(chunk, 'content_block'):
                        if chunk.content_block.type == 'text':
                            # 开始文本内容块
                            unified_response.choices[0].delta.content = chunk.content_block.text
                        elif chunk.content_block.type == 'tool_use':
                            # 开始工具调用块，初始化工具调用对象
                            current_tool_call = {
                                'id': chunk.content_block.id,
                                'type': 'function',
                                'index': tool_call_index,  # 添加索引字段
                                'function': {
                                    'name': chunk.content_block.name,
                                    'arguments': ''
                                }
                            }
                            tool_call_index += 1  # 递增索引
                            # 立即发送工具调用信息，确保ID被正确记录
                            unified_response.choices[0].delta.tool_calls = [current_tool_call]
                            yield unified_response
                elif chunk.type == 'content_block_delta':
                    if hasattr(chunk, 'delta'):
                        if hasattr(chunk.delta, 'text'):
                            # 文本内容增量
                            unified_response.choices[0].delta.content = chunk.delta.text
                        elif hasattr(chunk.delta, 'partial_json'):
                            # 工具调用参数增量
                            if current_tool_call:
                                current_tool_call['function']['arguments'] += chunk.delta.partial_json
                                unified_response.choices[0].delta.tool_calls = [current_tool_call]
                        elif hasattr(chunk.delta, 'thinking'):
                            # 思考内容（如果存在）
                            unified_response.choices[0].delta.reasoning_content = chunk.delta.thinking
                elif chunk.type == 'content_block_stop':
                    # 内容块结束，发送最终状态（如果之前未发送）
                    if current_tool_call and not unified_response.choices[0].delta.tool_calls:
                        # 即使参数为空也发送，确保工具调用ID被正确记录
                        unified_response.choices[0].delta.tool_calls = [current_tool_call]
                    current_tool_call = None
                elif chunk.type == 'message_delta':
                    # 消息级别的增量，通常包含停止原因
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'stop_reason'):
                        if chunk.delta.stop_reason:
                            unified_response.set_finish_reason(chunk.delta.stop_reason)
                            unified_response.choices[0].finish_reason = chunk.delta.stop_reason
                elif chunk.type == 'message_stop':
                    # 消息结束，只有在没有通过message_delta设置停止原因时才设置
                    if not unified_response.finish_reason:
                        stop_reason = getattr(chunk, 'stop_reason', 'stop') or 'stop'
                        unified_response.set_finish_reason(stop_reason)
                        unified_response.choices[0].finish_reason = stop_reason
            # 只有在有实际内容时才yield响应
            if (unified_response.choices[0].delta.content or
                unified_response.choices[0].delta.tool_calls or
                unified_response.choices[0].delta.reasoning_content or
                unified_response.finish_reason):
                yield unified_response
    def _process_streaming_events(self, response) -> Iterator[StreamEvent]:
        """
        处理Anthropic流式响应并转换为事件流
        Args:
            response: Anthropic的流式响应对象
        Returns:
            统一的流式事件迭代器
        """
        current_tool_call = None
        tool_call_index = 0  # 跟踪工具调用索引
        for chunk in response:
            if hasattr(chunk, 'type'):
                if chunk.type == 'message_start':
                    # message_start包含模型信息，不转换为事件
                    continue
                elif chunk.type == 'content_block_start':
                    if hasattr(chunk, 'content_block'):
                        if chunk.content_block.type == 'text':
                            yield StreamEvent(
                                event_type='content',
                                data=chunk.content_block.text
                            )
                        elif chunk.content_block.type == 'tool_use':
                            # 开始工具调用，立即发送事件以确保ID被记录
                            current_tool_call = {
                                'id': chunk.content_block.id,
                                'type': 'function',
                                'index': tool_call_index,  # 添加索引字段
                                'function': {
                                    'name': chunk.content_block.name,
                                    'arguments': ''
                                }
                            }
                            tool_call_index += 1  # 递增索引
                            yield StreamEvent(
                                event_type='tool_call',
                                data=current_tool_call
                            )
                elif chunk.type == 'content_block_delta':
                    if hasattr(chunk, 'delta'):
                        if hasattr(chunk.delta, 'text'):
                            yield StreamEvent(
                                event_type='content',
                                data=chunk.delta.text
                            )
                        elif hasattr(chunk.delta, 'thinking'):
                            yield StreamEvent(
                                event_type='thinking',
                                data=chunk.delta.thinking
                            )
                        elif hasattr(chunk.delta, 'partial_json'):
                            # 工具调用参数增量
                            if current_tool_call:
                                current_tool_call['function']['arguments'] += chunk.delta.partial_json
                                # 不立即发送事件，等待接收完成
                elif chunk.type == 'content_block_stop':
                    # 内容块结束，发送最终工具调用状态
                    if current_tool_call:
                        # 即使参数为空也发送事件，确保工具调用ID被记录
                        yield StreamEvent(
                            event_type='tool_call',
                            data=current_tool_call
                        )
                    current_tool_call = None
                elif chunk.type == 'message_delta':
                    # 消息级别的增量，处理停止原因
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'stop_reason'):
                        if chunk.delta.stop_reason:
                            yield StreamEvent(
                                event_type='finish',
                                data=chunk.delta.stop_reason
                            )
                elif chunk.type == 'message_stop':
                    # 消息结束事件，不再发送finish事件以避免重复
                    # 因为停止原因已经在message_delta阶段处理过了
                    pass
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        return self.model_name