import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import *

import os
import pandas as pd
import sqlite3
import re
import time
from datetime import datetime

from openai import OpenAI
from config import FIELD_KEYWORDS, init_database

# 配置信息
CLIENT = OpenAI(
    api_key="",
    base_url="https://api.moonshot.cn/v1",
)

def is_related_to_field(article_data: dict, target_field: str) -> bool:
    """判断文章是否属于特定领域（从数据库查询）"""
    # 获取文章ID
    article_id = get_article_id(article_data.get('link', ''))
    if not article_id:
        # 如果找不到文章ID，使用旧方法进行判断
        return legacy_is_related_to_field(article_data, target_field)
    
    # 从数据库查询
    conn = sqlite3.connect('journals.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT confidence FROM article_fields 
        WHERE article_id = ? AND field = ?
    """, (article_id, target_field))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        confidence = result[0]
        print(f"🔍 文章与领域 {target_field} 的相关度: {confidence:.2f}")
        return confidence > 0.5
    else:
        print(f"⚠️ 未找到文章与领域 {target_field} 的关联记录")
        return False

def get_article_id(link: str) -> int:
    """根据链接获取文章ID"""
    if not link:
        return None
        
    conn = sqlite3.connect('journals.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM articles WHERE link = ?", (link,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def legacy_is_related_to_field(article_data: dict, target_field: str) -> bool:
    """旧版领域判断方法（备用）"""
    title = article_data.get('original_title', '无标题')[:50]
    print(f"🔍 正在判断《{title}...》是否属于 {target_field} 领域...", end='')
    
    system_prompt = f"""你是一个专业的科研助手，需要判断论文是否属于特定研究领域。
    
目标领域：{target_field}
论文信息：
标题：{article_data.get('original_title', '')}
摘要：{article_data.get('abstract', '')[:2000]}  # 限制长度避免超token

请严格按以下规则判断：
1. 如果论文明显属于{target_field}领域，返回Y
2. 如果不确定或不属于，返回N
3. 只需返回单个字母，不要任何解释"""

    try:
        completion = CLIENT.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请判断这篇论文是否属于目标领域"}
            ],
            temperature=0.1,
            max_tokens=1
        )
        result = completion.choices[0].message.content.strip().upper() == 'Y'
        print("✅ 属于" if result else "❌ 不属于")
        return result
        
    except Exception as e:
        print(f"⚠️ 判断失败: {str(e)}")
        return False  # 失败时默认保留

def send_email(receiver_email: str, subject: str, field_df: pd.DataFrame):
    """发送邮件功能"""
    # 添加邮箱验证
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', receiver_email):
        print(f"❌ 无效的邮箱地址: {receiver_email}")
        return False

    try:
        print(f"\n📧 开始处理用户: {receiver_email}")
        start_time = time.time()
        
        # ========== 邮件配置 ==========
        sender_email = "1640618938@qq.com"
        password = "nwgadvjscqnbcjgd"
        smtp_server = "smtp.qq.com"
        port = 465

        # 初始化邮件对象
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        today = datetime.now().strftime("%Y-%m-%d")
        msg['Subject'] = subject

        # ========== HTML内容生成 ==========
        # 期刊颜色配置
        journal_colors = {
            "Science": "#2ecc71",
            "Nature": "#e74c3c",
            "Nature Biomedical Engineering": "#3498db",
            "Cell": "#9b59b6"
        }

        # 生成HTML内容（完整保留原有模板）
        html_template = """<html>
        <head>
        <style>
        body {{ 
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 20px auto;
            padding: 0 20px;
        }}
        .header {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .article {{
            margin-bottom: 40px;
            padding: 25px;
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        .article h3 {{
            color: #2c3e50;
            font-size: 1.5em;
            margin: 0 0 12px;
            font-weight: 600;
            border-left: 4px solid #3498db;
            padding-left: 12px;
        }}
        .authors {{
            color: #7f8c8d;
            font-size: 1em;
            margin: 0 0 15px;
            font-style: italic;
        }}
        .abstract {{
            color: #444;
            line-height: 1.8;
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
        }}
        .abstract strong {{
            color: #2c3e50;
            display: block;
            margin-bottom: 10px;
        }}
        .footer {{
            color: #7f8c8d;
            margin-top: 40px;
            padding-top: 25px;
            border-top: 1px solid #eee;
            font-size: 0.9em;
        }}
        .journal-header {{
            color: #2c3e50;
            border-left: 6px solid {color};
            padding: 10px 20px;
            margin: 30px 0 15px;
            background: #f8f9fa;
        }}
        </style>
        </head>
        <body>
            <div class="header">
                <h1>多期刊生物医学论文摘要</h1>
                <p>生成日期：{date}</p>
            </div>
            {journal_sections}
            <div class="footer">
                <p>此邮件为自动发送，请勿直接回复</p>
                <p>数据来源：Nature/Science/Cell RSS | 共包含 {count} 篇论文</p>
            </div>
        </body>
        </html>"""

        # 按期刊分组处理
        journal_sections = []
        for journal_name, journal_df in field_df.groupby('journal'):
            section_html = f"""
            <div class="journal-header" style="border-color: {journal_colors.get(journal_name, '#3498db')}">
                <h2>{journal_name}</h2>
                <p>收录论文：{len(journal_df)}篇</p>
            </div>
            """

            for _, row in journal_df.iterrows():
                # 处理作者显示
                authors = row['translated_authors'] or row['original_authors']
                author_list = str(authors).split(", ")
                if len(author_list) > 3:
                    display_authors = ", ".join(author_list[:3]) + " 等"
                else:
                    display_authors = authors

                section_html += f"""
                <div class="article">
                    <h3>{row['translated_title'] or row['original_title']}</h3>
                    <div class="authors">{display_authors}</div>
                    <div class="abstract">
                        <strong>摘要：</strong>
                        {row['abstract'].replace('\n', '<br>')}
                    </div>
                </div>
                """

            journal_sections.append(section_html)

        # 填充模板
        html_content = html_template.format(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            journal_sections="\n".join(journal_sections) if journal_sections else "<p>今日无新文章</p>",
            count=len(field_df),
            color="#3498db"
        )
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # ========== 发送邮件 ==========
        with smtplib.SMTP_SSL(smtp_server, port) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        
        elapsed = time.time() - start_time
        print(f"✅ 发送成功（耗时{elapsed:.1f}s）")
        return True
        
    except Exception as e:
        print(f"❌ 发送失败: {str(e)}")
        return False

def get_user_specific_data(user_id: str, user_field: str, global_df: pd.DataFrame) -> pd.DataFrame:
    """获取用户定制数据（基于global_df过滤用户感兴趣的领域文章）"""
    print(f"\n🔍 处理用户 {user_id} 的领域: {user_field}")
    
    if not user_field or user_field == "无":
        print("⚠️ 未设置领域，发送全部文章")
        return global_df.copy()
    
    # 将用户领域拆分为列表
    user_fields = [field.strip() for field in user_field.split(',')]
    print(f"📊 用户订阅了 {len(user_fields)} 个领域: {', '.join(user_fields)}")
    
    # 从数据库获取各个领域的文章ID
    try:
        conn = sqlite3.connect('journals.db')
        relevant_article_ids = set()  # 使用集合存储相关文章ID，避免重复
        
        for field in user_fields:
            cursor = conn.cursor()
            
            # 获取文章ID列表
            article_ids_query = """
            SELECT article_id FROM article_fields 
            WHERE field = ? AND confidence > 0.5
            """
            cursor.execute(article_ids_query, (field,))
            field_article_ids = [row[0] for row in cursor.fetchall()]
            
            if not field_article_ids:
                print(f"⚠️ 未找到与领域 '{field}' 相关的文章")
                continue
                
            print(f"✅ 找到 {len(field_article_ids)} 篇与领域 '{field}' 相关的文章")
            relevant_article_ids.update(field_article_ids)
        
        conn.close()
        
        # 如果没有找到任何相关文章ID
        if not relevant_article_ids:
            print("❌ 未找到与任何订阅领域相关的文章")
            return pd.DataFrame()
            
        print(f"📚 共找到 {len(relevant_article_ids)} 篇不重复的相关文章")
        
        # 从global_df中筛选出相关的文章（保持时间范围一致）
        if 'id' in global_df.columns:
            field_df = global_df[global_df['id'].isin(relevant_article_ids)]
            print(f"📄 其中 {len(field_df)} 篇在指定时间范围内")
            return field_df
        else:
            print("⚠️ global_df中没有id列，无法筛选相关文章")
            return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ 数据库查询失败: {str(e)}")
        
        # 回退到旧方法：直接对global_df进行筛选
        print("⚠️ 回退到逐篇判断方法...")
        all_field_articles = pd.DataFrame()
        
        for field in user_fields:
            field_df = pd.DataFrame()
            for _, row in global_df.iterrows():
                if is_related_to_field(row.to_dict(), field):
                    field_df = pd.concat([field_df, pd.DataFrame([row])], ignore_index=True)
            
            print(f"筛选到 {len(field_df)} 篇与领域 '{field}' 相关的文章")
            all_field_articles = pd.concat([all_field_articles, field_df], ignore_index=True)
        
        # 去除重复文章
        if not all_field_articles.empty:
            all_field_articles = all_field_articles.drop_duplicates(subset=['id'] if 'id' in all_field_articles.columns else None)
            print(f"📚 合并后共有 {len(all_field_articles)} 篇不重复文章")
            
        return all_field_articles

def get_latest_articles(days=1):
    """从数据库获取最近几天的文章"""
    try:
        conn = sqlite3.connect('journals.db')
        # 获取最近n天的文章
        query = f"""
        SELECT * FROM articles 
        WHERE publish_date >= date('now', '-{days} day')
        ORDER BY publish_date DESC, journal
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            print(f"⚠️ 最近{days}天没有新文章")
        else:
            print(f"📚 获取到{len(df)}篇最近{days}天的文章")
            
        return df
    except Exception as e:
        print(f"❌ 获取文章失败: {str(e)}")
        return pd.DataFrame()

def batch_send_emails(days=1):
    """批量发送邮件（基于用户ID）"""
    print(f"\n🚀 启动批量发送任务 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # 从数据库获取所有用户信息
    conn = sqlite3.connect('journals.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, email, phone, field FROM subscriptions')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        print("⚠️ 当前没有订阅用户")
        return
        
    print(f"👥 共发现 {len(users)} 个订阅用户")
    
    # 获取最近的文章
    global_df = get_latest_articles(days)
    
    if global_df.empty:
        print("⚠️ 最近无新文章，取消发送")
        return
    
    # 为每个用户处理
    success_count = 0
    for user_id, email, phone, field in users:
        try:
            # 获取用户定制数据
            if not email:
                print(f"⚠️ 用户 {user_id} 未设置邮箱，跳过发送")
                continue
                
            field_df = get_user_specific_data(user_id, field, global_df)
            
            if field_df.empty:
                print(f"⚠️ 用户 {user_id} 没有匹配的文章，跳过发送")
                continue
                
            if send_email(email, f"{field or '学术'}论文推送", field_df):
                success_count += 1
                print(f"✅ 成功发送至用户 {user_id} ({email})")
            
            time.sleep(5)  # 避免发送过快
            
        except Exception as e:
            print(f"❌ 用户 {user_id} 处理失败: {str(e)}")
            continue

    print(f"\n🎉 全部任务完成！成功发送 {success_count}/{len(users)} 个用户")

if __name__ == "__main__":
    # 确保数据库存在
    if not os.path.exists('journals.db'):
        init_database()
        
    # 默认发送最近1天的文章，可以通过参数调整
    import argparse
    parser = argparse.ArgumentParser(description='发送期刊文章邮件')
    parser.add_argument('--days', type=int, default=1, help='获取最近几天的文章')
    args = parser.parse_args()
    
    batch_send_emails(args.days) 
