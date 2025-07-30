# Unreal Engine & 游戏开发 RSS聚合器

一个专门用于搜集和浏览Unreal Engine和游戏开发相关技术文章的RSS聚合工具。

## 功能特性

- 🔄 **自动RSS抓取**: 定时抓取RSS源的最新文章
- 📱 **现代化界面**: 响应式设计，支持移动端浏览
- 🔍 **智能搜索**: 支持标题、内容、标签的全文搜索
- 🏷️ **分类管理**: 按照Unreal Engine、Unity、游戏开发等分类组织
- 📖 **阅读状态**: 标记已读/未读文章
- ⚙️ **RSS源管理**: 添加、删除、启用/禁用RSS源
- 🎯 **专业聚焦**: 预设游戏开发相关的优质RSS源

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python app.py
```

### 3. 访问应用

打开浏览器访问: http://localhost:5000

## 使用说明

### 添加RSS源

1. 点击导航栏的"RSS源管理"
2. 点击"添加RSS源"按钮
3. 填写RSS源信息：
   - **名称**: RSS源的显示名称
   - **RSS URL**: RSS feed的完整URL
   - **分类**: 选择合适的分类

### 浏览文章

- **首页**: 显示所有最新文章
- **分类筛选**: 点击左侧分类进行筛选
- **搜索**: 使用搜索框查找特定文章
- **阅读**: 点击文章标题或"阅读原文"按钮

### 管理功能

- **立即抓取**: 点击导航栏的"立即抓取"按钮手动更新
- **标记已读**: 点击文章的"标记已读"按钮
- **RSS源管理**: 启用/禁用或删除RSS源

## 预设RSS源

应用预设了以下优质RSS源：

- **Unreal Engine Blog**: 官方博客
- **Gamasutra/Game Developer**: 游戏开发资讯
- **Unity Blog**: Unity官方博客

## 技术栈

- **后端**: Python Flask
- **数据库**: SQLite
- **前端**: Bootstrap 5 + Font Awesome
- **RSS解析**: feedparser
- **定时任务**: APScheduler

## 目录结构

```
my_unrealengine_rss/
├── app.py              # 主应用文件
├── requirements.txt    # Python依赖
├── templates/          # HTML模板
│   ├── base.html      # 基础模板
│   ├── index.html     # 首页
│   ├── sources.html   # RSS源管理
│   └── article.html   # 文章详情
└── rss_feeds.db       # SQLite数据库（运行后生成）
```

## 自定义配置

### 修改抓取频率

在 `app.py` 中找到以下代码并修改：

```python
scheduler.add_job(
    func=RSSFetcher.fetch_all_sources,
    trigger="interval",
    hours=2,  # 修改这里的数值（小时）
    id='fetch_rss'
)
```

### 添加新的分类

在 `templates/sources.html` 的分类选择框中添加新选项：

```html
<option value="your_category">你的分类</option>
```

## 故障排除

### 常见问题

1. **RSS源无法抓取**
   - 检查RSS URL是否正确
   - 确认网络连接正常
   - 查看控制台日志信息

2. **文章显示不完整**
   - 某些RSS源可能只提供摘要
   - 点击"阅读原文"查看完整内容

3. **数据库错误**
   - 删除 `rss_feeds.db` 文件重新初始化
   - 检查文件权限

## 贡献

欢迎提交Issue和Pull Request来改进这个工具！

## 许可证

MIT License