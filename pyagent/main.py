import os
import argparse
import json
from openai import OpenAI
from .agent import Agent
from .config import get_system_prompt
from .frontends import CommandlineFrontend

def load_provider_config():
    # 获取当前脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config", "provider_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
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
        default="doubao-seed-1-6-250615",
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
    
    # 注意：现在使用数据库存储对话历史，不会自动清理
    # 如果需要清理特定会话的历史，请使用数据库API
    
    agent.run()


if __name__ == "__main__":
    main()