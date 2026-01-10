from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from PIL import Image
import os
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

# 创建蓝图
auth_bp = Blueprint('auth', __name__)

# 注意：在函数内部导入以避免循环导入
def get_db():
    from app import db
    return db

def get_forms():
    from app.forms import RegistrationForm, LoginForm, ChangePasswordForm, ChangeAvatarForm, ChangeUsernameForm
    return RegistrationForm, LoginForm, ChangePasswordForm, ChangeAvatarForm, ChangeUsernameForm

def get_models():
    from app.models import User, Dish, Order, Restaurant
    return User, Dish, Order, Restaurant

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_avatar(avatar_file):
    """保存并处理头像文件"""
    # 生成随机文件名
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(avatar_file.filename)
    avatar_filename = random_hex + f_ext
    avatar_path = os.path.join(current_app.config['AVATAR_UPLOAD_FOLDER'], avatar_filename)
    
    # 保存原始文件
    avatar_file.save(avatar_path)
    
    # 调整图片大小
    try:
        img = Image.open(avatar_path)
        # 将图片转换为RGB模式（如果是PNG的话）
        if img.mode in ('RGBA', 'LA', 'P'):
            # 创建一个白色背景
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # 调整大小
        output_size = (100, 100)
        img.thumbnail(output_size, Image.Resampling.LANCZOS)
        img.save(avatar_path)
    except Exception as e:
        # 如果处理失败，删除文件并抛出异常
        os.remove(avatar_path)
        raise e
    
    return avatar_filename

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    RegistrationForm, _, _, _, _ = get_forms()
    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            # 保存头像
            avatar_filename = save_avatar(form.avatar.data)
            
            # 创建用户
            hashed_password = generate_password_hash(form.password.data)
            User, _, _, _ = get_models()
            db = get_db()
            
            user = User(
                username=form.username.data,
                email=form.email.data,
                password_hash=hashed_password,
                avatar_path=avatar_filename
            )
            
            db.session.add(user)
            db.session.commit()
            
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'注册失败：{str(e)}', 'danger')
    
    return render_template('auth/register.html', title='注册', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    _, LoginForm, _, _, _ = get_forms()
    form = LoginForm()
    
    if form.validate_on_submit():
        User, _, _, _ = get_models()
        db = get_db()
        
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            
            # 更新最后登录时间
            from datetime import datetime
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            flash('登录成功！', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('登录失败，请检查邮箱和密码', 'danger')
    
    return render_template('auth/login.html', title='登录', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出登录', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """个人资料页面 - 包含修改密码、更换头像和修改用户名功能"""
    from app.forms import ChangePasswordForm, ChangeAvatarForm, ChangeUsernameForm
    
    # 创建表单
    change_password_form = ChangePasswordForm()
    change_avatar_form = ChangeAvatarForm()
    change_username_form = ChangeUsernameForm()
    
    # 处理修改密码
    if change_password_form.validate_on_submit():
        if check_password_hash(current_user.password_hash, change_password_form.current_password.data):
            # 验证新密码
            if change_password_form.new_password.data == change_password_form.confirm_password.data:
                # 更新密码
                current_user.password_hash = generate_password_hash(change_password_form.new_password.data)
                db = get_db()
                db.session.commit()
                flash('密码修改成功！', 'success')
                return redirect(url_for('auth.profile'))
            else:
                flash('两次输入的新密码不一致！', 'danger')
        else:
            flash('当前密码错误！', 'danger')
    
    # 处理更换头像
    if change_avatar_form.validate_on_submit():
        if change_avatar_form.avatar.data:
            try:
                # 保存新头像
                avatar_filename = save_avatar(change_avatar_form.avatar.data)
                
                # 如果用户有旧头像且不是默认头像，删除旧文件
                if current_user.avatar_path and current_user.avatar_path != 'default_avatar.png':
                    old_avatar_path = os.path.join(
                        current_app.config['AVATAR_UPLOAD_FOLDER'], 
                        current_user.avatar_path
                    )
                    if os.path.exists(old_avatar_path):
                        os.remove(old_avatar_path)
                
                # 更新用户头像路径
                current_user.avatar_path = avatar_filename
                db = get_db()
                db.session.commit()
                flash('头像更换成功！', 'success')
                return redirect(url_for('auth.profile'))
                
            except Exception as e:
                flash(f'头像上传失败：{str(e)}', 'danger')
        else:
            flash('请选择要上传的头像文件', 'warning')
    
    # 处理修改用户名
    if change_username_form.validate_on_submit():
        if check_password_hash(current_user.password_hash, change_username_form.password.data):
            # 检查新用户名是否可用
            db = get_db()
            User, _, _, _ = get_models()
            existing_user = User.query.filter_by(username=change_username_form.new_username.data).first()
            
            if existing_user and existing_user.id != current_user.id:
                flash('该用户名已被使用，请选择其他用户名', 'danger')
            else:
                # 更新用户名
                old_username = current_user.username
                current_user.username = change_username_form.new_username.data
                db.session.commit()
                flash(f'用户名已从 "{old_username}" 修改为 "{current_user.username}"！', 'success')
                return redirect(url_for('auth.profile'))
        else:
            flash('密码错误，无法修改用户名', 'danger')
    
    # 计算统计信息（如果用户有餐厅）
    stats = {}
    if current_user.restaurant:
        User, Dish, Order, Restaurant = get_models()
        db = get_db()
        
        # 在售菜品数量
        active_dishes_count = db.session.query(Dish).filter_by(
            restaurant_id=current_user.restaurant.id, 
            is_active=True
        ).count()
        
        # 已处理订单数量
        paid_orders_count = db.session.query(Order).filter_by(
            restaurant_id=current_user.restaurant.id, 
            status='paid'
        ).count()
        
        stats = {
            'active_dishes_count': active_dishes_count,
            'paid_orders_count': paid_orders_count,
            'total_sales': current_user.restaurant.total_sales or 0
        }
    
    return render_template('auth/profile.html', 
                         title='个人资料',
                         change_password_form=change_password_form,
                         change_avatar_form=change_avatar_form,
                         change_username_form=change_username_form,
                         stats=stats)