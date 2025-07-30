import json
import os

def get_system_prompt():
    # 获取当前脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 优先尝试读取纯文本格式的系统提示
    txt_path = os.path.join(script_dir, 'config', 'system_prompt.txt')
    json_path = os.path.join(script_dir, 'config', 'system_prompt.json')
    
    # 如果文本文件存在，直接读取
    if os.path.exists(txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"读取文本提示失败: {e}")
    
    # 文本文件不存在时，回退到JSON格式
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('system_prompt', "默认系统提示")
        except json.JSONDecodeError:
            print("JSON配置文件格式错误")
    
    # 都不存在时使用默认提示
    print("使用默认系统提示")
    return "这是一个默认的系统提示"

def save_provider_config(provider_config):
    """保存提供商配置到文件"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config', 'provider_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(provider_config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存配置时出错: {e}")
        return False