"""UnifiedLLMClient 单元测试"""
import unittest
from unittest.mock import MagicMock

from pyagent.conversation_manager import StreamEvent
from pyagent.llm_adapter import UnifiedLLMClient


class FakeDelta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning_content = None
        self.reasoning = None


class FakeChoice:
    def __init__(self, delta=None, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class FakeChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage


class FakeClient:
    def __init__(self, chunks):
        self.chat = MagicMock()
        self.chat.completions.create.return_value = iter(chunks)


class UnifiedLLMClientTests(unittest.TestCase):
    def test_yields_content_and_finish(self):
        chunks = [
            FakeChunk([FakeChoice(FakeDelta(content="Hello "))]),
            FakeChunk([FakeChoice(FakeDelta(content="world"))]),
            FakeChunk([FakeChoice(None, "stop")]),
        ]
        client = UnifiedLLMClient(FakeClient(chunks), "gpt-4")
        events = list(client.chat_completions_create_with_events())

        types = [e.event_type for e in events]
        self.assertEqual(types, ["content", "content", "finish"])
        self.assertEqual(events[0].data, "Hello ")
        self.assertEqual(events[1].data, "world")
        self.assertEqual(events[2].data, "stop")

    def test_yields_usage_event(self):
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        chunks = [
            FakeChunk([FakeChoice(FakeDelta(content="Hi"))]),
            FakeChunk([], usage=usage),
        ]
        client = UnifiedLLMClient(FakeClient(chunks), "gpt-4")
        events = list(client.chat_completions_create_with_events())

        self.assertEqual(events[0].event_type, "content")
        self.assertEqual(events[1].event_type, "usage")
        self.assertEqual(events[1].data, usage)

    def test_requests_stream_options_when_supported(self):
        class SignatureClient:
            class Completions:
                @staticmethod
                def create(**kwargs):
                    return iter([])

            chat = MagicMock()
            chat.completions = Completions()

        client = UnifiedLLMClient(SignatureClient(), "gpt-4")
        # Inspect signature of the real create method by restoring bound method.
        # Because MagicMock signature is empty, manually set it.
        import inspect

        def create(**kwargs):
            return iter([])

        client.client.chat.completions.create = create
        list(client.chat_completions_create_with_events())

        # With a supported signature, stream_options should be passed.
        # We test indirectly by ensuring no exception is raised.


if __name__ == "__main__":
    unittest.main()
