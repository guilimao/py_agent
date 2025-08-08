import tiktoken

class TokenCounter:
    """Token统计器，用于统计对话中的token使用量"""
    
    def __init__(self, model_name: str = "qwen3-235b-a22b"):
        # 根据模型选择合适的编码器
        if "qwen" in model_name.lower():
            self.encoding = tiktoken.get_encoding("o200k_base")  # Qwen使用o200k_base
        else:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        
        # 当前轮次的token统计
        self.current_round_stats = {
            "user_input_tokens": 0,
            "llm_output_tokens": 0,  # 包括思维链、自然语言、工具参数
            "tool_result_tokens": 0,
            "total_round_tokens": 0
        }
        
        # 总token统计
        self.total_stats = {
            "total_user_input_tokens": 0,
            "total_llm_output_tokens": 0,
            "total_tool_result_tokens": 0,
            "total_tokens": 0
        }
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
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
    
    def start_new_round(self):
        """开始新一轮对话，重置当前轮次统计"""
        self.current_round_stats = {
            "user_input_tokens": 0,
            "llm_output_tokens": 0,
            "tool_result_tokens": 0,
            "total_round_tokens": 0
        }
    
    def add_user_input(self, text: str):
        """添加用户输入的token统计"""
        tokens = self.count_tokens(text)
        self.current_round_stats["user_input_tokens"] = tokens
        self.total_stats["total_user_input_tokens"] += tokens
    
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
        self.total_stats["total_llm_output_tokens"] += tokens
    
    def add_tool_result(self, result: str):
        """添加工具返回结果的token统计"""
        tokens = self.count_tokens(str(result))
        self.current_round_stats["tool_result_tokens"] += tokens
        self.total_stats["total_tool_result_tokens"] += tokens
    
    def finish_round(self):
        """完成当前轮次，计算总token数"""
        self.current_round_stats["total_round_tokens"] = (
            self.current_round_stats["user_input_tokens"] +
            self.current_round_stats["llm_output_tokens"] +
            self.current_round_stats["tool_result_tokens"]
        )
        self.total_stats["total_tokens"] += self.current_round_stats["total_round_tokens"]
    
    def get_round_summary(self) -> str:
        """获取当前轮次的token统计摘要"""
        return f"""
📊 当前轮次Token统计:
   👤 用户输入: {self.current_round_stats['user_input_tokens']} tokens
   🤖 LLM输出: {self.current_round_stats['llm_output_tokens']} tokens
   🔧 工具结果: {self.current_round_stats['tool_result_tokens']} tokens
   📈 本轮总计: {self.current_round_stats['total_round_tokens']} tokens

📊 累计Token统计:
   👤 用户输入总计: {self.total_stats['total_user_input_tokens']} tokens
   🤖 LLM输出总计: {self.total_stats['total_llm_output_tokens']} tokens
   🔧 工具结果总计: {self.total_stats['total_tool_result_tokens']} tokens
   📊 总计: {self.total_stats['total_tokens']} tokens
"""