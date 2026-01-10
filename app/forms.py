from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, FloatField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional
from app.models import Restaurant, Category, User

class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[
        DataRequired(message='用户名不能为空'),
        Length(min=3, max=20, message='用户名长度应为3-20个字符')
    ])
    
    email = StringField('邮箱', validators=[
        DataRequired(message='邮箱不能为空'),
        Email(message='请输入有效的邮箱地址'),
        Length(max=120, message='邮箱地址过长')
    ])
    
    password = PasswordField('密码', validators=[
        DataRequired(message='密码不能为空'),
        Length(min=6, max=60, message='密码长度应为6-60个字符')
    ])
    
    confirm_password = PasswordField('确认密码', validators=[
        DataRequired(message='请确认密码'),
        EqualTo('password', message='两次输入的密码不一致')
    ])
    
    avatar = FileField('上传头像', validators=[
        FileRequired(message='请上传头像'),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '只支持jpg, jpeg, png, gif格式')
    ])
    
    submit = SubmitField('注册')
    
    def validate_username(self, username):
        """验证用户名是否已存在"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('该用户名已被使用，请选择其他用户名')
    
    def validate_email(self, email):
        """验证邮箱是否已存在"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('该邮箱已被注册，请使用其他邮箱')

class LoginForm(FlaskForm):
    email = StringField('邮箱', validators=[
        DataRequired(message='邮箱不能为空'),
        Email(message='请输入有效的邮箱地址')
    ])
    
    password = PasswordField('密码', validators=[
        DataRequired(message='密码不能为空')
    ])
    
    remember = BooleanField('记住我')
    
    submit = SubmitField('登录')

class RestaurantForm(FlaskForm):
    name = StringField('餐厅名称', validators=[
        DataRequired(message='餐厅名称不能为空'),
        Length(min=2, max=100, message='餐厅名称长度应为2-100个字符')
    ])
    
    description = TextAreaField('餐厅描述', validators=[
        Length(max=500, message='餐厅描述不能超过500字')
    ])
    
    logo = FileField('餐厅Logo', validators=[
        FileRequired(message='请上传餐厅Logo'),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '只支持jpg, jpeg, png, gif格式')
    ])
    
    submit = SubmitField('创建餐厅')
    
    def validate_name(self, name):
        restaurant = Restaurant.query.filter_by(name=name.data).first()
        if restaurant:
            raise ValidationError('该餐厅名称已被使用，请选择其他名称')

class RestaurantEditForm(FlaskForm):
    """餐厅编辑表单"""
    name = StringField('餐厅名称', validators=[
        DataRequired(message='餐厅名称不能为空'),
        Length(min=2, max=100, message='餐厅名称长度应为2-100个字符')
    ])
    
    description = TextAreaField('餐厅描述', validators=[
        Length(max=500, message='餐厅描述不能超过500字')
    ])
    
    logo = FileField('餐厅Logo', validators=[
        Optional(),  # 编辑时Logo可选
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '只支持jpg, jpeg, png, gif格式')
    ])
    
    submit = SubmitField('更新餐厅信息')
    
    def __init__(self, original_name=None, *args, **kwargs):
        super(RestaurantEditForm, self).__init__(*args, **kwargs)
        self.original_name = original_name
    
    def validate_name(self, name):
        """验证餐厅名称是否与其他餐厅重复（排除当前餐厅）"""
        if self.original_name and name.data == self.original_name:
            return  # 如果名称没有改变，不需要验证
        
        restaurant = Restaurant.query.filter_by(name=name.data).first()
        if restaurant:
            raise ValidationError('该餐厅名称已被使用，请选择其他名称')

class DishForm(FlaskForm):
    name = StringField('菜品名称', validators=[
        DataRequired(message='菜品名称不能为空'),
        Length(min=2, max=100, message='菜品名称长度应为2-100个字符')
    ])
    
    description = TextAreaField('菜品介绍', validators=[
        DataRequired(message='菜品介绍不能为空'),
        Length(max=500, message='菜品介绍不能超过500字')
    ])
    
    price = FloatField('价格（元）', validators=[
        DataRequired(message='价格不能为空'),
        NumberRange(min=0.01, max=9999.99, message='价格必须在0.01-9999.99之间')
    ])
    
    category_id = SelectField('菜品分类', coerce=int, validators=[
        DataRequired(message='请选择菜品分类')
    ])
    
    image = FileField('菜品图片', validators=[
        FileRequired(message='请上传菜品图片'),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '只支持jpg, jpeg, png, gif格式')
    ])
    
    submit = SubmitField('添加菜品')
    
    def __init__(self, restaurant_id=None, *args, **kwargs):
        super(DishForm, self).__init__(*args, **kwargs)
        if restaurant_id:
            # 动态加载该餐厅的分类
            categories = Category.query.filter_by(restaurant_id=restaurant_id).all()
            self.category_id.choices = [(c.id, c.name) for c in categories]

class CategoryEditForm(FlaskForm):
    name = StringField('分类名称', validators=[
        DataRequired(message='分类名称不能为空'),
        Length(min=1, max=50, message='分类名称长度应为1-50个字符')
    ])
    
    submit = SubmitField('更新分类')

class DishEditForm(FlaskForm):
    name = StringField('菜品名称', validators=[
        DataRequired(message='菜品名称不能为空'),
        Length(min=2, max=100, message='菜品名称长度应为2-100个字符')
    ])
    
    description = TextAreaField('菜品介绍', validators=[
        DataRequired(message='菜品介绍不能为空'),
        Length(max=500, message='菜品介绍不能超过500字')
    ])
    
    price = FloatField('价格（元）', validators=[
        DataRequired(message='价格不能为空'),
        NumberRange(min=0.01, max=9999.99, message='价格必须在0.01-9999.99之间')
    ])
    
    category_id = SelectField('菜品分类', coerce=int, validators=[
        DataRequired(message='请选择菜品分类')
    ])
    
    image = FileField('菜品图片', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '只支持jpg, jpeg, png, gif格式'),
        Optional()  # 编辑时图片是可选的
    ])
    
    is_active = BooleanField('是否上架')
    
    submit = SubmitField('更新菜品')
    
    def __init__(self, restaurant_id=None, *args, **kwargs):
        super(DishEditForm, self).__init__(*args, **kwargs)
        if restaurant_id:
            # 动态加载该餐厅的分类
            categories = Category.query.filter_by(restaurant_id=restaurant_id).all()
            self.category_id.choices = [(c.id, c.name) for c in categories]

class ReportFilterForm(FlaskForm):
    """报表筛选表单"""
    period = SelectField('统计周期', choices=[
        ('day', '今日'),
        ('week', '本周'), 
        ('month', '本月'),
        ('year', '今年'),
        ('all', '全部')
    ], default='week')
    
    chart_type = SelectField('图表类型', choices=[
        ('sales', '销售额'),
        ('quantity', '销量')
    ], default='sales')
    
    top_n = IntegerField('显示前N名', validators=[
        NumberRange(min=1, max=20, message='范围1-20')
    ], default=5)
    
    submit = SubmitField('生成报表')

class AdvisorQuestionForm(FlaskForm):
    """顾问提问表单"""
    question = TextAreaField('您的问题', validators=[
        DataRequired(message='请输入问题'),
        Length(max=500, message='问题不能超过500字')
    ])
    
    submit = SubmitField('提问')

# ================== 个人资料相关表单 ==================

class ChangePasswordForm(FlaskForm):
    """修改密码表单"""
    current_password = PasswordField('当前密码', validators=[
        DataRequired(message='当前密码不能为空')
    ])
    
    new_password = PasswordField('新密码', validators=[
        DataRequired(message='新密码不能为空'),
        Length(min=6, max=60, message='密码长度应为6-60个字符')
    ])
    
    confirm_password = PasswordField('确认新密码', validators=[
        DataRequired(message='请确认新密码'),
        EqualTo('new_password', message='两次输入的新密码不一致')
    ])
    
    submit = SubmitField('修改密码')

class ChangeAvatarForm(FlaskForm):
    """更换头像表单"""
    avatar = FileField('选择新头像', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '只支持jpg, jpeg, png, gif格式'),
        Optional()  # 可选，因为用户可能不想更换头像
    ])
    
    submit = SubmitField('更换头像')

class ChangeUsernameForm(FlaskForm):
    """修改用户名表单"""
    new_username = StringField('新用户名', validators=[
        DataRequired(message='新用户名不能为空'),
        Length(min=3, max=20, message='用户名长度应为3-20个字符')
    ])
    
    password = PasswordField('当前密码', validators=[
        DataRequired(message='需要输入当前密码以验证身份')
    ])
    
    submit = SubmitField('修改用户名')
    
    def validate_new_username(self, new_username):
        """验证新用户名是否已存在"""
        from flask_login import current_user
        # 检查是否与其他用户的用户名冲突（除了当前用户自己）
        user = User.query.filter_by(username=new_username.data).first()
        if user and user.id != current_user.id:
            raise ValidationError('该用户名已被使用，请选择其他用户名')