from app import db
from app.models import Restaurant, Category, Dish, Order, OrderItem, User, Blacklist
from datetime import datetime, timedelta
import logging
import traceback
from sqlalchemy import func, desc, distinct, extract
from sqlalchemy.orm import aliased

logger = logging.getLogger(__name__)

class ContextBuilder:
    """上下文构建器 - 保留所有功能 + 修复黑名单问题"""
    
    _last_context_update = {}
    
    @staticmethod
    def _force_refresh(restaurant_id):
        """强制刷新指定餐厅的上下文"""
        if restaurant_id in ContextBuilder._last_context_update:
            del ContextBuilder._last_context_update[restaurant_id]
        return True
    
    @staticmethod
    def _should_refresh(restaurant_id, interval_minutes=1):
        """判断是否需要刷新上下文"""
        from datetime import datetime
        
        if restaurant_id not in ContextBuilder._last_context_update:
            return True
            
        last_update = ContextBuilder._last_context_update[restaurant_id]
        time_diff = (datetime.now() - last_update).total_seconds() / 60
        
        return time_diff > interval_minutes
    
    @staticmethod
    def _mark_updated(restaurant_id):
        """标记上下文已更新"""
        ContextBuilder._last_context_update[restaurant_id] = datetime.now()
    
    @staticmethod
    def _safe_float(value, default=0.0):
        """安全转换为浮点数"""
        try:
            if value is None:
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _safe_str(value, default=""):
        """安全转换为字符串"""
        try:
            if value is None:
                return default
            return str(value)
        except:
            return default
    
    @staticmethod
    def _get_customer_blacklist_info(restaurant_id, customer):
        """
        修复：从Blacklist表获取顾客黑名单信息
        从Blacklist表中查询，而不是从User表的字段
        """
        try:
            customer_id = getattr(customer, 'id', None)
            if not customer_id:
                return {
                    'is_blacklisted': False,
                    'reason': '',
                    'since': '',
                    'found_in_blacklist': False
                }
            
            # 从Blacklist表查询
            blacklist_entry = Blacklist.query.filter_by(
                restaurant_id=restaurant_id,
                user_id=customer_id
            ).first()
            
            if blacklist_entry:
                # 如果在黑名单中
                reason = getattr(blacklist_entry, 'reason', '未提供原因')
                created_at = getattr(blacklist_entry, 'created_at', None)
                
                return {
                    'is_blacklisted': True,
                    'reason': str(reason) if reason else '未提供原因',
                    'since': str(created_at) if created_at else '未知时间',
                    'found_in_blacklist': True
                }
            
            # 如果不在Blacklist表中，检查User表的字段作为备选
            blacklist_info = {
                'is_blacklisted': False,
                'reason': '',
                'since': '',
                'found_in_blacklist': False
            }
            
            # 检查所有可能的黑名单状态字段（仅作备选）
            blacklist_fields = [
                'is_blacklisted', 'blacklisted', 'is_banned', 'banned',
                'is_disabled', 'disabled', 'is_blocked', 'blocked',
                'in_blacklist', 'blacklist_status', 'is_suspended'
            ]
            
            for field in blacklist_fields:
                if hasattr(customer, field):
                    value = getattr(customer, field)
                    if isinstance(value, bool) and value is True:
                        blacklist_info['is_blacklisted'] = True
                        break
                    elif isinstance(value, str) and value.lower() in ['banned', 'disabled', 'blocked', 'suspended', 'blacklisted']:
                        blacklist_info['is_blacklisted'] = True
                        break
                    elif value is True:
                        blacklist_info['is_blacklisted'] = True
                        break
            
            return blacklist_info
            
        except Exception as e:
            logger.error(f"获取顾客黑名单信息失败: {e}")
            return {
                'is_blacklisted': False,
                'reason': f'获取失败: {str(e)[:50]}',
                'since': '',
                'found_in_blacklist': False
            }
    
    @staticmethod
    def _get_all_blacklisted_customers(restaurant_id):
        """获取餐厅所有黑名单顾客信息"""
        try:
            blacklisted_customers = []
            
            # 从Blacklist表获取
            blacklist_entries = Blacklist.query.filter_by(
                restaurant_id=restaurant_id
            ).all()
            
            for entry in blacklist_entries:
                user_id = getattr(entry, 'user_id', None)
                if not user_id:
                    continue
                    
                # 获取用户信息
                user = User.query.get(user_id)
                if user:
                    username = getattr(user, 'username', f'用户{user_id}')
                    email = getattr(user, 'email', '未知邮箱')
                    
                    # 获取黑名单原因和时间
                    reason = getattr(entry, 'reason', '未提供原因')
                    created_at = getattr(entry, 'created_at', None)
                    
                    blacklisted_customers.append({
                        'user_id': user_id,
                        'username': username,
                        'email': email,
                        'reason': str(reason) if reason else '未提供原因',
                        'created_at': str(created_at) if created_at else '未知时间',
                        'source': 'blacklist_table'
                    })
            
            return blacklisted_customers
            
        except Exception as e:
            logger.error(f"获取黑名单顾客失败: {e}")
            return []
    
    @staticmethod
    def _get_restaurant_info(restaurant_id):
        """获取餐厅基本信息"""
        try:
            restaurant = Restaurant.query.get(restaurant_id)
            if not restaurant:
                return None, f"餐厅ID {restaurant_id} 不存在"
            
            info = f"=== 餐厅基本信息 ===\n"
            info += f"餐厅名称: {getattr(restaurant, 'name', '未知餐厅')}\n"
            info += f"餐厅ID: {restaurant_id}\n"
            
            # 添加联系方式等其他信息
            if hasattr(restaurant, 'phone') and restaurant.phone:
                info += f"联系电话: {restaurant.phone}\n"
            if hasattr(restaurant, 'address') and restaurant.address:
                info += f"地址: {restaurant.address}\n"
            if hasattr(restaurant, 'description') and restaurant.description:
                info += f"简介: {restaurant.description}\n"
            
            info += f"营业状态: {'营业中' if getattr(restaurant, 'is_active', True) else '已关闭'}\n"
            info += "\n"
            
            return restaurant, info
        except Exception as e:
            logger.error(f"获取餐厅信息失败: {e}")
            return None, f"获取餐厅信息失败: {e}\n"
    
    @staticmethod
    def _build_business_overview(restaurant_id):
        """构建经营概览"""
        try:
            context = "=== 经营概览 ===\n"
            
            # 当前时间
            now = datetime.utcnow()
            context += f"当前时间: {now}\n"
            
            # 菜品总数
            try:
                dish_count = Dish.query.filter_by(restaurant_id=restaurant_id, is_active=True).count()
                context += f"在售菜品数: {dish_count}\n"
            except Exception as e:
                logger.warning(f"获取菜品数失败: {e}")
            
            # 分类总数
            try:
                category_count = Category.query.filter_by(restaurant_id=restaurant_id).count()
                context += f"菜品分类数: {category_count}\n"
            except Exception as e:
                logger.warning(f"获取分类数失败: {e}")
            
            # 顾客总数
            try:
                customer_count = db.session.query(func.count(distinct(Order.user_id))).filter(
                    Order.restaurant_id == restaurant_id
                ).scalar() or 0
                context += f"顾客总数: {customer_count}\n"
            except Exception as e:
                logger.warning(f"获取顾客数失败: {e}")
            
            # 订单总数
            try:
                order_count = Order.query.filter_by(restaurant_id=restaurant_id).count()
                context += f"订单总数: {order_count}\n"
            except Exception as e:
                logger.warning(f"获取订单数失败: {e}")
            
            # 活跃订单
            try:
                active_order_count = Order.query.filter_by(
                    restaurant_id=restaurant_id
                ).filter(Order.status.notin_(['cancelled', 'completed'])).count()
                context += f"活跃订单: {active_order_count}\n"
            except Exception as e:
                logger.warning(f"获取活跃订单数失败: {e}")
            
            # 黑名单顾客数
            try:
                blacklist_count = Blacklist.query.filter_by(restaurant_id=restaurant_id).count()
                context += f"黑名单顾客数: {blacklist_count}\n"
            except Exception as e:
                logger.warning(f"获取黑名单数失败: {e}")
            
            context += f"餐厅ID: {restaurant_id}\n"
            context += f"数据更新时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            return context
            
        except Exception as e:
            logger.error(f"构建经营概览失败: {e}")
            return "=== 经营概览 ===\n经营概览获取失败\n\n"
    
    @staticmethod
    def _build_categories_context(restaurant_id):
        """构建菜品分类上下文"""
        try:
            categories = Category.query.filter_by(restaurant_id=restaurant_id).all()
            
            if not categories:
                logger.warning(f"餐厅 {restaurant_id} 没有菜品分类")
                return "=== 菜品分类 ===\n暂无分类\n\n"
            
            context = "=== 菜品分类 ===\n"
            for category in categories:
                category_id = getattr(category, 'id', '未知')
                category_name = getattr(category, 'name', '未命名分类')
                
                # 获取该分类下的菜品数量
                dish_count = Dish.query.filter_by(
                    category_id=category_id,
                    restaurant_id=restaurant_id,
                    is_active=True
                ).count()
                
                context += f"分类ID: {category_id}\n"
                context += f"分类名称: {category_name}\n"
                context += f"菜品数量: {dish_count}\n"
                context += f"---\n"
            
            context += f"总计分类数量: {len(categories)}\n\n"
            return context
            
        except Exception as e:
            logger.error(f"构建分类上下文失败: {e}")
            return "=== 菜品分类 ===\n分类信息获取失败\n\n"
    
    @staticmethod
    def _build_dishes_context(restaurant_id):
        """构建菜品上下文"""
        try:
            # 查询所有菜品
            dishes = Dish.query.filter_by(restaurant_id=restaurant_id).order_by(Dish.price.asc()).all()
            
            if not dishes:
                logger.warning(f"餐厅 {restaurant_id} 没有菜品数据")
                return "=== 所有菜品详情 ===\n暂无菜品\n\n"
            
            logger.info(f"查询到餐厅 {restaurant_id} 的菜品数量: {len(dishes)}")
            
            context = "=== 所有菜品详情（按价格从低到高排序） ===\n"
            
            # 按分类分组
            dishes_by_category = {}
            uncategorized_dishes = []
            
            for dish in dishes:
                category_id = getattr(dish, 'category_id', None)
                if category_id:
                    if category_id not in dishes_by_category:
                        dishes_by_category[category_id] = []
                    dishes_by_category[category_id].append(dish)
                else:
                    uncategorized_dishes.append(dish)
            
            # 获取分类名称映射
            category_names = {}
            if dishes_by_category:
                category_ids = list(dishes_by_category.keys())
                categories = Category.query.filter(Category.id.in_(category_ids)).all()
                for cat in categories:
                    category_names[cat.id] = getattr(cat, 'name', f"分类{cat.id}")
            
            # 输出有分类的菜品
            for category_id, dish_list in dishes_by_category.items():
                category_name = category_names.get(category_id, f"分类{category_id}")
                context += f"【{category_name}】\n"
                
                for dish in dish_list:
                    dish_id = getattr(dish, 'id', '未知')
                    dish_name = getattr(dish, 'name', '未知菜品')
                    
                    # 价格
                    price = ContextBuilder._safe_float(getattr(dish, 'price', 0))
                    
                    # 菜品状态
                    is_active = getattr(dish, 'is_active', True)
                    
                    context += f"- {dish_name} (ID:{dish_id}): ¥{price:.2f} {'✅' if is_active else '⏸️'}\n"
                    
                    # 描述
                    if hasattr(dish, 'description') and dish.description:
                        desc = str(dish.description)
                        if len(desc) > 30:
                            context += f"  描述: {desc[:30]}...\n"
                        else:
                            context += f"  描述: {desc}\n"
                
                context += "\n"
            
            # 输出无分类的菜品
            if uncategorized_dishes:
                context += f"【未分类菜品】\n"
                for dish in uncategorized_dishes:
                    dish_id = getattr(dish, 'id', '未知')
                    dish_name = getattr(dish, 'name', '未知菜品')
                    price = ContextBuilder._safe_float(getattr(dish, 'price', 0))
                    is_active = getattr(dish, 'is_active', True)
                    context += f"- {dish_name} (ID:{dish_id}): ¥{price:.2f} {'✅' if is_active else '⏸️'}\n"
                
                context += "\n"
            
            # 价格统计
            price_list = []
            for dish in dishes:
                if getattr(dish, 'is_active', True):  # 只统计在售菜品
                    price = ContextBuilder._safe_float(getattr(dish, 'price', 0))
                    if price > 0:
                        price_list.append(price)
            
            if price_list:
                min_price = min(price_list)
                max_price = max(price_list)
                avg_price = sum(price_list) / len(price_list)
                
                # 找到最便宜的菜品
                cheapest_dishes = []
                for dish in dishes:
                    if getattr(dish, 'is_active', True):
                        dish_price = ContextBuilder._safe_float(getattr(dish, 'price', 0))
                        if abs(dish_price - min_price) < 0.01:  # 浮点数比较
                            cheapest_dishes.append(getattr(dish, 'name', '未知菜品'))
                
                context += f"=== 价格统计 ===\n"
                context += f"最低价格: ¥{min_price:.2f}\n"
                context += f"最高价格: ¥{max_price:.2f}\n"
                context += f"平均价格: ¥{avg_price:.2f}\n"
                if cheapest_dishes:
                    context += f"最便宜菜品: {', '.join(cheapest_dishes[:3])}\n"
            
            context += f"\n总计菜品数量: {len(dishes)} (在售: {len([d for d in dishes if getattr(d, 'is_active', True)])})\n\n"
            return context
            
        except Exception as e:
            logger.error(f"构建菜品上下文失败: {e}")
            logger.error(traceback.format_exc())
            return "=== 所有菜品详情 ===\n菜品信息获取失败\n\n"
    
    @staticmethod
    def _build_sales_statistics(restaurant_id):
        """构建销售统计"""
        try:
            # 获取当前时间
            now = datetime.utcnow()
            
            context = "=== 销售统计 ===\n"
            
            # 查询函数
            def get_sales_query():
                return db.session.query(func.sum(Order.total_amount)).filter(
                    Order.restaurant_id == restaurant_id,
                    Order.status == 'paid'
                )
            
            # 总销售额
            try:
                total_sales = get_sales_query().scalar() or 0
                total_sales = float(total_sales) if total_sales else 0.0
                context += f"总销售额: ¥{total_sales:.2f}\n"
            except Exception as e:
                logger.warning(f"获取总销售额失败: {e}")
                context += f"总销售额: 获取失败\n"
            
            # 总订单数
            try:
                total_orders = db.session.query(func.count(Order.id)).filter(
                    Order.restaurant_id == restaurant_id,
                    Order.status == 'paid'
                ).scalar() or 0
                context += f"总订单数: {total_orders}\n"
            except Exception as e:
                logger.warning(f"获取总订单数失败: {e}")
                context += f"总订单数: 获取失败\n"
            
            # 平均订单金额
            if total_sales and total_orders:
                avg_order_value = total_sales / total_orders
                context += f"平均订单金额: ¥{avg_order_value:.2f}\n"
            
            # 最近30天销售
            try:
                thirty_days_ago = now - timedelta(days=30)
                recent_sales = db.session.query(func.sum(Order.total_amount)).filter(
                    Order.restaurant_id == restaurant_id,
                    Order.status == 'paid',
                    Order.created_at >= thirty_days_ago
                ).scalar() or 0
                recent_sales = float(recent_sales) if recent_sales else 0.0
                context += f"最近30天销售额: ¥{recent_sales:.2f}\n"
            except Exception as e:
                logger.warning(f"获取30天销售额失败: {e}")
            
            # 最近7天销售
            try:
                seven_days_ago = now - timedelta(days=7)
                weekly_sales = db.session.query(func.sum(Order.total_amount)).filter(
                    Order.restaurant_id == restaurant_id,
                    Order.status == 'paid',
                    Order.created_at >= seven_days_ago
                ).scalar() or 0
                weekly_sales = float(weekly_sales) if weekly_sales else 0.0
                context += f"最近7天销售额: ¥{weekly_sales:.2f}\n"
            except Exception as e:
                logger.warning(f"获取7天销售额失败: {e}")
            
            # 今日销售
            try:
                today = now.date()
                today_sales = db.session.query(func.sum(Order.total_amount)).filter(
                    Order.restaurant_id == restaurant_id,
                    Order.status == 'paid',
                    func.date(Order.created_at) == today
                ).scalar() or 0
                today_sales = float(today_sales) if today_sales else 0.0
                context += f"今日销售额: ¥{today_sales:.2f}\n"
            except Exception as e:
                logger.warning(f"获取今日销售额失败: {e}")
            
            context += "\n"
            return context
            
        except Exception as e:
            logger.error(f"构建销售统计失败: {e}")
            return "=== 销售统计 ===\n销售统计获取失败\n\n"
    
    @staticmethod
    def _build_customers_context(restaurant_id):
        """修复：构建顾客上下文 - 从Blacklist表获取黑名单状态"""
        try:
            # 获取所有在该餐厅消费过的顾客
            customer_ids = db.session.query(distinct(Order.user_id)).filter(
                Order.restaurant_id == restaurant_id
            ).all()
            
            customer_ids = [c[0] for c in customer_ids if c[0]]
            
            if not customer_ids:
                return "=== 顾客信息 ===\n暂无顾客数据\n\n"
            
            # 获取顾客详细信息
            customers = User.query.filter(User.id.in_(customer_ids)).all()
            
            # 获取该餐厅的黑名单列表
            blacklist_map = {}
            try:
                blacklist_entries = Blacklist.query.filter_by(restaurant_id=restaurant_id).all()
                for entry in blacklist_entries:
                    user_id = getattr(entry, 'user_id', None)
                    if user_id:
                        blacklist_map[user_id] = {
                            'reason': getattr(entry, 'reason', ''),
                            'created_at': getattr(entry, 'created_at', None)
                        }
            except Exception as e:
                logger.error(f"获取黑名单列表失败: {e}")
            
            context = "=== 顾客信息（包含黑名单状态） ===\n"
            
            blacklisted_count = 0
            total_customers = len(customers)
            
            for customer in customers:
                customer_id = getattr(customer, 'id', '未知')
                username = getattr(customer, 'username', '未知')
                email = getattr(customer, 'email', '未知邮箱')
                
                # 从黑名单映射中获取信息
                is_blacklisted = customer_id in blacklist_map
                blacklist_reason = blacklist_map.get(customer_id, {}).get('reason', '')
                blacklist_since = blacklist_map.get(customer_id, {}).get('created_at', '')
                
                if is_blacklisted:
                    blacklisted_count += 1
                
                # 获取订单统计
                orders = Order.query.filter_by(
                    restaurant_id=restaurant_id,
                    user_id=customer_id
                ).all()
                
                # 计算消费总额
                total_spent = 0.0
                paid_orders = []
                for order in orders:
                    if getattr(order, 'status', '') == 'paid':
                        order_total = getattr(order, 'total_amount', 0)
                        if order_total:
                            try:
                                total_spent += float(order_total)
                                paid_orders.append(order)
                            except (ValueError, TypeError):
                                pass
                
                order_count = len(orders)
                paid_order_count = len(paid_orders)
                
                context += f"【顾客ID: {customer_id}】\n"
                context += f"用户名: {username}\n"
                context += f"邮箱: {email}\n"
                context += f"订单数量: {order_count} (已支付: {paid_order_count})\n"
                context += f"总消费额: ¥{total_spent:.2f}\n"
                context += f"黑名单状态: {'⚠️ 已加入黑名单' if is_blacklisted else '✅ 正常'}\n"
                
                # 如果顾客在黑名单中，显示详细信息
                if is_blacklisted:
                    if blacklist_reason:
                        context += f"加入黑名单原因: {blacklist_reason}\n"
                    if blacklist_since:
                        context += f"加入黑名单时间: {blacklist_since}\n"
                
                # 最近订单
                if orders:
                    recent_orders = sorted(orders, key=lambda o: getattr(o, 'created_at', datetime.min), reverse=True)[:2]
                    context += f"最近订单:\n"
                    for order in recent_orders:
                        order_id = getattr(order, 'id', '未知')
                        order_time = getattr(order, 'created_at', '未知时间')
                        order_status = getattr(order, 'status', '未知')
                        order_amount = getattr(order, 'total_amount', 0)
                        
                        try:
                            order_amount = float(order_amount) if order_amount else 0.0
                        except (ValueError, TypeError):
                            order_amount = 0.0
                        
                        status_icon = "✅" if order_status == 'paid' else "⏳"
                        context += f"  - 订单#{order_id}: ¥{order_amount:.2f} {status_icon}{order_status} {order_time}\n"
                
                context += f"---\n"
            
            # 黑名单统计
            context += f"\n=== 黑名单统计 ===\n"
            context += f"顾客总数: {total_customers}\n"
            context += f"黑名单顾客: {blacklisted_count}\n"
            context += f"正常顾客: {total_customers - blacklisted_count}\n"
            context += f"黑名单比例: {blacklisted_count/max(total_customers, 1)*100:.1f}%\n\n"
            
            return context
            
        except Exception as e:
            logger.error(f"构建顾客上下文失败: {e}")
            logger.error(traceback.format_exc())
            return "=== 顾客信息 ===\n顾客信息获取失败（包含黑名单状态）\n\n"
    
    @staticmethod
    def _build_blacklist_summary(restaurant_id):
        """专门构建黑名单汇总信息 - 从Blacklist表获取"""
        try:
            # 从Blacklist表获取该餐厅的黑名单记录
            blacklist_entries = Blacklist.query.filter_by(restaurant_id=restaurant_id).all()
            
            # 获取黑名单用户ID列表
            blacklisted_user_ids = []
            blacklist_info_map = {}
            for entry in blacklist_entries:
                user_id = getattr(entry, 'user_id', None)
                if user_id:
                    blacklisted_user_ids.append(user_id)
                    blacklist_info_map[user_id] = {
                        'reason': getattr(entry, 'reason', '未提供原因'),
                        'created_at': getattr(entry, 'created_at', '未知时间'),
                        'entry_id': getattr(entry, 'id', '未知')
                    }
            
            # 获取所有在该餐厅消费过的顾客
            customer_ids = db.session.query(distinct(Order.user_id)).filter(
                Order.restaurant_id == restaurant_id
            ).all()
            
            customer_ids = [c[0] for c in customer_ids if c[0]]
            
            if not customer_ids:
                return "=== 黑名单汇总 ===\n暂无顾客数据\n\n"
            
            # 获取顾客详细信息
            customers = User.query.filter(User.id.in_(customer_ids)).all()
            
            blacklisted_customers = []
            normal_customers = []
            
            for customer in customers:
                customer_id = getattr(customer, 'id', '未知')
                
                if customer_id in blacklisted_user_ids:
                    # 黑名单顾客
                    customer_data = {
                        'id': customer_id,
                        'username': getattr(customer, 'username', '未知'),
                        'email': getattr(customer, 'email', '未知邮箱'),
                        'is_blacklisted': True,
                        'reason': blacklist_info_map.get(customer_id, {}).get('reason', '未提供原因'),
                        'since': blacklist_info_map.get(customer_id, {}).get('created_at', '未知时间'),
                        'entry_id': blacklist_info_map.get(customer_id, {}).get('entry_id', '未知')
                    }
                    blacklisted_customers.append(customer_data)
                else:
                    # 正常顾客
                    customer_data = {
                        'id': customer_id,
                        'username': getattr(customer, 'username', '未知'),
                        'email': getattr(customer, 'email', '未知邮箱'),
                        'is_blacklisted': False,
                        'reason': '',
                        'since': ''
                    }
                    normal_customers.append(customer_data)
            
            context = "=== 黑名单汇总信息 ===\n"
            context += f"顾客总数: {len(customers)}\n"
            context += f"黑名单顾客: {len(blacklisted_customers)}\n"
            context += f"正常顾客: {len(normal_customers)}\n"
            context += f"黑名单比例: {len(blacklisted_customers)/max(len(customers), 1)*100:.1f}%\n\n"
            
            if blacklisted_customers:
                context += f"【⚠️ 黑名单顾客详情】\n"
                for i, customer in enumerate(blacklisted_customers, 1):
                    context += f"{i}. ID: {customer['id']}, 用户名: {customer['username']}\n"
                    context += f"   邮箱: {customer['email']}\n"
                    if customer['reason']:
                        context += f"   原因: {customer['reason']}\n"
                    if customer['since']:
                        context += f"   加入时间: {customer['since']}\n"
                context += "\n"
            
            # 列出所有顾客的ID和用户名
            context += f"【所有顾客列表】\n"
            for i, customer in enumerate(customers[:30], 1):  # 最多显示30个
                username = getattr(customer, 'username', '未知')
                customer_id = getattr(customer, 'id', '未知')
                
                # 检查是否在黑名单中
                is_blacklisted = customer_id in blacklisted_user_ids
                status = "⚠️ 黑名单" if is_blacklisted else "✅ 正常"
                context += f"{i}. ID:{customer_id} 用户名:{username} 状态:{status}\n"
                
                # 特殊标记顾客B
                if username == "顾客B" or customer_id == 3:
                    context += f"   *特别注意: 这是顾客B (ID:3)*\n"
            
            if len(customers) > 30:
                context += f"... 等{len(customers)}位顾客\n"
            
            context += "\n"
            return context
            
        except Exception as e:
            logger.error(f"构建黑名单汇总失败: {e}")
            return "=== 黑名单汇总 ===\n黑名单汇总获取失败\n\n"
    
    @staticmethod
    def _build_popular_dishes_analysis(restaurant_id):
        """热门菜品分析"""
        try:
            context = "=== 热门菜品分析 ===\n"
            
            # 从订单项统计销量
            dish_stats = db.session.query(
                Dish.id,
                Dish.name,
                func.sum(OrderItem.quantity).label('total_sold'),
                func.sum(OrderItem.quantity * Dish.price).label('total_revenue')
            ).join(OrderItem, OrderItem.dish_id == Dish.id)\
             .join(Order, Order.id == OrderItem.order_id)\
             .filter(
                Dish.restaurant_id == restaurant_id,
                Order.status == 'paid',
                Dish.is_active == True
             ).group_by(Dish.id, Dish.name)\
             .order_by(desc(func.sum(OrderItem.quantity)))\
             .limit(10).all()
            
            if dish_stats:
                context += "销量TOP 10菜品:\n"
                for i, (dish_id, dish_name, total_sold, total_revenue) in enumerate(dish_stats, 1):
                    total_sold = total_sold or 0
                    total_revenue = float(total_revenue) if total_revenue else 0.0
                    context += f"{i}. {dish_name} (ID:{dish_id}): 销量{total_sold}份, 销售额¥{total_revenue:.2f}\n"
            else:
                # 如果没有订单数据，显示所有菜品
                context += "暂无销售数据，显示所有菜品:\n"
                dishes = Dish.query.filter_by(restaurant_id=restaurant_id, is_active=True).all()
                for i, dish in enumerate(dishes[:10], 1):
                    dish_id = getattr(dish, 'id', '未知')
                    dish_name = getattr(dish, 'name', '未知菜品')
                    price = getattr(dish, 'price', 0)
                    try:
                        price = float(price) if price else 0.0
                    except (ValueError, TypeError):
                        price = 0.0
                    context += f"{i}. {dish_name} (ID:{dish_id}): ¥{price:.2f}\n"
            
            context += "\n"
            return context
            
        except Exception as e:
            logger.error(f"构建热门菜品分析失败: {e}")
            return "=== 热门菜品分析 ===\n热门菜品分析获取失败\n\n"
    
    @staticmethod
    def _build_customer_analysis(restaurant_id):
        """顾客消费分析"""
        try:
            # 高价值顾客
            top_customers = db.session.query(
                User.id,
                User.username,
                func.count(Order.id).label('order_count'),
                func.sum(Order.total_amount).label('total_spent')
            ).join(Order, Order.user_id == User.id)\
             .filter(
                Order.restaurant_id == restaurant_id,
                Order.status == 'paid'
             ).group_by(User.id, User.username)\
             .order_by(desc(func.sum(Order.total_amount)))\
             .limit(10).all()
            
            context = "=== 顾客消费分析 ===\n"
            
            if top_customers:
                context += "消费最高的10位顾客:\n"
                for i, (user_id, username, order_count, total_spent) in enumerate(top_customers, 1):
                    total_spent = float(total_spent) if total_spent else 0.0
                    avg_value = total_spent / order_count if order_count > 0 else 0.0
                    
                    context += f"{i}. {username} (ID:{user_id}): {order_count}单, "
                    context += f"总消费¥{total_spent:.2f}, 均单¥{avg_value:.2f}\n"
            else:
                context += "暂无顾客消费数据\n"
            
            context += "\n"
            return context
            
        except Exception as e:
            logger.error(f"构建顾客分析失败: {e}")
            return "=== 顾客消费分析 ===\n顾客消费分析获取失败\n\n"
    
    @staticmethod
    def _build_orders_context(restaurant_id):
        """构建订单上下文"""
        try:
            orders = Order.query.filter_by(restaurant_id=restaurant_id).order_by(Order.created_at.desc()).limit(20).all()
            
            if not orders:
                return "=== 订单详情 ===\n暂无订单\n\n"
            
            context = "=== 最近订单（20条） ===\n"
            
            for order in orders:
                order_id = getattr(order, 'id', '未知')
                
                # 顾客信息
                customer_info = "未知顾客"
                customer_id = getattr(order, 'user_id', None)
                if customer_id:
                    customer = User.query.get(customer_id)
                    if customer:
                        customer_info = f"{getattr(customer, 'username', f'用户{customer_id}')}(ID:{customer_id})"
                
                # 订单信息
                order_time = getattr(order, 'created_at', '未知时间')
                order_status = getattr(order, 'status', '未知')
                order_total = ContextBuilder._safe_float(getattr(order, 'total_amount', 0))
                
                context += f"订单ID: {order_id}\n"
                context += f"顾客: {customer_info}\n"
                context += f"时间: {order_time}\n"
                context += f"状态: {order_status}\n"
                context += f"金额: ¥{order_total:.2f}\n"
                
                # 订单项
                order_items = OrderItem.query.filter_by(order_id=order_id).all()
                if order_items:
                    context += f"菜品:\n"
                    for item in order_items:
                        dish_name = "未知菜品"
                        quantity = getattr(item, 'quantity', 0)
                        
                        if hasattr(item, 'dish_id') and item.dish_id:
                            dish = Dish.query.get(item.dish_id)
                            if dish:
                                dish_name = getattr(dish, 'name', '未知菜品')
                        
                        context += f"  - {dish_name} × {quantity}\n"
                
                context += f"---\n"
            
            context += f"总订单数: {len(orders)}\n\n"
            return context
            
        except Exception as e:
            logger.error(f"构建订单上下文失败: {e}")
            return "=== 订单详情 ===\n订单信息获取失败\n\n"
    
    @staticmethod
    def build_restaurant_context(restaurant_id, force_refresh=False):
        """构建完整的餐厅上下文"""
        
        logger.info(f"开始构建餐厅 {restaurant_id} 的完整上下文...")
        
        # 检查是否需要刷新
        if force_refresh or ContextBuilder._should_refresh(restaurant_id):
            logger.info(f"正在刷新餐厅 {restaurant_id} 的上下文...")
        else:
            logger.info(f"使用缓存的餐厅 {restaurant_id} 上下文")
        
        try:
            # 获取餐厅基本信息
            restaurant, restaurant_info = ContextBuilder._get_restaurant_info(restaurant_id)
            if not restaurant:
                return f"餐厅ID {restaurant_id} 不存在"
            
            context = restaurant_info
            
            # 1. 经营概览
            context += ContextBuilder._build_business_overview(restaurant_id)
            
            # 2. 菜品分类
            context += ContextBuilder._build_categories_context(restaurant_id)
            
            # 3. 菜品详情
            context += ContextBuilder._build_dishes_context(restaurant_id)
            
            # 4. 热门菜品分析
            context += ContextBuilder._build_popular_dishes_analysis(restaurant_id)
            
            # 5. 销售统计
            context += ContextBuilder._build_sales_statistics(restaurant_id)
            
            # 6. 顾客信息（包含黑名单状态）
            context += ContextBuilder._build_customers_context(restaurant_id)
            
            # 7. 黑名单汇总（修复：从Blacklist表获取）
            context += ContextBuilder._build_blacklist_summary(restaurant_id)
            
            # 8. 顾客消费分析
            context += ContextBuilder._build_customer_analysis(restaurant_id)
            
            # 9. 订单详情
            context += ContextBuilder._build_orders_context(restaurant_id)
            
            # 标记已更新
            ContextBuilder._mark_updated(restaurant_id)
            
            logger.info(f"✅ 上下文构建完成，长度: {len(context)} 字符")
            
            return context
            
        except Exception as e:
            logger.error(f"构建上下文失败: {e}")
            logger.error(traceback.format_exc())
            return f"构建上下文时出错: {str(e)[:200]}..."
    
    @staticmethod
    def build_context_for_question(question, restaurant_id, max_length=4000):
        """根据问题构建上下文（智能截断）"""
        
        # 强制刷新上下文
        ContextBuilder._force_refresh(restaurant_id)
        
        # 先构建完整上下文
        full_context = ContextBuilder.build_restaurant_context(restaurant_id, force_refresh=True)
        
        # 如果上下文太长，进行智能截断
        if len(full_context) > max_length:
            logger.warning(f"上下文过长 ({len(full_context)} > {max_length})，进行智能截断")
            
            # 根据问题类型保留相关部分
            question_lower = question.lower()
            
            # 初始化上下文
            context = ""
            
            # 总是包含餐厅信息和经营概览
            restaurant, restaurant_info = ContextBuilder._get_restaurant_info(restaurant_id)
            if restaurant:
                context += restaurant_info
                context += ContextBuilder._build_business_overview(restaurant_id)
            
            # 黑名单相关问题时，重点保留黑名单信息
            if '黑名单' in question_lower or '拉黑' in question_lower or '禁用' in question_lower:
                context += ContextBuilder._build_blacklist_summary(restaurant_id)
                context += ContextBuilder._build_customers_context(restaurant_id)
                context += ContextBuilder._build_customer_analysis(restaurant_id)
                
            # 顾客相关问题时
            elif '顾客' in question_lower or '用户' in question_lower:
                context += ContextBuilder._build_customers_context(restaurant_id)
                context += ContextBuilder._build_blacklist_summary(restaurant_id)
                context += ContextBuilder._build_customer_analysis(restaurant_id)
                
            # 价格相关问题时
            elif '便宜' in question_lower or '贵' in question_lower or '价格' in question_lower:
                context += ContextBuilder._build_dishes_context(restaurant_id)
                context += ContextBuilder._build_categories_context(restaurant_id)
                context += ContextBuilder._build_popular_dishes_analysis(restaurant_id)
                
            # 销售相关问题时
            elif '销售' in question_lower or '营业额' in question_lower or '收入' in question_lower:
                context += ContextBuilder._build_sales_statistics(restaurant_id)
                context += ContextBuilder._build_orders_context(restaurant_id)
                context += ContextBuilder._build_customer_analysis(restaurant_id)
                
            # 订单相关问题时
            elif '订单' in question_lower or '状态' in question_lower:
                context += ContextBuilder._build_orders_context(restaurant_id)
                context += ContextBuilder._build_sales_statistics(restaurant_id)
                
            # 热门菜品相关
            elif '热门' in question_lower or '畅销' in question_lower or '推荐' in question_lower:
                context += ContextBuilder._build_popular_dishes_analysis(restaurant_id)
                context += ContextBuilder._build_dishes_context(restaurant_id)
                
            else:
                # 默认情况，保留所有信息但截断
                for part in [
                    ContextBuilder._build_dishes_context(restaurant_id),
                    ContextBuilder._build_categories_context(restaurant_id),
                    ContextBuilder._build_blacklist_summary(restaurant_id),
                    ContextBuilder._build_customers_context(restaurant_id)
                ]:
                    if len(context) + len(part) < max_length * 0.8:  # 留出20%空间
                        context += part
            
            logger.info(f"智能截断后上下文长度: {len(context)}")
            return context
        else:
            return full_context
    
    @staticmethod
    def build_minimal_context(restaurant_id):
        """构建最小上下文（快速版本）"""
        try:
            restaurant = Restaurant.query.get(restaurant_id)
            if not restaurant:
                return f"餐厅ID {restaurant_id} 不存在"
            
            context = f"餐厅: {getattr(restaurant, 'name', '未知餐厅')} (ID:{restaurant_id})\n"
            
            # 菜品数量
            dish_count = Dish.query.filter_by(restaurant_id=restaurant_id, is_active=True).count()
            context += f"在售菜品: {dish_count}\n"
            
            # 获取最便宜的菜品
            cheapest_dish = Dish.query.filter_by(
                restaurant_id=restaurant_id,
                is_active=True
            ).order_by(Dish.price.asc()).first()
            
            if cheapest_dish:
                dish_name = getattr(cheapest_dish, 'name', '未知菜品')
                price = getattr(cheapest_dish, 'price', 0)
                try:
                    price = float(price) if price else 0.0
                except (ValueError, TypeError):
                    price = 0.0
                context += f"最便宜菜品: {dish_name} (¥{price:.2f})\n"
            
            # 获取最贵的菜品
            expensive_dish = Dish.query.filter_by(
                restaurant_id=restaurant_id,
                is_active=True
            ).order_by(Dish.price.desc()).first()
            
            if expensive_dish:
                dish_name = getattr(expensive_dish, 'name', '未知菜品')
                price = getattr(expensive_dish, 'price', 0)
                try:
                    price = float(price) if price else 0.0
                except (ValueError, TypeError):
                    price = 0.0
                context += f"最贵菜品: {dish_name} (¥{price:.2f})\n"
            
            return context
            
        except Exception as e:
            logger.error(f"构建最小上下文失败: {e}")
            return f"餐厅ID: {restaurant_id}"
    
    @staticmethod
    def build_debug_context(restaurant_id, user_id=None):
        """调试专用：查看指定顾客的所有字段"""
        try:
            context = "=== 调试信息 ===\n"
            
            if user_id:
                customer = User.query.get(user_id)
                if customer:
                    context += f"顾客ID: {user_id} 的完整字段信息:\n"
                    
                    # 获取所有字段
                    for attr in dir(customer):
                        if not attr.startswith('_'):  # 排除私有属性
                            try:
                                value = getattr(customer, attr)
                                if not callable(value):  # 排除方法
                                    context += f"{attr}: {value}\n"
                            except:
                                context += f"{attr}: <无法获取值>\n"
                    
                    # 特别检查黑名单相关字段
                    context += "\n=== 黑名单相关字段检查 ===\n"
                    blacklist_fields = [
                        'is_blacklisted', 'blacklisted', 'is_banned', 'banned',
                        'is_disabled', 'disabled', 'is_blocked', 'blocked',
                        'in_blacklist', 'blacklist_status', 'is_suspended',
                        'blacklist_reason', 'ban_reason', 'disabled_reason',
                        'blacklisted_at', 'banned_at', 'disabled_at'
                    ]
                    
                    for field in blacklist_fields:
                        if hasattr(customer, field):
                            value = getattr(customer, field)
                            context += f"{field}: {value} (类型: {type(value)})\n"
                    
                    # 从Blacklist表检查
                    context += "\n=== Blacklist表检查 ===\n"
                    blacklist_entries = Blacklist.query.filter_by(user_id=user_id).all()
                    if blacklist_entries:
                        for entry in blacklist_entries:
                            context += f"黑名单记录ID: {getattr(entry, 'id', '未知')}\n"
                            context += f"餐厅ID: {getattr(entry, 'restaurant_id', '未知')}\n"
                            context += f"原因: {getattr(entry, 'reason', '未知')}\n"
                            context += f"创建时间: {getattr(entry, 'created_at', '未知')}\n"
                    else:
                        context += "在Blacklist表中没有找到记录\n"
                else:
                    context += f"顾客ID {user_id} 不存在\n"
            
            return context
            
        except Exception as e:
            return f"调试信息获取失败: {e}"