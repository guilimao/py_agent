import os
import argparse
import json
from openai import OpenAI
from agent import Agent
from config import get_system_prompt
from frontends import CommandlineFrontend

def load_provider_config():
    with open("config/provider_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def get_provider_from_model(model_name: str, provider_config: dict) -> str:
    for provider, config in provider_config.items():
        if model_name in config.get("models", []):
            return provider
    raise ValueError(f"未找到支持模型 {model_name} 的提供商，请检查 config/provider_config.json 配置")


def main():
    parser = argparse.ArgumentParser(description="配置Agent运行参数")
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-reasoner",
        help="指定使用的LLM模型名称"
    )
    args = parser.parse_args()

    provider_config = load_provider_config()
    provider = get_provider_from_model(args.model, provider_config)

    config = provider_config.get(provider)
    if not config:
        raise ValueError(f"提供商 {provider} 未在 config/provider_config.json 中配置")

    if args.model not in config["models"]:
        raise ValueError(f"模型 {args.model} 未在提供商 {provider} 的支持模型列表中，可用模型：{config['models']}")

    client = OpenAI(
        api_key=os.getenv(config["api_key_env"]),
        base_url=config["base_url"]
    )

    # 创建命令行前端实例
    frontend = CommandlineFrontend()
    
    agent = Agent(
        client=client,
        frontend=frontend,
        system_prompt=get_system_prompt(),
        model_name=args.model
    )
    
    # +++ 新增：清理上次对话历史 +++
    try:
        # 安全删除对话记忆文件
        if os.path.exists("config/conversation_memory.json"):
            os.remove("config/conversation_memory.json")
            print("已清理上次对话历史记录")
        else:
            print("未找到历史对话记录，无需清理")
            
        # 重置Agent内部状态（确保内存中没有残留）
        agent.messages = [{"role": "system", "content": get_system_prompt()}]
        agent.thinking_memory = []
        agent.tool_call_memory = []
        agent.last_saved_user_count = 0
    except Exception as e:
        print(f"清理历史时发生错误: {e}，将继续运行")
    # --- 清理结束 ---
    
    agent.run()


if __name__ == "__main__":
    main()