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
        default="doubao-1-5-thinking-pro-250415",
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

    agent = Agent(
        client=client,
        get_user_message=get_user_message,
        system_prompt=get_system_prompt(),
        model_name=args.model
    )
    agent.run()


if __name__ == "__main__":
    main()
