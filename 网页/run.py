import os
import sys

# 添加父目录到路径，以便导入config模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 添加上一级目录到路径

from config import init_database, get_db_connection

def check_database():
    """检查数据库是否存在，如果不存在则初始化"""
    try:
        # 尝试连接数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查subscriptions表是否包含password字段
        cursor.execute("SHOW COLUMNS FROM subscriptions")
        columns = {row[0] for row in cursor.fetchall()}

        # 如果subscriptions表不包含password字段，添加它
        if 'password' not in columns:
            print("更新subscriptions表，添加password字段...")
            cursor.execute("ALTER TABLE subscriptions ADD COLUMN password VARCHAR(255)")
            conn.commit()

        # 检查favorites表是否存在
        cursor.execute("SHOW TABLES LIKE 'favorites'")
        if not cursor.fetchone():
            print("创建favorites表...")
            cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255),
                article_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES subscriptions(user_id),
                FOREIGN KEY (article_id) REFERENCES articles(id),
                UNIQUE KEY unique_favorite (user_id, article_id),
                INDEX idx_favorites_user (user_id),
                INDEX idx_favorites_article (article_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
            conn.commit()

        cursor.close()
        conn.close()
        print("数据库检查完成")

    except Exception as e:
        print(f"数据库检查失败: {e}")
        print("正在初始化数据库...")
        init_database()

def run_server():
    """运行Flask服务器"""
    from server import app
    print("启动Web服务器...")
    app.run(debug=True, port=5000)

if __name__ == "__main__":
    print("=== 学术期刊推送系统启动 ===")
    check_database()
    run_server()
