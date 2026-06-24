from datetime import datetime
import os
import shutil
import tempfile

import json_repair

from . import conversation_saver
from .conversation_manager import ConversationManager, StreamResponseHandler
from .frontends import FrontendInterface
from .frontends.image_handler import ImageHandler
from .llm_adapter import UnifiedLLMClient
from .token_counter import TokenCounter
from .tools import TOOL_FUNCTIONS, TOOLS
from .tools.browser_manager import cleanup_browser
from .tools.web_browser import build_overflow_message


class Agent:
    def __init__(
        self,
        client: UnifiedLLMClient,
        frontend: FrontendInterface,
        system_prompt: str,
        model_name: str,
        model_parameters: list = None,
    ):
        self.client = client
        self.frontend = frontend
        self.conversation_manager = ConversationManager(system_prompt)
        self.model_name = model_name
        self.model_parameters = model_parameters or []

        # 会话级临时文件统一托管，退出时一起清理。
        self._temp_dir: str | None = None
        self._temp_files: list[str] = []

        self.token_counter = TokenCounter(model_name)
        self.token_counter.set_initial_tokens(system_prompt, TOOLS)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"conversation_{timestamp}"

    def _ensure_temp_dir(self) -> str:
        """确保会话专属临时目录存在。"""
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix=f"pyagent_{self.session_id}_")
        return self._temp_dir

    def _create_managed_temp_file(self, content: str, url: str = "") -> str:
        """在会话托管目录中创建临时文本文件。"""
        temp_dir = self._ensure_temp_dir()

        safe_slug = ""
        if url:
            slug = url.replace("https://", "").replace("http://", "")
            safe_chars = []
            for ch in slug[:50]:
                if ch.isalnum() or ch in ".-_":
                    safe_chars.append(ch)
                else:
                    safe_chars.append("_")
            safe_slug = "".join(safe_chars).strip("_")

        prefix = f"browser_{safe_slug}_" if safe_slug else "browser_"
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".txt", dir=temp_dir, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)

        self._temp_files.append(path)
        return path

    def _cleanup_temp_files(self) -> None:
        """清理会话托管的临时文件以及浏览器资源。"""
        cleanup_browser()
        if self._temp_dir and os.path.isdir(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
            self._temp_files.clear()

    def run(self):
        try:
            self.frontend.start_session()

            while True:
                user_input, has_input = self.frontend.get_input()
                if not has_input or user_input.lower() == "退出":
                    break

                clean_text, content_parts = ImageHandler.process_user_input(user_input)
                image_count = len(
                    [part for part in content_parts if part.get("type") == "image_url"]
                )

                self.conversation_manager.add_user_message(clean_text, content_parts)

                if len(self.conversation_manager.get_messages_for_sdk()) == 2:
                    system_message = self.conversation_manager.get_system_message()
                    if system_message:
                        conversation_saver.save_conversation([system_message], self.session_id)

                conversation_saver.save_conversation(
                    [self.conversation_manager.get_last_message()],
                    self.session_id,
                )

                # 开始新一轮统计，用户输入使用兜底计数；provider 用量在 LLM 响应后补充。
                self.token_counter.start_new_round(clean_text)
                user_tokens = self.token_counter.current_round_stats["user_input_tokens"]
                image_info = f" 已添加图像: {image_count}张" if image_count > 0 else ""
                self.frontend.output("info", f"📊 用户输入: {user_tokens} tokens{image_info}")

                self._process_conversation_round()

                # 每轮结束后主动清理浏览器事件循环状态。
                cleanup_browser()

        except KeyboardInterrupt:
            self.frontend.output("warning", "\n⚠️  用户中断，正在退出...")
        except Exception as e:
            self.frontend.output("error", f"发生错误: {str(e)}")
        finally:
            self._cleanup_temp_files()
            self.frontend.end_session()

    def _process_conversation_round(self):
        """处理一轮对话，期间可能发生多次工具调用。"""
        while True:
            messages = self.conversation_manager.get_messages_for_sdk()

            # 兜底估算：当前完整上下文的 token 数。
            context_window_tokens = self.token_counter.calculate_conversation_tokens(messages)

            api_params = self._build_api_params(messages)
            stream = self.client.chat_completions_create_with_events(**api_params)
            stream_handler = StreamResponseHandler(self.frontend)

            provider_usage = None
            for event in stream:
                if event.event_type == "usage":
                    provider_usage = event.data
                    continue
                stream_handler.handle_stream_event(event)

            result = stream_handler.get_result()

            fallback_output_tokens = self.token_counter.count_assistant_output(
                result["thinking"],
                result["content"],
                result["tool_calls"],
            )

            usage_info = (
                self.token_counter.extract_provider_usage(provider_usage)
                if provider_usage is not None
                else {}
            )
            prompt_tokens = usage_info.get("prompt_tokens")
            completion_tokens = usage_info.get("completion_tokens")
            total_tokens = usage_info.get("total_tokens")

            # 优先使用 provider 返回的 prompt/completion；不完整时回退到本地估算。
            has_full_provider_usage = (
                prompt_tokens is not None and completion_tokens is not None
            )
            if has_full_provider_usage:
                self.token_counter.add_api_usage(
                    prompt_tokens, completion_tokens, from_provider=True
                )
            elif (
                prompt_tokens is not None
                and completion_tokens is None
                and total_tokens is not None
            ):
                self.token_counter.add_api_usage(
                    prompt_tokens,
                    total_tokens - prompt_tokens,
                    from_provider=True,
                )
            elif (
                completion_tokens is not None
                and prompt_tokens is None
                and total_tokens is not None
            ):
                self.token_counter.add_api_usage(
                    total_tokens - completion_tokens,
                    completion_tokens,
                    from_provider=True,
                )
            else:
                self.token_counter.add_api_usage(
                    context_window_tokens, fallback_output_tokens
                )

            self._show_context_stats(context_window_tokens)
            self._show_response_stats(
                self.token_counter.current_round_stats["llm_output_tokens"]
            )

            self.conversation_manager.add_assistant_message(
                result["content"],
                result["thinking"],
                result["tool_calls"],
            )
            conversation_saver.save_conversation(
                [self.conversation_manager.get_last_message()],
                self.session_id,
            )

            if result["has_tool_calls"]:
                self._execute_tool_calls(result["tool_calls"])
            else:
                self.token_counter.finish_round()
                break

    def _build_api_params(self, messages: list) -> dict:
        api_params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "tools": TOOLS,
        }

        for param in self.model_parameters:
            if isinstance(param, list) and len(param) == 2:
                key, value = param
                if value == "Delete":
                    if key in api_params:
                        del api_params[key]
                else:
                    api_params[key] = value

        return api_params

    def _show_context_stats(self, context_window_tokens: int):
        self.frontend.output(
            "info",
            f"📊 上下文窗口: {context_window_tokens / 1000} 千tokens "
            f"📊 输入token总量: {self.token_counter.total_stats['total_input_tokens']} tokens  "
            f"📊 输出token总量: {self.token_counter.total_stats['total_output_tokens']} tokens",
        )

    def _show_response_stats(self, output_tokens: int):
        self.frontend.output(
            "info",
            f"📊 本轮输出: {output_tokens} tokens",
        )
        self.frontend.output(
            "info",
            f"📊 输入token总量: {self.token_counter.total_stats['total_input_tokens']} tokens  "
            f"📊 输出token总量: {self.token_counter.total_stats['total_output_tokens']} tokens",
        )

    def _display_tool_params(self, function_name: str, function_args: dict) -> None:
        if not function_args:
            self.frontend.output("tool_progress", "    参数: (无)\n")
            return

        param_lines = []
        for key, value in function_args.items():
            value_str = str(value)
            param_lines.append(f"    • {key}: {value_str}")

        params_text = "\n".join(param_lines)
        self.frontend.output("tool_progress", f"    参数:\n{params_text}\n")

    def _execute_tool_calls(self, tool_calls: list) -> None:
        self.frontend.output("info", "\n工具参数接收完成，开始执行...")

        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            tool_call_id = tool_call["id"]

            try:
                function_args = json_repair.loads(tool_call["function"]["arguments"])
            except Exception as e:
                self.frontend.output(
                    "error",
                    f"工具参数解析失败：{tool_call['function']['arguments']} - {str(e)}",
                )
                continue

            if function_name not in TOOL_FUNCTIONS:
                error_msg = (
                    f"工具 '{function_name}' 不存在。"
                    f"请检查可用工具列表，使用存在的工具重新尝试。"
                )
                self.frontend.output("error", f"❌ 未找到工具函数：{function_name}")
                self.conversation_manager.add_tool_result(
                    tool_call_id, f"[错误] {error_msg}"
                )
                conversation_saver.save_conversation(
                    [self.conversation_manager.get_last_message()],
                    self.session_id,
                )
                self.token_counter.add_tool_result(error_msg)
                self.frontend.output(
                    "info",
                    f"📊 工具返回token量: {self.token_counter.count_tokens(error_msg)}",
                )
                continue

            try:
                self._display_tool_params(function_name, function_args)

                import inspect

                tool_func = TOOL_FUNCTIONS[function_name]
                sig = inspect.signature(tool_func)
                valid_params = list(sig.parameters.keys())
                filtered_args = {k: v for k, v in function_args.items() if k in valid_params}

                ignored_params = set(function_args.keys()) - set(filtered_args.keys())
                if ignored_params:
                    self.frontend.output(
                        "warning",
                        f"⚠️  工具 '{function_name}' 忽略了不支持的参数: {ignored_params}",
                    )

                function_response = tool_func(**filtered_args)

                if (
                    isinstance(function_response, dict)
                    and function_response.get("type") == "image"
                ):
                    image_data = function_response.get("data", "")
                    filename = function_response.get("filename", "image")
                    mime_type = function_response.get("mime_type", "image/jpeg")
                    size = function_response.get("size", 0)
                    text_content = f"图像文件: {filename} ({mime_type}, {size} bytes)"

                    self.conversation_manager.add_tool_result_with_image(
                        tool_call_id,
                        text_content,
                        image_data,
                    )
                    conversation_saver.save_conversation(
                        [self.conversation_manager.get_last_message()],
                        self.session_id,
                    )

                    self.frontend.output("tool_result", f"[图像] {text_content}")
                    self.frontend.output("info", "📊 图像已添加到对话上下文")

                    self.token_counter.add_tool_result(text_content)
                    self.frontend.output(
                        "info",
                        f"📊 工具返回token量: {self.token_counter.count_tokens(text_content)}",
                    )
                    continue

                if (
                    isinstance(function_response, dict)
                    and function_response.get("type") == "error"
                ):
                    error_message = function_response.get("message", "未知错误")
                    self.conversation_manager.add_tool_result(
                        tool_call_id,
                        f"[错误] {error_message}",
                    )
                    conversation_saver.save_conversation(
                        [self.conversation_manager.get_last_message()],
                        self.session_id,
                    )

                    self.frontend.output("tool_result", f"[错误] {error_message}")
                    self.token_counter.add_tool_result(error_message)
                    self.frontend.output(
                        "info",
                        f"📊 工具返回token量: {self.token_counter.count_tokens(error_message)}",
                    )
                    continue

                if (
                    isinstance(function_response, dict)
                    and function_response.get("type") == "overflow"
                ):
                    content = function_response.get("content", "")
                    url = function_response.get("url", "")
                    title = function_response.get("title", "")
                    source_type = function_response.get("source_type", "网页内容")

                    temp_path = self._create_managed_temp_file(content, url=url)
                    response_str = build_overflow_message(
                        file_path=temp_path,
                        total_chars=len(content),
                        url=url,
                        title=title,
                        source_type=source_type,
                    )

                    self.conversation_manager.add_tool_result(tool_call_id, response_str)
                    conversation_saver.save_conversation(
                        [self.conversation_manager.get_last_message()],
                        self.session_id,
                    )

                    self.frontend.output("tool_result", response_str)
                    self.token_counter.add_tool_result(response_str)
                    self.frontend.output(
                        "info",
                        f"📊 工具返回token量: {self.token_counter.count_tokens(response_str)}",
                    )
                    continue

                response_str = str(function_response)
                self.conversation_manager.add_tool_result(tool_call_id, response_str)
                conversation_saver.save_conversation(
                    [self.conversation_manager.get_last_message()],
                    self.session_id,
                )

                self.frontend.output("tool_result", response_str)
                self.token_counter.add_tool_result(response_str)
                self.frontend.output(
                    "info",
                    f"📊 工具返回token量: {self.token_counter.count_tokens(response_str)}",
                )

            except Exception as e:
                self.frontend.output("error", f"❌ 工具执行失败：{function_name} - {str(e)}")
                self.conversation_manager.add_tool_result(tool_call_id, f"[错误] {str(e)}")
                conversation_saver.save_conversation(
                    [self.conversation_manager.get_last_message()],
                    self.session_id,
                )
                self.token_counter.add_tool_result(str(e))
                self.frontend.output(
                    "info",
                    f"📊 工具返回token量: {self.token_counter.count_tokens(str(e))}",
                )

        self.frontend.output(
            "info",
            f"📊 本轮工具返回累计: {self.token_counter.current_round_stats['tool_result_tokens']} tokens",
        )
