import json
import re

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class TokenCounter:
    """Token 统计器，用于统计对话中的 token 使用量。"""

    def __init__(self, model_name: str = "qwen3-235b-a22b"):
        self.model_name = model_name
        self.use_tiktoken = TIKTOKEN_AVAILABLE

        if self.use_tiktoken:
            try:
                if "qwen" in model_name.lower():
                    self.encoding = tiktoken.get_encoding("o200k_base")
                else:
                    self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except Exception:
                self.use_tiktoken = False
                self.encoding = None
        else:
            self.encoding = None

        self.current_round_stats = {
            "user_input_tokens": 0,
            "llm_output_tokens": 0,
            "tool_result_tokens": 0,
            "total_round_tokens": 0,
        }

        self.total_stats = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

        self.initial_tokens = {
            "system_prompt_tokens": 0,
            "tools_definition_tokens": 0,
            "total_initial_tokens": 0,
        }

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0

        if self.use_tiktoken and self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass

        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0

        text = text.strip()
        if not text:
            return 0

        char_count = len(text)
        words = re.findall(r"\b\w+\b", text)
        word_count = len(words)
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

        if chinese_chars > char_count * 0.3:
            estimated = max(chinese_chars * 0.6, char_count * 0.4)
        else:
            estimated = max(word_count * 1.3, char_count * 0.25)

        punctuation_count = len(re.findall(r"[^\w\s\u4e00-\u9fff]", text))
        estimated += punctuation_count * 0.2
        return max(1, int(estimated))

    def count_message_tokens(self, message: dict) -> int:
        total_tokens = 0

        content = message.get("content")
        if content:
            if isinstance(content, str):
                total_tokens += self.count_tokens(content)
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text" and item.get("text"):
                        total_tokens += self.count_tokens(item["text"])
                    elif item.get("type") == "image_url" and item.get("image_url", {}).get("url"):
                        total_tokens += 85
                        url = item["image_url"]["url"]
                        if url.startswith("data:image"):
                            try:
                                base64_part = url.split(",")[1]
                                image_size = len(base64_part) * 0.75
                                if image_size > 100000:
                                    total_tokens += 170
                                elif image_size > 50000:
                                    total_tokens += 85
                            except Exception:
                                total_tokens += 85

        reasoning_text = message.get("reasoning_content")
        if reasoning_text is None:
            reasoning_text = message.get("thinking")
        if reasoning_text:
            total_tokens += self.count_tokens(str(reasoning_text))

        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                if "function" in tool_call:
                    func_name = tool_call["function"].get("name", "")
                    func_args = tool_call["function"].get("arguments", "")
                    total_tokens += self.count_tokens(func_name) + self.count_tokens(func_args)

        return total_tokens

    def count_tools_tokens(self, tools: list) -> int:
        if not tools:
            return 0
        tools_json = json.dumps(tools, ensure_ascii=False, separators=(",", ":"))
        return self.count_tokens(tools_json)

    def set_initial_tokens(self, system_prompt: str, tools: list):
        system_tokens = self.count_tokens(system_prompt)
        tools_tokens = self.count_tools_tokens(tools)

        self.initial_tokens["system_prompt_tokens"] = system_tokens
        self.initial_tokens["tools_definition_tokens"] = tools_tokens
        self.initial_tokens["total_initial_tokens"] = system_tokens + tools_tokens

        self.total_stats["total_input_tokens"] = system_tokens + tools_tokens
        self.total_stats["total_tokens"] = system_tokens + tools_tokens

    def start_new_round(self):
        self.current_round_stats = {
            "user_input_tokens": 0,
            "llm_output_tokens": 0,
            "tool_result_tokens": 0,
            "total_round_tokens": 0,
        }

    def calculate_conversation_tokens(self, messages: list) -> int:
        total_tokens = self.initial_tokens["total_initial_tokens"]
        for message in messages:
            total_tokens += self.count_message_tokens(message)
        return total_tokens

    def update_total_stats(self, messages: list):
        actual_input_tokens = self.calculate_conversation_tokens(messages)
        self.total_stats["total_input_tokens"] = actual_input_tokens
        self.total_stats["total_tokens"] = (
            actual_input_tokens + self.total_stats["total_output_tokens"]
        )

    def add_user_input(self, text: str):
        tokens = self.count_tokens(text)
        self.current_round_stats["user_input_tokens"] = tokens

    def add_llm_output(self, thinking: str = "", content: str = "", tool_calls: list = None):
        tokens = 0

        if thinking:
            tokens += self.count_tokens(thinking)
        if content:
            tokens += self.count_tokens(content)
        if tool_calls:
            for tool_call in tool_calls:
                if "function" in tool_call:
                    func_name = tool_call["function"].get("name", "")
                    func_args = tool_call["function"].get("arguments", "")
                    tokens += self.count_tokens(func_name) + self.count_tokens(func_args)

        self.current_round_stats["llm_output_tokens"] += tokens
        self.total_stats["total_output_tokens"] += tokens

    def add_tool_result(self, result: str):
        tokens = self.count_tokens(str(result))
        self.current_round_stats["tool_result_tokens"] += tokens

    def finish_round(self):
        self.current_round_stats["total_round_tokens"] = (
            self.current_round_stats["user_input_tokens"]
            + self.current_round_stats["llm_output_tokens"]
            + self.current_round_stats["tool_result_tokens"]
        )

    def get_round_summary(self) -> str:
        strategy = "tiktoken" if self.use_tiktoken else "估算"
        return f"""
📊 当前轮次Token统计 ({strategy}策略):
   👤 用户输入: {self.current_round_stats['user_input_tokens']} tokens
   🤖 LLM输出: {self.current_round_stats['llm_output_tokens']} tokens
   🔧 工具结果: {self.current_round_stats['tool_result_tokens']} tokens
   📈 本轮总计: {self.current_round_stats['total_round_tokens']} tokens

📊 累计Token统计:
   📝 系统初始: {self.initial_tokens['total_initial_tokens']} tokens
   👤 用户输入: {self.current_round_stats['user_input_tokens']} tokens (本轮)
   🤖 LLM输出: {self.current_round_stats['llm_output_tokens']} tokens (本轮)
   🔧 工具结果: {self.current_round_stats['tool_result_tokens']} tokens (本轮)
   📥 总输入: {self.total_stats['total_input_tokens']} tokens
   📤 总输出: {self.total_stats['total_output_tokens']} tokens
   📊 总计: {self.total_stats['total_tokens']} tokens
"""

    def get_current_operation_summary(self, operation_type: str) -> str:
        if operation_type == "user_input":
            return f"📥 用户输入: {self.current_round_stats['user_input_tokens']} tokens"
        if operation_type == "llm_output":
            return f"📤 LLM输出: {self.current_round_stats['llm_output_tokens']} tokens"
        if operation_type == "tool_result":
            return f"📥 工具返回: {self.current_round_stats['tool_result_tokens']} tokens"
        return ""

    def get_total_summary(self) -> str:
        return (
            f"📊 总输入: {self.total_stats['total_input_tokens']} tokens, "
            f"总输出: {self.total_stats['total_output_tokens']} tokens, "
            f"总计: {self.total_stats['total_tokens']} tokens"
        )
