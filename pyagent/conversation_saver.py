import os
import sqlite3
import json
from datetime import datetime

class ConversationDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "conversations.db")
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建对话表 - content字段使用TEXT类型存储JSON字符串（包含base64编码的图片）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                thinking TEXT,
                content TEXT,  -- 存储文本或JSON字符串（包含base64图片编码）
                tool_calls TEXT,
                tool_call_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_timestamp 
            ON conversations(session_id, timestamp)
        ''')
        
        conn.commit()
        conn.close()
    

    
    def save_conversation(self, messages, session_id="default"):
        """
        保存对话消息到数据库（只保存增量消息）
        :param messages: 消息列表，每个消息是一个字典
        :param session_id: 会话ID，用于区分不同的对话会话
        """
        if not messages:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取数据库中该会话的最后一条消息的时间戳
        cursor.execute('''
            SELECT MAX(timestamp) FROM conversations 
            WHERE session_id = ?
        ''', (session_id,))
        
        result = cursor.fetchone()
        last_timestamp = result[0] if result and result[0] else None
        
        # 筛选出新消息
        new_messages = []
        for msg in messages:
            # 检查消息必须有timestamp
            if msg.get("timestamp") is None:
                raise ValueError(f"消息缺少timestamp字段: {msg}")
            
            msg_timestamp = msg["timestamp"]
            if last_timestamp is None:
                new_messages.append(msg)
            else:
                try:
                    msg_time = datetime.fromisoformat(msg_timestamp.replace('Z', '+00:00'))
                    db_time = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                    if msg_time > db_time:
                        new_messages.append(msg)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"消息timestamp格式错误: {msg_timestamp} - {str(e)}")
        
        # 保存新消息
        for msg in new_messages:
            content = msg.get("content")
            if isinstance(content, list):
                # 如果content是列表（包含图片base64编码），序列化为JSON字符串
                content_str = json.dumps(content, ensure_ascii=False)
            else:
                content_str = content
            
            # 获取消息的timestamp，必须存在
            msg_timestamp = msg.get("timestamp")
            if not msg_timestamp:
                raise ValueError(f"消息缺少timestamp字段: {msg}")
            
            conv = {
                "role": msg["role"],
                "thinking": msg.get("thinking"),
                "content": content_str,
                "tool_calls": json.dumps(msg.get("tool_calls")) if msg.get("tool_calls") else None,
                "tool_call_id": msg.get("tool_call_id"),
                "session_id": session_id,
                "timestamp": msg_timestamp
            }
            
            cursor.execute('''
                INSERT INTO conversations 
                (session_id, role, thinking, content, tool_calls, tool_call_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                conv["session_id"],
                conv["role"],
                conv["thinking"],
                conv["content"],
                conv["tool_calls"],
                conv["tool_call_id"],
                conv["timestamp"]
            ))
        
        conn.commit()
        conn.close()
    
    def get_conversations(self, session_id="default", limit=None):
        """
        获取指定会话的对话历史
        :param session_id: 会话ID
        :param limit: 限制返回的记录数量
        :return: 对话消息列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT role, thinking, content, tool_calls, tool_call_id, timestamp
            FROM conversations 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        '''
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (session_id,))
        rows = cursor.fetchall()
        
        conversations = []
        for row in rows:
            content = row[2]
            
            # 尝试解析content为JSON（处理content列表格式）
            try:
                if content and content.startswith('[') and content.endswith(']'):
                    parsed_content = json.loads(content)
                    if isinstance(parsed_content, list):
                        content = parsed_content
            except (json.JSONDecodeError, ValueError):
                # 如果解析失败，保持原样
                pass
            
            conv = {
                "role": row[0],
                "thinking": row[1],
                "content": content,
                "timestamp": row[5]
            }
            
            if row[3]:  # tool_calls
                conv["tool_calls"] = json.loads(row[3])
            if row[4]:  # tool_call_id
                conv["tool_call_id"] = row[4]
                
            conversations.append(conv)
        
        conn.close()
        return conversations
    
    def get_all_sessions(self):
        """获取所有会话ID列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_id, MIN(timestamp) as first_message_time
            FROM conversations 
            GROUP BY session_id
            ORDER BY first_message_time DESC
        ''')
        
        sessions = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sessions
    
    def delete_session(self, session_id):
        """删除指定会话的所有对话记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM conversations WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
    
    def close(self):
        """关闭数据库连接（实际上每次操作都会关闭，这里为了兼容性保留）"""
        pass

# 全局数据库实例
_db_instance = None

def get_database():
    """获取全局数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ConversationDatabase()
    return _db_instance

def save_conversation(messages, session_id="default"):
    """
    保存对话消息到数据库（兼容原有接口）
    :param messages: 消息列表，每个消息是一个字典
    :param session_id: 会话ID，默认为"default"
    """
    db = get_database()
    db.save_conversation(messages, session_id)