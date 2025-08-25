from openai import OpenAI
from .frontends import FrontendInterface
from .tools import TOOL_FUNCTIONS, TOOLS
from .token_counter import TokenCounter
from .frontends.image_handler import ImageHandler
from . import conversation_saver
from .context_compressor import ContextCompressor
import json_repair


class Agent:
    def __init__(
        self, 
        client: OpenAI, 
        frontend: FrontendInterface, 
        system_prompt: str, 
        model_name: str
    ):
        self.client = client
        self.frontend = frontend
        self.messages = [{"role": "system", "content": system_prompt}]
        self.model_name = model_name
        self.token_counter = TokenCounter(model_name)
        self.context_compressor = ContextCompressor(keep_recent_rounds=2)
        
        # 设置系统初始token（系统提示+工具定义）
        from .tools import TOOLS
        self.token_counter.set_initial_tokens(system_prompt, TOOLS)  


    def filter_thinking_field(self, messages):
        """过滤掉消息列表中的thinking字段"""
        filtered_messages = []
        for message in messages:
            new_message = message.copy()
            new_message.pop("thinking", None)
            
            # 处理content为列表的情况
            if isinstance(new_message.get("content"), list):
                # 保留content列表，但确保没有thinking字段
                pass
            elif isinstance(new_message.get("content"), str):
                # 字符串内容保持不变
                pass
            
            filtered_messages.append(new_message)
        return filtered_messages

    def run(self):
        try:
            self.frontend.start_session()
            while True:
                # 获取用户输入
                user_input, has_input = self.frontend.get_input()
                if not has_input or user_input.lower() == '退出':
                    break
                
                # 处理用户输入，提取图像
                clean_text, content_parts = ImageHandler.process_user_input(user_input)
                
                # 开始新一轮token统计
                self.token_counter.start_new_round()
                
                # 计算文本内容的token（如果有）
                if clean_text:
                    self.token_counter.add_user_input(clean_text)
                else:
                    # 只有图像的情况，计算一个基础token数
                    self.token_counter.add_user_input("[图像输入]")
                
                # 添加用户输入到对话上下文
                if content_parts:
                    # 使用content列表格式（包含文本和图像）
                    self.messages.append({"role": "user", "content": content_parts})
                else:
                    # 回退到纯文本格式
                    self.messages.append({"role": "user", "content": clean_text or "请分析上传的图像"})
                
                conversation_saver.save_conversation(self.messages)

                # 更新总token统计（使用全量计算）
                self.token_counter.update_total_stats(self.messages)
                
                # 显示用户输入后的token统计
                self.frontend.output('info', f"{self.token_counter.get_total_summary()}")

                while True:
                    full_response = ""  # LLM自然语言输出
                    tool_calls_cache = {}  # 工具调用缓存
                    reasoning_content = ""  # LLM思考过程

                    # 状态标志
                    has_received_reasoning = False

                    # 过滤掉thinking字段
                    filtered_messages = self.filter_thinking_field(self.messages)
                    
                    # 压缩上下文以节省token
                    compressed_messages = self.context_compressor.compress_context(filtered_messages)
                    
                    # 获取压缩统计信息
                    if len(filtered_messages) > 4:  # 只有消息足够多才显示压缩信息
                        stats = self.context_compressor.get_compression_stats(filtered_messages, compressed_messages)
                        if stats["saved_chars"] > 0:
                            self.frontend.output('info', f"上下文压缩: 节省 {stats['saved_chars']} 字符 ({stats['compression_ratio']}%)")

                    # 调用LLM生成响应（流式）
                    stream = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=compressed_messages,
                        stream=True,
                        tools=TOOLS,
                        tool_choice="auto",
                        max_tokens=16300,
                    #    extra_body={"enable_thinking": True if "qwen" in self.model_name.lower() else False}
                    )

                    finish_reason = None
                    for chunk in stream:
                        # 获取finish_reason
                        if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason

                        # 处理思考过程（思维链）
                        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                            if not has_received_reasoning:
                                has_received_reasoning = True
                            reasoning_content += chunk.choices[0].delta.reasoning_content
                            self.frontend.output('thinking', chunk.choices[0].delta.reasoning_content)

                        # 处理自然语言内容
                        elif chunk.choices[0].delta.content:
                            # 无论是否处于思考模式都直接输出内容
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

                    # 输出结束信息
                    if finish_reason:
                        self.frontend.output('end', f"\n[Stream结束] 完成原因: {finish_reason}")

                    # 处理自然语言输出（若有）
                    if full_response:
                        self.messages.append({
                            "role": "assistant",
                            "content": full_response,
                            "thinking": reasoning_content  # 保存思考过程
                        })
                        conversation_saver.save_conversation(self.messages)
                        
                        # 统计LLM输出token（思维链+自然语言）
                        self.token_counter.add_llm_output(
                            thinking=reasoning_content,
                            content=full_response
                        )
                        
                        # 更新总token统计（使用全量计算）
                        self.token_counter.update_total_stats(self.messages)
                        
                        # 显示LLM输出后的token统计
                        self.frontend.output('info', f"{self.token_counter.get_total_summary()}")

                    # 处理工具调用（若有）
                    if tool_calls_cache:
                        self.frontend.output('info', "\n工具参数接收完成，开始执行...")
                        
                        # 统计工具调用token
                        tool_calls_list = [
                            {
                                'id': tool_call['id'],
                                'type': 'function',
                                'function': {
                                    'name': tool_call['function']['name'],
                                    'arguments': tool_call['function']['arguments']
                                }
                            } for tool_call in tool_calls_cache.values()
                        ]
                        
                        # 添加工具调用token统计（如果还没有统计过思维链）
                        if not full_response:  # 只有工具调用，没有自然语言输出
                            self.token_counter.add_llm_output(
                                thinking=reasoning_content,
                                tool_calls=tool_calls_list
                            )
                        else:  # 已经有自然语言输出，只统计工具调用
                            self.token_counter.add_llm_output(
                                tool_calls=tool_calls_list
                            )
                        
                        # 更新总token统计（使用全量计算）
                        self.token_counter.update_total_stats(self.messages)
                        
                        # 添加工具调用指令到对话上下文
                        self.messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": tool_calls_list,
                            "thinking": reasoning_content  # 保存思考过程
                        })
                        conversation_saver.save_conversation(self.messages)

                        # 执行工具并记录结果
                        for tool_call in tool_calls_cache.values():
                            function_name = tool_call['function']['name']
                            try:
                                function_args = json_repair.loads(tool_call['function']['arguments'])
                            except Exception as e:
                                self.frontend.output("error", f"工具参数解析失败：{tool_call['function']['arguments']} - {str(e)}")
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
                                    conversation_saver.save_conversation(self.messages)
                                    
                                    # 统计工具返回结果的token
                                    self.token_counter.add_tool_result(str(function_response))
                                    self.frontend.output("tool_result",f"{function_response}")
                                    
                                    # 更新总token统计（使用全量计算）
                                    self.token_counter.update_total_stats(self.messages)
                                    
                                    # 显示工具返回后的token统计
                                    self.frontend.output('info', f"{self.token_counter.get_current_operation_summary('tool_result')}")
                                    self.frontend.output('info', f"{self.token_counter.get_total_summary()}")
                                except Exception as e:
                                    self.frontend.output('error', f"❌ 工具执行失败：{function_name} - {str(e)}")
                            else:
                                self.frontend.output('error', f"❌ 未找到工具函数：{function_name}")
                    else:
                        # 无工具调用时结束当前轮次
                        break

                    self.frontend.output('info', "\n")

                # 完成当前轮次token统计
                self.token_counter.finish_round()
                
                self.frontend.output('info', "\n")

        except Exception as e:
            self.frontend.output('error', f"发生错误: {str(e)}")
        finally:
            # 程序结束时恢复终端颜色为默认值
            self.frontend.end_session()
            # 程序结束时保存最后一次对话
            conversation_saver.save_conversation(self.messages)