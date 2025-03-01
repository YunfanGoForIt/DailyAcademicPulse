import sqlite3
import os
from config import init_database

def check_and_fix_database():
    """检查数据库结构并修复缺失的表"""
    print("🔍 检查数据库结构...")
    
    # 检查数据库文件是否存在
    if not os.path.exists('journals.db'):
        print("⚠️ 数据库文件不存在，正在创建新数据库...")
        init_database()
        print("✅ 数据库创建成功！")
        return
    
    # 连接到现有数据库
    conn = sqlite3.connect('journals.db')
    cursor = conn.cursor()
    
    # 检查article_fields表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='article_fields'")
    if not cursor.fetchone():
        print("⚠️ 发现缺失的表：article_fields，正在添加...")
        
        # 创建article_fields表
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
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_fields_article ON article_fields (article_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_fields_field ON article_fields (field)')
        
        conn.commit()
        print("✅ article_fields表创建成功！")
    else:
        print("✅ 数据库结构完整，article_fields表已存在。")
    
    conn.close()
    print("✅ 数据库检查完成！")

if __name__ == "__main__":
    check_and_fix_database() 