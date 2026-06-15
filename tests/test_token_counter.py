"""TokenCounter 单元测试"""
import unittest

from pyagent.token_counter import TokenCounter


class TokenCounterTests(unittest.TestCase):
    def setUp(self):
        self.counter = TokenCounter("qwen3-235b-a22b")
        self.counter.set_initial_tokens("你是助手", [])

    def test_count_tokens_english_words(self):
        # 5 个单词 => 5 tokens
        self.assertEqual(self.counter.count_tokens("Hello world from tests"), 4)

    def test_count_tokens_chinese_chars(self):
        text = "你好世界"
        self.assertEqual(self.counter.count_tokens(text), 4)

    def test_count_tokens_mixed(self):
        text = "Hello 你好 world 世界"
        self.assertEqual(self.counter.count_tokens(text), 6)

    def test_count_message_tokens_text(self):
        msg = {"role": "user", "content": "Hello 你好"}
        self.assertEqual(self.counter.count_message_tokens(msg), 3)

    def test_count_message_tokens_with_reasoning(self):
        msg = {"role": "assistant", "content": "OK", "reasoning_content": "因为"}
        self.assertEqual(self.counter.count_message_tokens(msg), 3)

    def test_provider_usage_overrides_fallback(self):
        self.counter.start_new_round("用户输入")
        user_tokens = self.counter.current_round_stats["user_input_tokens"]
        self.assertGreater(user_tokens, 0)

        fallback_output = self.counter.count_assistant_output(content="response")
        self.counter.add_api_usage(10, 5, from_provider=True)

        self.assertEqual(self.counter.total_stats["total_input_tokens"], 10)
        self.assertEqual(self.counter.total_stats["total_output_tokens"], 5)
        self.assertEqual(self.counter.total_stats["total_tokens"], 15)
        self.assertEqual(self.counter.current_round_stats["llm_output_tokens"], 5)
        self.assertEqual(self.counter._round_strategy, "provider usage")

    def test_fallback_usage(self):
        self.counter.start_new_round("hi")
        self.counter.add_api_usage(7, 3)
        self.assertEqual(self.counter.total_stats["total_input_tokens"], 7)
        self.assertEqual(self.counter.total_stats["total_output_tokens"], 3)
        self.assertEqual(self.counter.current_round_stats["llm_output_tokens"], 3)

    def test_extract_provider_usage_object(self):

        class FakeUsage:
            prompt_tokens = 12
            completion_tokens = 5
            total_tokens = 17

        self.assertEqual(
            self.counter.extract_provider_usage(FakeUsage()),
            {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        )

    def test_extract_provider_usage_dict(self):
        usage = {"prompt_tokens": 20, "completion_tokens": 8}
        self.assertEqual(
            self.counter.extract_provider_usage(usage),
            {"prompt_tokens": 20, "completion_tokens": 8},
        )

    def test_extract_provider_usage_partial_total(self):

        class FakeUsage:
            completion_tokens = 6
            total_tokens = 16

        info = self.counter.extract_provider_usage(FakeUsage())
        self.counter.add_api_usage(
            info.get("total_tokens", 0) - info.get("completion_tokens", 0),
            info["completion_tokens"],
            from_provider=True,
        )
        self.assertEqual(self.counter.total_stats["total_input_tokens"], 10)


if __name__ == "__main__":
    unittest.main()
