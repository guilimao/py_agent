import sqlite3
import os
import json
from typing import List, Dict, Any, Optional, Union
from contextlib import contextmanager

@contextmanager
def connect_to_db(db_path: str):
    """上下文管理器，用于连接到SQLite数据库"""
    conn = None
    try:
        # 确保数据库文件存在
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")
        
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 使用Row工厂以便获取列名
        yield conn
    except Exception as e:
        raise e
    finally:
        if conn:
            conn.close()

def execute_sql_query(db_path: str, query: str) -> str:
    """
    执行SQL查询并返回结果
    
    Args:
        db_path: SQLite数据库文件路径
        query: 要执行的SQL查询语句
        
    Returns:
        查询结果字符串，当结果长度大于3000字符时将被截断并添加提示
    """
    try:
        # 验证数据库文件路径
        db_path = os.path.abspath(db_path)
        if not os.path.exists(db_path):
            return f"错误：数据库文件不存在 - {db_path}"
        
        # 验证查询语句
        if not query or not query.strip():
            return "错误：查询语句不能为空"
        
        query = query.strip()
        
        with connect_to_db(db_path) as conn:
            cursor = conn.cursor()
            
            # 执行查询
            cursor.execute(query)
            
            # 获取列名
            column_names = [description[0] for description in cursor.description] if cursor.description else []
            
            # 获取所有结果行
            rows = cursor.fetchall()
            
            # 构建结果
            result_parts = []
            
            # 添加查询信息
            result_parts.append(f"数据库: {db_path}")
            result_parts.append(f"查询: {query}")
            result_parts.append("")
            
            if not column_names:
                # 没有列名，可能是非SELECT查询（如INSERT、UPDATE等）
                if rows:
                    # 有行但无列名，可能是PRAGMA等特殊查询
                    result_parts.append(f"查询影响的行数: {len(rows)}")
                    result_parts.append("")
                    
                    # 显示行数据
                    for i, row in enumerate(rows):
                        result_parts.append(f"行 {i+1}: {row}")
                else:
                    # 检查是否是非查询语句
                    if query.upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                        result_parts.append(f"执行成功，影响行数: {cursor.rowcount}")
                    else:
                        result_parts.append("查询执行成功，但未返回结果")
            else:
                # 有列名，是SELECT查询
                result_parts.append(f"查询结果: {len(rows)} 行，{len(column_names)} 列")
                result_parts.append("")
                
                # 构建表头
                header = "| " + " | ".join(str(name) for name in column_names) + " |"
                separator = "|-" + "-|-".join(["-" * len(str(name)) for name in column_names]) + "-|"
                
                result_parts.append(header)
                result_parts.append(separator)
                
                # 添加数据行
                for row in rows:
                    # 将行数据转换为列表
                    row_data = []
                    for col in column_names:
                        value = row[col] if col in row.keys() else row[column_names.index(col)]
                        # 处理None值和长文本
                        if value is None:
                            row_data.append("NULL")
                        else:
                            # 将值转换为字符串，如果太长则截断
                            str_value = str(value)
                            if len(str_value) > 100:
                                str_value = str_value[:97] + "..."
                            row_data.append(str_value)
                    
                    row_str = "| " + " | ".join(row_data) + " |"
                    result_parts.append(row_str)
            
            # 添加查询统计
            result_parts.append("")
            result_parts.append("--- 查询完成 ---")
            
            # 检查结果长度
            full_result = "\n".join(result_parts)
            if len(full_result) <= 3000:
                return full_result
            else:
                # 截断结果
                truncated_result = "\n".join(result_parts[:30])  # 保留前30行
                remaining_lines = len(result_parts) - 30
                if remaining_lines > 0:
                    truncated_result += f"\n\n[提示：结果过长，已截断部分内容。完整结果包含{len(result_parts)}行，超过3000字符。建议优化查询或导出结果到文件]"
                return truncated_result
                
    except sqlite3.Error as e:
        return f"SQLite错误: {str(e)}"
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"执行查询时发生错误: {str(e)}"

def get_table_info(db_path: str) -> str:
    """
    获取数据库的表结构信息
    
    Args:
        db_path: SQLite数据库文件路径
        
    Returns:
        表结构信息字符串
    """
    try:
        db_path = os.path.abspath(db_path)
        if not os.path.exists(db_path):
            return f"错误：数据库文件不存在 - {db_path}"
        
        with connect_to_db(db_path) as conn:
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = cursor.fetchall()
            
            result_parts = []
            result_parts.append(f"数据库: {db_path}")
            result_parts.append(f"表数量: {len(tables)}")
            result_parts.append("")
            
            if not tables:
                result_parts.append("数据库中没有表")
                return "\n".join(result_parts)
            
            for table_row in tables:
                table_name = table_row[0]
                result_parts.append(f"表: {table_name}")
                
                # 获取表结构
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # 构建列信息表
                if columns:
                    result_parts.append("  列结构:")
                    result_parts.append("  | 列名 | 类型 | 是否非空 | 默认值 | 主键 |")
                    result_parts.append("  |------|------|----------|--------|------|")
                    
                    for col in columns:
                        # col格式: (cid, name, type, notnull, dflt_value, pk)
                        col_name = col[1]
                        col_type = col[2] if col[2] else "TEXT"
                        not_null = "是" if col[3] else "否"
                        default_value = col[4] if col[4] is not None else "NULL"
                        pk = "是" if col[5] else "否"
                        result_parts.append(f"  | {col_name} | {col_type} | {not_null} | {default_value} | {pk} |")
                
                # 获取行数
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                result_parts.append(f"  行数: {row_count}")
                result_parts.append("")
            
            result = "\n".join(result_parts)
            if len(result) > 3000:
                truncated = result[:2900] + "\n\n[提示：表结构信息过长，已截断部分内容]"
                return truncated
            return result
            
    except Exception as e:
        return f"获取表信息时发生错误: {str(e)}"

# 工具元信息（供LLM识别）
SQLITE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "执行SQL查询并返回结果。支持SQLite数据库，可以执行SELECT、INSERT、UPDATE、DELETE等SQL语句。当返回结果长度大于3000字符时，将结果截断并添加提示。",
            "parameters": {
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "SQLite数据库文件路径"
                    },
                    "query": {
                        "type": "string",
                        "description": "要执行的SQL查询语句"
                    }
                },
                "required": ["db_path", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_info",
            "description": "获取SQLite数据库的表结构信息，包括表名、列结构、行数等。当返回结果长度大于3000字符时，将结果截断并添加提示。",
            "parameters": {
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "SQLite数据库文件路径"
                    }
                },
                "required": ["db_path"]
            }
        }
    }
]

# 工具函数映射（供Agent调用）
SQLITE_FUNCTIONS = {
    "execute_sql_query": execute_sql_query,
    "get_table_info": get_table_info
}