import json
import os
import platform

def get_system_info():
    """获取系统信息"""
    system = platform.system()
    release = platform.release()
    version = platform.version()
    
    if system == "Windows":
        return f"操作系统：{system} {release}"
    elif system == "Darwin":
        return f"操作系统：macOS {platform.mac_ver()[0]}"
    elif system == "Linux":
        return f"操作系统：{system} {release}"
    else:
        return f"操作系统：{system} {release}"

def get_system_prompt():
    # 获取当前脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 优先尝试读取纯文本格式的系统提示
    txt_path = os.path.join(script_dir, 'config', 'system_prompt.txt')
    json_path = os.path.join(script_dir, 'config', 'system_prompt.json')
    
    # 获取系统信息
    system_info = get_system_info()
    
    # 如果文本文件存在，直接读取并替换系统信息
    if os.path.exists(txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 替换文件中的系统信息占位符
                if "操作系统：" in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith("操作系统："):
                            lines[i] = system_info
                            break
                    return '\n'.join(lines)
                else:
                    # 如果没有找到系统信息行，添加到末尾
                    return content + f"\n{system_info}"
        except Exception as e:
            print(f"读取文本提示失败: {e}")
    
    # 文本文件不存在时，回退到JSON格式
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                prompt = config.get('system_prompt', "默认系统提示")
                return f"{prompt}\n{system_info}"
        except json.JSONDecodeError:
            print("JSON配置文件格式错误")
    
    # 都不存在时使用默认提示
    print("使用默认系统提示")
    return f"这是一个默认的系统提示\n{system_info}"

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