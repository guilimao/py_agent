import os
import json

def save_conversation(messages, file_path="config/conversation_memory.json"):
    """
    保存对话消息到文件
    :param messages: 消息列表，每个消息是一个字典
    :param file_path: 保存路径，默认为"config/conversation_memory.json"
    """
    conversations = []
    for msg in messages:
        conv = {
            "role": msg["role"],
            "thinking": msg.get("thinking"),
            "content": msg.get("content"),
        }
        if "tool_calls" in msg:
            conv["tool_calls"] = msg["tool_calls"]
        if "tool_call_id" in msg:
            conv["tool_call_id"] = msg["tool_call_id"]
        conversations.append(conv)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"conversations": conversations}, f, ensure_ascii=False, indent=2)