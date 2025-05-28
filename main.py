from openai import OpenAI

import os
import argparse  # 新增：命令行参数解析
from agent import Agent
from config import get_system_prompt
from input_handler import get_user_message

def main():
    parser = argparse.ArgumentParser(description="配置Agent运行参数")
    parser.add_argument(
        "--model", 
        type=str, 
        default="doubao-1-5-thinking-pro-250415",  # 默认原模型
        help="指定使用的LLM模型名称（如doubao-1-5-thinking-pro-250415、gpt-3.5-turbo等）"
    )
    args = parser.parse_args()

    system_prompt = get_system_prompt()
    client = OpenAI(
        api_key=os.getenv("ARK_API_KEY"), 
        base_url="https://ark.cn-beijing.volces.com/api/v3"
    )

    agent = Agent(
        client=client,
        get_user_message=get_user_message,
        system_prompt=system_prompt,
        model_name=args.model  # 关键修改：动态传递模型名称
    )
    agent.run()

if __name__ == "__main__":
    main()
