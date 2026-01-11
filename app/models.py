from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from sqlalchemy.orm import validates
from sqlalchemy import func, distinct, Date, cast

# 用户加载器
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_path = db.Column(db.String(200), default='default_avatar.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='customer')  # 'customer' 或 'owner'
    
    # 关系定义
    restaurant = db.relationship('Restaurant', backref='owner', uselist=False, lazy=True)
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    blacklisted_by = db.relationship('Blacklist', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    # 实例方法
    def get_total_spent(self):
        """获取用户总消费金额"""
        total = db.session.query(func.sum(Order.total_amount)) \
            .filter(Order.user_id == self.id, Order.status == 'paid') \
            .scalar()
        return total or 0.0
    
    def get_order_count(self):
        """获取用户订单数"""
        return Order.query.filter_by(user_id=self.id, status='paid').count()
    
    def get_favorite_dishes(self, limit=3):
        """获取用户最爱点的菜品（前3）"""
        result = db.session.query(
            Dish.name,
            func.sum(OrderItem.quantity).label('total_quantity')
        ).join(OrderItem, OrderItem.dish_id == Dish.id) \
         .join(Order, Order.id == OrderItem.order_id) \
         .filter(Order.user_id == self.id, Order.status == 'paid') \
         .group_by(Dish.id) \
         .order_by(func.sum(OrderItem.quantity).desc()) \
         .limit(limit).all()
        return result

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    logo_path = db.Column(db.String(200), default='default_logo.png')
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_sales = db.Column(db.Float, default=0.0)  # 餐厅总销售额，用于排序
    
    # 关系定义
    categories = db.relationship('Category', backref='restaurant', lazy='dynamic', cascade='all, delete-orphan')
    dishes = db.relationship('Dish', backref='restaurant', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='restaurant', lazy='dynamic')
    blacklist = db.relationship('Blacklist', backref='restaurant', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Restaurant {self.name}>'
    
    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) == 0:
            raise ValueError('餐厅名称不能为空')
        if len(name) > 100:
            raise ValueError('餐厅名称过长')
        return name.strip()
    
    # 实例方法
    def get_top_dishes(self, limit=5):
        """获取餐厅销量前5的菜品"""
        result = db.session.query(
            Dish,
            func.sum(OrderItem.quantity).label('total_quantity')
        ).join(OrderItem, OrderItem.dish_id == Dish.id) \
         .join(Order, Order.id == OrderItem.order_id) \
         .filter(Dish.restaurant_id == self.id, Order.status == 'paid') \
         .group_by(Dish.id) \
         .order_by(func.sum(OrderItem.quantity).desc()) \
         .limit(limit).all()
        return result
    
    def get_top_customers(self, limit=5):
        """获取消费额前5的顾客"""
        result = db.session.query(
            User,
            func.sum(Order.total_amount).label('total_spent')
        ).join(Order, Order.user_id == User.id) \
         .filter(Order.restaurant_id == self.id, Order.status == 'paid') \
         .group_by(User.id) \
         .order_by(func.sum(Order.total_amount).desc()) \
         .limit(limit).all()
        return result
    
    def get_daily_sales(self, days=7):
        """获取最近7天的销售额"""
        from datetime import datetime, timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days-1)
        
        result = db.session.query(
            cast(Order.created_at, Date).label('date'),
            func.sum(Order.total_amount).label('total_sales')
        ).filter(
            Order.restaurant_id == self.id,
            Order.status == 'paid',
            Order.created_at >= start_date
        ).group_by(cast(Order.created_at, Date)) \
         .order_by(cast(Order.created_at, Date)).all()
        
        # 返回结果，确保日期是字符串格式
        formatted_result = []
        for date_obj, total_sales in result:
            if date_obj:
                # 将日期对象转换为字符串
                if hasattr(date_obj, 'strftime'):
                    date_str = date_obj.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_obj)
            else:
                date_str = ''
            formatted_result.append((date_str, float(total_sales or 0)))
        
        return formatted_result

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系定义
    dishes = db.relationship('Dish', backref='category', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    @staticmethod
    def create_default_categories(restaurant_id):
        """为餐厅创建默认分类"""
        default_categories = ['饮品', '菜品', '主食', '其他']
        categories = []
        for name in default_categories:
            category = Category(name=name, restaurant_id=restaurant_id)
            db.session.add(category)
            categories.append(category)
        return categories

class Dish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(200), default='default_dish.png')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order_count = db.Column(db.Integer, default=0)  # 被点次数
    is_active = db.Column(db.Boolean, default=True)  # 是否上架
    
    # 关系定义
    order_items = db.relationship('OrderItem', backref='dish', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Dish {self.name}>'
    
    @validates('description')
    def validate_description(self, key, description):
        if len(description) > 500:
            raise ValueError('菜品介绍不能超过500字')
        return description
    
    @validates('price')
    def validate_price(self, key, price):
        if price <= 0:
            raise ValueError('价格必须大于0')
        return price
    
    # 实例方法
    def get_total_sales(self):
        """获取菜品总销售额"""
        total = db.session.query(func.sum(OrderItem.quantity * OrderItem.price_at_time)) \
            .join(Order, Order.id == OrderItem.order_id) \
            .filter(OrderItem.dish_id == self.id, Order.status == 'paid') \
            .scalar()
        return total or 0.0
    
    def get_total_quantity_sold(self):
        """获取菜品总销量"""
        total = db.session.query(func.sum(OrderItem.quantity)) \
            .join(Order, Order.id == OrderItem.order_id) \
            .filter(OrderItem.dish_id == self.id, Order.status == 'paid') \
            .scalar()
        return total or 0
    
    def get_customers(self):
        """获取点过该菜品的顾客"""
        customer_ids = db.session.query(distinct(Order.user_id)) \
            .join(OrderItem, OrderItem.order_id == Order.id) \
            .filter(OrderItem.dish_id == self.id, Order.status == 'paid') \
            .all()
        customer_ids = [cid[0] for cid in customer_ids]
        return User.query.filter(User.id.in_(customer_ids)).all()

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, paid, cancelled, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    remarks = db.Column(db.Text)  # 订单备注
    
    # 关系定义
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.id}>'
    
    # 添加本地时间属性（北京时间 UTC+8）
    @property
    def local_created_at(self):
        """返回本地时间（北京时间，UTC+8）"""
        if self.created_at:
            return self.created_at + timedelta(hours=8)
        return None
    
    @property
    def local_paid_at(self):
        """返回本地支付时间（北京时间，UTC+8）"""
        if self.paid_at:
            return self.paid_at + timedelta(hours=8)
        return None

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_time = db.Column(db.Float, nullable=False)  # 下单时的价格
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('restaurant_id', 'user_id', name='_restaurant_user_uc'),)
    
    def __repr__(self):
        return f'<Blacklist restaurant:{self.restaurant_id} user:{self.user_id}>'