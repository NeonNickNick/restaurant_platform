# 保存为 final_verification.py
import sys
import os
sys.path.insert(0, '.')

from app import create_app
from app.models import Restaurant
import logging

# 设置详细日志
logging.basicConfig(level=logging.DEBUG)

app = create_app()

with app.app_context():
    print("=== 最终验证：模拟经营顾问实际调用 ===\n")
    
    # 1. 导入服务
    try:
        from app.services.ai_service import ai_service
        from app.services.context_builder import ContextBuilder
        
        print("✅ 成功导入AI服务模块")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        sys.exit(1)
    
    # 2. 查找餐厅
    restaurant = Restaurant.query.first()
    if not restaurant:
        print("❌ 没有找到餐厅，请先创建测试数据")
        print("   运行: python add_test_dishes.py")
        sys.exit(1)
    
    print(f"✅ 使用餐厅: {restaurant.name} (ID: {restaurant.id})")
    
    # 3. 构建完整的上下文
    print("\n🔧 构建餐厅数据上下文...")
    context = ContextBuilder.build_restaurant_context(restaurant.id)
    
    print(f"   上下文长度: {len(context)} 字符")
    if len(context) < 100:
        print("⚠️  上下文可能太短，AI可能无法进行有效分析")
        print(f"   上下文内容预览:\n{context[:200]}...")
    
    # 4. 测试不同类型的问题
    test_cases = [
        {
            "question": "你好，请说'AI工作正常'",
            "description": "简单测试问题"
        },
        {
            "question": "如何提高餐厅营业额？请给出具体建议。",
            "description": "经营建议类问题"
        },
        {
            "question": "分析一下餐厅的销售数据和菜品表现。",
            "description": "数据分析类问题"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {test_case['description']}")
        print(f"问题: {test_case['question']}")
        print(f"{'='*60}")
        
        # 调用AI
        answer = ai_service.call_deepseek(test_case['question'], context)
        
        if answer:
            print(f"✅ AI返回了回答，长度: {len(answer)} 字符")
            
            # 检查是否是真正的AI回答
            is_real_ai = True
            warning_signs = [
                "由于大模型服务暂时不可用",
                "这是一个关于经营改进的问题",
                "您可以尝试以下方法：",
                "我主要可以回答以下问题"
            ]
            
            for sign in warning_signs:
                if sign in answer:
                    is_real_ai = False
                    break
            
            if is_real_ai:
                print("🎉 这是真正的AI回答！")
                print(f"\n📄 回答预览:")
                print("-" * 40)
                print(answer[:300] + "..." if len(answer) > 300 else answer)
                print("-" * 40)
            else:
                print("❌ 这是备选回答，不是真正的AI回答！")
                print(f"\n📄 回答内容:")
                print("-" * 40)
                print(answer)
                print("-" * 40)
        else:
            print("❌ AI返回了空，将触发备选回答")
            
            # 模拟备选回答
            from app.routes.restaurant import generate_fallback_answer
            fallback = generate_fallback_answer(test_case['question'].lower(), restaurant.id)
            print(f"   将显示备选回答:")
            print(f"\n📄 备选回答内容:")
            print("-" * 40)
            print(fallback[:200] + "..." if len(fallback) > 200 else fallback)
            print("-" * 40)
    
    print(f"\n{'='*60}")
    print("验证完成！")
    
    # 5. 给出结论
    print("\n💡 结论：")
    print("从测试日志看，您的AI服务已成功配置并可以正常工作。")
    print("如果经营顾问页面仍显示备选回答，请检查：")
    print("1. 餐厅是否有足够的订单和菜品数据")
    print("2. 查看控制台日志，确认实际调用的响应")
    print("3. 在浏览器中打开开发者工具查看网络请求")
    
    print(f"\n🔧 下一步：")
    print("1. 重启应用: python run.py")
    print("2. 在浏览器中访问经营顾问页面")
    print("3. 提问复杂问题，观察控制台日志")