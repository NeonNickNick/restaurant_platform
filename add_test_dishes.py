# 修改 add_test_dishes.py
import sys
import os
sys.path.insert(0, '.')
from app import create_app, db
from app.models import User, Restaurant, Category, Dish
from datetime import datetime

app = create_app()

with app.app_context():
    print("=== 开始添加测试菜品 ===")
    
    # 查找测试餐厅
    restaurant = Restaurant.query.filter_by(name='测试餐厅').first()
    if not restaurant:
        print('❌ 找不到测试餐厅')
        print('请先运行: python create_test_restaurant.py')
        sys.exit(1)
    
    print(f"✅ 找到餐厅: {restaurant.name}")
    
    categories = Category.query.filter_by(restaurant_id=restaurant.id).all()
    if not categories:
        print('❌ 找不到分类')
        print('  尝试创建默认分类...')
        # 创建默认分类
        default_categories = ['饮品', '菜品', '主食', '其他']
        for cat_name in default_categories:
            category = Category(name=cat_name, restaurant_id=restaurant.id)
            db.session.add(category)
        db.session.commit()
        categories = Category.query.filter_by(restaurant_id=restaurant.id).all()
        print(f"✅ 创建了 {len(categories)} 个分类")
    
    # 显示现有分类
    print(f"✅ 找到分类: {[cat.name for cat in categories]}")
    
    # 批量添加菜品
    test_dishes = [
        {'name': '卡布奇诺', 'category': '饮品', 'price': 26.0, 'desc': '奶泡丰富，咖啡与牛奶的完美结合'},
        {'name': '摩卡', 'category': '饮品', 'price': 30.0, 'desc': '巧克力与咖啡的绝妙搭配'},
        {'name': '美式咖啡', 'category': '饮品', 'price': 22.0, 'desc': '简单纯粹的美式风味'},
        {'name': '水果茶', 'category': '饮品', 'price': 25.0, 'desc': '多种新鲜水果调制'},
        {'name': '柠檬红茶', 'category': '饮品', 'price': 20.0, 'desc': '清爽解渴'},
        {'name': '芝士蛋糕', 'category': '其他', 'price': 35.0, 'desc': '口感细腻，芝士浓郁'},
        {'name': '巧克力布朗尼', 'category': '其他', 'price': 32.0, 'desc': '巧克力爱好者的最爱'},
        {'name': '薯条', 'category': '其他', 'price': 18.0, 'desc': '金黄酥脆'},
        {'name': '鸡翅', 'category': '菜品', 'price': 28.0, 'desc': '香辣鸡翅'},
        {'name': '沙拉', 'category': '菜品', 'price': 25.0, 'desc': '新鲜蔬菜沙拉'},
        {'name': '意大利面', 'category': '主食', 'price': 45.0, 'desc': '番茄肉酱意大利面'},
        {'name': '炒饭', 'category': '主食', 'price': 35.0, 'desc': '扬州炒饭'},
        {'name': '汉堡', 'category': '主食', 'price': 38.0, 'desc': '牛肉汉堡套餐'},
        {'name': '三明治', 'category': '主食', 'price': 25.0, 'desc': '火腿三明治'},
    ]
    
    added_count = 0
    for dish_info in test_dishes:
        # 找到对应分类
        category = next((c for c in categories if c.name == dish_info['category']), None)
        if not category:
            print(f'❌ 找不到分类: {dish_info["category"]}')
            continue
        
        # 检查菜品是否已存在
        existing_dish = Dish.query.filter_by(
            name=dish_info['name'],
            restaurant_id=restaurant.id
        ).first()
        
        if existing_dish:
            print(f'⚠️ 菜品已存在: {dish_info["name"]}')
            continue
        
        # 创建菜品
        dish = Dish(
            name=dish_info['name'],
            description=dish_info['desc'],
            price=dish_info['price'],
            image_path='',  # 空字符串，不使用图片
            category_id=category.id,
            restaurant_id=restaurant.id,
            is_active=True
        )
        db.session.add(dish)
        added_count += 1
        print(f'  添加: {dish_info["name"]} - ¥{dish_info["price"]}')
    
    try:
        db.session.commit()
        print(f'\n✅ 成功添加 {added_count} 个测试菜品')
    except Exception as e:
        db.session.rollback()
        print(f'❌ 添加失败: {e}')
        import traceback
        traceback.print_exc()