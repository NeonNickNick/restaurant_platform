from app import create_app, db
from app.models import Order, Restaurant, User
from sqlalchemy import func

app = create_app()
with app.app_context():
    # 查找一个餐厅
    restaurant = Restaurant.query.first()
    if restaurant:
        print(f"检查餐厅 {restaurant.name} 的订单...")
        
        # 使用与customers函数相同的查询
        from sqlalchemy import func
        customers_query = db.session.query(
            User,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('total_spent')
        ).join(
            Order, User.id == Order.user_id
        ).filter(
            Order.restaurant_id == restaurant.id,
            Order.status.in_(['paid', 'completed'])
        ).group_by(
            User.id
        ).all()
        
        print(f"查询结果: {len(customers_query)} 行")
        for row in customers_query:
            if row and row[0]:
                print(f"顾客: {row[0].username}, 订单数: {row[1]}, 消费额: {row[2]}")