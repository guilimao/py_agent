"""
Conversation state and stream event handling.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: Optional[str] = None
    content_parts: Optional[List[Dict[str, Any]]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    thinking: Optional[str] = None
    timestamp: Optional[str] = None

    def _base_dict(self) -> Dict[str, Any]:
        result = {"role": self.role.value}

        if self.content_parts:
            result["content"] = self.content_parts
        elif self.content is not None:
            result["content"] = self.content

        if self.tool_calls:
            result["tool_calls"] = self.tool_calls

        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        return result

    def to_dict(self) -> Dict[str, Any]:
        result = self._base_dict()

        # Keep the original storage format for local history and viewer pages.
        if self.role == MessageRole.ASSISTANT:
            result["thinking"] = self.thinking if self.thinking is not None else ""
        elif self.thinking is not None:
            result["thinking"] = self.thinking

        if self.timestamp:
            result["timestamp"] = self.timestamp

        return result

    def to_sdk_dict(self) -> Dict[str, Any]:
        result = self._base_dict()

        if self.role == MessageRole.ASSISTANT:
            # Reasoning models such as DeepSeek require reasoning_content to be
            # sent back on later turns, including assistant tool-call messages
            # whose reasoning text is empty.
            result["reasoning_content"] = self.thinking if self.thinking is not None else ""
        elif self.thinking is not None:
            result["thinking"] = self.thinking

        return result


@dataclass
class StreamEvent:
    event_type: str
    data: Any
    metadata: Optional[Dict[str, Any]] = None


class ConversationManager:
    def __init__(self, system_prompt: str):
        self.messages: List[Message] = []
        self.system_prompt = system_prompt
        self._add_system_message(system_prompt)

    def _add_system_message(self, content: str):
        self.messages.append(
            Message(
                role=MessageRole.SYSTEM,
                content=content,
                timestamp=datetime.now().isoformat(),
            )
        )

    def add_user_message(self, content: str, content_parts: Optional[List[Dict[str, Any]]] = None):
        if content_parts:
            self.messages.append(
                Message(
                    role=MessageRole.USER,
                    content_parts=content_parts,
                    timestamp=datetime.now().isoformat(),
                )
            )
        else:
            self.messages.append(
                Message(
                    role=MessageRole.USER,
                    content=content,
                    timestamp=datetime.now().isoformat(),
                )
            )

    def add_assistant_message(
        self,
        content: str,
        thinking: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ):
        # Persist empty reasoning for assistant tool-call turns so it can be
        # round-tripped as reasoning_content on the next request.
        if thinking is None:
            thinking = ""

        self.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=content,
                thinking=thinking,
                tool_calls=tool_calls,
                timestamp=datetime.now().isoformat(),
            )
        )

    def add_tool_result(self, tool_call_id: str, content: str):
        self.messages.append(
            Message(
                role=MessageRole.TOOL,
                content=content,
                tool_call_id=tool_call_id,
                timestamp=datetime.now().isoformat(),
            )
        )

    def add_tool_result_with_image(self, tool_call_id: str, text_content: str, image_data_url: str):
        content_parts: List[Dict[str, Any]] = []

        if text_content:
            content_parts.append({"type": "text", "text": text_content})

        content_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": image_data_url},
            }
        )

        self.messages.append(
            Message(
                role=MessageRole.TOOL,
                content_parts=content_parts,
                tool_call_id=tool_call_id,
                timestamp=datetime.now().isoformat(),
            )
        )

    def get_messages_for_sdk(self) -> List[Dict[str, Any]]:
        return [msg.to_sdk_dict() for msg in self.messages]

    def get_last_message(self) -> Optional[Dict[str, Any]]:
        if not self.messages:
            return None
        return self.messages[-1].to_dict()

    def get_system_message(self) -> Optional[Dict[str, Any]]:
        if not self.messages:
            return None
        if self.messages[0].role == MessageRole.SYSTEM:
            return self.messages[0].to_dict()
        return None

    def get_last_n_messages(self, n: int) -> List[Dict[str, Any]]:
        if not self.messages:
            return []
        start_index = max(0, len(self.messages) - n)
        return [msg.to_dict() for msg in self.messages[start_index:]]

    def get_recent_messages(self, count: int) -> List[Message]:
        return self.messages[-count:] if len(self.messages) > count else self.messages

    def compress_context(self, keep_recent_rounds: int) -> List[Dict[str, Any]]:
        if keep_recent_rounds <= 0:
            return self.get_messages_for_sdk()

        system_msg = self.messages[0]
        recent_messages = self.get_recent_messages(keep_recent_rounds * 2)

        compressed = [system_msg]
        for msg in recent_messages:
            if msg not in compressed:
                compressed.append(msg)

        return [msg.to_sdk_dict() for msg in compressed]

    def clear(self):
        self.messages = [self.messages[0]]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_messages": len(self.messages),
            "user_messages": len([m for m in self.messages if m.role == MessageRole.USER]),
            "assistant_messages": len([m for m in self.messages if m.role == MessageRole.ASSISTANT]),
            "tool_messages": len([m for m in self.messages if m.role == MessageRole.TOOL]),
        }


class StreamResponseHandler:
    def __init__(self, frontend):
        self.frontend = frontend
        self.full_content = ""
        self.full_thinking = ""
        self.tool_calls_cache: Dict[int, Dict[str, Any]] = {}
        self.has_received_thinking = False
        self.finish_reason = None

    def handle_stream_event(self, event: StreamEvent):
        if event.event_type == "thinking":
            if not self.has_received_thinking:
                self.has_received_thinking = True
            thinking_content = event.data
            self.full_thinking += thinking_content
            self.frontend.output("thinking", thinking_content)

        elif event.event_type == "content":
            content = event.data
            self.full_content += content
            self.frontend.output("content", content)

        elif event.event_type == "tool_call":
            self._handle_tool_call_chunk(event.data)

        elif event.event_type == "finish":
            self.finish_reason = event.data
            self.frontend.output("end", f"\n[Stream结束] 完成原因: {event.data}")

    def _handle_tool_call_chunk(self, tool_chunk):
        if isinstance(tool_chunk, dict):
            tool_index = tool_chunk.get("index", 0)
            tool_id = tool_chunk.get("id", "")
            function_name = tool_chunk.get("function", {}).get("name", "")
            function_args = tool_chunk.get("function", {}).get("arguments", "")
        else:
            tool_index = getattr(tool_chunk, "index", 0)
            tool_id = getattr(tool_chunk, "id", "")
            function = getattr(tool_chunk, "function", None)
            function_name = getattr(function, "name", "") if function is not None else ""
            function_args = getattr(function, "arguments", "") if function is not None else ""

        if tool_index not in self.tool_calls_cache:
            self.tool_calls_cache[tool_index] = {
                "id": "",
                "function": {"name": "", "arguments": ""},
            }
            if function_name:
                self.frontend.output("tool_call", function_name)

        if tool_id:
            self.tool_calls_cache[tool_index]["id"] = tool_id
        elif function_name and not self.tool_calls_cache[tool_index]["id"]:
            import uuid

            self.tool_calls_cache[tool_index]["id"] = f"toolcall_{uuid.uuid4().hex[:8]}"

        if function_name:
            self.tool_calls_cache[tool_index]["function"]["name"] = function_name
        if function_args:
            self.tool_calls_cache[tool_index]["function"]["arguments"] += function_args
            if len(self.tool_calls_cache[tool_index]["function"]["arguments"]) % 50 == 0:
                self.frontend.output("tool_progress", ".")

    def get_result(self) -> Dict[str, Any]:
        return {
            "content": self.full_content,
            "thinking": self.full_thinking,
            "tool_calls": self._get_tool_calls_list(),
            "finish_reason": self.finish_reason,
            "has_content": bool(self.full_content),
            "has_thinking": bool(self.full_thinking),
            "has_tool_calls": bool(self.tool_calls_cache),
        }

    def _get_tool_calls_list(self) -> Optional[List[Dict[str, Any]]]:
        if not self.tool_calls_cache:
            return None

        sorted_tool_calls = sorted(self.tool_calls_cache.items(), key=lambda item: item[0])
        return [
            {
                "id": tool_call["id"],
                "type": "function",
                "function": {
                    "name": tool_call["function"]["name"],
                    "arguments": tool_call["function"]["arguments"],
                },
            }
            for _, tool_call in sorted_tool_calls
        ]
