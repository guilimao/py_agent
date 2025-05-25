import json

def get_system_prompt():
    try:
        with open('system_prompt.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('system_prompt', "默认系统提示")
    except FileNotFoundError:
        print("配置文件不存在，使用默认系统提示")
        return "这是一个默认的系统提示"
    except json.JSONDecodeError:
        print("配置文件格式错误，使用默认系统提示")
        return "这是一个默认的系统提示"