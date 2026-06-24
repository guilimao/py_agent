from typing import Tuple
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.input import create_input
from prompt_toolkit.output import create_output
import os
import sys
import io
from .image_handler import ImageHandler


def sanitize_unicode(text: str, keep_trailing_high: bool = False) -> str:
    """
    清理字符串中的 surrogate 字符，防止后续 UTF-8 编码崩溃。

    Windows 控制台 / prompt_toolkit 可能返回包含孤立 surrogate
    （U+D800..U+DFFF）的字符串，这些字符无法被 UTF-8 编码，
    会在 json.dumps / sys.stdout.write / HTTP 请求序列化时引发
    UnicodeEncodeError。

    逐字符处理（而非全量 utf-16 循环），确保：
    - 配对的 surrogate 对 → 重组为正确的 Unicode 码点
    - 孤立的 surrogate → 替换为 U+FFFD（Unicode 替换字符）
    - keep_trailing_high=True 时，字符串末尾未配对的 high surrogate
      被保留（用于输入过程中的实时修复，等待 low surrogate 到达）
    """
    if not text:
        return text

    # 快速路径：不包含 surrogate 的字符串直接返回
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text

    # 逐字符处理，正确组合 surrogate 对并处理孤立 surrogate
    result = []
    pending_high: str | None = None  # 等待配对的 high surrogate

    for ch in text:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDBFF:  # high surrogate
            if pending_high is not None:
                # 前一个 high surrogate 孤立了，先处理它
                result.append('\uFFFD')
            pending_high = ch
        elif 0xDC00 <= cp <= 0xDFFF:  # low surrogate
            if pending_high is not None:
                # 与之前的 high surrogate 配对
                hi = ord(pending_high)
                lo = cp
                # 根据 UTF-16 公式重组为 Unicode 码点
                combined = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                result.append(chr(combined))
                pending_high = None
            else:
                # 孤立 low surrogate
                result.append('\uFFFD')
        else:
            # 非 surrogate 字符：先处理之前悬空的 high surrogate
            if pending_high is not None:
                result.append('\uFFFD')
                pending_high = None
            result.append(ch)

    # 末尾的 high surrogate：根据模式决定保留还是替换
    if pending_high is not None:
        if keep_trailing_high:
            # 输入过程中，保留末尾 high surrogate 等待配对
            result.append(pending_high)
        else:
            result.append('\uFFFD')

    return ''.join(result)


def _ensure_utf8_stdio():
    """
    确保 sys.stdin / sys.stdout 使用 UTF-8 编码。

    Windows 上 Python 根据系统 ACP（如 936/GBK）设置标准流的编码，
    即使控制台代码页已设为 65001（UTF-8）也无法正确处理
    扩展区域字符（U+10000 以上）。

    此函数必须在 prompt_toolkit 创建输入/输出对象之前调用，
    否则 Vt100Input / Vt100Output 回退路径会因 GBK 编码而损坏
    扩展 Unicode 字符的读取和渲染。
    """
    for stream, name in [(sys.stdin, 'stdin'), (sys.stdout, 'stdout')]:
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


def get_multiline_input() -> Tuple[str, bool]:
    """获取多行用户输入（使用Ctrl+Enter提交）"""
    try:
        # ★ 必须在 prompt_toolkit 创建输入/输出对象之前调用，
        # 确保 Vt100Input / Vt100Output 回退路径使用 UTF-8 而非 GBK。
        _ensure_utf8_stdio()

        # 创建自定义键绑定
        bindings = KeyBindings()

        # 绑定Ctrl+Enter为提交事件
        @bindings.add('c-\\')
        def _handle_ctrl_enter(event):
            event.current_buffer.validate_and_handle()

        # 禁用上下键加载历史记录（覆盖默认行为）
        @bindings.add('up')
        def _ignore_up(event):
            event.current_buffer.cursor_up()

        @bindings.add('down')
        def _ignore_down(event):
            event.current_buffer.cursor_down()

        # 显式创建输入/输出对象。
        try:
            pt_input = create_input()
        except Exception:
            pt_input = None
        try:
            pt_output = create_output()
        except Exception:
            pt_output = None

        # 创建多行输入会话
        session = PromptSession(
            multiline=True,
            prompt_continuation=lambda width, lineno, is_soft_wrap: '',
            key_bindings=bindings,
            input=pt_input,
            output=pt_output,
        )

        # ★ 核心修复：注册 on_text_changed 钩子，实时组合 surrogate 对。
        # 在 Windows 上 prompt_toolkit 通过 Win32 API 读取扩展字符时，
        # 会将其作为两个独立的 surrogate 字符存入 buffer（𬘫），
        # 每个 surrogate 的 wcwidth 为 -1（不可打印），渲染为 ?。
        # 此钩子在每次 buffer 变更后立即组合，消除渲染问题。
        _install_surrogate_fixer(session)

        print("\n\033[36m输入内容 (Ctrl+\\ 发送，ENTER换行，拖曳添加图像):\033[0m")
        text = session.prompt('')

        # 提交后再做一次 sanitize（处理 prompt() 返回后可能残留的边缘情况）
        text = sanitize_unicode(text)

        return text, True

    except KeyboardInterrupt:
        print("\033[2K\r", end='')
        return "", False
    except Exception as e:
        print(f"\n\033[91m输入错误: {e}\033[0m")
        return "", False


def _install_surrogate_fixer(session: PromptSession) -> None:
    """
    在 PromptSession 的 default_buffer 上安装 surrogate 修复钩子。

    每次 buffer 文本变更时自动检测并组合 surrogate 对，
    确保扩展 Unicode 字符在 TUI 输入区域中正确渲染。
    使用防递归标志避免 on_text_changed 中的无限循环。
    """
    buffer = session.default_buffer
    fixer_state = {'busy': False}

    def _fix_surrogates(_event):
        if fixer_state['busy']:
            return
        fixer_state['busy'] = True
        try:
            text = buffer.text
            # keep_trailing_high=True：输入过程中 high surrogate
            # 先于 low surrogate 到达时，保留末尾 high 等待配对
            fixed = sanitize_unicode(text, keep_trailing_high=True)
            if fixed != text:
                cursor = buffer.cursor_position
                pre_text = text[:cursor]
                pre_fixed = sanitize_unicode(pre_text, keep_trailing_high=True)
                new_cursor = len(pre_fixed)
                buffer.document = buffer.document.__class__(
                    fixed, new_cursor
                )
        finally:
            fixer_state['busy'] = False

    buffer.on_text_changed += _fix_surrogates