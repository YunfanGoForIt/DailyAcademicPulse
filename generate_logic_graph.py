import os
import json
import sqlite3
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from openai import OpenAI

# 使用环境变量存储API密钥或直接在代码中设置
DASHSCOPE_API_KEY = "sk-dc79c7928859459c9619daf752c542fc"
R1_MODEL_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 创建R1客户端
r1_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=R1_MODEL_BASE_URL
)

def generate_logic_graph(title: str, abstract: str) -> Tuple[str, str, str]:
    """使用deepseek-r1模型生成论文逻辑关系图
    
    Args:
        title: 论文标题
        abstract: 论文摘要
        
    Returns:
        Tuple[str, str, str]: (思维链过程, mermaid代码, 文字验证)
    """
    print(f"🔄 为论文《{title[:30]}...》生成逻辑关系图...")
    
    # 构造提示词
    prompt = f"""我需要你帮我分析以下学术论文的逻辑结构，并用mermaid图表格式展示出来，以帮助大一大二的本科生理解：

论文标题：{title}

摘要：{abstract}

请完成以下任务：
1. 分析文章中的关键概念、实体及其关系
2. 使用mermaid语法创建一个逻辑关系图（流程图或思维导图格式）
3. 将生成的图转化回文字，并与原摘要对比，确保逻辑不错（可以缺少一些信息，但逻辑必须正确）
4. 只输出最终的mermaid代码

mermaid代码应该清晰展示出论文的主要概念和它们之间的关系，便于理解论文的核心内容。"""
    
    try:
        # 调用deepseek-r1
        completion = r1_client.chat.completions.create(
            model="deepseek-r1",
            messages=[{'role': 'user', 'content': prompt}]
        )

        # 获取思维链和最终答案
        reasoning = completion.choices[0].message.reasoning_content  # 思维过程
        mermaid_code = completion.choices[0].message.content  # 最终结果
        
        # 从reasoning中提取文字验证部分（最后一个部分通常是验证）
        text_verification = extract_verification_from_reasoning(reasoning)
        
        print("✅ 逻辑关系图生成成功")
        return reasoning, mermaid_code, text_verification
        
    except Exception as e:
        print(f"❌ 逻辑关系图生成失败: {str(e)}")
        return ("生成失败", 
                "graph TD\n    A[生成失败] --> B[请稍后再试]", 
                "生成失败，请稍后再试")

def extract_verification_from_reasoning(reasoning: str) -> str:
    """从思维链中提取文字验证部分"""
    # 尝试寻找验证部分的标志词
    verification_markers = [
        "验证：", "验证", "对比：", "对比", 
        "转化为文字：", "文字描述：", "文字表述："
    ]
    
    for marker in verification_markers:
        if marker in reasoning:
            parts = reasoning.split(marker, 1)
            if len(parts) > 1:
                return parts[1].strip()
    
    # 如果没有找到标记，返回思维链的最后1/3部分作为验证
    lines = reasoning.strip().split('\n')
    third_part = lines[len(lines)*2//3:]
    return '\n'.join(third_part)

def save_logic_graph_to_db(article_id: int, mermaid_code: str, reasoning: str, verification: str) -> bool:
    """保存生成的逻辑关系图到数据库
    
    Args:
        article_id: 文章ID
        mermaid_code: 生成的mermaid代码
        reasoning: 思维链过程
        verification: 文字验证
        
    Returns:
        bool: 是否保存成功
    """
    # 确保数据库中有存储逻辑图的表
    ensure_logic_graph_table_exists()
    
    try:
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        
        # 检查是否已存在
        cursor.execute(
            "SELECT 1 FROM article_logic_graphs WHERE article_id = ?", 
            (article_id,)
        )
        
        if cursor.fetchone():
            # 更新现有记录
            cursor.execute("""
                UPDATE article_logic_graphs
                SET mermaid_code = ?, reasoning = ?, verification = ?, updated_at = ?
                WHERE article_id = ?
            """, (mermaid_code, reasoning, verification, datetime.now().isoformat(), article_id))
        else:
            # 插入新记录
            cursor.execute("""
                INSERT INTO article_logic_graphs
                (article_id, mermaid_code, reasoning, verification, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (article_id, mermaid_code, reasoning, verification, 
                  datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        print(f"✅ 已保存文章ID {article_id} 的逻辑关系图")
        return True
        
    except Exception as e:
        print(f"❌ 保存逻辑关系图失败: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def ensure_logic_graph_table_exists():
    """确保article_logic_graphs表存在"""
    conn = sqlite3.connect('journals.db')
    cursor = conn.cursor()
    
    # 创建存储逻辑图的表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS article_logic_graphs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER UNIQUE,
        mermaid_code TEXT,
        reasoning TEXT,
        verification TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logic_graphs_article ON article_logic_graphs (article_id)')
    
    conn.commit()
    conn.close()

def process_article_logic_graph(article_id: int) -> Optional[Dict[str, Any]]:
    """为特定文章生成逻辑关系图
    
    Args:
        article_id: 文章ID
        
    Returns:
        Optional[Dict[str, Any]]: 包含处理结果的字典，失败则返回None
    """
    try:
        # 获取文章信息
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT original_title, translated_title, abstract
            FROM articles
            WHERE id = ?
        """, (article_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"❌ 未找到ID为 {article_id} 的文章")
            return None
            
        original_title, translated_title, abstract = result
        
        # 使用中文标题和摘要优先
        title = translated_title or original_title
        
        # 如果没有摘要，无法生成逻辑图
        if not abstract or abstract == '摘要获取失败' or abstract == '内容处理异常':
            print(f"❌ 文章摘要不可用，无法生成逻辑图")
            return None
            
        # 生成逻辑关系图
        reasoning, mermaid_code, verification = generate_logic_graph(title, abstract)
        
        # 保存到数据库
        success = save_logic_graph_to_db(article_id, mermaid_code, reasoning, verification)
        
        if success:
            return {
                'article_id': article_id,
                'title': title,
                'mermaid_code': mermaid_code,
                'verification': verification,
                'reasoning': reasoning
            }
        else:
            return None
            
    except Exception as e:
        print(f"❌ 处理文章逻辑图失败: {str(e)}")
        return None

def get_article_logic_graph(article_id: int) -> Optional[Dict[str, Any]]:
    """获取文章的逻辑关系图
    
    Args:
        article_id: 文章ID
        
    Returns:
        Optional[Dict[str, Any]]: 包含逻辑图信息的字典，若不存在则返回None
    """
    try:
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        
        # 检查逻辑图是否存在
        cursor.execute("""
            SELECT alg.mermaid_code, alg.verification, alg.reasoning,
                   a.translated_title, a.original_title, a.abstract
            FROM article_logic_graphs alg
            JOIN articles a ON alg.article_id = a.id
            WHERE alg.article_id = ?
        """, (article_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            mermaid_code, verification, reasoning, translated_title, original_title, abstract = result
            return {
                'article_id': article_id,
                'title': translated_title or original_title,
                'abstract': abstract,
                'mermaid_code': mermaid_code,
                'verification': verification,
                'reasoning': reasoning
            }
        else:
            # 不存在，则生成新的
            return process_article_logic_graph(article_id)
            
    except Exception as e:
        print(f"❌ 获取逻辑关系图失败: {str(e)}")
        return None

def process_recent_articles(limit: int = 10):
    """为最近的文章生成逻辑关系图
    
    Args:
        limit: 处理的文章数量限制
    """
    try:
        # 确保表结构存在
        ensure_logic_graph_table_exists()
        
        # 获取最近的没有逻辑图的文章
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        
        # 查询没有逻辑图的最新文章
        cursor.execute("""
            SELECT a.id, a.translated_title, a.original_title
            FROM articles a
            LEFT JOIN article_logic_graphs alg ON a.id = alg.article_id
            WHERE alg.id IS NULL
            AND a.abstract IS NOT NULL 
            AND a.abstract != '摘要获取失败'
            AND a.abstract != '内容处理异常'
            ORDER BY a.id DESC
            LIMIT ?
        """, (limit,))
        
        articles = cursor.fetchall()
        conn.close()
        
        if not articles:
            print("✅ 所有文章已有逻辑关系图")
            return
            
        print(f"🔍 找到 {len(articles)} 篇需要生成逻辑关系图的文章")
        
        # 为每篇文章生成逻辑关系图
        for article_id, translated_title, original_title in articles:
            title = translated_title or original_title
            print(f"\n处理文章 #{article_id}: {title[:30]}...")
            result = process_article_logic_graph(article_id)
            if result:
                print(f"✅ 已完成 #{article_id}")
            else:
                print(f"❌ 处理失败 #{article_id}")
                
    except Exception as e:
        print(f"❌ 批量处理文章失败: {str(e)}")

if __name__ == "__main__":
    # 确保表结构存在
    ensure_logic_graph_table_exists()
    
    # 处理最近10篇文章
    process_recent_articles(10)
    print("✅ 逻辑关系图生成处理完成") 