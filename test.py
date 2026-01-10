from app import create_app, db
from app.models import User, Restaurant

app = create_app()
with app.app_context():
    # 获取testuser001
    user = User.query.filter_by(username='testuser001').first()
    if user:
        print(f'用户名: {user.username}')
        print(f'ID: {user.id}')
        print(f'有餐厅: {bool(user.restaurant)}')
        if user.restaurant:
            print(f'餐厅ID: {user.restaurant.id}')
            print(f'餐厅名称: {user.restaurant.name}')
            print(f'所有者ID: {user.restaurant.owner_id}')
    else:
        print('用户testuser001不存在')
        
    # 列出所有餐厅
    print('\\n=== 所有餐厅 ===')
    restaurants = Restaurant.query.all()
    for r in restaurants:
        print(f'ID: {r.id}, 名称: {r.name}, 所有者: {r.owner_id}')