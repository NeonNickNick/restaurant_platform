import os
import secrets
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename

def save_image(image_file, folder, size=(100, 100)):
    """
    保存图片并调整大小
    :param image_file: 上传的文件对象
    :param folder: 存储的文件夹（avatars/logos/dishes）
    :param size: 目标尺寸
    :return: 文件名
    """
    # 检查是否有文件
    if not image_file or image_file.filename == '':
        return None
    
    # 生成随机文件名
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(image_file.filename)
    filename = random_hex + f_ext
    
    # 确保目录存在
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    
    # 处理图片
    try:
        img = Image.open(image_file)
        
        # 转换为RGB（如果是PNG有透明通道）
        if img.mode in ('RGBA', 'LA', 'P'):
            # 创建白色背景
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # 根据文件夹调整不同的大小
        if folder == 'avatars':
            # 头像调整为100x100
            img.thumbnail((100, 100), Image.Resampling.LANCZOS)
        elif folder == 'dishes':
            # 菜品图片调整为300x300
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        elif folder == 'logos':
            # Logo调整为200x200
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
        else:
            # 默认调整大小
            img.thumbnail(size, Image.Resampling.LANCZOS)
        
        img.save(filepath)
        
        return filename
    except Exception as e:
        # 如果失败，删除文件
        if os.path.exists(filepath):
            os.remove(filepath)
        raise Exception(f'图片处理失败: {str(e)}')

def delete_image(file_path):
    """删除图片文件"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"删除文件失败: {e}")
    return False

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def format_currency(amount):
    """格式化金额显示"""
    if amount is None:
        return "¥0.00"
    return f"¥{amount:,.2f}"

def format_date(date, format_str="%Y-%m-%d %H:%M"):
    """格式化日期显示"""
    if date is None:
        return ""
    return date.strftime(format_str)

def calculate_percentage(part, total):
    """计算百分比"""
    if total == 0:
        return 0
    return round((part / total) * 100, 1)