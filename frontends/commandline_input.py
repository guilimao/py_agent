# frontends/commandline_input.py
"""
命令行输入处理 (原input_handler.py)
"""

def get_user_message() -> tuple[str, bool]:
    try:
        line = input("\n用户输入：")
        return line, True
    except EOFError:
        return "", False
    except KeyboardInterrupt:
        return "", False