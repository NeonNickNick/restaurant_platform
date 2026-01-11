from app import create_app, db
from app.models import Order, Restaurant, User

app = create_app()
with app.app_context():
    # 查找一个餐厅
    restaurant = Restaurant.query.first()
    if restaurant:
        print(f"餐厅: {restaurant.name} (ID: {restaurant.id})")
        
        # 查询该餐厅的所有订单
        orders = Order.query.filter_by(restaurant_id=restaurant.id).all()
        print(f"订单总数: {len(orders)}")
        
        for order in orders:
            customer = User.query.get(order.user_id)
            print(f"订单#{order.id}: 顾客: {customer.username if customer else '未知'}, 状态: {order.status}, 金额: {order.total_amount}")
    else:
        print("没有找到餐厅")