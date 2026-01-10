from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from app.models import User, Restaurant, Dish, Order, OrderItem, Category, Blacklist
from app import db
from sqlalchemy import desc

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/index')
def index():
    return render_template('index.html', title='首页')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', title='控制面板')

@main_bp.route('/menu')
@login_required
def menu():
    """点餐菜单页面 - 改为提示信息"""
    flash('点餐功能正在开发中，敬请期待！', 'info')
    return redirect(url_for('main.index'))

# ================= 新的点餐功能 =================

@main_bp.route('/restaurants')
@login_required
def restaurants():
    """餐厅列表页面 - 按销售额排序"""
    # 获取所有餐厅，按销售额降序排序
    restaurants_list = Restaurant.query.order_by(desc(Restaurant.total_sales)).all()
    
    # 初始化购物车（如果不存在）
    if 'cart' not in session:
        session['cart'] = {}
    
    return render_template('restaurants.html', 
                         title='选择餐厅',
                         restaurants=restaurants_list)

@main_bp.route('/restaurant/<int:restaurant_id>/menu')
@login_required
def restaurant_menu(restaurant_id):
    """餐厅菜单页面"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 获取所有分类
    categories = Category.query.filter_by(restaurant_id=restaurant_id).all()
    
    # 获取分类ID（如果有的话）
    category_id = request.args.get('category_id', type=int)
    
    # 构建菜品查询
    if category_id:
        # 显示特定分类的菜品
        dishes = Dish.query.filter_by(
            restaurant_id=restaurant_id,
            category_id=category_id,
            is_active=True
        ).all()
        current_category = Category.query.get(category_id)
    else:
        # 显示所有在售菜品
        dishes = Dish.query.filter_by(
            restaurant_id=restaurant_id,
            is_active=True
        ).all()
        current_category = None
    
    return render_template('restaurant_menu.html',
                         title=f'{restaurant.name} - 菜单',
                         restaurant=restaurant,
                         categories=categories,
                         dishes=dishes,
                         current_category=current_category)

@main_bp.route('/dish/<int:dish_id>')
@login_required
def dish_detail(dish_id):
    """菜品详情页面"""
    dish = Dish.query.get_or_404(dish_id)
    
    return render_template('dish_detail.html',
                         title=dish.name,
                         dish=dish)

@main_bp.route('/my-table')
@login_required
def my_table():
    """我的餐桌 - 购物车页面"""
    cart = session.get('cart', {})
    cart_items = []
    total_price = 0.0
    
    # 计算总价并准备购物车项目
    for dish_id_str, item in cart.items():
        try:
            dish_id = int(dish_id_str)
            dish = Dish.query.get(dish_id)
            if dish and item.get('quantity', 0) > 0:
                quantity = item['quantity']
                price = float(item.get('price', dish.price))
                item_total = price * quantity
                
                cart_items.append({
                    'dish': dish,
                    'quantity': quantity,
                    'price': price,
                    'item_total': item_total
                })
                
                total_price += item_total
        except (ValueError, TypeError):
            continue
    
    # 获取当前时间
    now = datetime.utcnow()
    
    return render_template('my_table.html',
                         title='我的餐桌',
                         cart_items=cart_items,
                         total_price=total_price,
                         now=now)

@main_bp.route('/api/add-to-cart/<int:dish_id>', methods=['POST'])
@login_required
def add_to_cart(dish_id):
    """添加菜品到购物车（API接口）"""
    dish = Dish.query.get_or_404(dish_id)
    
    # 获取数量（默认为1）
    quantity = request.json.get('quantity', 1)
    
    # 初始化购物车
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    
    # 添加或更新菜品
    dish_id_str = str(dish_id)
    if dish_id_str in cart:
        cart[dish_id_str]['quantity'] += quantity
    else:
        cart[dish_id_str] = {
            'dish_id': dish_id,
            'dish_name': dish.name,
            'dish_image': dish.image_path,
            'price': float(dish.price),
            'quantity': quantity,
            'restaurant_id': dish.restaurant_id
        }
    
    session['cart'] = cart
    session.modified = True
    
    return jsonify({
        'success': True,
        'message': f'已添加 {dish.name} 到我的餐桌',
        'cart_count': sum(item['quantity'] for item in cart.values())
    })

@main_bp.route('/api/update-cart/<int:dish_id>', methods=['POST'])
@login_required
def update_cart(dish_id):
    """更新购物车中菜品的数量"""
    dish_id_str = str(dish_id)
    cart = session.get('cart', {})
    
    if dish_id_str not in cart:
        return jsonify({'success': False, 'message': '菜品不在购物车中'}), 404
    
    quantity = request.json.get('quantity', 1)
    
    if quantity <= 0:
        # 如果数量为0或负数，从购物车中移除
        del cart[dish_id_str]
        removed = True
    else:
        cart[dish_id_str]['quantity'] = quantity
        removed = False
    
    session['cart'] = cart
    session.modified = True
    
    # 计算新的总价
    total_price = 0.0
    for item in cart.values():
        total_price += item['price'] * item['quantity']
    
    return jsonify({
        'success': True,
        'removed': removed,
        'total_price': round(total_price, 2),
        'cart_count': sum(item['quantity'] for item in cart.values())
    })

@main_bp.route('/api/ask-question/<int:dish_id>', methods=['POST'])
@login_required
def ask_question(dish_id):
    """AI询问功能 - 顾客端版本"""
    dish = Dish.query.get_or_404(dish_id)
    question = request.json.get('question', '').strip()
    
    if not question:
        return jsonify({'success': False, 'message': '请输入问题'}), 400
    
    try:
        # 为顾客创建简化的上下文
        context = f"""
        菜品信息：
        - 名称：{dish.name}
        - 分类：{dish.category.name}
        - 价格：¥{dish.price:.2f}
        - 描述：{dish.description}
        
        餐厅信息：
        - 餐厅名称：{dish.restaurant.name}
        """
        
        # 构建面向顾客的问题
        customer_question = f"""
        我是顾客，想问关于菜品"{dish.name}"的问题：
        {question}
        
        请用友好、简洁的语言回答顾客的问题，回答时请注意：
        1. 不要使用专业术语，用简单易懂的语言
        2. 不要透露餐厅内部经营数据
        3. 回答要热情友好
        4. 如果不知道确切答案，可以给出建议
        5. 如果是关于口味、配料、份量等问题，基于菜品描述给出合理回答
        """
        
        # 尝试调用AI
        from app.services.ai_service import ai_service
        ai_answer = ai_service.call_deepseek(customer_question, context)
        
        if ai_answer and "由于大模型服务暂时不可用" not in ai_answer:
            return jsonify({
                'success': True,
                'answer': ai_answer
            })
        else:
            # 如果AI不可用，使用简化的备选回答
            fallback_answer = generate_customer_fallback_answer(question, dish)
            return jsonify({
                'success': True,
                'answer': fallback_answer,
                'is_fallback': True
            })
            
    except ImportError as e:
        return jsonify({'success': False, 'message': f'AI服务未配置: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'AI服务出错: {str(e)}'}), 500
    
def generate_customer_fallback_answer(question, dish):
    """为顾客生成备选回答"""
    question_lower = question.lower()
    
    # 常见问题匹配
    if any(keyword in question_lower for keyword in ['辣', '辛辣', '辣度']):
        return f"关于'{dish.name}'的辣度：根据菜品描述，这道菜{'' if '辣' in dish.description.lower() else '不'}是辣味的。"
    
    elif any(keyword in question_lower for keyword in ['甜', '咸', '酸', '苦']):
        return f"关于'{dish.name}'的口味：这道菜的味道比较均衡，具体口味可以查看菜品描述。"
    
    elif any(keyword in question_lower for keyword in ['份量', '分量', '大小', '多少']):
        return f"关于'{dish.name}'的份量：这道菜是标准份量，适合1人食用。如果担心不够，可以多点一份。"
    
    elif any(keyword in question_lower for keyword in ['配料', '材料', '食材', '原料']):
        return f"关于'{dish.name}'的配料：主要食材包括在菜品描述中提到的材料。"
    
    elif any(keyword in question_lower for keyword in ['推荐', '好吃', '招牌', '特色']):
        return f"关于'{dish.name}'的推荐：这道菜是餐厅的{'' if dish.order_count > 0 else '新'}菜品，根据顾客反馈{'' if dish.order_count > 0 else '，因为是新菜，暂时没有评价'}。"
    
    elif any(keyword in question_lower for keyword in ['时间', '制作', '等待', '多久']):
        return f"关于'{dish.name}'的制作时间：这道菜的制作时间在20-30分钟左右，具体时间可能会根据餐厅忙闲有所调整。"
    
    elif any(keyword in question_lower for keyword in ['适合', '人群', '小孩', '老人']):
        return f"关于'{dish.name}'的适合人群：这道菜适合大多数人食用，如果有特殊饮食要求，请在订单备注中说明。"
    
    elif any(keyword in question_lower for keyword in ['热量', '卡路里', '健康', '营养']):
        return f"关于'{dish.name}'的营养信息：我们建议您根据个人需求选择，如有特殊饮食要求，可以咨询餐厅。"
    
    # 默认回答
    return f"关于您对'{dish.name}'的问题：{question}\n\n这道菜是{dish.category.name}，价格¥{dish.price:.2f}。菜品描述：{dish.description}\n\n如果您有更多具体问题，可以联系餐厅客服获得更详细的解答。"

@main_bp.route('/order/checkout', methods=['POST'])
@login_required
def checkout():
    """结算下单"""
    cart = session.get('cart', {})
    
    if not cart:
        return jsonify({'success': False, 'message': '购物车为空'}), 400
    
    # 检查购物车中所有菜品是否来自同一餐厅
    restaurant_ids = set()
    for item in cart.values():
        restaurant_ids.add(item['restaurant_id'])
    
    if len(restaurant_ids) != 1:
        return jsonify({'success': False, 'message': '一次只能点一家餐厅的菜品'}), 400
    
    restaurant_id = list(restaurant_ids)[0]
    
    try:
        # 创建订单
        order = Order(
            user_id=current_user.id,
            restaurant_id=restaurant_id,
            status='paid',
            total_amount=0.0
        )
        db.session.add(order)
        db.session.flush()  # 获取order.id
        
        # 添加订单项并计算总价
        total_amount = 0.0
        for item in cart.values():
            dish_id = item['dish_id']
            quantity = item['quantity']
            price = item['price']
            
            # 创建订单项
            order_item = OrderItem(
                order_id=order.id,
                dish_id=dish_id,
                quantity=quantity,
                price_at_time=price
            )
            db.session.add(order_item)
            
            # 更新菜品被点次数
            dish = Dish.query.get(dish_id)
            if dish:
                dish.order_count = (dish.order_count or 0) + quantity
            
            total_amount += price * quantity
        
        # 更新订单总金额
        order.total_amount = total_amount
        
        # 更新餐厅总销售额
        restaurant = Restaurant.query.get(restaurant_id)
        if restaurant:
            restaurant.total_sales = (restaurant.total_sales or 0) + total_amount
        
        db.session.commit()
        
        # 清空购物车
        session['cart'] = {}
        session.modified = True
        
        return jsonify({
            'success': True,
            'order_id': order.id,
            'total_amount': total_amount,
            'message': '下单成功！感谢您的订购。'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'下单失败: {str(e)}'}), 500

@main_bp.route('/order/complete/<int:order_id>')
@login_required
def order_complete(order_id):
    """订单完成页面"""
    order = Order.query.get_or_404(order_id)
    
    # 确保订单属于当前用户
    if order.user_id != current_user.id:
        flash('无权查看此订单', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # 获取当前时间
    now = datetime.utcnow()
    
    return render_template('order_complete.html',
                         title='订单完成',
                         order=order,
                         now=now)