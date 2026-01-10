from flask import render_template, redirect, url_for, flash, request, current_app, Blueprint, abort, jsonify, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import func, desc, text, and_, or_, case, distinct, cast, Date
from app import db
# 修改这里，添加 RestaurantEditForm
from app.forms import RestaurantForm, RestaurantEditForm, DishForm, CategoryEditForm, DishEditForm, ReportFilterForm, AdvisorQuestionForm
from app.models import User, Restaurant, Category, Dish, Order, OrderItem, Blacklist
from app.utils import save_image
import os
import json
from datetime import datetime, timedelta
import random

restaurant_bp = Blueprint('restaurant', __name__)

# 装饰器：检查用户是否有餐厅
def has_restaurant_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.restaurant:
            flash('请先创建餐厅', 'warning')
            return redirect(url_for('restaurant.create'))
        return f(*args, **kwargs)
    return decorated_function

# 装饰器：检查用户是否是餐厅所有者
def restaurant_owner_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(restaurant_id, *args, **kwargs):
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        if current_user.id != restaurant.owner_id:
            abort(403)  # 禁止访问
        return f(restaurant_id, *args, **kwargs)
    return decorated_function

@restaurant_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建餐厅"""
    # 检查是否已有餐厅
    if current_user.restaurant:
        flash('您已经拥有一个餐厅了', 'warning')
        return redirect(url_for('restaurant.dashboard', restaurant_id=current_user.restaurant.id))
    
    form = RestaurantForm()
    if form.validate_on_submit():
        try:
            # 保存Logo
            logo_filename = save_image(form.logo.data, 'logos')
            
            # 创建餐厅
            restaurant = Restaurant(
                name=form.name.data,
                description=form.description.data,
                logo_path=logo_filename,
                owner_id=current_user.id
            )
            db.session.add(restaurant)
            db.session.flush()  # 获取ID但不提交
            
            # 创建默认分类
            Category.create_default_categories(restaurant.id)
            
            db.session.commit()
            flash('餐厅创建成功！', 'success')
            return redirect(url_for('restaurant.dashboard', restaurant_id=restaurant.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')
    
    return render_template('restaurant/create.html', title='创建餐厅', form=form)

@restaurant_bp.route('/<int:restaurant_id>/dashboard')
@login_required
@restaurant_owner_required
def dashboard(restaurant_id):
    """餐厅管理仪表板"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 获取今日、本周、本月销售额
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # 今日销售额
    today_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid',
        func.date(Order.created_at) == today
    ).scalar() or 0
    
    # 本周销售额
    week_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid',
        func.date(Order.created_at) >= week_start
    ).scalar() or 0
    
    # 本月销售额
    month_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid',
        func.date(Order.created_at) >= month_start
    ).scalar() or 0
    
    # 获取统计信息
    stats = {
        'total_dishes': Dish.query.filter_by(restaurant_id=restaurant_id, is_active=True).count(),
        'total_orders': Order.query.filter_by(restaurant_id=restaurant_id, status='paid').count(),
        'total_sales': restaurant.total_sales or 0,
        'total_customers': db.session.query(Order.user_id)
            .filter_by(restaurant_id=restaurant_id, status='paid')
            .distinct().count(),
        'today_sales': today_sales,
        'week_sales': week_sales,
        'month_sales': month_sales,
    }
    
    # 获取最近订单
    recent_orders = Order.query.filter_by(
        restaurant_id=restaurant_id
    ).order_by(Order.created_at.desc()).limit(5).all()
    
    # 获取销量前5的菜品
    top_dishes = restaurant.get_top_dishes(limit=5)
    
    # 获取消费前5的顾客
    top_customers = restaurant.get_top_customers(limit=5)
    
    return render_template('restaurant/dashboard.html', 
                         title='餐厅管理',
                         restaurant=restaurant,
                         stats=stats,
                         recent_orders=recent_orders,
                         top_dishes=top_dishes,
                         top_customers=top_customers)
# 在dashboard函数后添加编辑餐厅信息的路由
@restaurant_bp.route('/<int:restaurant_id>/edit', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def edit_restaurant(restaurant_id):
    """编辑餐厅信息"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 使用顶部导入的 RestaurantEditForm
    form = RestaurantEditForm(original_name=restaurant.name, obj=restaurant)
    
    if form.validate_on_submit():
        try:
            # 检查餐厅名称是否与其他餐厅重复（排除当前餐厅）
            if form.name.data != restaurant.name:
                existing_restaurant = Restaurant.query.filter_by(name=form.name.data).first()
                if existing_restaurant and existing_restaurant.id != restaurant.id:
                    flash('该餐厅名称已被使用，请选择其他名称', 'danger')
                    return render_template('restaurant/edit_restaurant.html',
                                         title='编辑餐厅信息',
                                         restaurant=restaurant,
                                         form=form)
            
            # 更新餐厅基本信息
            restaurant.name = form.name.data
            restaurant.description = form.description.data or ""  # 确保不为None
            
            # 处理Logo上传
            if form.logo.data:
                # 保存新Logo
                logo_filename = save_image(form.logo.data, 'logos')
                
                # 如果有旧Logo且不是默认Logo，删除旧文件
                if restaurant.logo_path and restaurant.logo_path != 'default_logo.png':
                    old_logo_path = os.path.join(
                        current_app.config['LOGO_UPLOAD_FOLDER'], 
                        restaurant.logo_path
                    )
                    if os.path.exists(old_logo_path):
                        os.remove(old_logo_path)
                
                # 更新Logo路径
                restaurant.logo_path = logo_filename
            
            # 保存更改
            db.session.commit()
            
            flash('餐厅信息更新成功！', 'success')
            return redirect(url_for('restaurant.dashboard', restaurant_id=restaurant_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')
    
    return render_template('restaurant/edit_restaurant.html',
                         title='编辑餐厅信息',
                         restaurant=restaurant,
                         form=form)

# ================= 菜品分类管理功能 =================

@restaurant_bp.route('/<int:restaurant_id>/categories')
@login_required
@restaurant_owner_required
def categories(restaurant_id):
    """菜品分类管理"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    categories = Category.query.filter_by(restaurant_id=restaurant_id).order_by(Category.id).all()
    
    return render_template('restaurant/categories.html',
                         title='菜品分类管理',
                         restaurant=restaurant,
                         categories=categories)

@restaurant_bp.route('/<int:restaurant_id>/categories/add', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def add_category(restaurant_id):
    """添加菜品分类"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 使用 CategoryEditForm
    from app.forms import CategoryEditForm
    form = CategoryEditForm()
    
    if form.validate_on_submit():
        # 检查分类名是否重复
        existing_category = Category.query.filter_by(
            restaurant_id=restaurant_id,
            name=form.name.data
        ).first()
        
        if existing_category:
            flash('分类名称已存在', 'danger')
        else:
            category = Category(
                name=form.name.data,
                restaurant_id=restaurant_id
            )
            db.session.add(category)
            db.session.commit()
            flash('分类创建成功！', 'success')
            return redirect(url_for('restaurant.categories', restaurant_id=restaurant_id))
    
    return render_template('restaurant/add_category.html',
                         title='创建分类',
                         restaurant=restaurant,
                         form=form)

@restaurant_bp.route('/<int:restaurant_id>/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def edit_category(restaurant_id, category_id):
    """编辑菜品分类"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    category = Category.query.get_or_404(category_id)
    
    # 验证分类属于该餐厅
    if category.restaurant_id != restaurant_id:
        abort(404)
    
    form = CategoryEditForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        db.session.commit()
        flash('分类更新成功！', 'success')
        return redirect(url_for('restaurant.categories', restaurant_id=restaurant_id))
    
    return render_template('restaurant/edit_category.html',
                         title='编辑分类',
                         restaurant=restaurant,
                         category=category,
                         form=form)

@restaurant_bp.route('/<int:restaurant_id>/categories/<int:category_id>/delete', methods=['POST'])
@login_required
@restaurant_owner_required
def delete_category(restaurant_id, category_id):
    """删除菜品分类"""
    category = Category.query.get_or_404(category_id)
    
    # 验证分类属于该餐厅
    if category.restaurant_id != restaurant_id:
        abort(404)
    
    # 检查分类下是否有菜品
    dish_count = Dish.query.filter_by(category_id=category_id).count()
    
    if dish_count > 0:
        flash(f'该分类下有 {dish_count} 个菜品，无法删除。请先移动或删除这些菜品。', 'danger')
    else:
        try:
            db.session.delete(category)
            db.session.commit()
            flash('分类删除成功！', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'删除失败：{str(e)}', 'danger')
    
    return redirect(url_for('restaurant.categories', restaurant_id=restaurant_id))

# ================= 菜品管理功能 =================

@restaurant_bp.route('/<int:restaurant_id>/dishes')
@login_required
@restaurant_owner_required
def dishes(restaurant_id):
    """菜品列表"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    category_id = request.args.get('category_id', type=int)
    page = request.args.get('page', 1, type=int)
    
    # 构建查询
    query = Dish.query.filter_by(restaurant_id=restaurant_id)
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # 分页
    per_page = 12
    dishes = query.order_by(Dish.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    categories = Category.query.filter_by(restaurant_id=restaurant_id).all()
    
    return render_template('restaurant/dishes.html',
                         title='菜品管理',
                         restaurant=restaurant,
                         dishes=dishes,
                         categories=categories,
                         current_category=category_id)

@restaurant_bp.route('/<int:restaurant_id>/dishes/add', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def add_dish(restaurant_id):
    """添加菜品"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    form = DishForm(restaurant_id=restaurant_id)
    
    if form.validate_on_submit():
        try:
            # 保存菜品图片
            image_filename = save_image(form.image.data, 'dishes')
            
            # 创建菜品
            dish = Dish(
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
                image_path=image_filename,
                category_id=form.category_id.data,
                restaurant_id=restaurant_id
            )
            
            db.session.add(dish)
            db.session.commit()
            
            flash('菜品添加成功！', 'success')
            return redirect(url_for('restaurant.dishes', restaurant_id=restaurant_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'添加失败：{str(e)}', 'danger')
    
    return render_template('restaurant/add_dish.html',
                         title='添加菜品',
                         restaurant=restaurant,
                         form=form)

@restaurant_bp.route('/<int:restaurant_id>/dishes/<int:dish_id>')
@login_required
@restaurant_owner_required
def dish_detail(restaurant_id, dish_id):
    """菜品详情 - 增强版"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    dish = Dish.query.get_or_404(dish_id)
    
    # 验证菜品属于该餐厅
    if dish.restaurant_id != restaurant_id:
        abort(404)
    
    # 获取菜品统计信息
    total_sales = dish.get_total_sales()
    total_quantity = dish.get_total_quantity_sold()
    
    # 获取点过该菜品的顾客及其消费详情
    from sqlalchemy import func
    
    # 查询点过这道菜的顾客及其消费统计
    customer_details = db.session.query(
        User,
        func.sum(OrderItem.quantity).label('total_quantity'),
        func.sum(OrderItem.quantity * OrderItem.price_at_time).label('total_spent'),
        func.count(Order.id).label('order_count'),
        func.max(Order.created_at).label('last_order_time')
    ).join(Order, Order.user_id == User.id) \
     .join(OrderItem, OrderItem.order_id == Order.id) \
     .filter(
        Order.restaurant_id == restaurant_id,
        OrderItem.dish_id == dish_id,
        Order.status == 'paid'
     ).group_by(User.id) \
     .order_by(func.sum(OrderItem.quantity).desc()).all()
    
    # 获取点过该菜品的所有订单
    order_items = OrderItem.query.join(Order).filter(
        OrderItem.dish_id == dish_id,
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid'
    ).order_by(Order.created_at.desc()).limit(20).all()
    
    # 计算菜品销售趋势（最近30天）
    # 使用文件顶部导入的 datetime 模块
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    daily_sales = db.session.query(
        func.date(Order.created_at).label('order_date'),
        func.sum(OrderItem.quantity).label('daily_quantity'),
        func.sum(OrderItem.quantity * OrderItem.price_at_time).label('daily_sales')
    ).join(Order, Order.id == OrderItem.order_id) \
     .filter(
        OrderItem.dish_id == dish_id,
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid',
        Order.created_at >= thirty_days_ago
     ).group_by(func.date(Order.created_at)) \
     .order_by(func.date(Order.created_at)).all()
    
    # 修复：正确处理日期格式化
    trend_dates = []
    trend_quantities = []
    trend_sales = []
    
    for date_record, quantity, sales in daily_sales:
        # 修复：先检查 date_record 的类型
        if hasattr(date_record, 'strftime'):
            # 如果是日期对象
            trend_dates.append(date_record.strftime('%m-%d'))
        else:
            # 如果是字符串，直接使用
            if isinstance(date_record, str) and 'T' in date_record:
                # 如果包含时间，只取日期部分
                date_str = date_record.split('T')[0]
            else:
                date_str = str(date_record)
            
            # 提取月份和日期
            if '-' in date_str:
                # 格式如 "2023-12-01"，提取最后5个字符 "12-01"
                trend_dates.append(date_str[-5:])
            else:
                # 其他格式，直接使用
                trend_dates.append(date_str)
        
        trend_quantities.append(float(quantity or 0))
        trend_sales.append(float(sales or 0))
    
    return render_template('restaurant/dish_detail.html',
                         title=dish.name,
                         restaurant=restaurant,
                         dish=dish,
                         total_sales=total_sales,
                         total_quantity=total_quantity,
                         customer_details=customer_details,
                         order_items=order_items,
                         trend_dates=json.dumps(trend_dates, ensure_ascii=False),
                         trend_quantities=json.dumps(trend_quantities, ensure_ascii=False),
                         trend_sales=json.dumps(trend_sales, ensure_ascii=False),
                         Customer=User)  # 传入User模型以便模板中使用

@restaurant_bp.route('/<int:restaurant_id>/dishes/<int:dish_id>/edit', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def edit_dish(restaurant_id, dish_id):
    """编辑菜品"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    dish = Dish.query.get_or_404(dish_id)
    
    # 验证菜品属于该餐厅
    if dish.restaurant_id != restaurant_id:
        abort(404)
    
    form = DishEditForm(restaurant_id=restaurant_id, obj=dish)
    
    if form.validate_on_submit():
        try:
            dish.name = form.name.data
            dish.description = form.description.data
            dish.price = form.price.data
            dish.category_id = form.category_id.data
            dish.is_active = form.is_active.data
            
            # 如果有上传新图片
            if form.image.data:
                # 删除旧图片（如果不是默认图片）
                if dish.image_path != 'default_dish.png':
                    old_image_path = os.path.join(current_app.config['DISH_UPLOAD_FOLDER'], dish.image_path)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # 保存新图片
                image_filename = save_image(form.image.data, 'dishes')
                dish.image_path = image_filename
            
            db.session.commit()
            flash('菜品更新成功！', 'success')
            return redirect(url_for('restaurant.dishes', restaurant_id=restaurant_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')
    
    return render_template('restaurant/edit_dish.html',
                         title='编辑菜品',
                         restaurant=restaurant,
                         dish=dish,
                         form=form)

@restaurant_bp.route('/<int:restaurant_id>/dishes/<int:dish_id>/delete', methods=['POST'])
@login_required
@restaurant_owner_required
def delete_dish(restaurant_id, dish_id):
    """删除菜品"""
    dish = Dish.query.get_or_404(dish_id)
    
    # 验证菜品属于该餐厅
    if dish.restaurant_id != restaurant_id:
        abort(404)
    
    try:
        # 删除菜品图片（如果不是默认图片）
        if dish.image_path and dish.image_path != 'default_dish.png':
            image_path = os.path.join(current_app.config['DISH_UPLOAD_FOLDER'], dish.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(dish)
        db.session.commit()
        flash('菜品删除成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败：{str(e)}', 'danger')
    
    return redirect(url_for('restaurant.dishes', restaurant_id=restaurant_id))

@restaurant_bp.route('/<int:restaurant_id>/dishes/<int:dish_id>/toggle', methods=['POST'])
@login_required
@restaurant_owner_required
def toggle_dish_status(restaurant_id, dish_id):
    """切换菜品上架状态"""
    dish = Dish.query.get_or_404(dish_id)
    
    # 验证菜品属于该餐厅
    if dish.restaurant_id != restaurant_id:
        abort(404)
    
    dish.is_active = not dish.is_active
    status = "上架" if dish.is_active else "下架"
    
    try:
        db.session.commit()
        flash(f'菜品已{status}！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'操作失败：{str(e)}', 'danger')
    
    return redirect(url_for('restaurant.dishes', restaurant_id=restaurant_id))

# ================= 订单管理功能 =================

@restaurant_bp.route('/<int:restaurant_id>/orders')
@login_required
@restaurant_owner_required
def orders(restaurant_id):
    """订单列表"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 获取筛选参数
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    # 构建查询
    query = Order.query.filter_by(restaurant_id=restaurant_id)
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    # 分页
    orders = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    # 统计各状态订单数量
    status_counts = {
        'all': Order.query.filter_by(restaurant_id=restaurant_id).count(),
        'pending': Order.query.filter_by(restaurant_id=restaurant_id, status='pending').count(),
        'paid': Order.query.filter_by(restaurant_id=restaurant_id, status='paid').count(),
        'completed': Order.query.filter_by(restaurant_id=restaurant_id, status='completed').count(),
        'cancelled': Order.query.filter_by(restaurant_id=restaurant_id, status='cancelled').count()
    }
    
    return render_template('restaurant/orders.html',
                         title='订单管理',
                         restaurant=restaurant,
                         orders=orders,
                         status=status,
                         status_counts=status_counts)

@restaurant_bp.route('/<int:restaurant_id>/orders/<int:order_id>')
@login_required
@restaurant_owner_required
def order_detail(restaurant_id, order_id):
    """订单详情"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    order = Order.query.get_or_404(order_id)
    
    # 验证订单属于该餐厅
    if order.restaurant_id != restaurant_id:
        abort(404)
    
    return render_template('restaurant/order_detail.html',
                         title=f'订单 #{order.id}',
                         restaurant=restaurant,
                         order=order)

@restaurant_bp.route('/<int:restaurant_id>/orders/<int:order_id>/update_status', methods=['POST'])
@login_required
@restaurant_owner_required
def update_order_status(restaurant_id, order_id):
    """更新订单状态"""
    order = Order.query.get_or_404(order_id)
    
    # 验证订单属于该餐厅
    if order.restaurant_id != restaurant_id:
        abort(404)
    
    new_status = request.form.get('status')
    valid_statuses = ['pending', 'paid', 'completed', 'cancelled']
    
    if new_status not in valid_statuses:
        flash('无效的订单状态', 'danger')
        return redirect(url_for('restaurant.order_detail', restaurant_id=restaurant_id, order_id=order_id))
    
    # 更新状态
    order.status = new_status
    
    # 如果是完成订单，更新菜品被点次数
    if new_status == 'completed':
        for item in order.items:
            dish = Dish.query.get(item.dish_id)
            if dish:
                dish.order_count += item.quantity
    
    try:
        db.session.commit()
        flash('订单状态更新成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}', 'danger')
    
    return redirect(url_for('restaurant.order_detail', restaurant_id=restaurant_id, order_id=order_id))

# ================= 顾客管理功能 =================

@restaurant_bp.route('/<int:restaurant_id>/customers')
@login_required
@restaurant_owner_required
def customers(restaurant_id):
    """顾客管理"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 获取排序参数
    sort_by = request.args.get('sort_by', 'total_spent')
    page = request.args.get('page', 1, type=int)
    
    try:
        # 查询在该餐厅有过订单的所有顾客
        from sqlalchemy import func
        
        # 构建基础查询
        customers_query = db.session.query(
            User,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_spent')
        ).join(
            Order, User.id == Order.user_id
        ).filter(
            Order.restaurant_id == restaurant_id
        ).group_by(
            User.id
        )
        
        # 排序
        if sort_by == 'total_spent':
            customers_query = customers_query.order_by(func.sum(Order.total_amount).desc())
        else:  # order_count
            customers_query = customers_query.order_by(func.count(Order.id).desc())
        
        # 分页
        customers = customers_query.paginate(page=page, per_page=20, error_out=False)
        
        # 获取每个顾客的最后订单时间
        customer_last_orders = {}
        for customer_data in customers.items:
            if customer_data and customer_data[0]:
                customer = customer_data[0]
                last_order = Order.query.filter_by(
                    restaurant_id=restaurant_id,
                    user_id=customer.id
                ).order_by(Order.created_at.desc()).first()
                if last_order:
                    customer_last_orders[customer.id] = last_order.created_at
        
        # 获取每个顾客的订单状态统计
        customer_order_stats = {}
        for customer_data in customers.items:
            if customer_data and customer_data[0]:
                customer = customer_data[0]
                # 查询该顾客在该餐厅的订单状态统计
                status_counts = db.session.query(
                    Order.status,
                    func.count(Order.id).label('count')
                ).filter(
                    Order.restaurant_id == restaurant_id,
                    Order.user_id == customer.id
                ).group_by(Order.status).all()
                
                # 转换为字典
                stats_dict = {}
                for status, count in status_counts:
                    stats_dict[status] = count
                
                customer_order_stats[customer.id] = stats_dict
        
        # 查询黑名单
        blacklist = Blacklist.query.filter_by(restaurant_id=restaurant_id).all()
        blacklist_user_ids = [entry.user_id for entry in blacklist]
        
        return render_template('restaurant/customers.html',
                             title='顾客管理',
                             restaurant=restaurant,
                             customers=customers,
                             sort_by=sort_by,
                             customer_last_orders=customer_last_orders,
                             customer_order_stats=customer_order_stats,
                             blacklist_user_ids=blacklist_user_ids)
                             
    except Exception as e:
        # 如果发生错误，返回一个简单的页面
        import traceback
        print(f"顾客管理页面错误: {e}")
        print(traceback.format_exc())
        
        return render_template('restaurant/customers.html',
                             title='顾客管理',
                             restaurant=restaurant,
                             customers=None,
                             sort_by=sort_by,
                             customer_last_orders={},
                             customer_order_stats={},
                             blacklist_user_ids=[])

@restaurant_bp.route('/<int:restaurant_id>/customers/<int:customer_id>')
@login_required
@restaurant_owner_required
def customer_detail(restaurant_id, customer_id):
    """顾客详情"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    customer = User.query.get_or_404(customer_id)
    
    # 获取该顾客在该餐厅的消费记录
    from sqlalchemy import func
    
    # 消费总额
    total_spent = db.session.query(func.sum(Order.total_amount)).filter(
        Order.restaurant_id == restaurant_id,
        Order.user_id == customer_id,
        Order.status == 'paid'
    ).scalar() or 0
    
    # 订单总数
    order_count = Order.query.filter_by(
        restaurant_id=restaurant_id,
        user_id=customer_id,
        status='paid'
    ).count()
    
    # 订单列表
    orders = Order.query.filter_by(
        restaurant_id=restaurant_id,
        user_id=customer_id
    ).order_by(Order.created_at.desc()).all()
    
    # 最爱点的菜品
    favorite_dishes = customer.get_favorite_dishes(limit=5)
    
    # 检查是否在黑名单中
    blacklist_record = Blacklist.query.filter_by(
        restaurant_id=restaurant_id,
        user_id=customer_id
    ).first()
    is_blacklisted = blacklist_record is not None
    
    # 获取该顾客在该餐厅的菜品消费统计
    dish_stats = db.session.query(
        Dish.name,
        Category.name,
        func.sum(OrderItem.quantity).label('total_quantity'),
        func.sum(OrderItem.quantity * OrderItem.price_at_time).label('total_spent'),
        Dish.id
    ).join(Category, Category.id == Dish.category_id) \
     .join(OrderItem, OrderItem.dish_id == Dish.id) \
     .join(Order, Order.id == OrderItem.order_id) \
     .filter(
        Order.restaurant_id == restaurant_id,
        Order.user_id == customer_id,
        Order.status == 'paid'
     ).group_by(Dish.id) \
     .order_by(func.sum(OrderItem.quantity).desc()).all()
    
    return render_template('restaurant/customer_detail.html',
                         title=f'顾客: {customer.username}',
                         restaurant=restaurant,
                         customer=customer,
                         total_spent=total_spent,
                         order_count=order_count,
                         orders=orders,
                         favorite_dishes=favorite_dishes,
                         dish_stats=dish_stats,
                         is_blacklisted=is_blacklisted,
                         blacklist_record=blacklist_record)

# ================= 数据报表功能 =================

@restaurant_bp.route('/<int:restaurant_id>/reports', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def reports(restaurant_id):
    """数据报表"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    form = ReportFilterForm()
    
    # 默认值
    period = 'week'
    chart_type = 'sales'
    top_n = 5
    
    if form.validate_on_submit():
        period = form.period.data
        chart_type = form.chart_type.data
        top_n = form.top_n.data
    
    # 根据周期获取时间范围
    today = datetime.utcnow().date()
    if period == 'day':
        start_date = today
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif period == 'month':
        start_date = today.replace(day=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
    else:  # all
        start_date = None
    
    # 获取菜品数据
    query = db.session.query(
        Dish.name,
        Dish.category_id,
        func.sum(OrderItem.quantity).label('total_quantity'),
        func.sum(OrderItem.quantity * OrderItem.price_at_time).label('total_sales')
    ).join(OrderItem, OrderItem.dish_id == Dish.id) \
     .join(Order, Order.id == OrderItem.order_id) \
     .filter(
        Dish.restaurant_id == restaurant_id,
        Order.status == 'paid'
     )
    
    if start_date:
        query = query.filter(func.date(Order.created_at) >= start_date)
    
    dish_stats = query.group_by(Dish.id) \
                     .order_by(func.sum(OrderItem.quantity * OrderItem.price_at_time).desc()) \
                     .limit(top_n).all()
    
    # 将 dish_stats 转换为可序列化的格式
    serializable_dish_stats = []
    for dish in dish_stats:
        # 将每个 Row 对象转换为元组
        serializable_dish_stats.append([
            dish[0],  # 菜品名称
            int(dish[1]) if dish[1] is not None else 0,  # 分类ID
            int(dish[2]) if dish[2] is not None else 0,  # 总销量
            float(dish[3]) if dish[3] is not None else 0.0  # 总销售额
        ])
    
    # 准备图表数据
    labels = [dish[0] for dish in serializable_dish_stats]
    if chart_type == 'sales':
        data = [float(dish[3] or 0) for dish in serializable_dish_stats]
        chart_label = '销售额 (元)'
    else:
        data = [int(dish[2] or 0) for dish in serializable_dish_stats]
        chart_label = '销量 (份)'
    
    # 获取销售趋势数据（最近7天）- 修复：使用更可靠的查询方法
    daily_sales = []
    try:
        # 获取最近7天的日期
        date_list = []
        for i in range(6, -1, -1):  # 最近7天，从6天前到今天
            date = today - timedelta(days=i)
            date_list.append(date.strftime('%Y-%m-%d'))
        
        # 查询每天的销售额
        for date_str in date_list:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            sales = db.session.query(func.sum(Order.total_amount)).filter(
                Order.restaurant_id == restaurant_id,
                Order.status == 'paid',
                func.date(Order.created_at) == date_obj
            ).scalar() or 0
            daily_sales.append((date_str, float(sales)))
            
    except Exception as e:
        print(f"获取销售趋势数据时出错: {e}")
        # 返回空数据
        daily_sales = []
    
    # 确保日期是字符串格式
    trend_labels = []
    trend_data = []
    for date_str, sales in daily_sales:
        trend_labels.append(date_str)
        trend_data.append(float(sales or 0))
    
    # 计算分类销售数据
    category_sales = db.session.query(
        Category.name,
        func.sum(OrderItem.quantity * OrderItem.price_at_time).label('total_sales')
    ).join(Dish, Dish.category_id == Category.id) \
     .join(OrderItem, OrderItem.dish_id == Dish.id) \
     .join(Order, Order.id == OrderItem.order_id) \
     .filter(
        Category.restaurant_id == restaurant.id,
        Order.status == 'paid'
     ).group_by(Category.id) \
     .order_by(func.sum(OrderItem.quantity * OrderItem.price_at_time).desc()).all()
    
    # 将分类信息转换为字典，方便模板使用
    category_dict = {cat.id: cat.name for cat in Category.query.filter_by(restaurant_id=restaurant.id).all()}
    
    # 计算其他统计信息
    total_orders = Order.query.filter_by(restaurant_id=restaurant.id, status='paid').count()
    active_dishes = Dish.query.filter_by(restaurant_id=restaurant.id, is_active=True).count()
    total_customers = db.session.query(Order.user_id).filter_by(
        restaurant_id=restaurant.id, 
        status='paid'
    ).distinct().count()
    
    return render_template('restaurant/reports.html',
                         title='数据报表',
                         restaurant=restaurant,
                         form=form,
                         period=period,
                         chart_type=chart_type,
                         top_n=top_n,
                         labels=json.dumps(labels, ensure_ascii=False),
                         data=json.dumps(data, ensure_ascii=False),
                         chart_label=chart_label,
                         trend_labels=json.dumps(trend_labels, ensure_ascii=False),
                         trend_data=json.dumps(trend_data, ensure_ascii=False),
                         category_sales=category_sales,
                         dish_stats=serializable_dish_stats,  # 使用可序列化的数据
                         category_dict=category_dict,
                         total_orders=total_orders,
                         active_dishes=active_dishes,
                         total_customers=total_customers)

# ================= 黑名单管理功能 =================

@restaurant_bp.route('/<int:restaurant_id>/blacklist')
@login_required
@restaurant_owner_required
def blacklist(restaurant_id):
    """黑名单管理"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 获取黑名单列表
    blacklist_records = Blacklist.query.filter_by(
        restaurant_id=restaurant_id
    ).order_by(Blacklist.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('restaurant/blacklist.html',
                         title='黑名单管理',
                         restaurant=restaurant,
                         blacklist=blacklist_records)

@restaurant_bp.route('/<int:restaurant_id>/blacklist/add', methods=['POST'])
@login_required
@restaurant_owner_required
def add_to_blacklist(restaurant_id):
    """添加用户到黑名单"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    user_id = request.form.get('user_id', type=int)
    reason = request.form.get('reason', '').strip()
    
    if not user_id:
        flash('请选择用户', 'danger')
        return redirect(url_for('restaurant.customers', restaurant_id=restaurant_id))
    
    # 检查是否已在黑名单
    existing = Blacklist.query.filter_by(
        restaurant_id=restaurant_id,
        user_id=user_id
    ).first()
    
    if existing:
        flash('该用户已在黑名单中', 'warning')
        return redirect(url_for('restaurant.blacklist', restaurant_id=restaurant_id))
    
    # 创建黑名单记录
    blacklist_record = Blacklist(
        restaurant_id=restaurant_id,
        user_id=user_id,
        reason=reason
    )
    
    try:
        db.session.add(blacklist_record)
        db.session.commit()
        flash('用户已加入黑名单', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'操作失败：{str(e)}', 'danger')
    
    return redirect(url_for('restaurant.blacklist', restaurant_id=restaurant_id))

@restaurant_bp.route('/<int:restaurant_id>/blacklist/<int:record_id>/remove', methods=['POST'])
@login_required
@restaurant_owner_required
def remove_from_blacklist(restaurant_id, record_id):
    """从黑名单移除用户"""
    blacklist_record = Blacklist.query.get_or_404(record_id)
    
    # 验证记录属于该餐厅
    if blacklist_record.restaurant_id != restaurant_id:
        abort(404)
    
    try:
        db.session.delete(blacklist_record)
        db.session.commit()
        flash('用户已从黑名单移除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'操作失败：{str(e)}', 'danger')
    
    return redirect(url_for('restaurant.blacklist', restaurant_id=restaurant_id))

# ================= 经营顾问功能 =================

@restaurant_bp.route('/<int:restaurant_id>/advisor', methods=['GET', 'POST'])
@login_required
@restaurant_owner_required
def advisor(restaurant_id):
    """智能经营顾问 - 集成完整上下文的AI版本"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    form = AdvisorQuestionForm()
    answer = None
    used_ai = False
    
    if form.validate_on_submit():
        question = form.question.data.strip()
        
        if not question:
            flash('请输入问题', 'warning')
            return render_template('restaurant/advisor.html',
                                 title='智能经营顾问',
                                 restaurant=restaurant,
                                 form=form,
                                 answer=answer,
                                 used_ai=used_ai,
                                 active_dishes_count=0,
                                 total_orders_count=0,
                                 total_customers_count=0,
                                 now=datetime.utcnow())
        
        print(f"🎯 用户提问: {question}")
        
        try:
            from app.services.ai_service import ai_service
            from app.services.context_builder import ContextBuilder
            
            print("🤖 调用AI服务进行分析...")
            
            # 尝试完整分析模式
            ai_answer = ai_service.get_ai_analysis(question, restaurant_id, use_fast_mode=False)
            
            if ai_answer:
                print(f"✅ AI分析成功，回答长度: {len(ai_answer)}")
                answer = ai_answer
                used_ai = True
            else:
                print("⚠️ 完整分析失败，尝试快速模式...")
                # 尝试快速模式
                ai_answer = ai_service.get_ai_analysis(question, restaurant_id, use_fast_mode=True)
                
                if ai_answer:
                    print(f"✅ 快速分析成功，回答长度: {len(ai_answer)}")
                    answer = ai_answer
                    used_ai = True
                else:
                    print("❌ 所有AI调用失败，使用备选回答")
                    # 使用备选回答生成器
                    answer = generate_fallback_answer(question, restaurant_id)
                    
        except ImportError as e:
            print(f"❌ 导入AI服务失败: {e}")
            import traceback
            traceback.print_exc()
            answer = generate_fallback_answer(question, restaurant_id)
        except Exception as e:
            print(f"❌ AI调用异常: {e}")
            import traceback
            traceback.print_exc()
            answer = generate_fallback_answer(question, restaurant_id)
    
    # 计算统计数据
    active_dishes_count = Dish.query.filter_by(restaurant_id=restaurant_id, is_active=True).count()
    total_orders_count = Order.query.filter_by(restaurant_id=restaurant_id, status='paid').count()
    total_customers_count = db.session.query(Order.user_id).filter_by(
        restaurant_id=restaurant_id, 
        status='paid'
    ).distinct().count()
    
    return render_template('restaurant/advisor.html',
                         title='智能经营顾问',
                         restaurant=restaurant,
                         form=form,
                         answer=answer,
                         used_ai=used_ai,
                         active_dishes_count=active_dishes_count,
                         total_orders_count=total_orders_count,
                         total_customers_count=total_customers_count,
                         now=datetime.utcnow())

def generate_fallback_answer(question, restaurant_id):
    """备选回答生成器（当大模型不可用时使用）"""
    question_lower = question.lower()
    
    # 原有的关键词匹配逻辑
    if any(keyword in question_lower for keyword in ['销售额', '营业额', '收入', '销售趋势', '销售统计']):
        return analyze_sales_trends(restaurant_id)
    elif any(keyword in question_lower for keyword in ['热门', '畅销', '卖得好', '菜品销量', '最受欢迎', '什么菜好']):
        return analyze_popular_dishes(restaurant_id)
    elif any(keyword in question_lower for keyword in ['顾客', '客户', '消费', '客人', 'user', 'customer']):
        return analyze_customer_behavior(restaurant_id)
    elif any(keyword in question_lower for keyword in ['提高', '提升', '改进', '经营建议', '建议', '推荐']):
        return """🤔 这是一个关于经营改进的问题。由于AI服务暂时不可用，我无法提供详细的个性化建议。

基于常规餐厅经营经验，您可以考虑：

📈 提高销售额的策略：
1. 分析菜品销量，下架滞销菜品，增加热门菜品的推广
2. 推出优惠套餐或限时特价，吸引新顾客
3. 建立会员体系，鼓励老顾客重复消费
4. 优化菜单结构，设置主推菜品和利润菜品

👥 提升顾客体验：
1. 收集顾客反馈，了解菜品和服务问题
2. 优化用餐环境和服务流程
3. 推出个性化推荐，根据顾客喜好推荐菜品
4. 建立顾客回访机制

💰 成本控制建议：
1. 分析食材成本，优化采购渠道
2. 控制菜品浪费，合理安排备货
3. 优化人员排班，提高运营效率

🔧 运营改进：
1. 使用数据分析工具监控经营状况
2. 建立标准化的操作流程
3. 定期培训员工，提升服务质量

如需更具体的建议，请重新尝试连接AI服务，或提供更详细的问题描述。"""
    elif any(keyword in question_lower for keyword in ['什么好吃', '推荐什么', '点哪个']):
        return analyze_popular_dishes_with_recommendation(restaurant_id)
    elif any(keyword in question_lower for keyword in ['订单', 'order', '下单']):
        return """📊 订单相关信息：

由于AI服务暂时不可用，我无法查看具体的订单详情，但您可以：

1. 在订单管理页面查看所有订单
2. 筛选已支付、待处理、已完成等状态的订单
3. 查看订单详情，包括菜品、备注、配送信息
4. 分析订单趋势，了解高峰期和低谷期

请尝试以下操作：
- 前往"订单管理"查看具体订单
- 使用筛选功能查找特定订单
- 导出订单数据进行详细分析"""
    else:
        return """🤖 智能经营顾问已连接到本地数据库，但AI服务暂时不可用。

我能为您提供以下信息：

📈 销售数据分析：
- 最近销售趋势
- 热门菜品分析
- 顾客消费统计
- 经营状况概览

🔍 如何提问？
1. 销售相关："最近销售额如何？"、"最好的一天卖了多少？"
2. 菜品相关："哪些菜品最受欢迎？"、"推荐什么菜？"
3. 顾客相关："哪些顾客消费最多？"、"顾客喜欢什么？"
4. 经营建议："如何提高营业额？"、"有什么改进建议？"

💡 提示：
- 请使用具体的问题关键词
- 如"顾客A喜欢吃什么？"会搜索顾客A的订单记录
- 如"今天销售额多少？"会计算今日销售数据
- 如"哪些菜品卖得好？"会分析菜品销售排名

请重新尝试提问，或检查网络连接后重试。"""

def analyze_sales_trends(restaurant_id):
    """分析销售趋势"""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    # 获取最近7天销售数据
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    daily_sales = db.session.query(
        func.date(Order.created_at).label('date'),
        func.sum(Order.total_amount).label('sales')
    ).filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid',
        Order.created_at >= seven_days_ago
    ).group_by(func.date(Order.created_at)).all()
    
    if not daily_sales:
        return "📅 暂无近期的销售数据。建议先处理一些订单，以便生成销售分析。"
    
    # 找出销售额最高和最低的一天
    best_day = max(daily_sales, key=lambda x: x.sales) if daily_sales else None
    worst_day = min(daily_sales, key=lambda x: x.sales) if daily_sales else None
    
    total_sales = sum(day.sales for day in daily_sales)
    avg_sales = total_sales / len(daily_sales) if daily_sales else 0
    
    # 计算趋势
    sorted_days = sorted(daily_sales, key=lambda x: x.date)
    if len(sorted_days) >= 2:
        trend = "📈 上升" if sorted_days[-1].sales > sorted_days[-2].sales else "📉 下降"
    else:
        trend = "📊 稳定"
    
    # 构建详细的销售报告
    report = f"📊 最近7天销售分析\n\n"
    report += f"💰 总销售额：¥{total_sales:.2f}\n"
    report += f"📅 数据周期：{sorted_days[0].date} 至 {sorted_days[-1].date}\n"
    report += f"📈 销售趋势：{trend}\n\n"
    
    report += f"🏆 销售最佳：{best_day.date} ¥{best_day.sales:.2f}\n"
    if worst_day and worst_day != best_day:
        report += f"📉 销售最低：{worst_day.date} ¥{worst_day.sales:.2f}\n"
    report += f"📊 日均销售：¥{avg_sales:.2f}\n\n"
    
    report += f"📅 每日销售明细：\n"
    for day in sorted_days:
        report += f"  {day.date}：¥{day.sales:.2f}\n"
    
    # 添加建议
    report += f"\n💡 经营建议：\n"
    if best_day:
        report += f"1. 分析{best_day.date}的成功因素，尝试复制到其他日期\n"
    
    if len(daily_sales) >= 3:
        # 计算工作日和周末的区别
        weekdays_sales = []
        weekend_sales = []
        for day in daily_sales:
            date_obj = datetime.strptime(str(day.date), '%Y-%m-%d').date()
            if date_obj.weekday() < 5:  # 0-4是工作日
                weekdays_sales.append(day.sales)
            else:  # 5-6是周末
                weekend_sales.append(day.sales)
        
        if weekdays_sales and weekend_sales:
            weekday_avg = sum(weekdays_sales) / len(weekdays_sales) if weekdays_sales else 0
            weekend_avg = sum(weekend_sales) / len(weekend_sales) if weekend_sales else 0
            
            if weekday_avg > weekend_avg:
                report += f"2. 工作日销售额较高，可增加工作日促销\n"
            else:
                report += f"2. 周末销售额较高，可优化周末服务流程\n"
    
    report += f"3. 设置每日销售目标，鼓励员工提高服务质量\n"
    report += f"4. 定期分析销售数据，调整经营策略\n"
    
    return report

def analyze_popular_dishes(restaurant_id):
    """分析热门菜品"""
    from sqlalchemy import func
    
    # 获取销量前5的菜品
    top_dishes = db.session.query(
        Dish.id,
        Dish.name,
        Dish.category_id,
        Dish.price,
        Dish.description,
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.quantity * OrderItem.price).label('total_revenue')
    ).join(OrderItem, OrderItem.dish_id == Dish.id)\
     .join(Order, Order.id == OrderItem.order_id)\
     .filter(
        Dish.restaurant_id == restaurant_id,
        Order.status == 'paid',
        Dish.is_active == True
     ).group_by(Dish.id)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5).all()
    
    if not top_dishes:
        return "🍽️ 暂无菜品销售数据。建议先上架一些菜品并处理订单。"
    
    # 获取分类信息
    category_dict = {cat.id: cat.name for cat in Category.query.filter_by(restaurant_id=restaurant_id).all()}
    
    # 计算总销量
    total_sold_all = sum(dish.total_sold for dish in top_dishes)
    
    # 获取总销售额用于占比计算
    total_revenue_all = sum(dish.total_revenue for dish in top_dishes)
    
    # 构建菜品分析报告
    report = f"🏆 最受欢迎的菜品（按销量排名）\n\n"
    
    for i, dish in enumerate(top_dishes, 1):
        category_name = category_dict.get(dish.category_id, '未知分类')
        quantity_percentage = (dish.total_sold / total_sold_all * 100) if total_sold_all > 0 else 0
        revenue_percentage = (dish.total_revenue / total_revenue_all * 100) if total_revenue_all > 0 else 0
        avg_price = dish.total_revenue / dish.total_sold if dish.total_sold > 0 else dish.price
        
        report += f"{i}. {dish.name}\n"
        report += f"   📁 分类：{category_name}\n"
        if dish.description and len(dish.description) > 0:
            description_short = dish.description[:30] + "..." if len(dish.description) > 30 else dish.description
            report += f"   📝 描述：{description_short}\n"
        report += f"   📦 销量：{dish.total_sold} 份\n"
        report += f"   💰 销售额：¥{dish.total_revenue:.2f}\n"
        report += f"   📈 销量占比：{quantity_percentage:.1f}%\n"
        report += f"   🎯 销售额占比：{revenue_percentage:.1f}%\n"
        report += f"   💵 平均单价：¥{avg_price:.2f}\n\n"
    
    # 计算菜品平均价格
    avg_dish_price = total_revenue_all / total_sold_all if total_sold_all > 0 else 0
    report += f"📊 整体数据：\n"
    report += f"• 总销量：{total_sold_all} 份\n"
    report += f"• 总销售额：¥{total_revenue_all:.2f}\n"
    report += f"• 菜品平均价格：¥{avg_dish_price:.2f}\n"
    report += f"• TOP5菜品占总体：{quantity_percentage:.1f}%\n"
    
    # 添加建议
    report += f"\n💡 经营建议：\n"
    if top_dishes:
        report += f"1. 重点推广 {top_dishes[0].name}，这是您的招牌菜品\n"
    
    # 分析价格分布
    price_groups = {'低价(<¥20)': 0, '中价(¥20-50)': 0, '高价(>¥50)': 0}
    for dish in top_dishes:
        avg_price = dish.total_revenue / dish.total_sold if dish.total_sold > 0 else dish.price
        if avg_price < 20:
            price_groups['低价(<¥20)'] += 1
        elif avg_price <= 50:
            price_groups['中价(¥20-50)'] += 1
        else:
            price_groups['高价(>¥50)'] += 1
    
    report += f"2. 价格分布："
    for group, count in price_groups.items():
        if count > 0:
            report += f" {group}:{count}个"
    report += f"\n"
    
    report += f"3. 考虑将热门菜品加入套餐或推出特价组合\n"
    report += f"4. 分析滞销菜品，优化或下架\n"
    
    return report

def analyze_popular_dishes_with_recommendation(restaurant_id):
    """分析热门菜品并给出推荐"""
    from sqlalchemy import func
    
    # 获取销量前3的菜品
    top_dishes = db.session.query(
        Dish.id,
        Dish.name,
        Dish.category_id,
        Dish.price,
        Dish.description,
        func.sum(OrderItem.quantity).label('total_sold')
    ).join(OrderItem, OrderItem.dish_id == Dish.id)\
     .join(Order, Order.id == OrderItem.order_id)\
     .filter(
        Dish.restaurant_id == restaurant_id,
        Order.status == 'paid',
        Dish.is_active == True
     ).group_by(Dish.id)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(3).all()
    
    if not top_dishes:
        return "🍽️ 暂无菜品推荐数据。请先上架菜品并处理一些订单。"
    
    # 获取分类信息
    category_dict = {cat.id: cat.name for cat in Category.query.filter_by(restaurant_id=restaurant_id).all()}
    
    # 构建推荐报告
    report = f"🍽️ 为您推荐以下招牌菜品：\n\n"
    
    for i, dish in enumerate(top_dishes, 1):
        category_name = category_dict.get(dish.category_id, '未知分类')
        
        report += f"🥇 第{i}名：{dish.name}\n"
        report += f"   📁 分类：{category_name}\n"
        report += f"   💰 价格：¥{dish.price:.2f}\n"
        if dish.description and len(dish.description) > 0:
            description_short = dish.description[:50] + "..." if len(dish.description) > 50 else dish.description
            report += f"   📝 描述：{description_short}\n"
        report += f"   📊 销量：{dish.total_sold} 份（证明受欢迎）\n\n"
    
    # 添加推荐逻辑
    report += f"🤔 如何选择？\n"
    
    if len(top_dishes) >= 1:
        report += f"1. 如果喜欢招牌菜：{top_dishes[0].name} 是您的招牌，最受欢迎\n"
    
    if len(top_dishes) >= 2:
        report += f"2. 想尝试不同口味：{top_dishes[1].name} 也是不错的选择\n"
    
    if len(top_dishes) >= 3:
        report += f"3. 喜欢特色菜：{top_dishes[2].name} 是特色菜品\n"
    
    # 检查是否有促销菜品
    active_promotions = db.session.query(Dish).filter(
        Dish.restaurant_id == restaurant_id,
        Dish.is_active == True,
        Dish.is_promotion == True
    ).limit(2).all()
    
    if active_promotions:
        report += f"\n🎁 特价菜品推荐：\n"
        for dish in active_promotions:
            report += f"• {dish.name} - ¥{dish.price:.2f}（特价）\n"
    
    return report

def analyze_customer_behavior(restaurant_id):
    """分析顾客行为"""
    from sqlalchemy import func
    
    # 获取消费前5的顾客
    top_customers = db.session.query(
        User.id,
        User.username,
        User.email,
        func.sum(Order.total_amount).label('total_spent'),
        func.count(Order.id).label('order_count'),
        func.max(Order.created_at).label('last_order')
    ).join(Order, Order.user_id == User.id)\
     .filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid'
     ).group_by(User.id)\
     .order_by(func.sum(Order.total_amount).desc())\
     .limit(5).all()
    
    if not top_customers:
        return "👥 暂无顾客消费数据。"
    
    # 获取总销售额
    total_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid'
    ).scalar() or 0
    
    # 获取总订单数
    total_orders = db.session.query(func.count(Order.id)).filter(
        Order.restaurant_id == restaurant_id,
        Order.status == 'paid'
    ).scalar() or 0
    
    # 计算平均订单金额
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0
    
    # 获取总顾客数
    total_customers = len(top_customers)
    
    # 构建顾客分析报告
    report = f"👥 顾客消费分析\n\n"
    report += f"📊 整体数据：\n"
    report += f"• 总顾客数：{total_customers} 人\n"
    report += f"• 总订单数：{total_orders} 单\n"
    report += f"• 总销售额：¥{total_sales:.2f}\n"
    report += f"• 平均订单金额：¥{avg_order_value:.2f}\n\n"
    
    report += f"🏆 高价值顾客TOP {len(top_customers)}：\n"
    
    for i, customer in enumerate(top_customers, 1):
        customer_percentage = (customer.total_spent / total_sales * 100) if total_sales > 0 else 0
        avg_customer_order_value = customer.total_spent / customer.order_count if customer.order_count > 0 else 0
        last_order_date = customer.last_order.strftime('%Y-%m-%d') if customer.last_order else '无记录'
        
        # 计算平均下单周期
        if customer.order_count >= 2 and customer.last_order:
            # 这里简化计算，实际需要计算订单间隔
            report += f"\n{i}. {customer.username}\n"
        else:
            report += f"\n{i}. {customer.username}\n"
        
        report += f"   📧 邮箱：{customer.email}\n"
        report += f"   💰 总消费：¥{customer.total_spent:.2f}\n"
        report += f"   📦 订单数：{customer.order_count} 单\n"
        report += f"   📅 最近下单：{last_order_date}\n"
        report += f"   🎯 顾客占比：{customer_percentage:.1f}%\n"
        report += f"   💵 均单金额：¥{avg_customer_order_value:.2f}\n"
        
        # 判断顾客价值等级
        if customer_percentage > 20:
            report += f"   ⭐ 等级：VIP顾客\n"
        elif customer_percentage > 5:
            report += f"   ⭐ 等级：重要顾客\n"
        else:
            report += f"   ⭐ 等级：普通顾客\n"
    
    # 计算顾客价值分布
    if len(top_customers) >= 3:
        top3_percentage = sum(customer.total_spent for customer in top_customers[:3]) / total_sales * 100 if total_sales > 0 else 0
        report += f"\n📈 顾客价值分布：\n"
        report += f"• TOP3顾客贡献：{top3_percentage:.1f}% 销售额\n"
        report += f"• 其他顾客贡献：{100 - top3_percentage:.1f}% 销售额\n"
    
    # 添加经营建议
    report += f"\n💡 顾客关系管理建议：\n"
    
    if top_customers:
        # 分析最近下单时间
        from datetime import datetime, timedelta
        today = datetime.utcnow().date()
        
        recent_customers = 0
        for customer in top_customers:
            if customer.last_order:
                last_order_date = customer.last_order.date()
                days_since_last = (today - last_order_date).days
                if days_since_last <= 30:
                    recent_customers += 1
        
        report += f"1. 活跃顾客：{recent_customers}/{len(top_customers)} 人在30天内下单\n"
        
        if recent_customers < len(top_customers) / 2:
            report += f"2. 建议：联系未活跃顾客，推出回馈活动\n"
        else:
            report += f"2. 建议：继续保持服务质量，维持活跃度\n"
        
        report += f"3. VIP顾客 ({top_customers[0].username}) 值得特别关注和维护\n"
        report += f"4. 可设置会员等级，给予高价值顾客更多优惠\n"
        report += f"5. 定期发送个性化推荐，提高复购率\n"
    
    return report

# ================= 图片访问路由 =================

@restaurant_bp.route('/uploads/<path:folder>/<filename>')
def uploaded_file(folder, filename):
    """提供上传的文件"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], f'{folder}/{filename}')