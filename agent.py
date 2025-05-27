from openai import OpenAI
import sys
import json
from typing import Callable, Tuple
from tools import TOOL_FUNCTIONS, TOOLS

class Agent:
    def __init__(self, client: OpenAI, get_user_message: Callable[[], Tuple[str, bool]], system_prompt: str):
        self.client = client
        self.get_user_message = get_user_message
        self.messages = [{"role": "system", "content": system_prompt}]

    def save_conversation(self):
        """保存当前对话记录到文件（追加模式）"""
        # 提取当前对话记录
        new_conversations = []
        for i in range(1, len(self.messages), 2):  # 跳过系统提示
            if i + 1 < len(self.messages):
                user_input = self.messages[i]["content"]
                ai_response = self.messages[i + 1]["content"]
                new_conversations.append({"user_input": user_input, "ai_response": ai_response})

        # 读取现有记录（如果文件存在）
        try:
            with open("conversation_memory.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_conversations = existing_data.get("conversations", [])
        except (FileNotFoundError, json.JSONDecodeError):
            existing_conversations = []  # 文件不存在或为空时初始化空列表

        # 合并新旧记录
        updated_conversations = existing_conversations + new_conversations

        # 保存更新后的记录
        with open("conversation_memory.json", "w", encoding="utf-8") as f:
            json.dump({"conversations": updated_conversations}, f, ensure_ascii=False, indent=2)

    def run(self):
        try:
            print("对话开始，输入‘退出’结束对话")
            while True:
                # 保存当前对话记录
                self.save_conversation()

                # 获取用户输入
                user_input, has_input = self.get_user_message()
                if not has_input or user_input.lower() == '退出':
                    break
                self.messages.append({"role": "user", "content": user_input})

                print()

                while True:
                    full_response = ""
                    tool_calls_cache = {}
                    tool_calls = None
                    reasoning_content = ""
                    is_first_reasoning_chunk = True
                    is_first_chat_chunk = True

                    stream = self.client.chat.completions.create(
                        model="doubao-1-5-thinking-pro-250415",
                        messages=self.messages,
                        stream=True,
                        tools=TOOLS,
                        tool_choice="auto"
                    )

                    for chunk in stream:
                        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                            if is_first_reasoning_chunk:
                                print("<think>")
                                is_first_reasoning_chunk = False
                            reasoning_content += chunk.choices[0].delta.reasoning_content
                            sys.stdout.write(chunk.choices[0].delta.reasoning_content)
                            sys.stdout.flush()


                        elif chunk.choices[0].delta.content:
                            if is_first_chat_chunk and not is_first_reasoning_chunk:
                                print("</think>")
                                is_first_chat_chunk = False
                            chunk_content = chunk.choices[0].delta.content
                            full_response += chunk_content
                            sys.stdout.write(chunk_content)
                            sys.stdout.flush()

                        tool_calls = getattr(chunk.choices[0].delta, 'tool_calls', None)
                        if tool_calls is not None:
                            for tool_chunk in tool_calls if tool_calls else []:
                                if tool_chunk.index not in tool_calls_cache:
                                    tool_calls_cache[tool_chunk.index] = {
                                        'id': '',
                                        'function': {'name': '', 'arguments': ''}
                                    }
                                if tool_chunk.id:
                                    tool_calls_cache[tool_chunk.index]['id'] = tool_chunk.id
                                if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                    tool_calls_cache[tool_chunk.index]['function']['name'] = tool_chunk.function.name
                                if hasattr(tool_chunk.function, 'arguments') and tool_chunk.function.arguments:
                                    tool_calls_cache[tool_chunk.index]['function']['arguments'] += tool_chunk.function.arguments
                    print()

                    if full_response:
                        self.messages.append({"role": "assistant", "content": full_response})

                    if tool_calls_cache:
                        tool_calls = list(tool_calls_cache.values())
                        self.messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    'id': tool_call['id'],
                                    'type': 'function',
                                    'function': {
                                        'name': tool_call['function']['name'],
                                        'arguments': tool_call['function']['arguments']
                                    }
                                } for tool_call in tool_calls
                            ]
                        })
                        for tool_call in tool_calls:
                            function_name = tool_call['function']['name']
                            try:
                                function_args = json.loads(tool_call['function']['arguments'])
                            except json.JSONDecodeError:
                                print(f"工具参数解析失败：{tool_call['function']['arguments']}")
                                continue

                            if function_name in TOOL_FUNCTIONS:
                                print(f"工具调用中：{function_name}")
                                function_response = TOOL_FUNCTIONS[function_name](**function_args)
                                self.messages.append({
                                    "role": "tool",
                                    "content": str(function_response),
                                    "tool_call_id": tool_call['id']
                                })
                            else:
                                print(f"未找到工具函数：{function_name}")
                    else:
                        break

        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            # 最终保存一次对话记录
            self.save_conversation()