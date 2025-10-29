import os
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
        config = json.load(f)
    
    # 验证配置格式
    validate_provider_config(config)
    return config

def validate_provider_config(config: dict):
    """验证提供商配置格式"""
    for provider_name, provider_config in config.items():
        if not isinstance(provider_config, dict):
            raise ValueError(f"提供商 {provider_name} 的配置必须是对象")
        
        if "api_key_env" not in provider_config:
            raise ValueError(f"提供商 {provider_name} 缺少 api_key_env 配置")
        
        if "base_url" not in provider_config:
            raise ValueError(f"提供商 {provider_name} 缺少 base_url 配置")
        
        if "models" not in provider_config:
            raise ValueError(f"提供商 {provider_name} 缺少 models 配置")
        
        models = provider_config["models"]
        if not isinstance(models, list):
            raise ValueError(f"提供商 {provider_name} 的 models 必须是数组")
        
        for i, model in enumerate(models):
            if not isinstance(model, dict):
                raise ValueError(f"提供商 {provider_name} 的模型 {i} 必须是对象")
            
            if "name" not in model:
                raise ValueError(f"提供商 {provider_name} 的模型 {i} 缺少 name 属性")
            
            if "parameters" not in model:
                raise ValueError(f"提供商 {provider_name} 的模型 {i} 缺少 parameters 属性")
            
            if not isinstance(model["parameters"], list):
                raise ValueError(f"提供商 {provider_name} 的模型 {i} 的 parameters 必须是数组")

def get_provider_from_model(model_name: str, provider_config: dict) -> str:
    for provider, config in provider_config.items():
        models = config.get("models", [])
        for model in models:
            if isinstance(model, dict) and model.get("name") == model_name:
                return provider
    raise ValueError(f"未找到支持模型 {model_name} 的提供商，请检查 config/provider_config.json 配置")

def load_all_models(provider_config: dict) -> list:
    """从配置中加载所有可用模型并返回带序号的列表"""
    models = []
    for provider, config in provider_config.items():
        for model in config.get("models", []):
            if isinstance(model, dict):
                models.append({
                    "name": model.get("name"),
                    "provider": provider,
                    "api_key_env": config["api_key_env"],
                    "base_url": config["base_url"],
                    "parameters": model.get("parameters", [])
                })
    return models

def select_model_interactive(models: list) -> dict:
    """交互式选择模型"""
    print("\n" + "="*60)
    print("请选择要使用的模型：")
    print("="*60)
    
    for idx, model_info in enumerate(models, 1):
        print(f"{idx}. {model_info['name']} ({model_info['provider']})")
    
    print("="*60)
    
    while True:
        try:
            choice = input("请输入模型序号 (1-{}): ".format(len(models))).strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(models):
                selected = models[choice_num - 1]
                print(f"\n已选择模型: {selected['name']} ({selected['provider']})")
                return selected
            else:
                print(f"请输入 1-{len(models)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n用户取消选择，程序退出")
            exit(0)

def handle_missing_api_key(model_info: dict) -> bool:
    """处理缺失的API KEY，返回是否成功处理"""
    env_var = model_info["api_key_env"]
    provider = model_info["provider"]
    model_name = model_info["name"]
    
    print(f"\n⚠️  未找到环境变量 {env_var}")
    print(f"需要设置此变量才能使用 {provider} 提供商的 {model_name} 模型")
    
    while True:
        try:
            choice = input("\n是否需要添加API KEY? (y/n): ").strip().lower()
            
            if choice == 'y':
                # 让用户输入API KEY
                api_key = input(f"请输入 {provider} 的API KEY: ").strip()
                if api_key:
                    # 设置环境变量
                    os.environ[env_var] = api_key
                    print(f"✅ API KEY 已设置到环境变量 {env_var}")
                    return True
                else:
                    print("❌ API KEY 不能为空")
                    
            elif choice == 'n':
                print("重新加载模型列表...")
                return False
                
            else:
                print("请输入 'y' (添加) 或 'n' (重新加载模型)")
                
        except KeyboardInterrupt:
            print("\n\n用户取消操作，程序退出")
            exit(0)


def main():
    provider_config = load_provider_config()
    
    while True:
        # 加载所有可用模型
        all_models = load_all_models(provider_config)
        
        if not all_models:
            raise ValueError("未找到任何可用模型，请检查 config/provider_config.json 配置")
        
        # 交互式选择模型
        selected_model = select_model_interactive(all_models)
        
        # 验证API密钥是否存在
        api_key = os.getenv(selected_model["api_key_env"])
        
        if api_key:
            # API KEY已存在，直接创建客户端并运行
            break
        else:
            # API KEY缺失，处理缺失情况
            if handle_missing_api_key(selected_model):
                # 用户成功添加了API KEY，继续执行
                api_key = os.getenv(selected_model["api_key_env"])
                if api_key:
                    break
            else:
                # 用户选择返回或重新加载，继续循环
                continue
    
    # 创建OpenAI客户端
    client = OpenAI(
        api_key=api_key,
        base_url=selected_model["base_url"]
    )
    
    # 创建命令行前端实例
    frontend = CommandlineFrontend()
    
    # 创建并运行Agent
    agent = Agent(
        client=client,
        frontend=frontend,
        system_prompt=get_system_prompt(),
        model_name=selected_model["name"],
        model_parameters=selected_model.get("parameters", [])
    )
    
    agent.run()


if __name__ == "__main__":
    main()