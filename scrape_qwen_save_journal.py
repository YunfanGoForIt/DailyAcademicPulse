import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

from typing import *

import os
import json

from openai import OpenAI
from openai.types.chat.chat_completion import Choice

from rss import get_all_journal_articles
import re
import feedparser

from datetime import datetime, timedelta

from config import FIELD_KEYWORDS, JOURNALS_CONFIG, get_db_connection, init_database
from mysql.connector import Error


# 配置信息
CLIENT = OpenAI(
    api_key="sk-dc79c7928859459c9619daf752c542fc",  # 请替换为你的实际API密钥
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

def identify_journal_from_link(link):
    """根据链接识别期刊，使用配置中的domain_patterns"""
    if not link or link == '无链接':
        return '未知期刊'
        
    # 先检查现有期刊
    for journal_id, config in JOURNALS_CONFIG.items():
        domain_patterns = config.get('domain_patterns', [])
        exclude_patterns = config.get('exclude_patterns', [])
        
        # 检查是否匹配domain_patterns中的任一模式
        if any(pattern in link for pattern in domain_patterns):
            # 检查是否匹配exclude_patterns中的任一模式
            if not any(ex_pattern in link for ex_pattern in exclude_patterns):
                return config.get('journal_name', journal_id)
    
    # 如果没有匹配到任何期刊
    return '未知期刊'

def get_detailed_abstract(entry):
    """集成搜索与翻译（修复字段合并问题）"""
    # 从链接解析期刊名称
    link = getattr(entry, 'link', '')
    
    # 如果entry已经有journal属性，优先使用
    journal = getattr(entry, 'journal', None)
    if not journal:
        journal = identify_journal_from_link(link)
        
    # 补全entry的journal属性
    entry.journal = journal
    # 基础元数据提取（必须字段）
    base_data = {
        'journal': getattr(entry, 'journal', '未知期刊'),
        'original_title': getattr(entry, 'title', '无标题'),
        'original_authors': ', '.join(a.name for a in getattr(entry, 'authors', [])),
        'link': getattr(entry, 'link', '无链接'),
        'publish_date': parse_entry_date(entry).strftime('%Y-%m-%d')
    }

    try:
        # 增强版系统提示
        system_prompt = """作为学术助手，请完成：
1. 网络搜索获取用户提到的论文摘要（250字以内，中文）
2. 翻译标题和作者信息
3. json结构化返回：
{
  "original_title": "保留原始标题",
  "translated_title": "中文标题",
  "original_authors": "原始作者列表", 
  "translated_authors": "中文作者列表",
  "abstract": "中文摘要",
  "summary": "100字总结"
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请处理：{base_data['original_title']}"}
        ]

        # 调用通义千问API进行联网搜索获取信息
        completion = CLIENT.chat.completions.create(
            model="qwen-plus",  # 通义千问模型
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"},
            extra_body={
                "enable_search": True  # 启用联网搜索
            }
        )

        # 解析结构化响应
        try:
            response = completion.choices[0].message.content
            # 添加安全的JSON解析
            api_data = json.loads(response)  # 不需要指定encoding
            
            # 合并数据（优先使用API数据，保留基础元数据）
            return {
                **base_data,  # 基础字段
                'translated_title': api_data.get('translated_title', base_data['original_title']),
                'translated_authors': api_data.get('translated_authors', base_data['original_authors']),
                'abstract': api_data.get('abstract', '摘要获取失败'),
                'summary': api_data.get('summary', '总结生成失败')
            }
        except Exception as e:
            print(f"处理失败: {str(e)}")
            # 返回基础数据+错误信息
            return {
                **base_data,
                'translated_title': base_data['original_title'],
                'translated_authors': base_data['original_authors'],
                'abstract': '内容处理异常',
                'summary': '内容处理异常'
            }

    except Exception as e:
        print(f"⚠️ 全局异常: {str(e)}")
        return {
            'Translated Title': base_data['original_title'],
            'Translated Authors': base_data['original_authors'],
            'Abstract': '服务暂时不可用'
        }

def classify_article_fields(article_data: dict) -> Dict[str, float]:
    """判断文章属于哪些领域，返回领域及置信度"""
    title = article_data.get('original_title', '无标题')[:50]
    print(f"🔍 正在判断《{title}...》属于哪些领域...")
    
    # 准备领域列表，排除"无"
    fields = [field for field in FIELD_KEYWORDS.keys() if field != "无"]
    
    system_prompt = f"""你是一个专业的科研助手，需要判断论文属于哪些研究领域。

论文信息：
标题：{article_data.get('original_title', '')}
摘要：{article_data.get('abstract', '')[:2000]}

请判断这篇论文属于以下哪些领域（可多选），并给出置信度（0-1之间的小数）：
{', '.join(fields)}

请严格按以下JSON格式返回结果：
{{
  "fields": {{
    "领域1": 0.95,
    "领域2": 0.85,
    "领域3": 0.75
  }}
}}

只返回置信度大于0.5的领域。"""

    try:
        completion = CLIENT.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请分析这篇论文属于哪些领域"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(completion.choices[0].message.content)
        field_results = result.get("fields", {})
        
        # 打印结果
        if field_results:
            print("✅ 领域分类结果:")
            for field, confidence in field_results.items():
                print(f"  - {field}: {confidence:.2f}")
        else:
            print("❌ 未找到匹配的领域")
            
        return field_results
        
    except Exception as e:
        print(f"⚠️ 领域判断失败: {str(e)}")
        return {}  # 失败时返回空字典

def save_to_database(df):
    """增强字段验证并保存文章及其领域分类"""
    # 合法字段列表
    valid_columns = {
        'journal', 'original_title', 'translated_title',
        'original_authors', 'translated_authors',
        'abstract', 'summary', 'link', 'publish_date'
    }
    
    # 过滤非法字段
    df = df[[col for col in df.columns if col in valid_columns]]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取当前记录数
        cursor.execute("SELECT COUNT(*) FROM articles")
        original_count = cursor.fetchone()[0]
        
        # 保存文章并获取新增文章的ID
        new_article_ids = []
        
        for _, row in df.iterrows():
            # 准备插入数据
            columns = ', '.join(row.index)
            placeholders = ', '.join(['%s'] * len(row))
            
            # 执行插入
            cursor.execute(f"""
                INSERT IGNORE INTO articles 
                ({columns}) 
                VALUES ({placeholders})
            """, tuple(row))
            
            # 如果是新插入的文章，获取其ID
            if cursor.rowcount > 0:
                article_id = cursor.lastrowid
                new_article_ids.append((article_id, row.to_dict()))
        
        conn.commit()
        
        # 获取保存后的记录数
        cursor.execute("SELECT COUNT(*) FROM articles")
        new_count = cursor.fetchone()[0]
        added = new_count - original_count
        skipped = len(df) - added
        
        print(f"💾 数据库更新: 新增 {added} 篇, 跳过 {skipped} 篇重复")
        
        # 为新增文章进行领域分类并保存
        for article_id, article_data in new_article_ids:
            print(f"\n🔍 为文章ID {article_id} 进行领域分类...")
            field_results = classify_article_fields(article_data)
            
            # 保存领域分类结果
            for field, confidence in field_results.items():
                cursor.execute("""
                    INSERT INTO article_fields 
                    (article_id, field, confidence) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE confidence = VALUES(confidence)
                """, (article_id, field, confidence))
            
            conn.commit()
            print(f"✅ 已保存 {len(field_results)} 个领域分类结果")
            
            # 如果启用了逻辑关系图功能，为新文章生成逻辑关系图
            if LOGIC_GRAPH_ENABLED:
                if article_data.get('abstract') and article_data.get('abstract') not in ['摘要获取失败', '内容处理异常']:
                    print(f"🔄 为文章ID {article_id}「{article_data.get('translated_title', '')[:20]}...」生成逻辑关系图...")
                    try:
                        start_time = time.time()
                        result = process_article_logic_graph(article_id)
                        elapsed = time.time() - start_time
                        
                        if result:
                            print(f"✅ 逻辑关系图生成成功 (耗时: {elapsed:.1f}秒)")
                            # 显示生成的mermaid代码长度作为参考
                            mermaid_length = len(result.get('mermaid_code', ''))
                            print(f"   mermaid代码长度: {mermaid_length} 字符")
                        else:
                            print(f"⚠️ 逻辑关系图生成失败 (耗时: {elapsed:.1f}秒)")
                    except Exception as e:
                        print(f"❌ 逻辑关系图处理异常: {str(e)}")
                else:
                    print(f"⏩ 文章ID {article_id} 摘要不可用，跳过逻辑关系图生成")
            
            print(f"✓ 文章ID {article_id} 处理完成\n{'='*50}")
        
    except Exception as e:
        print(f"❌ 保存到数据库失败: {str(e)}")
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def article_exists(link: str, entry) -> bool:
    """增强去重检查"""
    if not link or link == '无链接':
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM articles WHERE link = %s OR (journal = %s AND original_title = %s) LIMIT 1",
        (link, getattr(entry, 'journal', '未知期刊'), getattr(entry, 'title', '无标题'))
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

def get_rss_articles(articles_num=3):
    """获取并处理期刊文章（增强日志输出）"""
    print(f"\n🔍 开始获取最新文章（{datetime.now().strftime('%Y-%m-%d %H:%M')}）")
    all_articles = []
    
    entries = get_all_journal_articles(articles_num)
    total = len(entries)
    print(f"📥 共发现 {total} 篇候选文章")
    
    # 新增字典来存储每个期刊的标题和数量
    journal_count = {}

    for idx, entry in enumerate(entries, 1):
        try:
            # 进度显示
            progress = f"[{idx}/{total}]"
            
            # 基础信息
            title = getattr(entry, 'title', '无标题')[:40] + "..." 
            link = getattr(entry, 'link', '无链接')
            journal = getattr(entry, 'journal', '未知期刊')  # 获取期刊名称
            print(f"\n{progress} 📄 处理文章: {title}")
            print(f"🔗 文章链接: {link}")
            
            # 检查重复
            if article_exists(link, entry):
                print("⏩ 跳过重复文章")
                continue
                
            # 处理流程
            start_time = time.time()
            processed_data = get_detailed_abstract(entry)
            elapsed = time.time() - start_time
            
            if processed_data:
                print(f"✅ 处理成功（耗时{elapsed:.1f}s）")
                # 显示文章基本信息
                print(f"  期刊: {processed_data.get('journal', '未知')}")
                print(f"  标题: {processed_data.get('translated_title', '无标题')[:50]}...")
                df = pd.DataFrame([processed_data])
                save_to_database(df)
                all_articles.append(processed_data)

                # 更新期刊计数
                if journal in journal_count:
                    journal_count[journal] += 1
                else:
                    journal_count[journal] = 1
            else:
                print("⚠️ 处理失败，保留基础信息")
                all_articles.append({
                    'original_title': title,
                    'link': link,
                    'publish_date': datetime.now().strftime('%Y-%m-%d')
                })
                
        except Exception as e:
            print(f"❌ 严重错误: {str(e)}")
            continue
            
    print(f"\n📊 最终处理完成：成功 {len(all_articles)} 篇，失败 {total - len(all_articles)} 篇")
    
    # 输出每个期刊获取到的数据条数和对应标题
    print("\n📚 各期刊获取到的数据条数：")
    for journal, count in journal_count.items():
        print(f"{journal}: {count} 条")

    return pd.DataFrame(all_articles)

def parse_entry_date(entry):
    """增强日期解析可靠性"""
    try:
        # 优先使用已解析的日期
        if hasattr(entry, 'published_parsed'):
            return datetime(*entry.published_parsed[:6])
            
        # 备选日期字段
        date_str = getattr(entry, 'published', '') or \
                  getattr(entry, 'updated', '') or \
                  getattr(entry, 'created', '')
                  
        if not date_str:
            return datetime.now()
            
        # 尝试多种日期格式
        for fmt in ('%a, %d %b %Y %H:%M:%S %Z',
                   '%Y-%m-%dT%H:%M:%SZ',
                   '%Y-%m-%d %H:%M:%S',
                   '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        return datetime.now()
    except:
        return datetime.now()

def is_related_to_field(article_data: dict, target_field: str) -> bool:
    """判断文章是否属于特定领域（从数据库查询）"""
    # 获取文章ID
    article_id = get_article_id(article_data.get('link', ''))
    if not article_id:
        # 如果找不到文章ID，使用旧方法进行判断
        return legacy_is_related_to_field(article_data, target_field)
    
    # 从数据库查询
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT confidence FROM article_fields 
        WHERE article_id = %s AND field = %s
    """, (article_id, target_field))
    result = cursor.fetchone()
    cursor.close()
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
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM articles WHERE link = %s", (link,))
    result = cursor.fetchone()
    cursor.close()
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
            model="qwen-plus",
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

def check_database_exists():
    """检查云端数据库是否存在"""
    try:
        conn = get_db_connection()  # 使用你之前定义的获取数据库连接的函数
        cursor = conn.cursor()
        
        # 检查数据库是否存在
        cursor.execute("SHOW DATABASES LIKE 'academic_pulse';")
        result = cursor.fetchone()
        print(result)
        if result:
            print("✅ 数据库 'academic_pulse' 已存在。")
        else:
            print("❌ 数据库 'academic_pulse' 不存在，正在初始化...")
            init_database()  # 调用初始化函数创建数据库和表结构
        return(result)

    except Error as e:
        print(f"❌ 数据库连接失败: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":

    check_database_exists()  # 检查云端数据库
    # 确保数据库存在

    # 导入逻辑关系图生成模块
    try:
        from generate_logic_graph import process_article_logic_graph, ensure_logic_graph_table_exists

        LOGIC_GRAPH_ENABLED = True
        print("✅ 逻辑关系图模块已加载，将自动为新文章生成逻辑关系图")
    except ImportError:
        print("⚠️ 逻辑关系图模块导入失败，将不生成逻辑关系图")
        LOGIC_GRAPH_ENABLED = False

    # 如果启用了逻辑关系图功能，确保相关表存在
    if LOGIC_GRAPH_ENABLED:
        print("🔄 确保逻辑关系图表结构存在...")
        ensure_logic_graph_table_exists()
        
    # 只执行抓取和保存
    print("\n🚀 开始抓取期刊文章并生成逻辑关系图...")
    get_rss_articles()
    print("✅ 数据抓取、保存和逻辑关系图生成 全部完成")
