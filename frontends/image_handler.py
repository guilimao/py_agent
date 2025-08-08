import base64
import os
import mimetypes
from typing import Tuple, List, Dict, Any
import re

class ImageHandler:
    """处理图像文件的工具类"""
    
    @staticmethod
    def is_image_file(file_path: str) -> bool:
        """检查文件是否为支持的图像格式"""
        if not os.path.exists(file_path):
            return False
        
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('image/'):
            return True
        
        # 检查文件扩展名
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
        ext = os.path.splitext(file_path)[1].lower()
        return ext in image_extensions
    
    @staticmethod
    def encode_image_to_base64(file_path: str) -> str:
        """将图像文件编码为base64字符串"""
        try:
            with open(file_path, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                # 根据扩展名确定MIME类型
                ext = os.path.splitext(file_path)[1].lower()
                mime_map = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp',
                    '.webp': 'image/webp',
                    '.tiff': 'image/tiff',
                    '.svg': 'image/svg+xml'
                }
                mime_type = mime_map.get(ext, 'image/jpeg')
            
            return f"data:{mime_type};base64,{encoded_string}"
        except Exception as e:
            raise Exception(f"图像编码失败: {str(e)}")
    
    @staticmethod
    def extract_image_references(text: str) -> List[str]:
        """从文本中提取可能的图像文件路径"""
        # 匹配常见的文件路径模式
        patterns = [
            r'[a-zA-Z]:\\[^<>"|?*\n\r\t]+\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|svg)',
            r'[^<>"|?*\n\r\t]+\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|svg)',
            r'"([^"]*\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|svg))"',
            r'\'([^\']*\.(?:jpg|jpeg|png|gif|bmp|webp|tiff|svg))\''
        ]
        
        image_paths = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    # 捕获组的情况
                    image_paths.extend([m for m in matches if m])
                else:
                    image_paths.extend(matches)
        
        return list(set(image_paths))  # 去重
    
    @staticmethod
    def process_user_input(text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        处理用户输入，提取图像并返回格式化的内容
        
        Returns:
            Tuple[str, List[Dict[str, Any]]]: (纯文本内容, 图像内容列表)
        """
        image_paths = ImageHandler.extract_image_references(text)
        content_parts = []
        
        # 纯文本内容（移除图像路径）
        clean_text = text
        
        # 处理找到的图像
        processed_images = []
        for image_path in image_paths:
            if ImageHandler.is_image_file(image_path):
                try:
                    base64_url = ImageHandler.encode_image_to_base64(image_path)
                    processed_images.append({
                        "type": "image_url",
                        "image_url": {
                            "url": base64_url
                        }
                    })
                    # 从文本中移除图像路径
                    clean_text = clean_text.replace(image_path, '').strip()
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                except Exception as e:
                    print(f"处理图像 {image_path} 时出错: {e}")
        
        # 如果清理后的文本不为空，添加到内容中
        if clean_text.strip():
            content_parts.append({
                "type": "text",
                "text": clean_text.strip()
            })
        
        # 添加所有图像
        content_parts.extend(processed_images)
        
        return clean_text, content_parts