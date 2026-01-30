import subprocess
import threading
import time
import chardet
import os
import sys
from typing import Dict, List, Optional, Tuple
from queue import Queue, Empty


class TerminalSession:
    """单个终端会话的管理类"""
    
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.process: Optional[subprocess.Popen] = None
        self.output_queue = Queue()
        self.output_lines: List[str] = []
        self.last_activity = time.time()
        self.is_running = False
        self.current_command = ""
        self.start_time = time.time()
        
    def start(self):
        """启动新的终端会话"""
        try:
            # 根据操作系统选择合适的shell
            if os.name == 'nt':  # Windows
                self.process = subprocess.Popen(
                    ['cmd.exe'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    bufsize=0
                )
            else:  # Unix-like systems
                self.process = subprocess.Popen(
                    ['/bin/bash'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    bufsize=0
                )
            
            self.is_running = True
            
            # 启动输出读取线程
            self._start_output_reader()
            
            return True
        except Exception as e:
            return False
    
    def _start_output_reader(self):
        """启动后台线程读取终端输出"""
        def read_output():
            while self.is_running and self.process and self.process.stdout:
                try:
                    # 读取输出数据
                    data = self.process.stdout.read(1024)
                    if not data:
                        break
                    
                    # 根据操作系统使用固定的编码顺序解码
                    text = None
                    if os.name == 'nt':  # Windows 系统
                        # Windows 优先尝试 GBK/GB2312，然后是 UTF-8
                        for encoding in ['gbk', 'gb2312', 'utf-8', 'latin-1']:
                            try:
                                text = data.decode(encoding, errors='strict')
                                break
                            except UnicodeDecodeError:
                                continue
                    else:  # Unix-like 系统
                        # Linux/Mac 优先尝试 UTF-8
                        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                            try:
                                text = data.decode(encoding, errors='strict')
                                break
                            except UnicodeDecodeError:
                                continue
                    
                    # 如果所有编码都失败，使用 latin-1 确保不丢失数据
                    if text is None:
                        text = data.decode('latin-1', errors='ignore')
                    
                    # 将输出按行分割并存储
                    lines = text.splitlines(keepends=True)
                    for line in lines:
                        clean_line = line.rstrip('\r\n')
                        if clean_line:
                            self.output_lines.append(clean_line)
                            self.output_queue.put(clean_line)
                    
                    self.last_activity = time.time()
                    
                    # 限制存储的行数，防止内存占用过大
                    if len(self.output_lines) > 10000:
                        self.output_lines = self.output_lines[-5000:]
                        
                except Exception as e:
                    # 读取错误时停止
                    break
        
        # 启动后台线程
        reader_thread = threading.Thread(target=read_output, daemon=True)
        reader_thread.start()
    
    # 已废弃，现在使用固定编码顺序解码
    # def _detect_encoding(self, data: bytes) -> str:
    #     """使用chardet检测字节数据的编码"""
    #     try:
    #         detection = chardet.detect(data)
    #         return detection['encoding'] or 'utf-8'
    #     except Exception:
    #         return 'utf-8'
    
    def execute_command(self, command: str) -> bool:
        """在终端中执行命令"""
        if not self.is_running or not self.process:
            return False
        
        try:
            # 确保命令以换行符结尾
            if not command.endswith('\n'):
                command += '\n'
            
            self.process.stdin.write(command.encode('utf-8'))
            self.process.stdin.flush()
            
            self.current_command = command.strip()
            self.last_activity = time.time()
            
            return True
        except Exception:
            return False
    
    def get_recent_output(self, count: int = 30) -> List[str]:
        """获取最近的输出内容"""
        return self.output_lines[-count:] if len(self.output_lines) >= count else self.output_lines
    
    def get_last_output(self, count: int = 20) -> List[str]:
        """获取上一条命令的最后输出"""
        return self.output_lines[-count:] if len(self.output_lines) >= count else self.output_lines
    
    def is_command_complete(self, timeout: float = 3.0) -> Tuple[bool, str]:
        """
        检查命令是否执行完成
        返回: (是否完成, 状态描述)
        """
        current_time = time.time()
        
        # 如果进程已经结束
        if self.process and self.process.poll() is not None:
            return True, "进程已结束"
        
        # 如果超过1分钟，返回执行中状态
        if current_time - self.last_activity > 60:
            return False, "命令执行中"
        
        # 检查5秒内是否有新输出
        if current_time - self.last_activity > timeout:
            return True, "执行完毕"
        
        return False, "执行中"
    
    def close(self):
        """关闭终端会话"""
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass
            finally:
                self.process = None


class TerminalManager:
    """终端会话管理器"""
    
    def __init__(self):
        self.sessions: Dict[int, TerminalSession] = {}
    
    def get_or_create_session(self, session_id: int) -> TerminalSession:
        """获取或创建指定ID的终端会话"""
        if session_id not in self.sessions:
            session = TerminalSession(session_id)
            if session.start():
                self.sessions[session_id] = session
            else:
                raise RuntimeError(f"无法创建终端会话 {session_id}")
        
        return self.sessions[session_id]
    
    def close_session(self, session_id: int):
        """关闭指定ID的终端会话"""
        if session_id in self.sessions:
            self.sessions[session_id].close()
            del self.sessions[session_id]
    
    def close_all_sessions(self):
        """关闭所有终端会话"""
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()


# 全局终端管理器实例
terminal_manager = TerminalManager()


def truncate_output_by_chars(output_text: str, max_chars: int = 5000) -> str:
    """
    当输出文本超过最大字符数时，截断为最后若干行，使总字符数不超过限制
    
    Args:
        output_text: 原始输出文本
        max_chars: 最大字符数限制
        
    Returns:
        截断后的输出文本
    """
    if len(output_text) <= max_chars:
        return output_text
    
    # 提示信息
    truncation_message = "...\n(由于输出过长，已截断为最后若干行)\n"
    message_len = len(truncation_message)
    
    # 计算可用于实际内容的字符数
    available_chars = max_chars - message_len
    
    # 如果可用字符数不足，直接返回提示信息
    if available_chars <= 0:
        return truncation_message.strip()
    
    # 简单方法：从末尾截取 available_chars 个字符
    # 然后确保从行开头开始
    truncated = output_text[-available_chars:]
    
    # 查找第一个换行符，确保从完整行开始
    first_newline = truncated.find('\n')
    if first_newline != -1:
        truncated = truncated[first_newline + 1:]
    
    # 构建最终结果
    result = truncation_message + truncated
    
    # 确保不超过限制
    if len(result) > max_chars:
        result = result[:max_chars]
    
    return result


def execute_command(send: str = None, session_id: int = None, refresh: bool = False) -> str:
    """
    在命令行终端中执行命令
    
    Args:
        send: 需要执行的命令
        session_id: 终端会话编号（任意整数）
        refresh: 是否刷新状态（True时只返回最近输出，不执行命令）
    
    Returns:
        str: 包含执行结果、会话编号和执行状态的格式化字符串
    """
    
    if session_id is None:
        return "❌ 错误：必须指定会话编号(session_id)"
    
    try:
        # 获取或创建终端会话
        session = terminal_manager.get_or_create_session(session_id)
        
        if refresh:
            # 刷新状态，返回最近20条输出
            recent_output = session.get_last_output(20)
            if not recent_output:
                return f"会话 {session_id} 暂无输出"
            
            output_text = "\n".join(recent_output)
            # 应用字符数截断
            output_text = truncate_output_by_chars(output_text, 5000)
            return f"""
📟 终端会话 {session_id} - 状态刷新
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 会话编号: {session_id}
📊 执行状态: 刷新状态
"""
        
        if not send:
            return "❌ 错误：必须提供要执行的命令(send)"
        
        # 执行命令
        if not session.execute_command(send):
            return f"❌ 错误：无法在会话 {session_id} 中执行命令"
        
        # 等待命令执行或超时
        start_time = time.time()
        max_wait = 60  # 最大等待60秒
        
        while True:
            is_complete, status = session.is_command_complete()
            
            if is_complete:
                # 命令执行完成
                output = session.get_recent_output()
                output_text = "\n".join(output)
                # 应用字符数截断
                output_text = truncate_output_by_chars(output_text, 5000)
                
                return f"""
📟 终端会话 {session_id} - 命令执行完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {send}
📋 输出结果:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 会话编号: {session_id}
📊 执行状态: 执行完毕
"""
            
            elif status == "命令执行中":
                # 超过1分钟，返回最近30条输出
                output = session.get_recent_output(30)
                if len(session.output_lines) > 30:
                    output_text = "...\n" + "\n".join(output)
                else:
                    output_text = "\n".join(output)
                
                # 应用字符数截断
                output_text = truncate_output_by_chars(output_text, 5000)
                
                return f"""
📟 终端会话 {session_id} - 命令执行中
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {send}
⏱️  运行时间: {int(time.time() - start_time)}秒
📋 最近输出:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 会话编号: {session_id}
📊 执行状态: 执行中
"""
            
            # 检查是否超时
            if time.time() - start_time > max_wait:
                output = session.get_recent_output(30)
                output_text = "\n".join(output)
                # 应用字符数截断
                output_text = truncate_output_by_chars(output_text, 5000)
                
                return f"""
📟 终端会话 {session_id} - 命令超时
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 执行命令: {send}
⏱️  运行时间: {int(time.time() - start_time)}秒 (超时)
📋 当前输出:
{output_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 会话编号: {session_id}
📊 执行状态: 执行中
"""
            
            # 短暂等待后继续检查
            time.sleep(5)
    
    except Exception as e:
        return f"❌ 执行命令时发生错误: {str(e)}"


# 工具元信息（供LLM识别）
COMMAND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "在命令行终端中执行命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "send": {
                        "type": "string",
                        "description": "需要执行的命令"
                    },
                    "session_id": {
                        "type": "integer",
                        "description": "终端会话编号（指定命令由哪个终端执行，新建终端时指定一个新编号即可）"
                    },
                    "refresh": {
                        "type": "boolean",
                        "description": "检查终端状态（True时只返回最近输出，不执行命令）",
                        "default": False
                    }
                },
                "required": ["session_id"]
            }
        }
    }
]

# 工具函数映射（供Agent调用）
COMMAND_FUNCTIONS = {
    "execute_command": execute_command
}


# 清理函数（程序退出时调用）
def cleanup():
    """清理所有终端会话"""
    terminal_manager.close_all_sessions()


# 注册清理函数
import atexit
atexit.register(cleanup)