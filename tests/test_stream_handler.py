"""StreamResponseHandler 单元测试"""
import unittest
from unittest.mock import MagicMock

from pyagent.conversation_manager import StreamEvent, StreamResponseHandler


class StreamResponseHandlerTests(unittest.TestCase):
    def _create_handler(self):
        frontend = MagicMock()
        return StreamResponseHandler(frontend), frontend

    def test_single_finish_outputs_end_once(self):
        handler, frontend = self._create_handler()

        handler.handle_stream_event(StreamEvent("content", "Hello"))
        handler.handle_stream_event(StreamEvent("finish", "stop"))

        end_calls = [c for c in frontend.output.call_args_list if c.args[0] == "end"]
        self.assertEqual(len(end_calls), 1)
        self.assertIn("stop", end_calls[0].args[1])

    def test_duplicate_finish_outputs_end_once(self):
        """OpenRouter 等部分提供商会发送多个 finish_reason 块，应只提示一次结束。"""
        handler, frontend = self._create_handler()

        handler.handle_stream_event(StreamEvent("content", "Hello"))
        handler.handle_stream_event(StreamEvent("finish", "stop"))
        handler.handle_stream_event(StreamEvent("finish", "stop"))

        end_calls = [c for c in frontend.output.call_args_list if c.args[0] == "end"]
        self.assertEqual(len(end_calls), 1)

    def test_last_finish_reason_used_in_result(self):
        handler, frontend = self._create_handler()

        handler.handle_stream_event(StreamEvent("finish", "stop"))
        handler.handle_stream_event(StreamEvent("finish", "length"))

        result = handler.get_result()
        self.assertEqual(result["finish_reason"], "length")


if __name__ == "__main__":
    unittest.main()
