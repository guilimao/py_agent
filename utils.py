from typing import Tuple

def get_user_message() -> Tuple[str, bool]:
    try:
        line = input("用户输入：")
        return line, True
    except EOFError:
        return "", False
    except KeyboardInterrupt:
        return "", False