"""
Streaming adapter for OpenAI-compatible chat completions.
"""

import inspect
from typing import Iterator, Optional

from ..conversation_manager import StreamEvent


class UnifiedLLMClient:
    def __init__(self, client, model_name: str):
        self.client = client
        self.model_name = model_name
        self._supports_stream_options: Optional[bool] = None

    def _has_stream_options(self) -> bool:
        if self._supports_stream_options is None:
            try:
                sig = inspect.signature(self.client.chat.completions.create)
                self._supports_stream_options = "stream_options" in sig.parameters
            except Exception:
                self._supports_stream_options = False
        return self._supports_stream_options

    def chat_completions_create_with_events(self, **kwargs) -> Iterator[StreamEvent]:
        kwargs.setdefault("stream", True)
        kwargs.setdefault("model", self.model_name)

        # 向支持的提供商请求在流末尾返回 usage 信息。
        if self._has_stream_options() and "stream_options" not in kwargs:
            kwargs["stream_options"] = {"include_usage": True}

        stream = self.client.chat.completions.create(**kwargs)

        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                yield StreamEvent(event_type="usage", data=usage)

            if not chunk.choices:
                continue

            choice = chunk.choices[0]

            if choice.finish_reason:
                yield StreamEvent(event_type="finish", data=choice.finish_reason)
                continue

            delta = choice.delta

            reasoning_content = getattr(delta, "reasoning_content", None)
            reasoning = getattr(delta, "reasoning", None)
            if reasoning_content is not None:
                yield StreamEvent(event_type="thinking", data=reasoning_content)
            elif reasoning is not None:
                yield StreamEvent(event_type="thinking", data=reasoning)
            elif getattr(delta, "content", None):
                yield StreamEvent(event_type="content", data=delta.content)
            elif getattr(delta, "tool_calls", None):
                for tc in delta.tool_calls:
                    yield StreamEvent(event_type="tool_call", data=tc)

    def get_model_name(self) -> str:
        return self.model_name
