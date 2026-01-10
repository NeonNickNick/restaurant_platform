@main_bp.route('/api/ask-question/<int:dish_id>', methods=['POST'])
@login_required
def ask_question(dish_id):
    """AI询问功能 - 顾客端版本"""
    dish = Dish.query.get_or_404(dish_id)
    question = request.json.get('question', '').strip()
    
    if not question:
        return jsonify({'success': False, 'message': '请输入问题'}), 400
    
    try:
        # 创建简单的菜品上下文
        context = f"""
        菜品：{dish.name}
        价格：¥{dish.price:.2f}
        分类：{dish.category.name}
        描述：{dish.description}
        餐厅：{dish.restaurant.name}
        """
        
        # 尝试使用顾客专用AI服务
        try:
            from app.services.customer_ai_service import customer_ai_service
            ai_answer = customer_ai_service.get_customer_answer(question, context)
        except ImportError:
            # 如果顾客专用服务不可用，使用原来的AI服务
            from app.services.ai_service import ai_service
            customer_question = f"顾客问：{question}\n请用友好、简洁的语言回答，不要透露内部数据，回答要亲切。"
            ai_answer = ai_service.call_deepseek(customer_question, context)
        
        if ai_answer and "由于大模型服务暂时不可用" not in ai_answer:
            return jsonify({
                'success': True,
                'answer': ai_answer
            })
        else:
            # 使用简化的备选回答
            fallback_answer = generate_customer_fallback_answer(question, dish)
            return jsonify({
                'success': True,
                'answer': fallback_answer,
                'is_fallback': True
            })
            
    except Exception as e:
        # 如果所有AI都失败，使用备选回答
        fallback_answer = generate_customer_fallback_answer(question, dish)
        return jsonify({
            'success': True,
            'answer': fallback_answer,
            'is_fallback': True
        })