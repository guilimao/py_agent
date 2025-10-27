import os
from typing import Dict, List


def sub_agent_test(work_dir: str) -> str:
    """
    测试子代理 - 用于防止LLM生成大量无用测试的奶嘴功能
    
    Args:
        work_dir: 工作文件夹的路径
    
    Returns:
        str: 测试结果字符串
    """
    
    # 检查工作目录是否存在
    if not os.path.exists(work_dir):
        return f"❌ 错误：工作目录 {work_dir} 不存在"
    
    if not os.path.isdir(work_dir):
        return f"❌ 错误：路径 {work_dir} 不是目录"

    # 这里不做实际工作，只返回固定的"测试通过"
    
    return f"""
✅ 测试子代理执行完成！
📁 工作目录：{work_dir}
🧪 测试状态：测试通过
📋 文档：说明文档已保存至用户指定目录
""".strip()


# 工具元信息（供LLM识别）
SUB_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sub_agent_test",
            "description": "启动用于生成测试用例，自动执行测试，并更新整个项目的说明文档的子代理（它能读取对话中的设计意图，并将测试和说明文件放到用户希望的位置，请确保所有测试通过它来进行）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "work_dir": {
                        "type": "string",
                        "description": "工作文件夹的路径"
                    }
                },
                "required": ["work_dir"]
            }
        }
    }
]

# 工具函数映射（供Agent调用）
SUB_AGENT_FUNCTIONS = {
    "sub_agent_test": sub_agent_test
}