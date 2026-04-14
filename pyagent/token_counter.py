import json
import re

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

class TokenCounter:
    """Token统计器，用于统计对话中的token使用量"""
    
    def __init__(self, model_name: str = "qwen3-235b-a22b", inherit_from: 'TokenCounter' = None):
        self.model_name = model_name
        self.use_tiktoken = TIKTOKEN_AVAILABLE
        
        if self.use_tiktoken:
            try:
                # 根据模型选择合适的编码器
                if "qwen" in model_name.lower():
                    self.encoding = tiktoken.get_encoding("o200k_base")  # Qwen使用o200k_base
                else:
                    self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except Exception:
                # 如果获取编码器失败，退回到估算策略
                self.use_tiktoken = False
                self.encoding = None
        else:
            self.encoding = None
        
        # 如果指定了继承来源，复制其统计状态
        if inherit_from is not None:
            self.current_round_stats = inherit_from.current_round_stats.copy()
            self.total_stats = inherit_from.total_stats.copy()
            self.initial_tokens = inherit_from.initial_tokens.copy()
        else:
            # 当前轮次的token统计
            self.current_round_stats = {
                "user_input_tokens": 0,
                "llm_output_tokens": 0,  # 包括思维链、自然语言、工具参数
                "tool_result_tokens": 0,
                "total_round_tokens": 0
            }
            
            # 总token统计
            self.total_stats = {
                "total_input_tokens": 0,      # 总输入token（包括系统提示、工具定义、用户输入、工具返回）
                "total_output_tokens": 0,     # 总输出token（LLM输出：思考+自然语言+工具调用）
                "total_tokens": 0             # 总token = 总输入 + 总输出
            }
            
            # 系统初始token统计
            self.initial_tokens = {
                "system_prompt_tokens": 0,
                "tools_definition_tokens": 0,
                "total_initial_tokens": 0
            }
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if not text:
            return 0
            
        if self.use_tiktoken and self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                # 如果编码失败，退回到估算策略
                pass
        
        # 估算策略：基于字符和单词的混合估算
        return self._estimate_tokens(text)
    
    def _estimate_tokens(self, text: str) -> int:
        """当tiktoken不可用时使用的估算策略"""
        if not text:
            return 0
            
        # 移除多余的空白字符
        text = text.strip()
        if not text:
            return 0
            
        # 估算策略1：基于字符数（英文约4字符/token，中文约1.5字符/token）
        char_count = len(text)
        
        # 估算策略2：基于单词数（英文约0.75单词/token）
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        
        # 估算策略3：基于中文字符（每个中文字符约0.6 token）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        
        # 混合估算：取字符和单词估算的加权平均
        # 对于英文文本，单词估算更准确；对于中文文本，字符估算更准确
        if chinese_chars > char_count * 0.3:  # 中文占比较高
            # 中文为主的文本
            estimated = max(chinese_chars * 0.6, char_count * 0.4)
        else:
            # 英文为主的文本
            estimated = max(word_count * 1.3, char_count * 0.25)
        
        # 添加标点符号和特殊字符的估算
        punctuation_count = len(re.findall(r'[^\w\s\u4e00-\u9fff]', text))
        estimated += punctuation_count * 0.2
        
        # 确保至少为1个token
        return max(1, int(estimated))
    
    def count_message_tokens(self, message: dict) -> int:
        """计算消息对象的token数量"""
        total_tokens = 0
        
        # 处理content字段（支持字符串和列表格式）
        content = message.get("content")
        if content:
            if isinstance(content, str):
                total_tokens += self.count_tokens(content)
            elif isinstance(content, list):
                # 处理content列表（包含文本和图像）
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text" and item.get("text"):
                            total_tokens += self.count_tokens(item["text"])
                        elif item.get("type") == "image_url" and item.get("image_url", {}).get("url"):
                            # 图像URL的token估算（OpenAI的估算方式）
                            # 基础token + 图像大小估算
                            total_tokens += 85  # 基础图像token
                            
                            # 尝试从base64估算图像大小
                            url = item["image_url"]["url"]
                            if url.startswith("data:image"):
                                try:
                                    # 提取base64部分
                                    base64_part = url.split(",")[1]
                                    # 估算token（每像素约0.002 tokens，但这里简化处理）
                                    image_size = len(base64_part) * 0.75  # base64解码后的大小
                                    if image_size > 100000:  # 大于100KB
                                        total_tokens += 170  # 高分辨率图像
                                    elif image_size > 50000:  # 大于50KB
                                        total_tokens += 85   # 中等分辨率图像
                                except:
                                    total_tokens += 85  # 默认估算
        
        # 计算thinking的token
        if message.get("thinking"):
            total_tokens += self.count_tokens(str(message["thinking"]))
        
        # 计算tool_calls的token
        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                if "function" in tool_call:
                    func_name = tool_call["function"].get("name", "")
                    func_args = tool_call["function"].get("arguments", "")
                    total_tokens += self.count_tokens(func_name) + self.count_tokens(func_args)
        
        return total_tokens

    def count_tools_tokens(self, tools: list) -> int:
        """计算工具定义的token数量"""
        if not tools:
            return 0
        
        # 将工具定义转换为JSON字符串进行token计算
        tools_json = json.dumps(tools, ensure_ascii=False, separators=(',', ':'))
        return self.count_tokens(tools_json)

    def set_initial_tokens(self, system_prompt: str, tools: list):
        """设置系统初始token（系统提示+工具定义）"""
        system_tokens = self.count_tokens(system_prompt)
        tools_tokens = self.count_tools_tokens(tools)
        
        self.initial_tokens["system_prompt_tokens"] = system_tokens
        self.initial_tokens["tools_definition_tokens"] = tools_tokens
        self.initial_tokens["total_initial_tokens"] = system_tokens + tools_tokens
        
        # 将初始token计入总输入token
        self.total_stats["total_input_tokens"] = system_tokens + tools_tokens
        self.total_stats["total_tokens"] = system_tokens + tools_tokens
    
    def start_new_round(self):
        """开始新一轮对话，重置当前轮次统计"""
        self.current_round_stats = {
            "user_input_tokens": 0,
            "llm_output_tokens": 0,
            "tool_result_tokens": 0,
            "total_round_tokens": 0
        }
    
    def calculate_conversation_tokens(self, messages: list) -> int:
        """计算整个对话历史的token总数（用于API调用前的输入token计算）"""
        total_tokens = 0
        
        # 包括系统提示和工具定义的初始token
        total_tokens += self.initial_tokens["total_initial_tokens"]
        
        # 计算所有历史消息的token
        for message in messages:
            total_tokens += self.count_message_tokens(message)
            
        return total_tokens

    def update_total_stats(self, messages: list):
        """根据当前对话历史更新总token统计"""
        # 计算真实的总输入token（包括历史对话）
        actual_input_tokens = self.calculate_conversation_tokens(messages)
        
        # 更新总统计
        self.total_stats["total_input_tokens"] = actual_input_tokens
        self.total_stats["total_tokens"] = actual_input_tokens + self.total_stats["total_output_tokens"]

    def add_user_input(self, text: str):
        """添加用户输入的token统计（仅当前轮次）"""
        tokens = self.count_tokens(text)
        self.current_round_stats["user_input_tokens"] = tokens
        # 注意：总输入token由外部calculate_conversation_tokens方法统一计算

    def add_llm_output(self, thinking: str = "", content: str = "", tool_calls: list = None):
        """添加LLM输出的token统计"""
        tokens = 0
        
        # 思维链token
        if thinking:
            tokens += self.count_tokens(thinking)
        
        # 自然语言内容token
        if content:
            tokens += self.count_tokens(content)
        
        # 工具调用token
        if tool_calls:
            for tool_call in tool_calls:
                if "function" in tool_call:
                    func_name = tool_call["function"].get("name", "")
                    func_args = tool_call["function"].get("arguments", "")
                    tokens += self.count_tokens(func_name) + self.count_tokens(func_args)
        
        self.current_round_stats["llm_output_tokens"] += tokens
        self.total_stats["total_output_tokens"] += tokens

    def add_tool_result(self, result: str):
        """添加工具返回结果的token统计（仅当前轮次）"""
        tokens = self.count_tokens(str(result))
        self.current_round_stats["tool_result_tokens"] += tokens
        # 注意：总输入token由外部calculate_conversation_tokens方法统一计算

    def finish_round(self):
        """完成当前轮次，计算总token数"""
        self.current_round_stats["total_round_tokens"] = (
            self.current_round_stats["user_input_tokens"] +
            self.current_round_stats["llm_output_tokens"] +
            self.current_round_stats["tool_result_tokens"]
        )

    def get_round_summary(self) -> str:
        """获取当前轮次的token统计摘要"""
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
        """获取当前操作的token统计"""
        if operation_type == "user_input":
            return f"📥 用户输入: {self.current_round_stats['user_input_tokens']} tokens"
        elif operation_type == "llm_output":
            return f"📤 LLM输出: {self.current_round_stats['llm_output_tokens']} tokens"
        elif operation_type == "tool_result":
            return f"📥 工具返回: {self.current_round_stats['tool_result_tokens']} tokens"
        else:
            return ""

    def get_total_summary(self) -> str:
        """获取总token统计"""
        strategy = "tiktoken" if self.use_tiktoken else "估算"
        return f"📊 总输入: {self.total_stats['total_input_tokens']} tokens, 总输出: {self.total_stats['total_output_tokens']} tokens, 总计: {self.total_stats['total_tokens']} tokens"