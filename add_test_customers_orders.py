# 修改 add_test_customers_orders.py
import sys
import os
sys.path.insert(0, '.')
from app import create_app, db
from app.models import User, Restaurant, Dish, Order, OrderItem
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("=== 创建测试顾客和订单（简化版）===")
    
    # 1. 查找测试餐厅
    restaurant = Restaurant.query.filter_by(name='测试餐厅').first()
    if not restaurant:
        print('❌ 找不到测试餐厅')
        print('请先运行: python create_test_restaurant.py')
        sys.exit(1)
    
    print(f"✅ 找到餐厅: {restaurant.name}")
    
    # 2. 检查是否有菜品
    dishes = Dish.query.filter_by(restaurant_id=restaurant.id, is_active=True).all()
    if not dishes:
        print('❌ 餐厅没有菜品')
        print('请先运行: python add_test_dishes.py')
        sys.exit(1)
    
    print(f"✅ 找到菜品: {len(dishes)} 个")
    
    # 3. 创建简单的测试顾客
    test_customers_data = [
        {'username': '顾客A', 'email': 'customer_a@test.com'},
        {'username': '顾客B', 'email': 'customer_b@test.com'},
        {'username': '顾客C', 'email': 'customer_c@test.com'},
    ]
    
    test_customers = []
    for data in test_customers_data:
        # 检查是否已存在
        user = User.query.filter_by(email=data['email']).first()
        if not user:
            user = User(
                username=data['username'],
                email=data['email'],
                password_hash=generate_password_hash('password123'),
                role='customer',
                avatar_path=''
            )
            db.session.add(user)
            print(f"✅ 创建顾客: {data['username']}")
        else:
            print(f"⚠️ 顾客已存在: {data['username']}")
        
        test_customers.append(user)
    
    db.session.commit()
    
    # 4. 创建简单的订单
    order_count = 0
    today = datetime.utcnow()
    
    for i, customer in enumerate(test_customers):
        # 每个顾客创建1-2个订单
        for j in range(2):
            order = Order(
                user_id=customer.id,
                restaurant_id=restaurant.id,
                status='paid',
                created_at=today - timedelta(days=i*3 + j),
                total_amount=0
            )
            db.session.add(order)
            db.session.flush()  # 获取order.id
            
            # 添加1-2个菜品到订单
            selected_dishes = dishes[:2]  # 简单选择前2个菜品
            order_total = 0
            
            for dish in selected_dishes:
                quantity = 1
                price = dish.price
                item_total = price * quantity
                order_total += item_total
                
                order_item = OrderItem(
                    order_id=order.id,
                    dish_id=dish.id,
                    quantity=quantity,
                    price_at_time=price
                )
                db.session.add(order_item)
            
            # 更新订单总金额
            order.total_amount = order_total
            order_count += 1
            print(f"✅ 创建订单 #{order.id}: ¥{order_total:.2f}")
    
    # 5. 更新餐厅总销售额
    from sqlalchemy import func
    total_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.restaurant_id == restaurant.id,
        Order.status.in_(['paid', 'completed'])
    ).scalar() or 0
    
    restaurant.total_sales = total_sales
    
    try:
        db.session.commit()
        print(f"\n🎉 测试数据创建完成！")
        print(f"   餐厅: {restaurant.name}")
        print(f"   顾客: {len(test_customers)} 人")
        print(f"   订单: {order_count} 个")
        print(f"   菜品: {len(dishes)} 个")
        print(f"   总销售额: ¥{total_sales:.2f}")
    except Exception as e:
        db.session.rollback()
        print(f'❌ 创建失败: {e}')
        import traceback
        traceback.print_exc()