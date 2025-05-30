from openai import OpenAI
import sys
import json
from typing import Callable, Tuple
from tools import TOOL_FUNCTIONS, TOOLS

class Agent:
    def __init__(
        self, 
        client: OpenAI, 
        get_user_message: Callable[[], Tuple[str, bool]], 
        system_prompt: str, 
        model_name: str = "doubao-1-5-thinking-pro-250415"
    ):
        self.client = client
        self.get_user_message = get_user_message
        self.messages = [{"role": "system", "content": system_prompt}]
        self.model_name = model_name  
        self.thinking_memory = []  # 存储思考内容
        self.tool_call_memory = []  # 存储工具调用信息
        self.last_saved_user_count = 0  # 记录上次保存时的用户消息数量

    def save_conversation(self):
        # 获取当前所有用户输入的消息索引
        user_message_indices = [idx for idx, msg in enumerate(self.messages) if msg["role"] == "user"]
        current_user_count = len(user_message_indices)
        added_count = current_user_count - self.last_saved_user_count

        if added_count <= 0:
            return  # 没有新增用户输入，无需保存

        new_conversations = []
        # 只处理新增的用户输入（最后added_count个）
        for conv_idx in range(self.last_saved_user_count, current_user_count):
            user_msg_idx = user_message_indices[conv_idx]
            # 获取用户输入内容
            user_input = self.messages[user_msg_idx]["content"]
            
            # 查找该用户输入对应的AI响应（最近的assistant角色且包含content的消息）
            ai_response = ""
            # 从用户输入的下一条消息开始查找
            for ai_msg_idx in range(user_msg_idx + 1, len(self.messages)):
                msg = self.messages[ai_msg_idx]
                if msg["role"] == "assistant" and "content" in msg:
                    ai_response = msg["content"]
                    break  # 找到第一个有效AI响应后停止
            
            # 获取对应轮次的思考内容和工具调用信息（按对话顺序索引）
            thinking = self.thinking_memory[conv_idx] if conv_idx < len(self.thinking_memory) else ""
            tool_calls = self.tool_call_memory[conv_idx] if conv_idx < len(self.tool_call_memory) else []
            
            new_conversations.append({
                "user_input": user_input,
                "ai_response": ai_response,
                "thinking": thinking,
                "tool_calls": tool_calls
            })

        try:
            with open("conversation_memory.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_conversations = existing_data.get("conversations", [])
        except (FileNotFoundError, json.JSONDecodeError):
            existing_conversations = []

        updated_conversations = existing_conversations + new_conversations
        with open("conversation_memory.json", "w", encoding="utf-8") as f:
            json.dump({"conversations": updated_conversations}, f, ensure_ascii=False, indent=2)

        # 更新上次保存的用户消息数量
        self.last_saved_user_count = current_user_count

    def run(self):
        try:
            print("\n对话开始，输入‘退出’结束对话")
            while True:
                self.save_conversation()

                user_input, has_input = self.get_user_message()
                if not has_input or user_input.lower() == '退出':
                    break
                self.messages.append({"role": "user", "content": user_input})

                print()

                # 初始化当前轮次的思考内容和工具调用缓存
                current_reasoning = ""
                current_tool_calls = {}

                while True:
                    full_response = ""
                    tool_calls_cache = {}
                    tool_calls = None
                    reasoning_content = ""
                    is_first_reasoning_chunk = True
                    is_first_chat_chunk = True

                    stream = self.client.chat.completions.create(
                        model=self.model_name,
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
                        if tool_calls is not None and not is_first_chat_chunk:
                            for tool_chunk in tool_calls if tool_calls else []:
                                if tool_chunk.index not in tool_calls_cache:
                                    tool_calls_cache[tool_chunk.index] = {
                                        'id': '',
                                        'function': {'name': '', 'arguments': ''}
                                    }
                                    # 首次检测到工具调用时立即提示
                                    if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                        print(f"\n检测到工具调用：{tool_chunk.function.name}")

                                # 更新工具ID
                                if tool_chunk.id:
                                    tool_calls_cache[tool_chunk.index]['id'] = tool_chunk.id

                                # 更新工具名称（可能分块返回）
                                if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                    tool_calls_cache[tool_chunk.index]['function']['name'] = tool_chunk.function.name

                                # 更新工具参数并显示进度
                                if hasattr(tool_chunk.function, 'arguments') and tool_chunk.function.arguments:
                                    tool_calls_cache[tool_chunk.index]['function']['arguments'] += tool_chunk.function.arguments
                                    # 显示参数接收进度（避免频繁输出）
                                    if len(tool_calls_cache[tool_chunk.index]['function']['arguments']) % 50 == 0:
                                        sys.stdout.write(".")
                                        sys.stdout.flush()

                    # 结束参数接收提示
                    if tool_calls_cache:
                        print("\n工具参数接收完成，开始执行...")

                    # 记录当前轮次的思考内容
                    current_reasoning += reasoning_content

                    if full_response:
                        self.messages.append({"role": "assistant", "content": full_response})

                    if tool_calls_cache:
                        # 记录工具调用信息
                        current_tool_calls.update(tool_calls_cache)
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
                                } for tool_call in tool_calls_cache.values()
                            ]
                        })
                        for tool_call in tool_calls_cache.values():
                            function_name = tool_call['function']['name']
                            try:
                                function_args = json.loads(tool_call['function']['arguments'])
                            except json.JSONDecodeError:
                                print(f"工具参数解析失败：{tool_call['function']['arguments']}")
                                continue

                            if function_name in TOOL_FUNCTIONS:
                                function_response = TOOL_FUNCTIONS[function_name](**function_args)
                                self.messages.append({
                                    "role": "tool",
                                    "content": str(function_response),
                                    "tool_call_id": tool_call['id']
                                })
                            else:
                                print(f"未找到工具函数：{function_name}")
                    else:
                        # 没有工具调用时结束当前轮次处理
                        break

                    # 清空参数进度提示
                    sys.stdout.write("\n")

                # 轮次结束时保存思考内容和工具调用信息
                self.thinking_memory.append(current_reasoning)
                self.tool_call_memory.append(list(current_tool_calls.values()))
                sys.stdout.write("\n")

        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            self.save_conversation()
