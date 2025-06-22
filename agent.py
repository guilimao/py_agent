from openai import OpenAI
import sys
import json
from typing import Callable, Tuple
from frontends import FrontendInterface
import os
from tools import TOOL_FUNCTIONS, TOOLS

class Agent:
    def __init__(
        self, 
        client: OpenAI, 
        frontend: FrontendInterface, 
        system_prompt: str, 
        model_name: str = "qwen3-235b-a22b"
    ):
        self.client = client
        self.frontend = frontend
        self.messages = [{"role": "system", "content": system_prompt}]
        self.model_name = model_name  

    def save_conversation(self):
        """保存所有对话消息到文件（包括用户输入、LLM输出、工具返回）"""
        conversations = []
        for msg in self.messages:
            conv = {
                "role": msg["role"],
                "thinking": msg.get("thinking"),
                "content": msg.get("content"),
            }
            # 添加工具调用信息（仅assistant角色有）
            if "tool_calls" in msg:
                conv["tool_calls"] = msg["tool_calls"]
            # 添加思考过程（仅assistant角色有）
            if "thinking" in msg:
                conv["thinking"] = msg["thinking"]
            # 添加工具调用ID（仅tool角色有）
            if "tool_call_id" in msg:
                conv["tool_call_id"] = msg["tool_call_id"]
            conversations.append(conv)
        
        # 保存对话历史到config/conversation_memory.json
        os.makedirs("config", exist_ok=True)
        with open("config/conversation_memory.json", "w", encoding="utf-8") as f:
            json.dump({"conversations": conversations}, f, ensure_ascii=False, indent=2)

    def run(self):
        try:
            self.frontend.start_session()
            self.frontend.output('info', "\n对话开始，输入‘退出’结束对话")
            while True:
                # 获取用户输入
                user_input, has_input = self.frontend.get_input()
                if not has_input or user_input.lower() == '退出':
                    break
                # 添加用户输入到对话上下文
                self.messages.append({"role": "user", "content": user_input})
                self.save_conversation()

                self.frontend.output('info', "")

                while True:
                    full_response = ""  # LLM自然语言输出
                    tool_calls_cache = {}  # 工具调用缓存
                    reasoning_content = ""  # LLM思考过程

                    # 状态标志
                    has_received_reasoning = False
                    has_received_chat_content = False

                    # 调用LLM生成响应（流式）
                    stream = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=self.messages,
                        stream=True,
                        tools=TOOLS,
                        tool_choice="auto",
                        extra_body={"enable_thinking": True if "qwen" in self.model_name.lower() else False}
                    )

                    for chunk in stream:
                        # 处理思考过程（思维链）
                        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                            if not has_received_reasoning:
                                has_received_reasoning = True
                            reasoning_content += chunk.choices[0].delta.reasoning_content
                            self.frontend.output('thinking', chunk.choices[0].delta.reasoning_content)

                        # 处理自然语言内容
                        elif chunk.choices[0].delta.content:
                            if has_received_reasoning and not has_received_chat_content:
                                # 思考模式结束，恢复默认颜色
                                has_received_chat_content = True
                            
                            if has_received_chat_content:
                                chunk_content = chunk.choices[0].delta.content
                                full_response += chunk_content
                                self.frontend.output('content', chunk_content)

                        # 处理工具调用
                        tool_calls = getattr(chunk.choices[0].delta, 'tool_calls', None)
                        if tool_calls is not None:
                            for tool_chunk in tool_calls if tool_calls else []:
                                if tool_chunk.index not in tool_calls_cache:
                                    tool_calls_cache[tool_chunk.index] = {
                                        'id': '',
                                        'function': {'name': '', 'arguments': ''}
                                    }
                                    # 首次检测到工具调用时提示
                                    if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                        self.frontend.output('tool_call', tool_chunk.function.name)

                                # 更新工具ID、名称、参数
                                if tool_chunk.id:
                                    tool_calls_cache[tool_chunk.index]['id'] = tool_chunk.id
                                if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                                    tool_calls_cache[tool_chunk.index]['function']['name'] = tool_chunk.function.name
                                if hasattr(tool_chunk.function, 'arguments') and tool_chunk.function.arguments:
                                    tool_calls_cache[tool_chunk.index]['function']['arguments'] += tool_chunk.function.arguments
                                    # 显示参数接收进度（每50字符一个点）
                                    if len(tool_calls_cache[tool_chunk.index]['function']['arguments']) % 50 == 0:
                                        self.frontend.output('tool_progress', ".")

                    # 处理自然语言输出（若有）
                    if full_response:
                        self.messages.append({
                            "role": "assistant",
                            "content": full_response,
                            "thinking": reasoning_content  # 保存思考过程
                        })
                        self.save_conversation()

                    # 处理工具调用（若有）
                    if tool_calls_cache:
                        self.frontend.output('info', "\n工具参数接收完成，开始执行...")
                        # 添加工具调用指令到对话上下文
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
                            ],
                            "thinking": reasoning_content  # 保存思考过程
                        })
                        self.save_conversation()

                        # 执行工具并记录结果
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
                                    # 添加工具返回结果到对话上下文
                                    self.messages.append({
                                        "role": "tool",
                                        "content": str(function_response),
                                        "tool_call_id": tool_call['id']
                                    })
                                    self.save_conversation()
                                    self.frontend.output('tool_result', f"工具执行成功：{function_name}", result=function_response)
                                except Exception as e:
                                    self.frontend.output('error', f"工具执行失败：{function_name} - {str(e)}")
                            else:
                                self.frontend.output('error', f"未找到工具函数：{function_name}")
                    else:
                        # 无工具调用时结束当前轮次
                        break

                    self.frontend.output('info', "\n")

                self.frontend.output('info', "\n")

        except Exception as e:
            self.frontend.output('error', f"发生错误: {str(e)}")
        finally:
            # 程序结束时恢复终端颜色为默认值
            self.frontend.end_session()
            # 程序结束时保存最后一次对话
            self.save_conversation()