import os
import argparse
import json
from openai import OpenAI
from agent import Agent
from config import get_system_prompt
from input_handler import get_user_message

def load_provider_config():
    with open("config/provider_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def get_provider_from_model(model_name: str) -> str:
    provider_mapping = {
        "doubao": ["doubao"],
        "openai": ["gpt"],
        "deepseek": ["deepseek"]
    }
    for provider, keywords in provider_mapping.items():
        if any(keyword in model_name.lower() for keyword in keywords):
            return provider
    raise ValueError(f"未识别的模型提供商，模型名称：{model_name}")

def main():
    parser = argparse.ArgumentParser(description="配置Agent运行参数")
    parser.add_argument(
        "--model",
        type=str,
        default="doubao-1-5-thinking-pro-250415",
        help="指定使用的LLM模型名称（如doubao-1-5-thinking-pro-250415、gpt-3.5-turbo、deepseek-llm-7b等）"
    )
    args = parser.parse_args()

    provider_config = load_provider_config()
    provider = get_provider_from_model(args.model)
    config = provider_config.get(provider)
    if not config:
        raise ValueError(f"提供商{provider}未在config/provider_config.json中配置")

    if args.model not in config["models"]:
        raise ValueError(f"模型{args.model}未在提供商{provider}的支持模型列表中，可用模型：{config['models']}")

    client = OpenAI(
        api_key=os.getenv(config["api_key_env"]),
        base_url=config["base_url"]
    )

    agent = Agent(
        client=client,
        get_user_message=get_user_message,
        system_prompt=get_system_prompt(),
        model_name=args.model
    )
    agent.run()

if __name__ == "__main__":
    main()