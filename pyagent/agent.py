from .frontends import FrontendInterface
from .tools import TOOL_FUNCTIONS, TOOLS
from .token_counter import TokenCounter
from .frontends.image_handler import ImageHandler
from . import conversation_saver
from .context_compressor import ContextCompressor
from .llm_adapter import UnifiedLLMClient
from .conversation_manager import ConversationManager, StreamResponseHandler
import json_repair


class Agent:
    def __init__(
        self, 
        client: UnifiedLLMClient, 
        frontend: FrontendInterface, 
        system_prompt: str, 
        model_name: str,
        model_parameters: list = None
    ):
        self.client = client
        self.frontend = frontend
        self.conversation_manager = ConversationManager(system_prompt)
        self.model_name = model_name
        self.model_parameters = model_parameters or []
        self.token_counter = TokenCounter(model_name)
        self.context_compressor = ContextCompressor(keep_recent_rounds=2)
        
        # 设置系统初始token（系统提示+工具定义）
        from .tools import TOOLS
        self.token_counter.set_initial_tokens(system_prompt, TOOLS)
        
        # 保存系统消息到数据库（确保系统提示被存储）
        system_message = self.conversation_manager.get_system_message()
        if system_message:
            conversation_saver.save_conversation([system_message])

    def run(self):
        try:
            self.frontend.start_session()
            total_input_tokens = 0
            total_output_tokens = 0
            
            while True:
                # 获取用户输入
                user_input, has_input = self.frontend.get_input()
                if not has_input or user_input.lower() == '退出':
                    break
                
                # 处理用户输入，提取图像
                clean_text, content_parts = ImageHandler.process_user_input(user_input)
                
                # 统计图像数量
                image_count = len([part for part in content_parts if part.get("type") == "image_url"])
                
                # 添加用户输入到对话上下文
                self.conversation_manager.add_user_message(clean_text, content_parts)
                conversation_saver.save_conversation([self.conversation_manager.get_last_message()])

                # 计算输入token总数
                user_tokens = self.token_counter.count_tokens(clean_text)
                image_info = f" 已添加图像: {image_count}张" if image_count > 0 else ""
                self.frontend.output('info', f"📊 用户输入: {user_tokens} tokens{image_info}")
                
                # 处理对话循环（可能包含工具调用）
                self._process_conversation_round(total_input_tokens, total_output_tokens)

        except Exception as e:
            self.frontend.output('error', f"发生错误: {str(e)}")
        finally:
            # 程序结束时恢复终端颜色为默认值
            self.frontend.end_session()

    def _process_conversation_round(self, total_input_tokens: int, total_output_tokens: int):
        """处理一轮对话（可能包含多个工具调用）"""
        tool_result_tokens = 0
        
        while True:
            # 获取完整的对话上下文（不再压缩）
            messages = self.conversation_manager.get_messages_for_sdk()
            
            # 计算本次请求的上下文窗口token量
            context_window_tokens = self.token_counter.calculate_conversation_tokens(messages)
            total_input_tokens += context_window_tokens
            
            self._show_context_stats(context_window_tokens, total_input_tokens, total_output_tokens)
            
            # 构建API参数
            api_params = self._build_api_params(messages)
            
            # 使用新的事件接口处理流式响应
            stream = self.client.chat_completions_create_with_events(**api_params)
            
            # 创建流式响应处理器
            stream_handler = StreamResponseHandler(self.frontend)
            
            # 处理流式事件
            for event in stream:
                stream_handler.handle_stream_event(event)
            
            # 获取处理结果
            result = stream_handler.get_result()
            
            # 更新输出token统计
            thinking_tokens = self.token_counter.count_tokens(result["thinking"]) if result["has_thinking"] else 0
            content_tokens = self.token_counter.count_tokens(result["content"]) if result["has_content"] else 0
            total_output_tokens += thinking_tokens + content_tokens
            
            # 显示token统计
            self._show_response_stats(thinking_tokens, content_tokens, total_input_tokens, total_output_tokens)
            
            # 添加助手消息到对话历史
            self.conversation_manager.add_assistant_message(
                result["content"],
                result["thinking"],
                result["tool_calls"]
            )
            conversation_saver.save_conversation([self.conversation_manager.get_last_message()])
            
            # 处理工具调用
            if result["has_tool_calls"]:
                total_output_tokens += self._execute_tool_calls(result["tool_calls"])
            else:
                # 没有工具调用，结束当前轮次
                break

    def _build_api_params(self, messages: list) -> dict:
        """构建API调用参数"""
        api_params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "tools": TOOLS,
            "max_tokens": 32000,
        }
        
        # 应用模型参数
        for param in self.model_parameters:
            if isinstance(param, list) and len(param) == 2:
                key, value = param
                # 如果参数值为"Delete"，则从api_params中移除该参数
                if value == "Delete":
                    if key in api_params:
                        del api_params[key]
                else:
                    api_params[key] = value
        
        return api_params

    def _show_context_stats(self, context_window_tokens: int, total_input_tokens: int, 
                           total_output_tokens: int):
        """显示上下文统计信息"""
        self.frontend.output('info', 
            f"📊 上下文窗口: {context_window_tokens/1000} 千tokens "
            f"📊 输入token总量: {total_input_tokens} tokens  "
            f"📊 输出token总量: {total_output_tokens} tokens")

    def _show_response_stats(self, thinking_tokens: int, content_tokens: int, 
                           total_input_tokens: int, total_output_tokens: int):
        """显示响应统计信息"""
        self.frontend.output('info', 
            f"📊 思考输出: {thinking_tokens} tokens  "
            f"📊 回答输出: {content_tokens} tokens")
        self.frontend.output('info', 
            f"📊 输入token总量: {total_input_tokens} tokens  "
            f"📊 输出token总量: {total_output_tokens} tokens")

    def _execute_tool_calls(self, tool_calls: list) -> int:
        """执行工具调用，返回工具调用的token消耗"""
        self.frontend.output('info', "\n工具参数接收完成，开始执行...")
        
        tool_calls_tokens = 0
        
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            tool_call_id = tool_call['id']
            
            try:
                function_args = json_repair.loads(tool_call['function']['arguments'])
            except Exception as e:
                self.frontend.output("error", 
                    f"工具参数解析失败：{tool_call['function']['arguments']} - {str(e)}")
                continue
            
            # 计算工具调用的token
            tool_calls_tokens += (
                self.token_counter.count_tokens(function_name) + 
                self.token_counter.count_tokens(tool_call['function']['arguments'])
            )
            
            if function_name in TOOL_FUNCTIONS:
                try:
                    function_response = TOOL_FUNCTIONS[function_name](**function_args)
                    
                    # 添加工具返回结果到对话上下文
                    self.conversation_manager.add_tool_result(tool_call_id, str(function_response))
                    conversation_saver.save_conversation([self.conversation_manager.get_last_message()])
                    
                    # 计算工具返回结果的token
                    tool_result_tokens = self.token_counter.count_tokens(str(function_response))
                    self.frontend.output("tool_result", str(function_response))
                    self.frontend.output('info', f"📊 工具返回token量: {tool_result_tokens}")
                    
                    # 累加工具结果的token
                    tool_calls_tokens += tool_result_tokens
                    
                except Exception as e:
                    self.frontend.output('error', f"❌ 工具执行失败：{function_name} - {str(e)}")
            else:
                self.frontend.output('error', f"❌ 未找到工具函数：{function_name}")
        
        self.frontend.output('info', f"📊 调用请求输出token量: {tool_calls_tokens}")
        return tool_calls_tokens