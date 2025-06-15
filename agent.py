from openai import OpenAI
import sys
import json
from typing import Callable, Tuple
import os
from tools import TOOL_FUNCTIONS, TOOLS

class Agent:
    def __init__(
        self, 
        client: OpenAI, 
        get_user_message: Callable[[], Tuple[str, bool]], 
        system_prompt: str, 
        model_name: str = "doubao-seed-1-6-thinking-250615"
    ):
        self.client = client
        self.get_user_message = get_user_message
        self.messages = [{"role": "system", "content": system_prompt}]
        self.model_name = model_name  
        self.thinking_memory = []  # 存储思考内容
        self.tool_call_memory = []  # 存储工具调用信息（包含response）
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

        # 保存对话历史到conversation_memory.json
        os.makedirs("config", exist_ok=True)
        try:
            with open("config/conversation_memory.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_conversations = existing_data.get("conversations", [])
        except (FileNotFoundError, json.JSONDecodeError):
            existing_conversations = []

        updated_conversations = existing_conversations + new_conversations
        with open("config/conversation_memory.json", "w", encoding="utf-8") as f:
            json.dump({"conversations": updated_conversations}, f, ensure_ascii=False, indent=2)

        # 新增：处理字数统计
        try:
            with open("config/word_count.json", "r", encoding="utf-8") as f:
                word_count_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            word_count_data = {
                "total_user_input": 0,
                "total_ai_response": 0,
                "total_tool_response": 0,
                "conversations": []
            }

        # 遍历新增的对话，更新字数统计
        for conv in new_conversations:
            # 计算当前轮次的各部分字数
            user_len = len(conv["user_input"])
            ai_len = len(conv["ai_response"])
            # 工具返回字数：累加所有工具调用的response长度
            tool_len = sum(len(tool_call.get("response", "")) for tool_call in conv["tool_calls"])
            
            # 更新总字数
            word_count_data["total_user_input"] += user_len
            word_count_data["total_ai_response"] += ai_len
            word_count_data["total_tool_response"] += tool_len
            
            # 添加当前轮次的统计到列表
            word_count_data["conversations"].append({
                "user_input_length": user_len,
                "ai_response_length": ai_len,
                "tool_response_length": tool_len
            })

        # 保存字数统计到文件
        with open("config/word_count.json", "w", encoding="utf-8") as f:
            json.dump(word_count_data, f, ensure_ascii=False, indent=2)

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
                    
                    # 使用更可靠的状态标志
                    has_received_reasoning = False
                    has_received_chat_content = False
                    has_received_tool_calls = False

                    stream = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=self.messages,
                        stream=True,
                        tools=TOOLS,
                        tool_choice="auto"
                    )

                    for chunk in stream:
                        # 处理思维链输出
                        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                            if not has_received_reasoning:
                                print("\n\033[90m思考过程：")
                                has_received_reasoning = True
                            reasoning_content += chunk.choices[0].delta.reasoning_content
                            sys.stdout.write(chunk.choices[0].delta.reasoning_content)
                            sys.stdout.flush()

                        # 处理普通聊天内容
                        elif chunk.choices[0].delta.content:
                            if has_received_reasoning and not has_received_chat_content:
                                print("\033[0m")  # 恢复默认颜色
                            has_received_chat_content = True
                            chunk_content = chunk.choices[0].delta.content
                            full_response += chunk_content
                            sys.stdout.write(chunk_content)
                            sys.stdout.flush()

                        # 处理工具调用 - 现在无论是否收到聊天内容都处理
                        tool_calls = getattr(chunk.choices[0].delta, 'tool_calls', None)
                        if tool_calls is not None:
                            has_received_tool_calls = True
                            for tool_chunk in tool_calls if tool_calls else []:
                                if tool_chunk.index not in tool_calls_cache:
                                    tool_calls_cache[tool_chunk.index] = {
                                        'id': '',
                                        'function': {'name': '', 'arguments': ''},
                                        'response': ''  # 新增：存储工具返回结果
                                    }
                                    # 首次检测到工具调用时立即提示
                                    if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                        print(f"\n\033[94m检测到工具调用：{tool_chunk.function.name}\033[0m")

                                # 更新工具ID
                                if tool_chunk.id:
                                    tool_calls_cache[tool_chunk.index]['id'] = tool_chunk.id

                                # 更新工具名称（可能分块返回）
                                if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                    tool_calls_cache[tool_chunk.index]['function']['name'] = tool_chunk.function.name

                                # 更新工具参数并显示进度
                                if hasattr(tool_chunk.function, 'arguments') and tool_chunk.function.arguments:
                                    tool_calls_cache[tool_chunk.index]['function']['arguments'] += tool_chunk.function.arguments
                                    # 显示参数接收进度（每50字符显示一个点）
                                    if len(tool_calls_cache[tool_chunk.index]['function']['arguments']) % 50 == 0:
                                        sys.stdout.write(".")
                                        sys.stdout.flush()

                    # 如果只有思维链没有聊天内容，需要关闭颜色并换行
                    if has_received_reasoning and not has_received_chat_content:
                        print("\033[0m")

                    # 结束参数接收提示
                    if tool_calls_cache:
                        print("\n工具参数接收完成，开始执行...")

                    # 记录当前轮次的思考内容
                    current_reasoning += reasoning_content

                    if full_response:
                        self.messages.append({"role": "assistant", "content": full_response})

                    # 处理工具调用 - 现在只要检测到工具调用就处理
                    if tool_calls_cache:
                        # 记录工具调用信息（包含response字段）
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
                                print(f"\033[91m工具参数解析失败：{tool_call['function']['arguments']}\033[0m")
                                continue

                            if function_name in TOOL_FUNCTIONS:
                                try:
                                    function_response = TOOL_FUNCTIONS[function_name](**function_args)
                                    # 新增：存储工具返回结果到tool_call字典
                                    tool_call['response'] = str(function_response)
                                    self.messages.append({
                                        "role": "tool",
                                        "content": str(function_response),
                                        "tool_call_id": tool_call['id']
                                    })
                                    print(f"\n\033[92m工具执行成功：{function_name}\033[0m")
                                    print(f"\033[90m工具返回结果：{function_response}\033[0m")
                                except Exception as e:
                                    print(f"\033[91m工具执行失败：{function_name} - {str(e)}\033[0m")
                            else:
                                print(f"\033[91m未找到工具函数：{function_name}\033[0m")
                    else:
                        # 没有工具调用时结束当前轮次处理
                        break

                    # 清空参数进度提示
                    sys.stdout.write("\n")

                # 轮次结束时保存思考内容和工具调用信息（包含response）
                self.thinking_memory.append(current_reasoning)
                self.tool_call_memory.append(list(current_tool_calls.values()))
                sys.stdout.write("\n")

        except Exception as e:
            print(f"\033[91m发生错误: {str(e)}\033[0m")
        finally:
            self.save_conversation()
