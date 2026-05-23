"""
网页内容抓取工具 - 基于 httpx + trafilatura

输入链接，抓取页面内容并以多种格式返回。
支持 Markdown、纯文本、HTML、JSON、XML 等输出格式。

【代理说明】
本工具使用 httpx 进行网络请求，httpx 会自动读取系统环境变量中的代理配置：
  - HTTP_PROXY / http_proxy   → HTTP 代理
  - HTTPS_PROXY / https_proxy → HTTPS 代理
  - ALL_PROXY / all_proxy     → 全局代理（兜底）
无需手动配置，环境变量设置好后即可生效。

依赖说明：本工具依赖 trafilatura 和 httpx[socks] 库，需在项目虚拟环境中运行。
  - 通过 `uv run python main.py` 启动：✅ 自动生效
  - 通过 `pyagent` 命令启动（uv tool install）：✅ 自动生效
  - 直接 `python main.py`：❌ 需要先激活虚拟环境
"""

import json
import os
from typing import Any, Optional

import httpx
import trafilatura

# httpx 客户端全局单例（复用连接池，提高性能）
_HTTPX_CLIENT: Optional[httpx.Client] = None


def _get_httpx_client() -> httpx.Client:
    """获取或创建 httpx 客户端单例。

    httpx 会自动读取 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY 等环境变量，
    无需手动传入代理配置。
    """
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is None:
        _HTTPX_CLIENT = httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
    return _HTTPX_CLIENT


def _download_with_httpx(url: str) -> Optional[str]:
    """使用 httpx 下载网页，自动使用系统环境变量配置的代理。

    Returns:
        HTML 字符串，或 None 表示下载失败。
    """
    try:
        client = _get_httpx_client()
        response = client.get(url)
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def fetch_web_page(
    url: str,
    output_format: str = "markdown",
    include_tables: bool = True,
    include_links: bool = True,
    include_images: bool = False,
    include_comments: bool = False,
    include_formatting: bool = False,
    favor_precision: bool = False,
    favor_recall: bool = False,
) -> str:
    """
    抓取指定URL的网页内容，提取正文并以指定格式返回。

    网络请求基于 httpx（自动读取系统代理环境变量），
    内容提取基于 trafilatura v2.0.0+ 官方 API。

    Args:
        url: 要抓取的网页链接，必须以 http:// 或 https:// 开头
        output_format: 输出格式
            - "markdown"（默认）：Markdown 格式，适合阅读和二次处理
            - "text"：纯文本，不含任何标记
            - "html"：清理后的 HTML
            - "json"：结构化 JSON，包含元数据和正文
            - "xml"：XML 格式
        include_tables: 是否保留表格（默认 True）
        include_links: 是否保留链接（默认 True）
        include_images: 是否包含图片信息（默认 False）
        include_comments: 是否包含评论（默认 False）
        include_formatting: 是否保留文本格式（加粗/斜体等，默认 False）
        favor_precision: 优先精确度，减少噪音但可能遗漏内容（默认 False）
        favor_recall: 优先召回率，尽可能多保留内容但可能包含噪音（默认 False）

    Returns:
        提取后的网页内容字符串
    """
    # ---- 参数校验 ----
    if not url or not url.strip():
        return "[错误] 请提供有效的网页链接"

    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return (
            f"[错误] 无效的URL格式：{url}\n"
            f"URL必须以 http:// 或 https:// 开头"
        )

    # ---- 输出格式校验 ----
    valid_formats = {"txt", "text", "markdown", "md", "html", "json", "xml"}
    fmt = output_format.lower().strip()
    if fmt not in valid_formats:
        return (
            f"[错误] 不支持的输出格式：'{output_format}'\n"
            f"支持格式：markdown, text, html, json, xml"
        )

    fmt_map = {
        "txt": "txt", "text": "txt", "md": "markdown", "markdown": "markdown",
        "html": "html", "json": "json", "xml": "xml",
    }
    actual_format = fmt_map[fmt]

    # ---- 下载网页（通过 httpx，自动使用系统代理） ----
    try:
        downloaded = _download_with_httpx(url)
    except Exception as e:
        return (
            f"[错误] 下载网页时发生异常：{str(e)}\n"
            f"URL：{url}\n"
            f"建议：检查网络连接或代理配置是否正确"
        )

    if downloaded is None:
        return (
            f"[错误] 无法下载网页内容：{url}\n"
            f"可能原因：\n"
            f"  - 网站拒绝连接或返回空内容\n"
            f"  - 网络不可达（请检查代理配置）\n"
            f"  - 需要JavaScript渲染（静态抓取无法处理SPA应用）\n"
            f"  - SSL证书问题\n"
            f"\n"
            f"当前系统代理配置：\n"
            f"  HTTP_PROXY={os.environ.get('HTTP_PROXY', '未设置')}\n"
            f"  HTTPS_PROXY={os.environ.get('HTTPS_PROXY', '未设置')}\n"
            f"  ALL_PROXY={os.environ.get('ALL_PROXY', '未设置')}"
        )

    # ---- 提取内容 ----
    try:
        if actual_format == "json":
            data = trafilatura.bare_extraction(
                downloaded,
                as_dict=True,
                include_comments=include_comments,
                include_tables=include_tables,
                include_images=include_images,
                include_links=include_links,
                include_formatting=include_formatting,
                favor_precision=favor_precision,
                favor_recall=favor_recall,
                with_metadata=True,
            )
            if data is None:
                return _empty_content_warning(url)

            data["source_url"] = url

            metadata = trafilatura.extract_metadata(downloaded)
            if metadata:
                for key in ("title", "author", "date", "hostname", "description", "categories", "tags"):
                    val = getattr(metadata, key, None)
                    if val and (key not in data or not data.get(key)):
                        data[key] = val

            for key in ('body', 'commentsbody'):
                val = data.get(key)
                if val is not None and hasattr(val, 'itertext'):
                    data[key] = ''.join(val.itertext()).strip()

            return json.dumps(data, ensure_ascii=False, indent=2, default=str)

        else:
            result = trafilatura.extract(
                downloaded,
                output_format=actual_format,
                include_comments=include_comments,
                include_tables=include_tables,
                include_images=include_images,
                include_links=include_links,
                include_formatting=include_formatting,
                favor_precision=favor_precision,
                favor_recall=favor_recall,
                with_metadata=False,
            )

            if result is None or result.strip() == "":
                return _empty_content_warning(url)

            metadata = trafilatura.extract_metadata(downloaded)

            if actual_format == "html":
                return _build_html_output(url, metadata, result)
            elif actual_format == "markdown":
                return _build_markdown_output(url, metadata, result)
            else:
                return _build_text_output(url, metadata, result)

    except Exception as e:
        return f"[错误] 提取网页内容时发生异常：{str(e)}"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _empty_content_warning(url: str) -> str:
    """生成空内容警告"""
    return (
        f"[警告] 成功下载网页但未能提取到有效正文内容：{url}\n"
        f"可能原因：\n"
        f"  - 页面为纯JavaScript渲染的SPA应用\n"
        f"  - 页面内容过少或为空白页\n"
        f"  - 页面结构无法被 trafilatura 识别\n"
        f"\n"
        f"建议尝试：\n"
        f"  - 调整 favor_recall=True 参数以更包容地提取\n"
        f"  - 设置 include_comments=True 查看是否有评论内容"
    )


def _build_markdown_output(url: str, metadata: Any, content: str) -> str:
    """构建带元数据的 Markdown 输出"""
    header = "# 网页内容抓取结果\n\n"
    header += f"**来源URL**：{url}\n\n"

    if metadata:
        if metadata.title:
            header += f"**标题**：{metadata.title}\n\n"
        if metadata.author:
            header += f"**作者**：{metadata.author}\n\n"
        if metadata.date:
            header += f"**日期**：{metadata.date}\n\n"
        if hasattr(metadata, 'categories') and metadata.categories:
            cats = ", ".join(metadata.categories)
            header += f"**分类**：{cats}\n\n"
        if hasattr(metadata, 'tags') and metadata.tags:
            tags = ", ".join(metadata.tags)
            header += f"**标签**：{tags}\n\n"

    header += "---\n\n"
    return _truncate_if_needed(header + content)


def _build_text_output(url: str, metadata: Any, content: str) -> str:
    """构建带元数据的纯文本输出"""
    header = f"来源URL：{url}\n"

    if metadata:
        if metadata.title:
            header += f"标题：{metadata.title}\n"
        if metadata.author:
            header += f"作者：{metadata.author}\n"
        if metadata.date:
            header += f"日期：{metadata.date}\n"

    header += "---\n\n"
    return _truncate_if_needed(header + content)


def _build_html_output(url: str, metadata: Any, content: str) -> str:
    """构建带元数据的 HTML 输出"""
    header = f"<!-- 来源URL：{url} -->\n"

    if metadata:
        if metadata.title:
            header += f"<!-- 标题：{metadata.title} -->\n"
        if metadata.author:
            header += f"<!-- 作者：{metadata.author} -->\n"
        if metadata.date:
            header += f"<!-- 日期：{metadata.date} -->\n"

    header += "\n"
    return _truncate_if_needed(header + content)


def _truncate_if_needed(content: str, max_chars: int = 50000) -> str:
    """对过长内容进行截断并添加提示"""
    if len(content) > max_chars:
        truncated = content[:max_chars]
        truncated += (
            f"\n\n---\n\n"
            f"[提示：内容过长，已截断。原始内容约 {len(content)} 字符，"
            f"此处仅显示前 {max_chars} 字符。]"
        )
        return truncated
    return content


# ---------------------------------------------------------------------------
# 工具元信息（供LLM识别）
# ---------------------------------------------------------------------------
WEB_FETCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_web_page",
            "description": (
                "抓取指定URL的网页内容，提取正文并以多种格式返回。"
                "支持 Markdown（默认）、纯文本、HTML、JSON、XML 五种输出格式。"
                "可灵活控制是否保留表格、链接、图片、评论、文本格式等元素。"
                "适用于阅读网页文章、提取文档内容、采集结构化数据等场景。"
                "注意：无法处理需要JavaScript渲染的单页应用（SPA）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要抓取的网页链接，必须以 http:// 或 https:// 开头",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["markdown", "text", "html", "json", "xml"],
                        "description": (
                            "输出格式：\n"
                            "- 'markdown'（默认）：Markdown格式，适合阅读和二次处理\n"
                            "- 'text'：纯文本，不含任何标记\n"
                            "- 'html'：清理后的HTML\n"
                            "- 'json'：结构化JSON，包含元数据和正文\n"
                            "- 'xml'：XML格式"
                        ),
                    },
                    "include_tables": {
                        "type": "boolean",
                        "description": "是否保留表格（默认 True）",
                    },
                    "include_links": {
                        "type": "boolean",
                        "description": "是否保留链接（默认 True）",
                    },
                    "include_images": {
                        "type": "boolean",
                        "description": "是否包含图片信息（默认 False）",
                    },
                    "include_comments": {
                        "type": "boolean",
                        "description": "是否包含评论（默认 False）",
                    },
                    "include_formatting": {
                        "type": "boolean",
                        "description": "是否保留加粗/斜体等文本格式（默认 False）",
                    },
                    "favor_precision": {
                        "type": "boolean",
                        "description": "优先精确度，减少噪音但可能遗漏内容（默认 False）",
                    },
                    "favor_recall": {
                        "type": "boolean",
                        "description": "优先召回率，尽可能多保留内容但可能包含噪音（默认 False）",
                    },
                },
                "required": ["url"],
            },
        },
    }
]

# 工具函数映射（供Agent执行）
WEB_FETCH_FUNCTIONS = {
    "fetch_web_page": fetch_web_page,
}
