import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timezone
import feedparser
import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import hashlib
from urllib.parse import urljoin, urlparse
import re
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rss_feeds.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 数据库模型
class RSSSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    category = db.Column(db.String(50), default='general')
    active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), nullable=False, unique=True)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    summary = db.Column(db.Text)  # 新增：AI生成的文章摘要
    author = db.Column(db.String(100))
    published_date = db.Column(db.DateTime)
    source_id = db.Column(db.Integer, db.ForeignKey('rss_source.id'), nullable=False)
    tags = db.Column(db.String(500))  # 逗号分隔的标签
    read_status = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    source = db.relationship('RSSSource', backref=db.backref('articles', lazy=True))

# 内容提取和摘要生成
class ContentProcessor:
    @staticmethod
    def extract_article_content(url):
        """从文章URL提取正文内容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 移除脚本和样式元素
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # 尝试找到主要内容区域
            content_selectors = [
                'article', '.article', '#article',
                '.content', '#content', '.post-content',
                '.entry-content', '.post-body', '.article-body',
                'main', '.main', '#main'
            ]
            
            content = None
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = elements[0]
                    break
            
            if not content:
                # 如果没找到特定的内容区域，使用body
                content = soup.find('body')
            
            if content:
                # 提取文本并清理
                text = content.get_text()
                # 清理多余的空白字符
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:5000]  # 限制长度
            
            return ""
            
        except Exception as e:
            logger.warning(f"无法提取文章内容 {url}: {str(e)}")
            return ""
    
    @staticmethod
    def generate_summary(title, description, content):
        """生成结构化的技术摘要"""
        try:
            # 合并所有可用的文本内容
            full_text = ""
            if title:
                full_text += f"标题: {title}\n"
            if description:
                full_text += f"描述: {description}\n"
            if content:
                full_text += f"内容: {content[:3000]}\n"  # 增加内容长度限制
            
            if not full_text.strip():
                return "暂无内容摘要"
            
            # 生成结构化摘要
            summary = ContentProcessor._generate_structured_summary(full_text, title)
            return summary
            
        except Exception as e:
            logger.warning(f"生成摘要时出错: {str(e)}")
            return "摘要生成失败，请查看原文"
    
    @staticmethod
    def _generate_structured_summary(text, title=""):
        """生成结构化的技术摘要，包含关键技术点和论点"""
        
        # 技术领域分类和关键词
        tech_categories = {
            '游戏引擎': ['unreal', 'unity', 'godot', 'engine', 'framework', 'runtime'],
            '渲染技术': ['render', 'shader', 'graphics', 'gpu', 'vulkan', 'directx', 'opengl', 'lighting', 'shadow', 'material'],
            '物理仿真': ['physics', 'collision', 'rigidbody', 'simulation', 'dynamics', 'constraint'],
            '动画系统': ['animation', 'skeletal', 'blend', 'timeline', 'motion', 'ik', 'bone'],
            '人工智能': ['ai', 'ml', 'neural', 'behavior', 'pathfinding', 'decision', 'learning'],
            '性能优化': ['optimization', 'performance', 'profiling', 'memory', 'cpu', 'fps', 'bottleneck'],
            '架构设计': ['architecture', 'pattern', 'design', 'component', 'system', 'modular', 'ecs'],
            '网络编程': ['network', 'multiplayer', 'server', 'client', 'synchronization', 'latency'],
            '虚拟现实': ['vr', 'ar', 'xr', 'virtual', 'augmented', 'headset', 'tracking'],
            '工具开发': ['tool', 'editor', 'pipeline', 'automation', 'workflow', 'asset']
        }
        
        # 技术方法和实现关键词
        implementation_keywords = [
            'implement', 'algorithm', 'approach', 'method', 'technique', 'solution',
            '实现', '算法', '方法', '技术', '解决方案', '策略'
        ]
        
        # 问题和挑战关键词
        problem_keywords = [
            'problem', 'issue', 'challenge', 'limitation', 'bottleneck', 'bug',
            '问题', '挑战', '限制', '瓶颈', '困难', '缺陷'
        ]
        
        # 结果和效果关键词
        result_keywords = [
            'result', 'performance', 'improvement', 'benefit', 'advantage', 'effect',
            '结果', '性能', '改进', '优势', '效果', '提升'
        ]
        
        # 按句子分割文本
        sentences = re.split(r'[.!?。！？]\s*', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
        
        # 分析每个句子
        analyzed_sentences = []
        for sentence in sentences[:20]:  # 分析前20个句子
            analysis = ContentProcessor._analyze_sentence(sentence, tech_categories, 
                                                        implementation_keywords, 
                                                        problem_keywords, 
                                                        result_keywords)
            if analysis['relevance_score'] > 0:
                analyzed_sentences.append(analysis)
        
        # 按相关性排序
        analyzed_sentences.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # 构建结构化摘要
        summary_parts = []
        
        # 1. 技术领域概述
        tech_areas = ContentProcessor._extract_tech_areas(analyzed_sentences)
        if tech_areas:
            summary_parts.append(f"📋 **技术领域**: {', '.join(tech_areas)}")
        
        # 2. 关键技术点
        key_points = ContentProcessor._extract_key_points_structured(analyzed_sentences, 'implementation')
        if key_points:
            summary_parts.append("🔧 **关键技术点**:")
            for i, point in enumerate(key_points[:3], 1):
                summary_parts.append(f"   {i}. {point}")
        
        # 3. 主要论点/观点
        main_arguments = ContentProcessor._extract_key_points_structured(analyzed_sentences, 'argument')
        if main_arguments:
            summary_parts.append("💡 **主要论点**:")
            for i, arg in enumerate(main_arguments[:3], 1):
                summary_parts.append(f"   {i}. {arg}")
        
        # 4. 问题与解决方案
        problems_solutions = ContentProcessor._extract_problems_solutions(analyzed_sentences)
        if problems_solutions:
            summary_parts.append("⚡ **问题与解决方案**:")
            for i, ps in enumerate(problems_solutions[:2], 1):
                summary_parts.append(f"   {i}. {ps}")
        
        # 5. 性能/效果
        results = ContentProcessor._extract_key_points_structured(analyzed_sentences, 'result')
        if results:
            summary_parts.append("📈 **效果与收益**:")
            for i, result in enumerate(results[:2], 1):
                summary_parts.append(f"   {i}. {result}")
        
        # 如果没有提取到足够信息，生成基础摘要
        if len(summary_parts) < 2:
            summary_parts = [f"这是一篇关于{tech_areas[0] if tech_areas else '游戏开发'}的技术文章"]
            if analyzed_sentences:
                best_sentence = ContentProcessor._simplify_to_chinese(analyzed_sentences[0]['text'])
                if best_sentence:
                    summary_parts.append(best_sentence)
        
        # 组合摘要
        summary = '\n'.join(summary_parts)
        
        # 限制总长度
        if len(summary) > 500:
            lines = summary.split('\n')
            summary = '\n'.join(lines[:8]) + '\n...'
        
        return summary
    
    @staticmethod
    def _analyze_sentence(sentence, tech_categories, impl_keywords, prob_keywords, result_keywords):
        """分析句子的技术相关性和类型"""
        sentence_lower = sentence.lower()
        
        analysis = {
            'text': sentence,
            'tech_areas': [],
            'type': 'general',
            'relevance_score': 0,
            'keywords': []
        }
        
        # 检查技术领域
        for area, keywords in tech_categories.items():
            for keyword in keywords:
                if keyword in sentence_lower:
                    analysis['tech_areas'].append(area)
                    analysis['keywords'].append(keyword)
                    analysis['relevance_score'] += 2
        
        # 确定句子类型
        if any(kw in sentence_lower for kw in impl_keywords):
            analysis['type'] = 'implementation'
            analysis['relevance_score'] += 3
        elif any(kw in sentence_lower for kw in prob_keywords):
            analysis['type'] = 'problem'
            analysis['relevance_score'] += 2
        elif any(kw in sentence_lower for kw in result_keywords):
            analysis['type'] = 'result'
            analysis['relevance_score'] += 2
        elif any(word in sentence_lower for word in ['新', 'new', '创新', 'innovative', '提出', 'propose']):
            analysis['type'] = 'argument'
            analysis['relevance_score'] += 2
        
        # 额外加分项
        if re.search(r'\d+%|\d+倍|\d+x', sentence):  # 包含数字/百分比
            analysis['relevance_score'] += 1
        if len(sentence) > 30 and len(sentence) < 150:  # 长度适中
            analysis['relevance_score'] += 1
        
        return analysis
    
    @staticmethod
    def _extract_tech_areas(analyzed_sentences):
        """提取主要技术领域"""
        area_count = {}
        for sentence in analyzed_sentences:
            for area in sentence['tech_areas']:
                area_count[area] = area_count.get(area, 0) + 1
        
        # 返回出现频率最高的技术领域
        sorted_areas = sorted(area_count.items(), key=lambda x: x[1], reverse=True)
        return [area for area, count in sorted_areas[:3]]
    
    @staticmethod
    def _extract_key_points_structured(analyzed_sentences, point_type):
        """提取特定类型的关键点"""
        points = []
        for sentence in analyzed_sentences:
            if sentence['type'] == point_type and sentence['relevance_score'] >= 3:
                simplified = ContentProcessor._simplify_to_chinese(sentence['text'])
                if simplified and len(simplified) > 10:
                    points.append(simplified)
        
        return points[:3]  # 最多返回3个点
    
    @staticmethod
    def _extract_problems_solutions(analyzed_sentences):
        """提取问题与解决方案对"""
        problems = []
        solutions = []
        
        for sentence in analyzed_sentences:
            if sentence['type'] == 'problem':
                problems.append(ContentProcessor._simplify_to_chinese(sentence['text']))
            elif sentence['type'] == 'implementation':
                solutions.append(ContentProcessor._simplify_to_chinese(sentence['text']))
        
        # 组合问题和解决方案
        combined = []
        for i in range(min(len(problems), len(solutions))):
            if problems[i] and solutions[i]:
                combined.append(f"问题: {problems[i][:50]}... → 解决: {solutions[i][:50]}...")
        
        return combined[:2]
    
    @staticmethod
    def _simplify_to_chinese(text):
        """将英文技术句子简化并中文化"""
        if not text:
            return ""
        
        # 常见技术术语的中文替换
        replacements = {
            'Unreal Engine': 'Unreal引擎',
            'Unity': 'Unity引擎',
            'rendering': '渲染',
            'performance': '性能',
            'optimization': '优化',
            'shader': '着色器',
            'physics': '物理',
            'animation': '动画',
            'AI': '人工智能',
            'VR': '虚拟现实',
            'AR': '增强现实',
            'GPU': '图形处理器',
            'CPU': '处理器',
            'framework': '框架',
            'algorithm': '算法',
            'gameplay': '游戏玩法'
        }
        
        # 应用替换
        result = text
        for eng, cn in replacements.items():
            result = re.sub(r'\b' + re.escape(eng) + r'\b', cn, result, flags=re.IGNORECASE)
        
        # 移除过长的技术细节
        if len(result) > 100:
            # 尝试提取主要信息
            sentences = re.split(r'[.。]', result)
            if sentences:
                result = sentences[0] + "。"
        
        return result.strip()

# RSS抓取功能
class RSSFetcher:
    @staticmethod
    def fetch_articles(source):
        try:
            logger.info(f"正在抓取RSS源: {source.name}")
            
            # 设置超时时间
            import socket
            socket.setdefaulttimeout(30)  # 30秒超时
            
            feed = feedparser.parse(source.url)
            
            if feed.bozo:
                logger.warning(f"RSS源可能有问题: {source.name} - {feed.bozo_exception}")
            
            if not hasattr(feed, 'entries') or not feed.entries:
                logger.warning(f"RSS源没有文章: {source.name}")
                return 0
            
            logger.info(f"RSS源 {source.name} 找到 {len(feed.entries)} 篇文章")
            
            new_articles = 0
            # 限制每次处理的文章数量，避免超时
            max_articles = 10
            
            for i, entry in enumerate(feed.entries[:max_articles]):
                try:
                    logger.info(f"正在检查文章: {entry.title[:50]}... (URL: {entry.link})")
                    
                    # 检查文章是否已存在
                    existing = Article.query.filter_by(url=entry.link).first()
                    if existing:
                        logger.info(f"文章已存在，跳过: {entry.title[:50]}...")
                        continue
                    
                    logger.info(f"文章不存在，开始处理: {entry.title[:50]}...")
                    
                    # 解析发布日期
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_date = datetime(*entry.published_parsed[:6])
                        except (ValueError, TypeError):
                            pass
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        try:
                            published_date = datetime(*entry.updated_parsed[:6])
                        except (ValueError, TypeError):
                            pass
                    
                    # 提取描述
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description
                    
                    # 清理HTML标签
                    if description:
                        soup = BeautifulSoup(description, 'html.parser')
                        description = soup.get_text()[:500]
                    
                    # 提取标签
                    tags = []
                    if hasattr(entry, 'tags'):
                        tags = [tag.term for tag in entry.tags]
                    
                    # 提取文章内容并生成摘要（简化处理，避免超时）
                    logger.info(f"正在处理文章 {i+1}/{min(len(feed.entries), max_articles)}: {entry.title[:50]}...")
                    
                    # 简化内容提取，避免超时
                    article_content = ""
                    article_summary = ContentProcessor.generate_summary(
                        entry.title, 
                        description, 
                        ""  # 暂时不提取完整内容，避免超时
                    )
                    
                    # 创建新文章
                    article = Article(
                        title=entry.title[:500],  # 限制标题长度
                        url=entry.link,
                        description=description,
                        content=article_content,
                        summary=article_summary,
                        author=getattr(entry, 'author', '')[:100],  # 限制作者长度
                        published_date=published_date,
                        source_id=source.id,
                        tags=','.join(tags)[:500]  # 限制标签长度
                    )
                    
                    db.session.add(article)
                    new_articles += 1
                    logger.info(f"成功添加文章: {entry.title[:50]}...")
                    
                except Exception as e:
                    logger.warning(f"处理文章时出错: {str(e)}")
                    continue
            
            # 更新源的最后更新时间
            source.last_updated = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"从 {source.name} 抓取了 {new_articles} 篇新文章")
            return new_articles
            
        except Exception as e:
            logger.error(f"抓取RSS源 {source.name} 时出错: {str(e)}")
            db.session.rollback()  # 回滚事务
            return 0
    
    @staticmethod
    def fetch_all_sources():
        """抓取所有RSS源的文章"""
        try:
            logger.info("开始抓取所有RSS源")
            sources = RSSSource.query.filter_by(active=True).all()
            
            logger.info(f"找到 {len(sources)} 个活跃的RSS源")
            
            if not sources:
                logger.warning("没有找到活跃的RSS源")
                return 0
            
            total_new_articles = 0
            successful_sources = 0
            failed_sources = 0
            
            for i, source in enumerate(sources):
                try:
                    logger.info(f"正在处理RSS源 {i+1}/{len(sources)}: {source.name} (URL: {source.url})")
                    new_articles = RSSFetcher.fetch_articles(source)
                    total_new_articles += new_articles
                    successful_sources += 1
                    logger.info(f"RSS源 {source.name} 完成，新增 {new_articles} 篇文章")
                    
                except Exception as e:
                    failed_sources += 1
                    logger.error(f"处理RSS源 {source.name} 时出错: {str(e)}")
                    continue
            
            logger.info(f"RSS抓取完成！成功: {successful_sources}, 失败: {failed_sources}, 总新增文章: {total_new_articles}")
            return total_new_articles
            
        except Exception as e:
            logger.error(f"抓取所有RSS源时出错: {str(e)}")
            return 0

# 路由
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    query = Article.query
    
    if category:
        source_ids = [s.id for s in RSSSource.query.filter_by(category=category).all()]
        query = query.filter(Article.source_id.in_(source_ids))
    
    if search:
        query = query.filter(
            db.or_(
                Article.title.contains(search),
                Article.description.contains(search),
                Article.tags.contains(search)
            )
        )
    
    articles = query.order_by(Article.published_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # 获取分类统计
    categories = db.session.query(RSSSource.category, db.func.count(Article.id)).join(Article).group_by(RSSSource.category).all()
    
    return render_template('index.html', articles=articles, categories=categories, current_category=category, search=search)

@app.route('/sources')
def sources():
    sources = RSSSource.query.all()
    return render_template('sources.html', sources=sources)

@app.route('/add_source', methods=['POST'])
def add_source():
    name = request.form.get('name')
    url = request.form.get('url')
    category = request.form.get('category', 'general')
    
    if not name or not url:
        return jsonify({'error': '名称和URL不能为空'}), 400
    
    # 检查URL是否已存在
    existing = RSSSource.query.filter_by(url=url).first()
    if existing:
        return jsonify({'error': 'RSS源已存在'}), 400
    
    source = RSSSource(name=name, url=url, category=category)
    db.session.add(source)
    db.session.commit()
    
    # 立即抓取一次
    RSSFetcher.fetch_articles(source)
    
    return redirect(url_for('sources'))

@app.route('/delete_source/<int:source_id>', methods=['POST'])
def delete_source(source_id):
    source = RSSSource.query.get_or_404(source_id)
    
    # 删除相关文章
    Article.query.filter_by(source_id=source_id).delete()
    
    # 删除RSS源
    db.session.delete(source)
    db.session.commit()
    
    return redirect(url_for('sources'))

@app.route('/toggle_source/<int:source_id>', methods=['POST'])
def toggle_source(source_id):
    source = RSSSource.query.get_or_404(source_id)
    source.active = not source.active
    db.session.commit()
    return redirect(url_for('sources'))

@app.route('/fetch_now', methods=['GET', 'POST'])
def fetch_now():
    try:
        print("=" * 50)
        print("🚀 手动抓取RSS源请求已接收！")
        print("=" * 50)
        logger.info("🚀 开始手动抓取RSS源")
        
        # 设置更严格的超时控制
        import signal
        import threading
        
        def timeout_handler():
            logger.error("RSS抓取超时")
            return None
        
        # 使用线程来执行抓取，避免阻塞主线程
        result = {'new_articles': 0, 'error': None}
        
        def fetch_worker():
            try:
                print("📡 开始执行抓取工作线程")
                # 在线程中创建应用上下文
                with app.app_context():
                    result['new_articles'] = RSSFetcher.fetch_all_sources()
                print(f"✅ 抓取工作线程完成，获得 {result['new_articles']} 篇新文章")
            except Exception as e:
                result['error'] = str(e)
                print(f"❌ 抓取线程出错: {str(e)}")
                logger.error(f"抓取线程出错: {str(e)}")
        
        # 创建并启动抓取线程
        fetch_thread = threading.Thread(target=fetch_worker)
        fetch_thread.daemon = True
        fetch_thread.start()
        print("🔄 抓取线程已启动，等待完成...")
        
        # 等待最多60秒
        fetch_thread.join(timeout=60)
        
        if fetch_thread.is_alive():
            print("⏰ RSS抓取超时（60秒）")
            logger.error("RSS抓取超时（60秒）")
            return jsonify({
                'success': False, 
                'message': '抓取超时，请稍后再试'
            }), 408
        
        if result['error']:
            print(f"❌ RSS抓取出错: {result['error']}")
            logger.error(f"RSS抓取出错: {result['error']}")
            return jsonify({
                'success': False, 
                'message': f'抓取失败: {result["error"]}'
            }), 500
        
        new_articles = result['new_articles']
        print(f"🎉 手动抓取完成，获得 {new_articles} 篇新文章")
        logger.info(f"手动抓取完成，获得 {new_articles} 篇新文章")
        return jsonify({
            'success': True, 
            'message': f'抓取完成，获得 {new_articles} 篇新文章'
        })
        
    except Exception as e:
        print(f"💥 手动抓取RSS源时出错: {str(e)}")
        logger.error(f"手动抓取RSS源时出错: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'抓取失败: {str(e)}'
        }), 500

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    article = Article.query.get_or_404(article_id)
    
    # 标记为已读
    article.read_status = True
    db.session.commit()
    
    return render_template('article.html', article=article)

@app.route('/mark_read/<int:article_id>', methods=['POST'])
def mark_read(article_id):
    article = Article.query.get_or_404(article_id)
    article.read_status = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/mark_all_read', methods=['POST'])
def mark_all_read():
    Article.query.update({'read_status': True})
    db.session.commit()
    return jsonify({'success': True, 'message': '所有文章已标记为已读'})

@app.route('/clear_data', methods=['POST'])
def clear_data():
    """清除所有文章数据并重置RSS源状态"""
    try:
        logger.info("开始清除所有文章数据")
        
        # 删除所有文章
        deleted_count = Article.query.count()
        Article.query.delete()
        
        # 重置所有RSS源的最后更新时间，并确保它们是活跃的
        sources = RSSSource.query.all()
        for source in sources:
            source.last_updated = None
            source.active = True  # 确保RSS源是活跃的
        
        db.session.commit()
        
        logger.info(f"成功清除 {deleted_count} 篇文章，重置 {len(sources)} 个RSS源")
        return jsonify({
            'success': True, 
            'message': f'成功清除 {deleted_count} 篇文章和所有已读记录，重置 {len(sources)} 个RSS源'
        })
        
    except Exception as e:
        logger.error(f"清除数据时出错: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'清除数据失败: {str(e)}'
        }), 500

@app.route('/debug/sources')
def debug_sources():
    """调试路由：查看RSS源状态"""
    sources = RSSSource.query.all()
    source_info = []
    for source in sources:
        source_info.append({
            'id': source.id,
            'name': source.name,
            'url': source.url,
            'active': source.active,
            'last_updated': source.last_updated.isoformat() if source.last_updated else None,
            'category': source.category
        })
    
    return jsonify({
        'total_sources': len(sources),
        'active_sources': len([s for s in sources if s.active]),
        'sources': source_info
    })

@app.route('/test', methods=['GET', 'POST'])
def test_route():
    """测试路由：验证服务器响应"""
    print("=" * 50)
    print("🧪 测试路由被调用！")
    print(f"请求方法: {request.method}")
    print("=" * 50)
    return jsonify({
        'success': True,
        'message': '测试路由正常工作！',
        'method': request.method
    })

# 初始化数据库和默认RSS源
def init_db():
    with app.app_context():
        # 检查是否需要添加summary列
        try:
            db.session.execute(text("SELECT summary FROM article LIMIT 1"))
        except Exception:
            # summary列不存在，添加它
            logger.info("添加summary列到article表")
            db.session.execute(text("ALTER TABLE article ADD COLUMN summary TEXT"))
            db.session.commit()
        
        # 检查是否需要添加content列
        try:
            db.session.execute(text("SELECT content FROM article LIMIT 1"))
        except Exception:
            # content列不存在，添加它
            logger.info("添加content列到article表")
            db.session.execute(text("ALTER TABLE article ADD COLUMN content TEXT"))
            db.session.commit()
        
        db.create_all()
        
        # 添加专注于游戏开发技术的RSS源
        default_sources = [
            # 引擎技术
            {
                'name': 'Unreal Engine Blog',
                'url': 'https://www.unrealengine.com/en-US/feed',
                'category': 'unreal_engine'
            },
            {
                'name': 'Unity Blog',
                'url': 'https://blog.unity.com/feed',
                'category': 'unity'
            },
            {
                'name': 'Godot Engine News',
                'url': 'https://godotengine.org/rss.xml',
                'category': 'game_engines'
            },
            
            # 游戏开发综合
            {
                'name': 'Game Developer (Gamasutra)',
                'url': 'https://www.gamedeveloper.com/rss.xml',
                'category': 'game_development'
            },
            {
                'name': 'Indie Game Developer',
                'url': 'https://www.indiegamedev.net/feed/',
                'category': 'indie_development'
            },
            
            # 图形编程和渲染技术
            {
                'name': 'Real-Time Rendering',
                'url': 'http://www.realtimerendering.com/blog/feed/',
                'category': 'graphics_programming'
            },
            {
                'name': 'Graphics Programming Weekly',
                'url': 'https://www.jendrikillner.com/tags/weekly/index.xml',
                'category': 'graphics_programming'
            },
            {
                'name': 'Advances in Real-Time Rendering',
                'url': 'http://advances.realtimerendering.com/feed/',
                'category': 'graphics_programming'
            },
            
            # 物理引擎和仿真
            {
                'name': 'Bullet Physics',
                'url': 'https://pybullet.org/wordpress/feed/',
                'category': 'physics_simulation'
            },
            {
                'name': 'NVIDIA PhysX',
                'url': 'https://developer.nvidia.com/rss.xml',
                'category': 'physics_simulation'
            },
            
            # 动画技术
            {
                'name': 'Animation Mentor Blog',
                'url': 'https://www.animationmentor.com/blog/feed/',
                'category': 'animation'
            },
            {
                'name': 'Blender News',
                'url': 'https://www.blender.org/news/rss/',
                'category': 'animation'
            },
            
            # 游戏引擎架构
            {
                'name': 'Game Engine Architecture',
                'url': 'https://www.gameenginebook.com/feed/',
                'category': 'engine_architecture'
            },
            {
                'name': 'Molecular Musings',
                'url': 'https://blog.molecular-matters.com/feed/',
                'category': 'engine_architecture'
            },
            
            # AI和机器学习在游戏中的应用
            {
                'name': 'Unity ML-Agents',
                'url': 'https://blogs.unity3d.com/category/machine-learning/feed/',
                'category': 'ai_ml'
            },
            {
                'name': 'Game AI Pro',
                'url': 'http://www.gameaipro.com/feed/',
                'category': 'ai_ml'
            },
            
            # 性能优化
            {
                'name': 'Intel Game Dev',
                'url': 'https://www.intel.com/content/www/us/en/developer/topic-technology/gamedev/rss.xml',
                'category': 'performance'
            },
            {
                'name': 'AMD GPUOpen',
                'url': 'https://gpuopen.com/feed/',
                'category': 'performance'
            },
            
            # VR/AR技术
            {
                'name': 'Oculus Developer Blog',
                'url': 'https://developer.oculus.com/blog/rss/',
                'category': 'vr_ar'
            },
            {
                'name': 'Unity XR',
                'url': 'https://blogs.unity3d.com/category/xr/feed/',
                'category': 'vr_ar'
            },
            
            # 技术博客和个人分享
            {
                'name': 'Inigo Quilez',
                'url': 'https://iquilezles.org/articles/rss.xml',
                'category': 'technical_blogs'
            },
            {
                'name': 'Fabien Sanglard',
                'url': 'https://fabiensanglard.net/rss.xml',
                'category': 'technical_blogs'
            },
            {
                'name': 'Aras Pranckevičius',
                'url': 'https://aras-p.info/blog/feed/',
                'category': 'technical_blogs'
            }
        ]
        
        for source_data in default_sources:
            existing = RSSSource.query.filter_by(url=source_data['url']).first()
            if not existing:
                source = RSSSource(**source_data)
                db.session.add(source)
        
        db.session.commit()

# 定时任务
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=RSSFetcher.fetch_all_sources,
        trigger="interval",
        hours=2,  # 每2小时抓取一次
        id='fetch_rss'
    )
    scheduler.start()

if __name__ == '__main__':
    init_db()
    start_scheduler()
    app.run(debug=True, host='0.0.0.0', port=5000)