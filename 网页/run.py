import os
import sys
import sqlite3

# 添加父目录到路径，以便导入config模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import init_database

def check_database():
    """检查数据库是否存在，如果不存在则初始化"""
    db_path = '../journals.db'
    if not os.path.exists(db_path):
        print("数据库文件不存在，正在初始化...")
        init_database()
    
    # 检查subscriptions表是否包含password字段
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(subscriptions)")
    columns = {row[1] for row in cursor.fetchall()}
    
    # 如果subscriptions表不包含password字段，添加它
    if 'password' not in columns:
        print("更新subscriptions表，添加password字段...")
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN password TEXT")
        conn.commit()
    
    # 检查favorites表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'")
    if not cursor.fetchone():
        print("创建favorites表...")
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_article ON favorites (article_id)')
        conn.commit()
    
    conn.close()
    print("数据库检查完成")

def run_server():
    """运行Flask服务器"""
    from server import app
    print("启动Web服务器...")
    app.run(debug=True, port=5000)

if __name__ == "__main__":
    print("=== 学术期刊推送系统启动 ===")
    check_database()
    run_server() 