"""
Streaming adapter for OpenAI-compatible chat completions.
"""

from typing import Iterator

from ..conversation_manager import StreamEvent


class UnifiedLLMClient:
    def __init__(self, client, model_name: str):
        self.client = client
        self.model_name = model_name

    def chat_completions_create_with_events(self, **kwargs) -> Iterator[StreamEvent]:
        kwargs.setdefault("stream", True)
        kwargs.setdefault("model", self.model_name)

        stream = self.client.chat.completions.create(**kwargs)

        for chunk in stream:
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
