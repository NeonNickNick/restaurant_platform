import sys
import os
sys.path.insert(0, '.')
from app import create_app, db
from app.models import User, Restaurant, Order, Dish, Category, OrderItem, Blacklist

app = create_app()

with app.app_context():
    print("=== 修复数据库表结构 ===")
    
    # 方法1：删除并重建所有表
    print("1. 删除所有表...")
    db.drop_all()
    
    print("2. 重新创建所有表（使用最新模型）...")
    db.create_all()
    
    print("✅ 数据库表已重建，现在有正确的字段结构")
    
    # 验证表结构
    print("\\n=== 验证表结构 ===")
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    
    for table in tables:
        columns = [col['name'] for col in inspector.get_columns(table)]
        print(f'{table}: {len(columns)} 列')
        if table == 'order':
            print(f'  Order表包含remarks字段: {"remarks" in columns}')
            print(f'  所有列: {columns}')
    
    print("\\n✅ 数据库修复完成！")
    print("现在可以运行测试数据脚本了。")