from flask import Flask, request, jsonify, session, send_from_directory
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta
import json
import sys
import uuid

# 添加父目录到路径，以便导入config模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import init_database

# 导入逻辑关系图模块
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from generate_logic_graph import (
        process_article_logic_graph, 
        get_article_logic_graph, 
        ensure_logic_graph_table_exists
    )
    LOGIC_GRAPH_ENABLED = True
except ImportError:
    print("⚠️ 逻辑关系图模块导入失败，相关API将不可用")
    LOGIC_GRAPH_ENABLED = False

app = Flask(__name__, static_folder='public')
app.secret_key = secrets.token_hex(16)  # 生成随机密钥用于session

# 数据库路径
DB_PATH = '../journals.db'

# 确保数据库存在
def ensure_db_exists():
    if not os.path.exists(DB_PATH):
        # 如果数据库不存在，使用config.py中的init_database函数初始化
        init_database()
    
    # 检查subscriptions表是否包含所需字段
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查subscriptions表结构
    cursor.execute("PRAGMA table_info(subscriptions)")
    columns = {row[1] for row in cursor.fetchall()}
    
    # 确保subscriptions表有所需字段
    required_fields = {'user_id', 'email', 'phone', 'field'}
    if not required_fields.issubset(columns):
        print("更新subscriptions表结构...")
        # 创建临时表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions_new (
            user_id TEXT PRIMARY KEY,
            email TEXT,
            phone TEXT,
            field TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 复制数据
        if 'subscriptions' in {table[0] for table in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
            cursor.execute("INSERT INTO subscriptions_new SELECT * FROM subscriptions")
        
        # 删除旧表并重命名
        cursor.execute("DROP TABLE IF EXISTS subscriptions")
        cursor.execute("ALTER TABLE subscriptions_new RENAME TO subscriptions")
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions (email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_phone ON subscriptions (phone)')
    
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

# 密码哈希函数
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 静态文件路由 - 修改根路由指向login.html
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

# 用户注册/登录API
@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    password = data.get('password')
    selected_fields = data.get('selectedFields', [])
    
    if not (email or phone):
        return jsonify({'error': '请填写邮箱或手机号'}), 400
    
    if not password:
        return jsonify({'error': '请填写密码'}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查用户是否存在
        query = "SELECT user_id, email, phone, field FROM subscriptions WHERE "
        params = []
        
        if email:
            query += "email = ?"
            params.append(email)
        
        if phone:
            if email:
                query += " OR phone = ?"
            else:
                query += "phone = ?"
            params.append(phone)
        
        cursor.execute(query, params)
        user = cursor.fetchone()
        
        hashed_password = hash_password(password)
        
        if user:
            # 用户存在，尝试登录
            user_id = user[0]
            
            # 检查密码
            cursor.execute("SELECT 1 FROM subscriptions WHERE user_id = ? AND password = ?", 
                          (user_id, hashed_password))
            if not cursor.fetchone():
                return jsonify({'error': '密码错误'}), 401
            
            # 获取用户领域
            fields = user[3].split(',') if user[3] else []
            
            # 设置session
            session['user_id'] = user_id
            session['email'] = user[1]
            session['phone'] = user[2]
            session['fields'] = fields
            
            return jsonify({
                'success': True,
                'message': '登录成功',
                'user': {
                    'id': user_id,
                    'email': user[1],
                    'phone': user[2],
                    'fields': fields
                }
            })
        else:
            # 用户不存在，创建新用户
            user_id = str(uuid.uuid4())
            fields_str = ','.join(selected_fields)
            
            cursor.execute(
                'INSERT INTO subscriptions (user_id, email, phone, field, password) VALUES (?, ?, ?, ?, ?)',
                (user_id, email, phone, fields_str, hashed_password)
            )
            
            conn.commit()
            
            # 设置session
            session['user_id'] = user_id
            session['email'] = email
            session['phone'] = phone
            session['fields'] = selected_fields
            
            return jsonify({
                'success': True,
                'message': '注册成功',
                'user': {
                    'id': user_id,
                    'email': email,
                    'phone': phone,
                    'fields': selected_fields
                }
            }), 201
    
    except Exception as e:
        return jsonify({'error': f'操作失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 退出登录API
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# 获取文章API
@app.route('/api/papers', methods=['GET'])
def get_papers():
    # 检查用户是否登录
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    # 获取查询参数
    field_filter = request.args.get('field', 'all')
    days = int(request.args.get('days', 30))  # 默认获取30天内的文章
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        cursor = conn.cursor()
        
        # 构建查询
        query = '''
        SELECT a.id, a.journal, a.original_title, a.translated_title, 
               a.original_authors, a.translated_authors, a.abstract, 
               a.summary, a.link, a.publish_date, GROUP_CONCAT(af.field, ', ') as fields,
               (SELECT 1 FROM article_logic_graphs alg WHERE alg.article_id = a.id) as has_logic_graph
        FROM articles a
        LEFT JOIN article_fields af ON a.id = af.article_id
        '''
        
        params = []
        where_clauses = []
        
        # 添加日期过滤
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        where_clauses.append("a.publish_date >= ?")
        params.append(cutoff_date)
        
        # 添加领域过滤
        if field_filter != 'all':
            where_clauses.append("af.field = ?")
            params.append(field_filter)
        
        # 组合WHERE子句
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        # 分组和排序
        query += " GROUP BY a.id ORDER BY a.publish_date DESC LIMIT 50"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # 获取用户收藏的文章ID
        cursor.execute(
            'SELECT article_id FROM favorites WHERE user_id = ?',
            (session['user_id'],)
        )
        favorited_ids = {row[0] for row in cursor.fetchall()}
        
        # 转换为JSON格式
        papers = []
        for row in rows:
            paper = {
                'id': row['id'],
                'journal': row['journal'],
                'title': row['translated_title'] or row['original_title'],
                'originalTitle': row['original_title'],
                'authors': (row['translated_authors'] or row['original_authors']).split(', '),
                'abstract': row['abstract'] or '',
                'summary': row['summary'] or '',
                'link': row['link'],
                'publishDate': row['publish_date'],
                'fields': row['fields'].split(', ') if row['fields'] else [],
                'favorite': row['id'] in favorited_ids,
                'hasLogicGraph': bool(row['has_logic_graph']) if 'has_logic_graph' in row.keys() else False
            }
            papers.append(paper)
        
        return jsonify(papers)
    
    except Exception as e:
        return jsonify({'error': f'获取文章失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 获取所有领域API
@app.route('/api/fields', methods=['GET'])
def get_fields():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 从article_fields表获取所有唯一的领域
        cursor.execute('SELECT DISTINCT field FROM article_fields')
        fields = [row[0] for row in cursor.fetchall()]
        
        return jsonify(fields)
    
    except Exception as e:
        return jsonify({'error': f'获取领域失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 获取用户信息API
@app.route('/api/user', methods=['GET'])
def get_user():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    return jsonify({
        'id': session['user_id'],
        'email': session.get('email', ''),
        'phone': session.get('phone', ''),
        'fields': session.get('fields', [])
    })

# 添加会话检查路由，用于重定向已登录用户
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({'authenticated': True})
    else:
        return jsonify({'authenticated': False}), 401

# 添加收藏API
@app.route('/api/favorites', methods=['POST'])
def add_favorite():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    data = request.json
    article_id = data.get('article_id')
    
    if not article_id:
        return jsonify({'error': '缺少文章ID'}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查文章是否存在
        cursor.execute('SELECT 1 FROM articles WHERE id = ?', (article_id,))
        if not cursor.fetchone():
            return jsonify({'error': '文章不存在'}), 404
        
        # 添加收藏
        try:
            cursor.execute(
                'INSERT INTO favorites (user_id, article_id) VALUES (?, ?)',
                (session['user_id'], article_id)
            )
            conn.commit()
            return jsonify({'success': True, 'message': '收藏成功'})
        except sqlite3.IntegrityError:
            # 已经收藏过了
            return jsonify({'success': True, 'message': '已经收藏过了'})
    
    except Exception as e:
        return jsonify({'error': f'收藏失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 取消收藏API
@app.route('/api/favorites', methods=['DELETE'])
def remove_favorite():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    article_id = request.args.get('article_id')
    
    if not article_id:
        return jsonify({'error': '缺少文章ID'}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 删除收藏
        cursor.execute(
            'DELETE FROM favorites WHERE user_id = ? AND article_id = ?',
            (session['user_id'], article_id)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': '取消收藏成功'})
        else:
            return jsonify({'error': '未找到收藏记录'}), 404
    
    except Exception as e:
        return jsonify({'error': f'取消收藏失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 获取收藏列表API
@app.route('/api/favorites', methods=['GET'])
def get_favorites():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取用户收藏的文章
        query = '''
        SELECT a.id, a.journal, a.original_title, a.translated_title, 
               a.original_authors, a.translated_authors, a.abstract, 
               a.summary, a.link, a.publish_date, GROUP_CONCAT(af.field, ', ') as fields
        FROM favorites f
        JOIN articles a ON f.article_id = a.id
        LEFT JOIN article_fields af ON a.id = af.article_id
        WHERE f.user_id = ?
        GROUP BY a.id
        ORDER BY f.created_at DESC
        '''
        
        cursor.execute(query, (session['user_id'],))
        rows = cursor.fetchall()
        
        # 转换为JSON格式
        papers = []
        for row in rows:
            paper = {
                'id': row['id'],
                'journal': row['journal'],
                'title': row['translated_title'] or row['original_title'],
                'originalTitle': row['original_title'],
                'authors': (row['translated_authors'] or row['original_authors']).split(', '),
                'abstract': row['abstract'] or '',
                'summary': row['summary'] or '',
                'link': row['link'],
                'publishDate': row['publish_date'],
                'fields': row['fields'].split(', ') if row['fields'] else [],
                'favorite': True
            }
            papers.append(paper)
        
        return jsonify(papers)
    
    except Exception as e:
        return jsonify({'error': f'获取收藏失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 检查文章是否已收藏API
@app.route('/api/favorites/check', methods=['GET'])
def check_favorites():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    article_ids = request.args.get('ids')
    if not article_ids:
        return jsonify({'error': '缺少文章ID'}), 400
    
    try:
        article_ids = article_ids.split(',')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 查询哪些文章已被收藏
        placeholders = ','.join(['?' for _ in article_ids])
        query = f'''
        SELECT article_id FROM favorites 
        WHERE user_id = ? AND article_id IN ({placeholders})
        '''
        
        cursor.execute(query, [session['user_id']] + article_ids)
        favorited_ids = [str(row[0]) for row in cursor.fetchall()]
        
        return jsonify({'favorited': favorited_ids})
    
    except Exception as e:
        return jsonify({'error': f'检查收藏失败: {str(e)}'}), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 获取文章逻辑关系图API
@app.route('/api/paper/logic-graph/<int:article_id>', methods=['GET'])
def get_logic_graph(article_id):
    # 检查用户是否登录
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    if not LOGIC_GRAPH_ENABLED:
        return jsonify({'error': '逻辑关系图功能未启用'}), 503
    
    try:
        # 检查文章是否存在
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': '文章不存在'}), 404
        
        # 查询逻辑关系图
        cursor.execute("""
            SELECT alg.mermaid_code, alg.verification
            FROM article_logic_graphs alg
            WHERE alg.article_id = ?
        """, (article_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            mermaid_code, verification = result
            return jsonify({
                'article_id': article_id,
                'mermaid_code': mermaid_code,
                'verification': verification
            })
        else:
            return jsonify({'error': '该文章暂无逻辑关系图'}), 404
            
    except Exception as e:
        return jsonify({'error': f'获取逻辑关系图失败: {str(e)}'}), 500

# 按需生成文章逻辑关系图API
@app.route('/api/paper/generate-logic-graph/<int:article_id>', methods=['POST'])
def generate_logic_graph(article_id):
    # 检查用户是否登录
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    
    if not LOGIC_GRAPH_ENABLED:
        return jsonify({'error': '逻辑关系图功能未启用'}), 503
    
    try:
        # 检查文章是否存在
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': '文章不存在'}), 404
        conn.close()
        
        # 生成逻辑关系图（这会自动存到数据库中）
        result = process_article_logic_graph(article_id)
        
        if result:
            return jsonify({
                'article_id': article_id,
                'mermaid_code': result['mermaid_code'],
                'verification': result['verification'],
                'success': True
            })
        else:
            return jsonify({'error': '生成逻辑关系图失败'}), 500
            
    except Exception as e:
        return jsonify({'error': f'生成逻辑关系图失败: {str(e)}'}), 500

if __name__ == '__main__':
    ensure_db_exists()
    app.run(debug=True, port=5000) 