# 新建配置文件存放公共配置和数据库初始化
import sqlite3
import os
import mysql.connector
from mysql.connector import Error
from db_config import MYSQL_CONFIG

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

# 期刊RSS配置
JOURNALS_CONFIG = {
    'Science': {
        'rss_url': 'https://science.sciencemag.org/rss/current.xml',
        'domain_patterns': ['science.org'],
        'journal_name': 'Science'
    },
    'Nature': {
        'rss_url': 'https://www.nature.com/nature.rss',
        'domain_patterns': ['nature.com'],
        'journal_name': 'Nature',
        'exclude_patterns': ['biomedeng', 'natbiomedeng']  # 排除特定子刊物
    },
    'Nature Biomedical Engineering': {
        'rss_url': 'https://www.nature.com/natbiomedeng.rss',
        'domain_patterns': ['nature.com', 'biomedeng', 'natbiomedeng'],
        'journal_name': 'Nature Biomedical Engineering'
    },
    'Cell': {
        'rss_url': 'https://www.cell.com/cell/current.rss',
        'domain_patterns': ['cell.com'],
        'journal_name': 'Cell'
    },
    'Journal Name': {
        'rss_url': 'http://www.thelancet.com/rssfeed/lancet_online.xml',
        'domain_patterns': ['thelancet.com'],  
        'journal_name': 'The Lancet',  
    },
    'Nature Communication': {
        'rss_url': 'https://www.nature.com/ncomms.rss',
        'domain_patterns': ['nature.com'],
        'journal_name': 'Nature Communication'
    },
}

def init_database():
    """初始化MySQL数据库和表结构"""
    try:
        # 连接到MySQL服务器
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        # 创建数据库
        cursor.execute("CREATE DATABASE IF NOT EXISTS academic_pulse CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute("USE academic_pulse;")  # 切换到新创建的数据库

        # 创建文章表 - 添加了 original_authors 和 translated_authors 字段
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            journal VARCHAR(255),
            original_title TEXT,
            translated_title TEXT,
            original_authors TEXT,      -- 添加这个字段
            translated_authors TEXT,     -- 添加这个字段
            abstract TEXT,
            summary TEXT,
            link TEXT,
            publish_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ''')
        print("✅ articles 表创建成功")

        # 创建文章领域表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS article_fields (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT,
            field VARCHAR(255),
            confidence FLOAT,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            INDEX idx_article_field (article_id, field)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ''')
        print("✅ article_fields 表创建成功")

        # 创建逻辑关系图表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS article_logic_graphs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT UNIQUE,
            mermaid_code TEXT,
            reasoning TEXT,
            verification TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            INDEX idx_logic_graphs_article (article_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ''')
        print("✅ article_logic_graphs 表创建成功")

        # 创建订阅表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255) UNIQUE,
            email VARCHAR(255),
            password VARCHAR(255),
            fields TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ''')
        print("✅ subscriptions 表创建成功")

        # 创建收藏表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            article_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES subscriptions(user_id),
            FOREIGN KEY (article_id) REFERENCES articles(id),
            UNIQUE KEY unique_favorite (user_id, article_id),
            INDEX idx_favorites_user (user_id),
            INDEX idx_favorites_article (article_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ''')
        print("✅ favorites 表创建成功")

        # 提交更改
        conn.commit()
        print("✅ 数据库和表结构初始化成功")

    except Error as e:
        print(f"❌ 数据库初始化失败: {e}")
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        return conn
    except Error as e:
        print(f"❌ 数据库连接失败: {e}")
        raise

if __name__ == "__main__":
    init_database() 