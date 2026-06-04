import os as _os

from .cmdline import COMMAND_FUNCTIONS, COMMAND_TOOLS
from .directory_list import DIRECTORY_FUNCTIONS, DIRECTORY_TOOLS
from .image_tools import IMAGE_FUNCTIONS, IMAGE_TOOLS
from .web_browser import WEB_BROWSER_FUNCTIONS, WEB_BROWSER_TOOLS

TOOLS = [
    *COMMAND_TOOLS,
    *DIRECTORY_TOOLS,
    *IMAGE_TOOLS,
    *WEB_BROWSER_TOOLS,
]

TOOL_FUNCTIONS = {
    **COMMAND_FUNCTIONS,
    **DIRECTORY_FUNCTIONS,
    **IMAGE_FUNCTIONS,
    **WEB_BROWSER_FUNCTIONS,
}

# write_file 仅在 Windows 下注册，避免非 Windows 平台 LLM 尝试调用
if _os.name == 'nt':
    from .file_write import FILE_WRITE_FUNCTIONS, FILE_WRITE_TOOLS
    TOOLS.extend(FILE_WRITE_TOOLS)
    TOOL_FUNCTIONS.update(FILE_WRITE_FUNCTIONS)
