# 新建配置文件存放公共配置和数据库初始化
import sqlite3
import os

# 领域关键词配置
FIELD_KEYWORDS = {
    "无": [],
    "数学与统计学": ["数学", "统计学", "概率论", "数论", "代数", "几何", "拓扑", "分析", "应用数学", "计算数学", "统计分析", "数据科学", "随机过程"],
    "物理学与力学": ["物理学", "力学", "量子物理", "相对论", "粒子物理", "核物理", "固体物理", "流体力学", "热力学", "光学", "声学", "电磁学", "凝聚态物理"],
    "化学与材料科学": ["化学", "材料科学", "有机化学", "无机化学", "物理化学", "分析化学", "高分子材料", "纳米材料", "复合材料", "功能材料", "生物材料", "催化剂"],
    "地球科学": ["地理学", "地质学", "大气科学", "海洋学", "地球物理", "水文学", "气象学", "矿物学", "岩石学", "地震学", "地貌学", "古生物学", "环境地理"],
    "天文学与空间科学": ["天文学", "空间科学", "宇宙学", "天体物理", "行星科学", "恒星演化", "星系形成", "黑洞", "暗物质", "暗能量", "引力波", "航天技术"],
    "生命科学与生物医学工程": ["生物学", "生命科学", "分子生物学", "细胞生物学", "遗传学", "生物化学", "生物医学工程", "生物信息学", "生态学", "微生物学", "神经科学", "免疫学"],
    "能源与动力工程": ["能源工程", "动力工程", "电气工程", "热能工程", "新能源", "可再生能源", "核能", "电力系统", "电机", "发电", "输配电", "储能技术", "能源转换"],
    "电子与信息工程": ["电子工程", "信息工程", "通信工程", "控制工程", "网络空间安全", "信号处理", "集成电路", "微电子", "电磁场", "天线", "雷达", "无线通信", "光通信"],
    "计算机科学与人工智能": ["计算机科学", "人工智能", "机器学习", "深度学习", "自然语言处理", "计算机视觉", "数据挖掘", "软件工程", "算法", "操作系统", "分布式系统", "云计算", "大数据"],
    "环境科学与工程": ["环境科学", "环境工程", "污染控制", "环境监测", "生态修复", "水处理", "大气治理", "固废处理", "环境规划", "环境影响评价", "可持续发展", "循环经济"]
}

def init_database():
    """初始化数据库和表结构"""
    conn = sqlite3.connect('journals.db')
    cursor = conn.cursor()
    
    # 创建文章表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journal TEXT,
        original_title TEXT,
        translated_title TEXT,
        original_authors TEXT,
        translated_authors TEXT,
        abstract TEXT,
        summary TEXT,
        link TEXT UNIQUE,
        publish_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建订阅表，确保包含密码字段
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_id TEXT PRIMARY KEY,
        email TEXT,
        phone TEXT,
        field TEXT,
        password TEXT,  -- 添加密码字段
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建文章-领域关系表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS article_fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        field TEXT,
        confidence REAL,
        FOREIGN KEY (article_id) REFERENCES articles(id),
        UNIQUE(article_id, field)
    )
    ''')
    
    # 创建用户收藏表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        article_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES subscriptions(user_id),
        FOREIGN KEY (article_id) REFERENCES articles(id),
        UNIQUE(user_id, article_id)
    )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_date ON articles (publish_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_journal ON articles (journal)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions (email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_phone ON subscriptions (phone)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_fields_article ON article_fields (article_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_fields_field ON article_fields (field)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites (user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_article ON favorites (article_id)')
    
    conn.commit()
    conn.close()
    
    print("✅ 数据库初始化完成")
    
if __name__ == "__main__":
    init_database() 