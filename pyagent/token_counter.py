import json
import re
from typing import Any, Dict, List, Optional

# 当服务商没有返回用量信息时的兜底策略：统计中文字符 + 单词数量。
# 中文按单个字符计数；英文等其它单词按空白分隔的非中文字符串计数。
_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_WHITESPACE_RE = re.compile(r"\s+")


class TokenCounter:
    """Token 统计器。

    优先使用 LLM 服务商（OpenAI 兼容接口）返回的真实用量；当服务商未返回
    用量信息时，回退到简单的“中文字符数 + 单词数”估算。
    """

    def __init__(self, model_name: str = "qwen3-235b-a22b"):
        self.model_name = model_name

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

        # "provider usage" 或 "words+chars"
        self._round_strategy = "words+chars"

    # ------------------------------------------------------------------
    # 基础计数（兜底策略）
    # ------------------------------------------------------------------
    @staticmethod
    def _count_text_tokens(text: str) -> int:
        """统计文本中的中文字符数与单词数之和。"""
        if not text:
            return 0
        text = str(text)
        chinese_chars = len(_CHINESE_CHAR_RE.findall(text))
        non_chinese = _CHINESE_CHAR_RE.sub(" ", text)
        words = len([w for w in _WHITESPACE_RE.split(non_chinese.strip()) if w])
        return chinese_chars + words

    def count_tokens(self, text: str) -> int:
        """返回文本的 token 估算值；在移除 tiktoken 后使用单词+中文字符兜底。"""
        return self._count_text_tokens(text)

    # ------------------------------------------------------------------
    # 消息 / 工具 / 会话级别的估算
    # ------------------------------------------------------------------
    def count_message_tokens(self, message: Dict[str, Any]) -> int:
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

    def count_tools_tokens(self, tools: List[Dict[str, Any]]) -> int:
        if not tools:
            return 0
        tools_json = json.dumps(tools, ensure_ascii=False, separators=(",", ":"))
        return self.count_tokens(tools_json)

    def count_assistant_output(
        self,
        thinking: str = "",
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """估算一次 LLM 响应的输出 token 数（不含 provider 用量时使用）。"""
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
        return tokens

    def set_initial_tokens(self, system_prompt: str, tools: List[Dict[str, Any]]):
        system_tokens = self.count_tokens(system_prompt)
        tools_tokens = self.count_tools_tokens(tools)

        self.initial_tokens = {
            "system_prompt_tokens": system_tokens,
            "tools_definition_tokens": tools_tokens,
            "total_initial_tokens": system_tokens + tools_tokens,
        }

    def calculate_conversation_tokens(self, messages: List[Dict[str, Any]]) -> int:
        total_tokens = self.initial_tokens["total_initial_tokens"]
        for message in messages:
            total_tokens += self.count_message_tokens(message)
        return total_tokens

    # ------------------------------------------------------------------
    # 轮次 / 总量统计
    # ------------------------------------------------------------------
    def start_new_round(self, user_input: str = ""):
        self.current_round_stats = {
            "user_input_tokens": self.count_tokens(user_input),
            "llm_output_tokens": 0,
            "tool_result_tokens": 0,
            "total_round_tokens": 0,
        }
        self._round_strategy = "words+chars"

    def add_api_usage(
        self,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        from_provider: bool = False,
    ):
        """记录一次 API 调用的输入/输出 token 用量，累加到会话总量。

        当 from_provider=True 时，会同时标记本轮统计来源为 provider 真实用量。
        """
        if prompt_tokens is not None and prompt_tokens > 0:
            self.total_stats["total_input_tokens"] += prompt_tokens
        if completion_tokens is not None and completion_tokens > 0:
            self.total_stats["total_output_tokens"] += completion_tokens
            self.current_round_stats["llm_output_tokens"] += completion_tokens
        if from_provider and (prompt_tokens is not None or completion_tokens is not None):
            self._round_strategy = "provider usage"

        self.total_stats["total_tokens"] = (
            self.total_stats["total_input_tokens"] + self.total_stats["total_output_tokens"]
        )

    def add_tool_result(self, result: str):
        tokens = self.count_tokens(str(result))
        self.current_round_stats["tool_result_tokens"] += tokens

    def finish_round(self):
        self.current_round_stats["total_round_tokens"] = (
            self.current_round_stats["user_input_tokens"]
            + self.current_round_stats["llm_output_tokens"]
            + self.current_round_stats["tool_result_tokens"]
        )

    # ------------------------------------------------------------------
    # Provider 用量解析
    # ------------------------------------------------------------------
    @staticmethod
    def extract_provider_usage(usage: Any) -> Dict[str, int]:
        """从 OpenAI 兼容接口返回的 usage 对象中提取 prompt/completion/total。"""
        result: Dict[str, int] = {}
        if usage is None:
            return result

        def _get(name: str):
            value = getattr(usage, name, None)
            if value is None and isinstance(usage, dict):
                value = usage.get(name)
            return value

        prompt = _get("prompt_tokens")
        completion = _get("completion_tokens")
        total = _get("total_tokens")

        if prompt is not None:
            result["prompt_tokens"] = int(prompt)
        if completion is not None:
            result["completion_tokens"] = int(completion)
        if total is not None:
            result["total_tokens"] = int(total)
        return result

    # ------------------------------------------------------------------
    # 摘要输出
    # ------------------------------------------------------------------
    def get_round_summary(self) -> str:
        strategy = self._round_strategy
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
