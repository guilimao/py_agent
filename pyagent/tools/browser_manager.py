"""
浏览器生命周期管理器

管理 Playwright 浏览器实例的创建、复用和销毁。
采用模块级单例模式，Agent 会话期间保持浏览器存活以支持同一网站的多次操作，
会话结束时统一清理防止内存泄露。
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_browser_manager: Optional['BrowserManager'] = None


def get_browser_manager() -> 'BrowserManager':
    """获取浏览器管理器单例。"""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


def cleanup_browser() -> None:
    """清理浏览器资源，供 Agent 会话结束时调用。"""
    global _browser_manager
    if _browser_manager is not None:
        _browser_manager.cleanup()
        _browser_manager = None


# ---------------------------------------------------------------------------
# BrowserManager
# ---------------------------------------------------------------------------

class BrowserManager:
    """Playwright 浏览器生命周期管理器。

    特性：
    - 懒加载：首次使用时才启动浏览器
    - 会话复用：同一会话中多次调用共享浏览器实例
    - 无头模式：默认以 headless 模式运行，适合服务器/CLI 环境
    - 自动清理：调用 cleanup() 释放所有资源
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._current_url = ""

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _ensure_browser(self):
        """确保浏览器已启动并返回当前 Page。

        懒加载策略：首次调用时依次创建 playwright → browser → context → page。
        若已有 page 且未关闭，直接复用。
        """
        if self._playwright is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            # 使用环境变量或默认配置
            headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
            self._browser = self._playwright.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

        if self._context is None:
            # 自动读取系统代理环境变量
            proxy_config = None
            proxy_server = (
                os.environ.get('HTTPS_PROXY')
                or os.environ.get('https_proxy')
                or os.environ.get('HTTP_PROXY')
                or os.environ.get('http_proxy')
                or os.environ.get('ALL_PROXY')
                or os.environ.get('all_proxy')
            )
            if proxy_server:
                proxy_config = {"server": proxy_server}

            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
                java_script_enabled=True,
                proxy=proxy_config,
            )

        if self._page is None or self._page.is_closed():
            self._page = self._context.new_page()

        return self._page

    # ------------------------------------------------------------------
    # 页面操作
    # ------------------------------------------------------------------

    def navigate(self, url: str, wait_until: str = "load", timeout: int = 30):
        """导航到指定 URL。

        Args:
            url: 目标 URL
            wait_until: 等待策略 - "load"|"domcontentloaded"|"networkidle"|"commit"
            timeout: 超时秒数
        """
        page = self._ensure_browser()
        page.goto(url, wait_until=wait_until, timeout=timeout * 1000)
        self._current_url = page.url
        return page

    def get_page(self):
        """获取当前 Page 对象。"""
        return self._ensure_browser()

    def get_current_url(self) -> str:
        """获取当前页面 URL。"""
        page = self._ensure_browser()
        return page.url

    def get_title(self) -> str:
        """获取当前页面标题。"""
        page = self._ensure_browser()
        return page.title()

    def get_content(self) -> str:
        """获取当前页面渲染后的完整 HTML。"""
        page = self._ensure_browser()
        return page.content()

    def screenshot(self, path: str, full_page: bool = False) -> str:
        """对当前页面截图并保存到指定路径。

        Args:
            path: 保存路径
            full_page: 是否截取整个页面（含滚动区域）

        Returns:
            保存的文件路径
        """
        page = self._ensure_browser()
        page.screenshot(path=path, full_page=full_page)
        return path

    def click(self, selector: str, timeout: int = 10):
        """点击匹配选择器的元素。

        Args:
            selector: CSS 选择器或文本选择器
            timeout: 等待元素出现的超时秒数
        """
        page = self._ensure_browser()
        page.click(selector, timeout=timeout * 1000)

    def fill(self, selector: str, value: str, timeout: int = 10):
        """填写输入框。

        Args:
            selector: CSS 选择器
            value: 要填入的文本
            timeout: 超时秒数
        """
        page = self._ensure_browser()
        page.fill(selector, value, timeout=timeout * 1000)

    def evaluate(self, expression: str):
        """在页面中执行 JavaScript 表达式。

        Args:
            expression: JavaScript 表达式

        Returns:
            表达式返回值（可序列化的）
        """
        page = self._ensure_browser()
        return page.evaluate(expression)

    def wait_for_selector(self, selector: str, timeout: int = 10, state: str = "visible"):
        """等待选择器匹配的元素出现。

        Args:
            selector: CSS 选择器
            timeout: 超时秒数
            state: 等待状态 - "attached"|"detached"|"visible"|"hidden"
        """
        page = self._ensure_browser()
        page.wait_for_selector(selector, timeout=timeout * 1000, state=state)

    def wait_for_load_state(self, state: str = "load", timeout: int = 30):
        """等待页面加载状态。

        Args:
            state: "load"|"domcontentloaded"|"networkidle"
            timeout: 超时秒数
        """
        page = self._ensure_browser()
        page.wait_for_load_state(state, timeout=timeout * 1000)

    def scroll(self, direction: str = "down", amount: int = 500):
        """滚动页面。

        Args:
            direction: "down"|"up"|"bottom"|"top"
            amount: 滚动像素数（direction 为 down/up 时有效）
        """
        page = self._ensure_browser()
        if direction == "bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif direction == "top":
            page.evaluate("window.scrollTo(0, 0)")
        elif direction == "up":
            page.evaluate(f"window.scrollBy(0, {-amount})")
        else:  # down
            page.evaluate(f"window.scrollBy(0, {amount})")

    def press_key(self, key: str):
        """按下键盘按键。

        Args:
            key: 按键名称，如 "Enter"、"Escape"、"Tab"、"ArrowDown" 等
        """
        page = self._ensure_browser()
        page.keyboard.press(key)

    def type_text(self, text: str, delay: int = 0):
        """逐字输入文本（模拟真实打字）。

        Args:
            text: 要输入的文本
            delay: 每个字符间的延迟（毫秒）
        """
        page = self._ensure_browser()
        page.keyboard.type(text, delay=delay)

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def cleanup(self):
        """清理所有浏览器资源，释放内存。

        按 page → context → browser → playwright 的顺序关闭，
        确保资源正确释放。
        """
        try:
            if self._page is not None and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        self._page = None

        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        self._context = None

        try:
            if self._browser is not None and self._browser.is_connected():
                self._browser.close()
        except Exception:
            pass
        self._browser = None

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = None

        self._current_url = ""

    def is_alive(self) -> bool:
        """检查浏览器是否存活。"""
        try:
            return (
                self._browser is not None
                and self._browser.is_connected()
                and self._page is not None
                and not self._page.is_closed()
            )
        except Exception:
            return False
