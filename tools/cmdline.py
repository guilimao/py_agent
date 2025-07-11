import subprocess
import threading
import uuid
import time
from queue import Queue, Empty
import chardet  # 用于编码检测
import sys
import platform

# === 会话类 ===
class CommandSession:
    def __init__(self, command: str):
        self.command = command
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0  # 使用无缓冲模式
        )
        self.output_buffer = []  # 存储所有输出字节数据
        self.last_output_position = 0  # 记录上次读取的位置
        self.queue = Queue()
        self.completed = False  # 明确标记会话是否完成
        self.encoding = None  # 存储检测到的编码
        self.last_output_time = time.time()  # 最后输出时间
        self.status = "running"  # 添加会话状态: running, completed, timed_out
        self.start_time = time.time()  # 记录命令开始时间
        self.long_running_notified = False  # 标记是否已通知长时间运行
        
        self._start_reader()
        self._start_monitor()
        
        # 系统默认编码，用于优先尝试
        self.system_encoding = self._get_system_encoding()

    def _get_system_encoding(self):
        """获取系统默认编码"""
        # Windows系统通常使用GBK或GB2312
        if platform.system() == 'Windows':
            return 'gbk'  # 大多数Windows中文版使用GBK
            
        # Linux/MacOS通常使用UTF-8
        return 'utf-8'

    def _start_reader(self):
        def reader():
            """读取字节数据并放入队列"""
            while self.status == "running":
                chunk = self.process.stdout.read(4096)  # 读取字节块
                if not chunk:  # 进程结束
                    break
                self.output_buffer.append(chunk)
                self.queue.put(chunk)
                self.last_output_time = time.time()  # 更新最后输出时间

            # 标记会话完成
            if self.status == "running":  # 只在仍是运行状态时标记完成
                self.status = "completed"
                self.queue.put(b"\n[Command Completed]\n")
                self.output_buffer.append(b"\n[Command Completed]\n")

        self.reader_thread = threading.Thread(target=reader, daemon=True)
        self.reader_thread.start()

    def _detect_encoding(self):
        """检测输出编码，优先考虑系统默认编码"""
        if self.encoding:  # 如果已经检测到编码，不再重复检测
            return
            
        full_data = b''.join(self.output_buffer)
        if len(full_data) < 100:  # 数据量太小，可能无法准确检测
            return
            
        # 首先尝试系统默认编码
        try:
            full_data.decode(self.system_encoding)
            self.encoding = self.system_encoding
            return
        except UnicodeDecodeError:
            pass  # 继续尝试其他编码
            
        # 使用chardet检测
        result = chardet.detect(full_data)
        confidence = result['confidence']
        encoding = result['encoding'] or 'utf-8'
        
        # 降低置信度要求，增加常见中文编码的优先级
        if confidence > 0.4:
            # 对常见中文编码给予更高优先级
            if encoding.lower() in ['gb2312', 'gbk', 'gb18030']:
                self.encoding = encoding
            else:
                # 对UTF-8要求更高的置信度
                if encoding.lower() == 'utf-8' and confidence > 0.6:
                    self.encoding = encoding
                else:
                    # 对其他编码使用系统默认编码
                    self.encoding = self.system_encoding
        else:
            # 尝试几种常见编码，按优先级排序
            priority_encodings = [
                self.system_encoding,  # 系统默认编码优先
                'utf-8',
                'gbk',
                'gb2312',
                'gb18030',
                'cp936'
            ]
            
            for enc in priority_encodings:
                try:
                    full_data.decode(enc)
                    self.encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            else:
                self.encoding = 'utf-8'  # 所有尝试都失败，默认使用UTF-8

    def _start_monitor(self):
        """监控进程状态和超时"""
        def monitor():
            # 等待进程结束
            self.process.wait()

            # 如果状态仍是运行中，则标记为完成
            if self.status == "running":
                self.status = "completed"
                # 添加结束标记
                self.queue.put(b"\n[Command Completed]\n")
                self.output_buffer.append(b"\n[Command Completed]\n")

        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
    
    def check_timeout(self):
        """检查会话是否因超时而暂停"""
        if self.status == "running" and self.process.poll() is None:
            # 检查超过5秒无新输出
            if time.time() - self.last_output_time > 5.0:
                self.status = "timed_out"
                return True
        return False

    def read_output(self, max_bytes=4096) -> bytes:
        """从队列中读取字节数据"""
        chunks = []
        total_bytes = 0
        while total_bytes < max_bytes:
            try:
                chunk = self.queue.get_nowait()
                chunks.append(chunk)
                total_bytes += len(chunk)
            except Empty:
                break
        return b''.join(chunks)

    def get_new_output(self) -> str:
        """获取自上次读取以来的新输出（已解码）"""
        # 获取新的字节块
        new_bytes = b''.join(self.output_buffer[self.last_output_position:])
        
        # 更新读取位置
        self.last_output_position = len(self.output_buffer)
        
        # 如果尚未检测到编码，使用系统默认编码
        encoding = self.encoding if self.encoding else self.system_encoding
        
        try:
            return new_bytes.decode(encoding, errors='replace')
        except UnicodeDecodeError:
            # 如果解码失败，尝试使用系统默认编码
            return new_bytes.decode(self.system_encoding, errors='replace')

    def get_full_output(self) -> str:
        """获取完整的解码输出"""
        # 在输出最终结果前进行编码检测
        self._detect_encoding()

        # 如果仍然没有检测到编码，使用系统默认编码
        if not self.encoding:
            self.encoding = self.system_encoding

        full_data = b''.join(self.output_buffer)
        try:
            return full_data.decode(self.encoding, errors='replace')
        except (UnicodeDecodeError, LookupError):
            return full_data.decode(self.system_encoding, errors='replace')

    def is_finished(self) -> bool:
        """检查会话是否真正结束（进程退出）"""
        return self.status == "completed"
    
    def is_timed_out(self) -> bool:
        """检查会话是否因超时而暂停"""
        return self.status == "timed_out"
    
    def is_active(self) -> bool:
        """检查会话是否仍在运行"""
        return self.status == "running"
    
    def is_long_running(self) -> bool:
        """检查会话是否运行超过15秒"""
        return time.time() - self.start_time > 15.0

    def send_input(self, text: str):
        """发送输入到进程"""
        if self.status == "running" and self.process.poll() is None:
            # 使用UTF-8编码输入
            self.process.stdin.write(text.encode('utf-8') + b'\n')
            self.process.stdin.flush()
        elif self.status == "timed_out":
            # 如果会话因超时暂停，重新激活
            self.status = "running"
            self.last_output_time = time.time()  # 重置超时计时器
            self.process.stdin.write(text.encode('utf-8') + b'\n')
            self.process.stdin.flush()

    def terminate(self):
        """终止命令进程"""
        if self.status == "running" and self.process.poll() is None:
            # 终止进程
            self.process.terminate()
            # 等待进程结束
            self.process.wait()
            # 设置状态为terminated
            self.status = "terminated"
            # 添加终止标记
            self.queue.put(b"\n[Command Terminated]\n")
            self.output_buffer.append(b"\n[Command Terminated]\n")


# === 会话管理器 ===
class CommandSessionManager:
    def __init__(self):
        self.sessions = {}

    def start_command(self, command: str) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = CommandSession(command)
        return session_id

    def get_output_with_status(self, session_id: str) -> tuple:
        """获取输出和状态信息"""
        session = self.sessions.get(session_id)
        if not session:
            return ("[无效的会话 ID]", "invalid")
        
        # 检查超时状态
        session.check_timeout()
        
        if session.is_finished():
            output = session.get_full_output()
            status = "已完成"
        elif session.is_timed_out():
            output = session.get_new_output() + "\n\n[会话因等待输入而暂停]"
            status = "等待输入中"
        else:
            # 只获取自上次读取以来的新输出
            output = session.get_new_output()
            status = "运行中"
            
            # 添加长时间运行提示
            if session.is_long_running() and not session.long_running_notified:
                output += "\n\n[注意] 指令运行时长过长，但仍在运行中"
                session.long_running_notified = True
            
        return (output, status)

    def send_input(self, session_id: str, input_text: str) -> tuple:
        session = self.sessions.get(session_id)
        if not session:
            return ("[无效的会话 ID]", "invalid")

        if session.is_finished():
            return (f"[错误] 会话 {session_id} 已结束，无法发送输入", "已完成")
        
        session.send_input(input_text)
        # 等待一小段时间让命令处理输入
        time.sleep(0.1)
        return self.get_output_with_status(session_id)

    def terminate(self, session_id: str) -> tuple:
        session = self.sessions.get(session_id)
        if not session:
            return ("[无效的会话 ID]", "invalid")

        if not session.is_finished():
            # 改为调用 session.terminate() 方法
            session.terminate()
            
        output = session.get_full_output()
        return (output, "已终止")


# === 实例化管理器 ===
SESSION_MANAGER = CommandSessionManager()

def command_session(action: str, command: str = None, session_id: str = None, input_text: str = None) -> str:
    if action == "start":
        if not command:
            return "[错误] start 操作需要提供 command 参数"
        sid = SESSION_MANAGER.start_command(command)
        
        # 等待命令完成或超时
        start_time = time.time()
        accumulated_output = ""
        status = "运行中"
        
        while status == "运行中":
            # 检查是否超过15秒
            if time.time() - start_time > 15.0:
                # 获取当前所有输出
                new_output, status = SESSION_MANAGER.get_output_with_status(sid)
                accumulated_output += new_output
                break
                
            time.sleep(2)  # 每次等待2秒
            new_output, status = SESSION_MANAGER.get_output_with_status(sid)
            accumulated_output += new_output
        
        # 添加状态标记
        result = f"【状态】{status}\n【输出】\n{accumulated_output}"
        
        # 添加会话ID信息
        result += f"\n\n【会话ID】{sid}"
        return result

    elif action == "send":
        if not session_id or input_text is None:
            return "[错误] send 操作需要提供 session_id 和 input_text"
        output, status = SESSION_MANAGER.send_input(session_id, input_text)
        return f"【状态】{status}\n【输出】\n{output}"

    elif action == "terminate":
        if not session_id:
            return "[错误] terminate 操作需要提供 session_id 参数"
        output, status = SESSION_MANAGER.terminate(session_id)
        return f"【状态】{status}\n【输出】\n{output}"

    elif action == "status":
        if not session_id:
            return "[错误] status 操作需要提供 session_id 参数"
        
        output, status = SESSION_MANAGER.get_output_with_status(session_id)
        return f"【状态】{status}\n【输出】\n{output}"

    else:
        return f"[错误] 未知的操作类型：{action}"

COMMAND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "command_session",
            "description": "用于执行命令行指令，支持建立持久会话",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "send", "terminate", "status"],
                        "description": "操作类型：start=启动命令，返回执行结果；send=对已有的会话发送输入；terminate=强制终止会话；status=查看指定会话的进一步信息"
                    },
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，仅在 start 时使用"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "命令会话 ID，用于 send、terminate、status"
                    },
                    "input_text": {
                        "type": "string",
                        "description": "发送到已有会话的输入内容，仅在 send 时使用"
                    }
                },
                "required": ["action"]
            }
        }
    }
]

COMMAND_FUNCTIONS = {
    "command_session": command_session
}

if __name__ == "__main__":
    print("=== 命令会话测试工具 ===")
    print("支持的操作类型: start, send, terminate, status")
    print("输入 'exit' 或 'quit' 退出程序")
    print("========================\n")
    
    while True:
        # 获取操作类型
        action = input("请输入操作类型 (start/send/terminate/status): ").strip().lower()
        
        # 检查是否退出
        if action in ['exit', 'quit']:
            print("程序已退出")
            break
            
        # 检查操作类型是否有效
        if action not in ['start', 'send', 'terminate', 'status']:
            print("无效的操作类型，请重新输入")
            continue
            
        # 根据操作类型获取所需参数
        command = None
        session_id = None
        input_text = None
        
        if action == 'start':
            command = input("请输入要执行的命令: ").strip()
            if not command:
                print("命令不能为空")
                continue
        else:
            session_id = input("请输入会话ID: ").strip()
            if not session_id:
                print("会话ID不能为空")
                continue
                
            if action == 'send':
                input_text = input("请输入要发送的内容: ")
        
        # 执行命令会话
        try:
            result = command_session(
                action=action,
                command=command,
                session_id=session_id,
                input_text=input_text
            )
            
            # 格式化输出结果
            print("\n" + "=" * 50)
            print(f"操作: {action}")
            if command:
                print(f"命令: {command}")
            if session_id:
                print(f"会话ID: {session_id}")
            print("-" * 50)
            print(result)
            print("=" * 50 + "\n")
            
        except Exception as e:
            print(f"\n执行过程中发生错误: {str(e)}\n")