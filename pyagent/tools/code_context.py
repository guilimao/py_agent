import os
import chardet
from typing import List, Dict

# 默认支持的文件扩展名
DEFAULT_EXTENSIONS = {
    '.py', '.js', '.java', '.cpp', '.c', '.ts', '.go', '.php', '.vue', '.tsx', 
    '.json', '.yaml', '.yml', '.ini', '.toml', '.env', '.properties', '.txt',
    '.html', '.css', '.xml', '.sql', '.sh', '.bat', '.md', '.rst'
}


def _get_all_files(directory: str) -> List[str]:
    """获取目录下所有符合扩展名的文件"""
    target_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext in DEFAULT_EXTENSIONS:
                target_files.append(file_path)
    
    return sorted(target_files)


def _read_file_with_encoding(file_path: str) -> str:
    """使用chardet检测编码并读取文件内容"""
    try:
        # 首先读取二进制数据用于编码检测
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        # 使用chardet检测编码
        detection = chardet.detect(raw_data)
        encoding = detection['encoding'] or 'utf-8'
        
        # 使用检测到的编码解码文件内容
        try:
            content = raw_data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            # 如果检测的编码失败，尝试常见编码
            for alt_encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                try:
                    content = raw_data.decode(alt_encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content = raw_data.decode('latin-1', errors='ignore')
        
        return content
    
    except Exception as e:
        return f"[读取文件失败: {str(e)}]"


def extract_code_context(directory: str) -> str:
    """
    提取指定路径下的所有符合扩展名的文件内容
    
    Args:
        directory: 目标目录路径
    
    Returns:
        str: 格式化的文件内容字符串
    """
    
    if not os.path.isdir(directory):
        return f"错误：目录 {directory} 不存在"
    
    # 获取所有目标文件
    files = _get_all_files(directory)
    
    if not files:
        return f"警告：目录 {directory} 中未找到符合扩展名的文件"
    
    # 构建目录结构信息
    result_parts = ["目录结构:"]
    base_dir = os.path.abspath(directory)
    
    for file_path in files:
        rel_path = os.path.relpath(file_path, base_dir)
        result_parts.append(f"  {rel_path}")
    
    result_parts.append("")  # 空行分隔
    
    # 读取并添加所有文件内容
    for file_path in files:
        rel_path = os.path.relpath(file_path, base_dir)
        content = _read_file_with_encoding(file_path)
        
        result_parts.extend([
            f"<{rel_path} 开始>",
            content,
            f"<{rel_path} 结束>",
            ""
        ])
    
    return "\n".join(result_parts).rstrip()


# 工具元信息（供LLM识别）
CODE_CONTEXT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_code_context",
            "description": "提取指定路径下的所有代码文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目标目录路径"
                    }
                },
                "required": ["directory"]
            }
        }
    }
]

# 工具函数映射（供Agent调用）
CODE_CONTEXT_FUNCTIONS = {
    "extract_code_context": extract_code_context
}