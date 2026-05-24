"""
浏览器工具 —— 基于 Playwright 的网页抓取与操作

提供统一的 browser_use 工具，通过 action 参数切换不同功能。
使用 Playwright 的 aria_snapshot(mode="ai") 提取页面内容，
输出 LLM 友好的结构化语义表示，保留交互元素引用。
"""

import os
import tempfile
from typing import Union

from .browser_manager import get_browser_manager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_RETURN_CHARS = 50000

VALID_ACTIONS = {
    "navigate", "get_content", "screenshot",
    "click", "fill", "evaluate",
    "wait", "scroll", "press_key",
}

ACTIONS_NEED_URL = {"navigate"}
ACTIONS_NEED_SELECTOR = {"click", "fill", "wait"}


# ---------------------------------------------------------------------------
# 溢出信号
# ---------------------------------------------------------------------------

def _make_overflow(content: str, url: str = "", title: str = "") -> dict:
    return {"type": "overflow", "content": content, "url": url, "title": title}


def _check_overflow(content: str, url: str = "", title: str = "",
                    max_chars: int = MAX_RETURN_CHARS) -> Union[str, dict]:
    if len(content) > max_chars:
        return _make_overflow(content=content, url=url, title=title)
    return content


def build_overflow_message(
    file_path: str,
    total_chars: int,
    url: str = "",
    title: str = "",
    source_type: str = "网页内容",
) -> str:
    """构建「内容已转储到文件」的提示消息。"""
    lines = [
        f"[提示] {source_type}过长（{total_chars}字符），完整内容已保存到临时文件。",
        "",
    ]
    if url:
        lines.append(f"来源URL：{url}")
    if title:
        label = "页面标题" if source_type == "网页内容" else "来源"
        lines.append(f"{label}：{title}")

    lines += [
        "",
        f"文件路径：{file_path}",
        "",
        "您可以按需使用以下命令读取：",
        f"  head -n 200 {file_path}    # 查看前200行",
        f"  tail -n 200 {file_path}    # 查看后200行",
        f"  cat {file_path}            # 查看全部内容",
        f"  less {file_path}           # 分页浏览",
        f"  grep '关键词' {file_path}  # 搜索指定内容",
        f"  wc -l {file_path}          # 统计行数",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主工具函数
# ---------------------------------------------------------------------------

def browser_use(
    action: str,
    url: str = "",
    selector: str = "",
    value: str = "",
    expression: str = "",
    wait_until: str = "load",
    wait_for_selector: str = "",
    wait_state: str = "visible",
    scroll_direction: str = "down",
    scroll_amount: int = 500,
    full_page: bool = False,
    timeout: int = 30,
) -> Union[str, dict]:
    """
    统一的浏览器工具 —— 通过 action 参数切换不同功能。

    页面内容通过 Playwright 的 AI 模式 aria_snapshot 提取，
    输出结构化的语义表示，包含元素引用（如 [ref=e3]），
    便于 LLM 理解和后续交互操作。

    Args:
        action: 操作类型
            - "navigate": 导航到URL并返回页面语义结构
            - "get_content": 获取当前页面的语义结构（不重新导航）
            - "screenshot": 对当前页面截图
            - "click": 点击页面元素（需 selector）
            - "fill": 填写输入框（需 selector + value）
            - "evaluate": 执行JavaScript表达式（需 expression）
            - "wait": 等待元素出现或页面加载完成
            - "scroll": 滚动页面
            - "press_key": 按键操作（需 value 作为按键名）
        url: 网页链接（navigate 时必需）
        selector: CSS选择器或文本选择器，用于 click/fill/wait
        value: fill 时作为输入文本，press_key 时作为按键名
        expression: JavaScript表达式，用于 evaluate
        wait_until: 导航等待策略 - "load"|"domcontentloaded"|"networkidle"
        wait_for_selector: 导航后额外等待的选择器 / wait 操作的目标选择器
        wait_state: wait 操作的等待状态 - "visible"|"attached"|"detached"|"hidden"
        scroll_direction: 滚动方向 - "down"|"up"|"top"|"bottom"
        scroll_amount: 滚动像素数
        full_page: 截图时是否截取完整页面
        timeout: 超时秒数（默认30）

    Returns:
        - str: 操作结果
        - dict: {"type": "overflow", ...} 内容过长时的溢出信号
    """
    # ---- 参数校验 ----
    if not action or action.strip() == "":
        return "[错误] 必须指定 action 参数"

    action = action.strip().lower()
    if action not in VALID_ACTIONS:
        return (
            f"[错误] 不支持的 action：'{action}'\n"
            f"支持的操作：{', '.join(sorted(VALID_ACTIONS))}"
        )

    if action in ACTIONS_NEED_URL and not url:
        return f"[错误] action='{action}' 需要提供 url 参数"

    if action in ACTIONS_NEED_SELECTOR and not selector:
        return f"[错误] action='{action}' 需要提供 selector 参数"

    if action == "fill" and not value:
        return "[错误] action='fill' 需要提供 value 参数（要填入的文本）"

    if action == "evaluate" and not expression:
        return "[错误] action='evaluate' 需要提供 expression 参数"

    # ---- 获取浏览器管理器 ----
    try:
        bm = get_browser_manager()
    except Exception as e:
        return f"[错误] 无法初始化浏览器：{str(e)}"

    # ---- 执行操作 ----
    try:
        if action == "navigate":
            return _handle_navigate(bm, url, wait_until, wait_for_selector, timeout)

        elif action == "get_content":
            return _handle_get_content(bm)

        elif action == "screenshot":
            return _handle_screenshot(bm, full_page)

        elif action == "click":
            return _handle_click(bm, selector, timeout)

        elif action == "fill":
            return _handle_fill(bm, selector, value, timeout)

        elif action == "evaluate":
            return _handle_evaluate(bm, expression)

        elif action == "wait":
            return _handle_wait(bm, wait_for_selector, wait_until, wait_state, timeout)

        elif action == "scroll":
            return _handle_scroll(bm, scroll_direction, scroll_amount)

        elif action == "press_key":
            return _handle_press_key(bm, value)

        else:
            return f"[错误] 未知 action：{action}"

    except Exception as e:
        return f"[错误] 浏览器操作失败（{action}）：{str(e)}"


# ---------------------------------------------------------------------------
# 各 action 处理函数
# ---------------------------------------------------------------------------

def _get_page_snapshot(bm) -> str:
    """获取当前页面的 AI 模式语义快照。

    使用 Playwright 的 aria_snapshot(mode="ai")，
    输出结构化的可访问性树，包含：
    - 语义角色（heading, paragraph, link, button, list 等）
    - 元素引用 [ref=eN]（可用于后续 click/fill 定位）
    - URL 信息
    - 文本内容
    """
    page = bm.get_page()
    return page.aria_snapshot(mode="ai")


def _handle_navigate(bm, url, wait_until, wait_for_selector, timeout) -> Union[str, dict]:
    """导航到 URL 并返回页面语义快照。"""
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return f"[错误] 无效的URL：{url}\nURL 必须以 http:// 或 https:// 开头"

    bm.navigate(url, wait_until=wait_until, timeout=timeout)
    actual_url = bm.get_current_url()
    title = bm.get_title()

    if wait_for_selector:
        try:
            bm.wait_for_selector(wait_for_selector, timeout=timeout)
        except Exception:
            pass

    # 获取 AI 语义快照
    snapshot = _get_page_snapshot(bm)

    # 构建带元数据的输出
    header = f"来源URL：{actual_url}\n"
    if title:
        header += f"页面标题：{title}\n"
    header += f"---\n\n"
    output = header + snapshot

    return _check_overflow(output, url=actual_url, title=title)


def _handle_get_content(bm) -> Union[str, dict]:
    """获取当前页面的语义快照。"""
    if not bm.is_alive() or not bm.get_current_url():
        return "[提示] 浏览器尚未导航到任何页面，请先使用 action='navigate' 打开一个URL"

    url = bm.get_current_url()
    title = bm.get_title()
    snapshot = _get_page_snapshot(bm)

    header = f"来源URL：{url}\n"
    if title:
        header += f"页面标题：{title}\n"
    header += f"---\n\n"
    output = header + snapshot

    return _check_overflow(output, url=url, title=title)


def _handle_screenshot(bm, full_page) -> str:
    """截图并保存到临时文件。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    url_slug = ""
    current_url = bm.get_current_url()
    if current_url:
        slug = current_url.replace("https://", "").replace("http://", "")
        safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in slug[:40])
        url_slug = safe.strip("_")

    prefix = f"screenshot_{url_slug}_" if url_slug else "screenshot_"
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".png")
    os.close(fd)

    bm.screenshot(path, full_page=full_page)

    return (
        f"[截图已保存]\n"
        f"文件路径：{path}\n"
        f"页面URL：{current_url}\n"
        f"页面标题：{bm.get_title()}\n"
        f"全页面截图：{'是' if full_page else '否'}"
    )


def _handle_click(bm, selector, timeout) -> str:
    """点击元素。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    bm.click(selector, timeout=timeout)
    return (
        f"[点击成功]\n"
        f"选择器：{selector}\n"
        f"当前URL：{bm.get_current_url()}\n"
        f"页面标题：{bm.get_title()}"
    )


def _handle_fill(bm, selector, value, timeout) -> str:
    """填写输入框。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    bm.fill(selector, value, timeout=timeout)
    return (
        f"[填写成功]\n"
        f"选择器：{selector}\n"
        f"填入内容：{value[:100]}{'...' if len(value) > 100 else ''}\n"
        f"当前URL：{bm.get_current_url()}"
    )


def _handle_evaluate(bm, expression) -> str:
    """执行 JavaScript。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    result = bm.evaluate(expression)
    result_str = str(result)
    return (
        f"[JavaScript执行结果]\n"
        f"表达式：{expression[:200]}{'...' if len(expression) > 200 else ''}\n"
        f"返回值：{result_str[:5000]}"
    )


def _handle_wait(bm, wait_for_selector, wait_until, wait_state, timeout) -> str:
    """等待元素或加载状态。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    if wait_for_selector:
        bm.wait_for_selector(wait_for_selector, timeout=timeout, state=wait_state)
        return (
            f"[等待完成]\n"
            f"选择器：{wait_for_selector}\n"
            f"状态：{wait_state}\n"
            f"当前URL：{bm.get_current_url()}"
        )
    else:
        bm.wait_for_load_state(state=wait_until, timeout=timeout)
        return (
            f"[等待完成]\n"
            f"加载状态：{wait_until}\n"
            f"当前URL：{bm.get_current_url()}"
        )


def _handle_scroll(bm, direction, amount) -> str:
    """滚动页面。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    bm.scroll(direction=direction, amount=amount)
    scroll_info = f"像素：{amount}" if direction in ("up", "down") else f"到：{direction}"
    return (
        f"[滚动完成]\n"
        f"方向：{direction}（{scroll_info}）\n"
        f"当前URL：{bm.get_current_url()}"
    )


def _handle_press_key(bm, key) -> str:
    """按键操作。"""
    if not bm.is_alive():
        return "[错误] 浏览器未启动，请先使用 action='navigate' 打开页面"

    if not key:
        return "[错误] press_key 需要提供 value 参数作为按键名"

    bm.press_key(key)
    return (
        f"[按键完成]\n"
        f"按键：{key}\n"
        f"当前URL：{bm.get_current_url()}"
    )


# ---------------------------------------------------------------------------
# 工具元信息（供 LLM 识别）
# ---------------------------------------------------------------------------

WEB_BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_use",
            "description": (
                "基于Playwright浏览器的网页工具，支持页面导航、内容读取、元素操作等。"
                "可以处理JavaScript渲染的单页应用(SPA)。"
                "浏览器在会话期间保持运行，支持同一网站的多次连续操作。"
                "\n\n"
                "页面内容以结构化语义快照（AI模式）呈现，"
                "包含元素引用[ref=eN]可用于后续的click/fill等交互操作。"
                "\n\n"
                "操作类型(action)：\n"
                "- navigate: 导航到URL并返回页面语义结构\n"
                "- get_content: 获取当前页面语义结构（不重新导航）\n"
                "- screenshot: 对当前页面截图，保存到临时文件\n"
                "- click: 点击页面元素，需提供CSS选择器\n"
                "- fill: 填写输入框，需提供CSS选择器和填充文本\n"
                "- evaluate: 在页面中执行JavaScript表达式\n"
                "- wait: 等待元素出现(需selector)或页面加载完成\n"
                "- scroll: 滚动页面 (down/up/top/bottom)\n"
                "- press_key: 键盘按键 (Enter/Escape/Tab等，通过value参数指定)\n"
                "\n"
                "典型流程：先用 navigate 打开页面，再用 click/fill 操作，"
                "最后用 get_content 获取结果。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "操作类型：navigate（导航并提取内容）、"
                            "get_content（获取当前页面内容）、"
                            "screenshot（截图）、click（点击）、fill（填写）、"
                            "evaluate（执行JS）、wait（等待）、scroll（滚动）、"
                            "press_key（按键）"
                        ),
                        "enum": [
                            "navigate", "get_content", "screenshot",
                            "click", "fill", "evaluate",
                            "wait", "scroll", "press_key",
                        ],
                    },
                    "url": {
                        "type": "string",
                        "description": "网页链接。navigate 时必需。",
                    },
                    "selector": {
                        "type": "string",
                        "description": (
                            "CSS选择器或Playwright文本选择器，"
                            "用于 click/fill/wait 操作。"
                            "例如：'#login-btn'、'.search-input'、'text=提交'"
                        ),
                    },
                    "value": {
                        "type": "string",
                        "description": (
                            "fill 操作时作为输入文本，"
                            "press_key 时作为按键名（如 Enter、Escape、Tab）"
                        ),
                    },
                    "expression": {
                        "type": "string",
                        "description": "JavaScript表达式，用于 evaluate 操作",
                    },
                    "wait_until": {
                        "type": "string",
                        "enum": ["load", "domcontentloaded", "networkidle"],
                        "description": (
                            "导航等待策略：load（默认，完整加载）、"
                            "domcontentloaded（DOM就绪）、networkidle（网络空闲）"
                        ),
                    },
                    "wait_for_selector": {
                        "type": "string",
                        "description": (
                            "导航后额外等待的选择器，或 wait 操作的目标选择器"
                        ),
                    },
                    "wait_state": {
                        "type": "string",
                        "enum": ["visible", "attached", "detached", "hidden"],
                        "description": "wait操作的元素等待状态，默认visible",
                    },
                    "scroll_direction": {
                        "type": "string",
                        "enum": ["down", "up", "top", "bottom"],
                        "description": "scroll操作的滚动方向，默认down",
                    },
                    "scroll_amount": {
                        "type": "integer",
                        "description": "scroll操作的滚动像素数，默认500",
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "screenshot时是否截取完整页面（含滚动区域），默认false",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "操作超时秒数，默认30",
                    },
                },
                "required": ["action"],
            },
        },
    }
]

# 工具函数映射（供Agent执行）
WEB_BROWSER_FUNCTIONS = {
    "browser_use": browser_use,
}
