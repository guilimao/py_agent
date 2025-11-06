from flask import Flask, render_template, jsonify, redirect, request
import os
import sqlite3
import json
from datetime import datetime
import pytz
import shutil

app = Flask(__name__)

def get_db_path():
    """获取数据库文件的相对路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pyagent_dir = os.path.dirname(script_dir)
    db_path = os.path.join(pyagent_dir, "conversations.db")
    return os.path.abspath(db_path)

def check_db_exists():
    """检查数据库文件是否存在"""
    db_path = get_db_path()
    return os.path.exists(db_path)

def convert_to_local_time(timestamp_str):
    """将UTC时间转换为本地时间"""
    if not timestamp_str:
        return ""

    try:
        if 'T' in timestamp_str and timestamp_str.endswith('Z'):
            utc_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            utc_time = datetime.fromisoformat(timestamp_str)

        local_tz = pytz.timezone('Asia/Shanghai')
        if utc_time.tzinfo is None:
            utc_time = pytz.utc.localize(utc_time)

        local_time = utc_time.astimezone(local_tz)
        return local_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(timestamp_str)[:19] if timestamp_str else ""

def get_all_sessions():
    """获取所有会话列表"""
    if not check_db_exists():
        return []

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT session_id, MIN(timestamp) as first_message_time, COUNT(*) as message_count
        FROM conversations 
        GROUP BY session_id
        ORDER BY first_message_time DESC
    ''')
    
    sessions = []
    for row in cursor.fetchall():
        session_id, first_message_time, message_count = row
        
        cursor.execute('''
            SELECT content FROM conversations 
            WHERE session_id = ? AND role = 'user'
            ORDER BY timestamp ASC 
            LIMIT 1
        ''', (session_id,))
        
        first_user_msg = cursor.fetchone()
        title = "无标题"
        
        if first_user_msg and first_user_msg[0]:
            content = first_user_msg[0]
            try:
                if content.startswith('[') and content.endswith(']'):
                    parsed = json.loads(content)
                    if isinstance(parsed, list) and parsed:
                        for item in parsed:
                            if isinstance(item, dict) and item.get('type') == 'text' and item.get('text'):
                                title = item['text'][:50]
                                break
                        if title == "无标题" and parsed[0].get('text'):
                            title = parsed[0]['text'][:50]
                else:
                    title = content[:50]
            except:
                title = content[:50]
        
        sessions.append({
            'session_id': session_id,
            'first_message_time': convert_to_local_time(first_message_time),
            'message_count': message_count,
            'title': title
        })
    
    conn.close()
    return sessions

def get_conversations(session_id):
    """获取指定会话的所有消息"""
    if not check_db_exists():
        return []
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT role, thinking, content, tool_calls, tool_call_id, timestamp
        FROM conversations 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
    ''', (session_id,))
    
    conversations = []
    for row in cursor.fetchall():
        role, thinking, content, tool_calls, tool_call_id, timestamp = row
        
        try:
            if content and content.startswith('[') and content.endswith(']'):
                parsed_content = json.loads(content)
                if isinstance(parsed_content, list):
                    content = parsed_content
        except (json.JSONDecodeError, ValueError):
            pass
        
        conv = {
            'role': role,
            'thinking': thinking,
            'content': content,
            'timestamp': convert_to_local_time(timestamp)
        }
        
        if tool_calls:
            conv['tool_calls'] = json.loads(tool_calls)
        if tool_call_id:
            conv['tool_call_id'] = tool_call_id
            
        conversations.append(conv)
    
    conn.close()
    return conversations

@app.route('/')
def index():
    """主页 - 重定向到第一个会话"""
    if not check_db_exists():
        return render_template('session.html',
                             conversations=[],
                             current_session=None,
                             sessions=[],
                             db_exists=False)

    sessions = get_all_sessions()
    if sessions:
        return redirect('/session/' + sessions[0]['session_id'])
    else:
        return render_template('session.html',
                             conversations=[],
                             current_session=None,
                             sessions=[],
                             db_exists=True)

@app.route('/session/<session_id>')
def view_session(session_id):
    """查看指定会话的详细内容"""
    if not check_db_exists():
        return render_template('session.html',
                             conversations=[],
                             current_session=None,
                             sessions=[],
                             db_exists=False)

    conversations = get_conversations(session_id)
    sessions = get_all_sessions()

    return render_template('session.html',
                         conversations=conversations,
                         current_session=session_id,
                         sessions=sessions,
                         db_exists=True)

@app.route('/api/sessions')
def api_sessions():
    """API - 获取所有会话列表"""
    if not check_db_exists():
        return jsonify({'error': '数据库不存在'}), 404

    sessions = get_all_sessions()
    return jsonify(sessions)

@app.route('/api/session/<session_id>')
def api_session(session_id):
    """API - 获取指定会话的详细内容"""
    if not check_db_exists():
        return jsonify({'error': '数据库不存在'}), 404

    conversations = get_conversations(session_id)
    return jsonify(conversations)

@app.route('/import-database', methods=['POST'])
def import_database():
    """导入数据库文件"""
    if 'database' not in request.files:
        return jsonify({'error': '没有选择文件'}), 400

    file = request.files['database']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if not file.filename.endswith('.db'):
        return jsonify({'error': '请选择有效的数据库文件(.db)'}), 400

    try:
        db_path = get_db_path()

        if os.path.exists(db_path):
            backup_path = db_path + '.backup'
            shutil.copy2(db_path, backup_path)

        file.save(db_path)

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
            if not cursor.fetchone():
                conn.close()
                if os.path.exists(db_path + '.backup'):
                    shutil.copy2(db_path + '.backup', db_path)
                return jsonify({'error': '无效的数据库文件，缺少conversations表'}), 400
            conn.close()
        except Exception as e:
            if os.path.exists(db_path + '.backup'):
                shutil.copy2(db_path + '.backup', db_path)
            return jsonify({'error': f'数据库文件无效: {str(e)}'}), 500

        if os.path.exists(db_path + '.backup'):
            os.remove(db_path + '.backup')

        return jsonify({'success': True, 'message': '数据库导入成功'})

    except Exception as e:
        return jsonify({'error': f'导入失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)