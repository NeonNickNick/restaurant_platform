"""
改进的AI服务模块 - 整合完整上下文和智能网络处理
"""
import requests
import json
import time
import logging
from flask import current_app
from app.services.context_builder import ContextBuilder

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AIService:
    """AI服务类 - 整合完整上下文和智能网络处理"""
    
    def __init__(self):
        """初始化时不立即获取配置，延迟到实际调用时"""
        self.api_key = None
        self.api_url = None
        self.model = None
        self._initialized = False
        logger.info("AIService 初始化完成（延迟配置）")
    
    def _init_config(self):
        """延迟初始化配置 - 在应用上下文中调用"""
        if not self._initialized:
            try:
                self.api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
                self.api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')
                self.model = current_app.config.get('DEEPSEEK_MODEL', 'deepseek-chat')
                self._initialized = True
                
                logger.info(f"✅ AI服务配置加载完成，API密钥长度: {len(self.api_key)}")
                logger.info(f"   API URL: {self.api_url}")
                logger.info(f"   模型: {self.model}")
            except RuntimeError as e:
                logger.error(f"❌ 初始化配置失败（不在应用上下文中）: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ 初始化配置异常: {e}")
                raise
    
    def call_deepseek(self, question, restaurant_id, use_reasoner=False, retry_count=0, max_retries=2):
        """调用DeepSeek API - 使用完整上下文和智能处理"""
        
        # 确保配置已初始化
        if not self._initialized:
            self._init_config()
        
        logger.info(f"🔧 开始AI调用 (重试 {retry_count}/{max_retries}): {question}")
        
        # 检查API密钥
        if not self.api_key or len(self.api_key) < 20:
            logger.error(f"❌ API密钥无效: 长度={len(self.api_key) if self.api_key else 0}")
            return None
        
        try:
            # 构建完整的餐厅上下文
            logger.info(f"🔄 构建餐厅 {restaurant_id} 的完整上下文...")
            
            # 使用智能上下文构建器，根据问题类型选择相关数据
            context = ContextBuilder.build_context_for_question(question, restaurant_id, max_length=5000)
            
            logger.info(f"📊 上下文构建完成，长度: {len(context)} 字符")
            
            # 如果上下文太长，进行智能压缩
            if len(context) > 4000:
                logger.warning(f"⚠️ 上下文过长 ({len(context)} 字符)，进行智能压缩")
                context = self._compress_context(context, question)
                logger.info(f"📉 压缩后上下文长度: {len(context)} 字符")
            
            # 构建智能提示词
            prompt = self._build_intelligent_prompt(question, context)
            
            # 准备请求
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # 根据上下文长度调整token数量
            estimated_tokens = len(prompt) // 4  # 粗略估算，中文大约1个token=2-3个字符
            max_tokens = min(1500, estimated_tokens + 500)  # 确保有足够空间返回答案
            
            payload = {
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': max_tokens,
                'temperature': 0.7
            }
            
            if use_reasoner:
                payload["reasoning"] = True
            
            logger.info(f"📤 发送请求到DeepSeek API...")
            logger.info(f"   问题: {question[:50]}...")
            logger.info(f"   上下文长度: {len(context)} 字符")
            logger.info(f"   提示词长度: {len(prompt)} 字符")
            logger.info(f"   预计token数: ~{estimated_tokens}")
            logger.info(f"   使用模型: {self.model}")
            
            # 调用API - 使用更长的超时时间
            start_time = time.time()
            
            # 动态设置超时：根据上下文长度调整
            read_timeout = 30 + (len(context) // 1000) * 5  # 每1000字符增加5秒
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=(10, min(read_timeout, 120))  # 连接10秒，读取最多120秒
            )
            
            elapsed = time.time() - start_time
            
            logger.info(f"📥 收到响应，状态码: {response.status_code}, 耗时: {elapsed:.2f}秒")
            
            if response.status_code == 200:
                data = response.json()
                
                if 'choices' in data and data['choices']:
                    answer = data['choices'][0]['message']['content']
                    logger.info(f"🎯 获取AI回答成功，长度: {len(answer)} 字符")
                    logger.debug(f"回答预览: {answer[:200]}...")
                    return answer
                else:
                    logger.error(f"❌ API返回无choices: {data}")
                    return None
            else:
                logger.error(f"❌ API调用失败: {response.status_code}")
                logger.error(f"   错误信息: {response.text[:200]}")
                return None
                
        except requests.exceptions.Timeout as e:
            logger.error(f"⏰ 请求超时: {e}")
            
            # 重试逻辑
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # 指数退避
                logger.info(f"等待 {wait_time} 秒后重试 ({retry_count + 1}/{max_retries})...")
                time.sleep(wait_time)
                
                # 递归重试
                return self.call_deepseek(question, restaurant_id, use_reasoner, retry_count + 1, max_retries)
            else:
                logger.error(f"❌ 重试{max_retries}次后仍然失败")
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"🔌 网络连接错误: {e}")
            
            # 如果是连接错误，也可以重试
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.info(f"等待 {wait_time} 秒后重试连接 ({retry_count + 1}/{max_retries})...")
                time.sleep(wait_time)
                
                return self.call_deepseek(question, restaurant_id, use_reasoner, retry_count + 1, max_retries)
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ 调用异常: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _compress_context(self, context, question):
        """智能压缩上下文，保留关键信息"""
        logger.info(f"🔄 智能压缩上下文...")
        
        # 根据问题类型确定关键信息
        question_lower = question.lower()
        lines = context.split('\n')
        compressed_lines = []
        
        # 保留关键部分
        key_sections = []
        
        if '顾客' in question_lower and ('喜欢' in question_lower or '最爱' in question_lower or '吃什么' in question_lower):
            # 顾客喜好问题
            key_sections = ['=== 顾客信息 ===', '=== 订单详情', '=== 详细订单项记录']
        elif '销售' in question_lower or '营业额' in question_lower or '收入' in question_lower:
            # 销售问题
            key_sections = ['=== 销售统计', '=== 订单详情']
        elif '热门' in question_lower or '畅销' in question_lower or '卖得好' in question_lower:
            # 热门菜品问题
            key_sections = ['=== 热门菜品分析', '=== 菜品详情']
        else:
            # 通用问题，保留所有关键部分
            key_sections = [
                '=== 餐厅基本信息',
                '=== 顾客信息',
                '=== 销售统计',
                '=== 热门菜品分析',
                '=== 订单详情'
            ]
        
        in_key_section = False
        for line in lines:
            # 检查是否是关键部分标题
            if any(section in line for section in key_sections):
                in_key_section = True
                compressed_lines.append(line)
            elif line.startswith('===') and in_key_section:
                # 遇到下一个部分，结束当前关键部分
                in_key_section = False
                if len(compressed_lines) < 3000:  # 限制行数
                    compressed_lines.append(line)
            elif in_key_section and len(compressed_lines) < 3000:
                compressed_lines.append(line)
        
        compressed_context = '\n'.join(compressed_lines)
        
        # 如果仍然太长，截断
        if len(compressed_context) > 4000:
            compressed_context = compressed_context[:4000] + "...[上下文被截断]"
        
        logger.info(f"📉 压缩后保留 {len(compressed_lines)} 行，{len(compressed_context)} 字符")
        return compressed_context
    
    def _build_intelligent_prompt(self, question, context):
        """构建智能提示词，使用完整上下文"""
        return f"""# 🍽️ 餐厅经营顾问分析任务

## 📊 餐厅完整数据
以下是餐厅的完整数据，包含：
1. 餐厅基本信息
2. 菜品分类和详情
3. 顾客信息和消费记录
4. 所有订单详情（包含备注）
5. 订单项具体内容
6. 销售统计
7. 热门菜品分析
8. 顾客消费分析
9. 经营概览

{context}

## ❓ 用户问题
{question}

## 🎯 请作为专业餐厅经营顾问，基于以上完整数据回答

**回答要求：**
1. 仔细查阅相关数据，确保回答准确
2. 如果问及具体顾客，请查找该顾客的订单记录和菜品偏好
3. 如果问及销售，请引用具体的销售统计数据
4. 如果问及菜品，请参考菜品详情和销售记录
5. 如果数据中没有相关信息，明确说明"未找到相关数据"
6. 给出具体、可操作的建议

**特别注意：**
- 顾客喜好问题：查看顾客订单记录，分析点餐频次和金额
- 销售问题：分析销售趋势、平均订单金额、高峰期
- 菜品问题：分析销量、受欢迎程度、价格合理性
- 经营建议：基于数据给出优化方案

请开始你的专业分析："""
    
    def call_deepseek_fast(self, question, restaurant_id):
        """快速调用DeepSeek API - 使用简化上下文"""
        try:
            # 使用最小上下文
            minimal_context = ContextBuilder.build_minimal_context(restaurant_id)
            
            # 构建极简提示词
            prompt = f"餐厅数据：{minimal_context}\n问题：{question}\n请简要回答："
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            payload = {
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 500,  # 更少的token
                'temperature': 0.7
            }
            
            logger.info("🚀 发送快速请求到DeepSeek API...")
            
            # 更短的超时时间
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=(5, 30)  # 连接5秒，读取30秒
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and data['choices']:
                    answer = data['choices'][0]['message']['content']
                    logger.info(f"✅ 快速调用成功，回答长度: {len(answer)}")
                    return answer
            
            return None
            
        except Exception as e:
            logger.error(f"快速调用失败: {e}")
            return None
    
    def get_ai_analysis(self, question, restaurant_id, use_fast_mode=False):
        """获取AI分析 - 主入口函数"""
        if use_fast_mode:
            logger.info("🚀 使用快速模式调用AI...")
            return self.call_deepseek_fast(question, restaurant_id)
        else:
            logger.info("🧠 使用完整模式调用AI...")
            return self.call_deepseek(question, restaurant_id, use_reasoner=True)

# 创建全局实例
ai_service = AIService()