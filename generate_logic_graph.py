import os
import json
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from openai import OpenAI
from config import get_db_connection

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
3. 在思维链中将生成的图转化回文字，并与原摘要对比，确保逻辑不错（可以缺少一些信息，但逻辑必须正确），如不正确，则再次生成逻辑关系图
4. 最终只输出的mermaid代码，不要输出其他任何无关的文字

mermaid代码应该清晰展示出论文的主要概念和它们之间的关系，便于理解论文的核心内容。"""
    
    try:
        # 调用deepseek-r1
        completion = r1_client.chat.completions.create(
            model="deepseek-r1",
            messages=[{'role': 'user', 'content': prompt}]
        )

        # 获取思维链和最终答案
        reasoning = completion.choices[0].message.reasoning_content  # 思维过程
        print("思维链：", reasoning)
        mermaid_code = completion.choices[0].message.content  # 最终结果
        print("mermaid代码：", mermaid_code)
        # 清理mermaid代码
        mermaid_code = clean_mermaid_code(mermaid_code)
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
    """保存生成的逻辑关系图到数据库"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查是否已存在
        cursor.execute(
            "SELECT 1 FROM article_logic_graphs WHERE article_id = %s", 
            (article_id,)
        )
        
        if cursor.fetchone():
            # 更新现有记录
            cursor.execute("""
                UPDATE article_logic_graphs
                SET mermaid_code = %s, reasoning = %s, verification = %s, updated_at = %s
                WHERE article_id = %s
            """, (mermaid_code, reasoning, verification, datetime.now().isoformat(), article_id))
        else:
            # 插入新记录
            cursor.execute("""
                INSERT INTO article_logic_graphs
                (article_id, mermaid_code, reasoning, verification, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (article_id, mermaid_code, reasoning, verification, 
                  datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        print(f"✅ 已保存文章ID {article_id} 的逻辑关系图")
        return True
        
    except Exception as e:
        print(f"❌ 保存逻辑关系图失败: {str(e)}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def ensure_logic_graph_table_exists():
    """确保article_logic_graphs表存在"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建存储逻辑图的表
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
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

def process_article_logic_graph(article_id: int) -> Optional[Dict[str, Any]]:
    """为特定文章生成逻辑关系图"""
    try:
        # 获取文章信息
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT original_title, translated_title, abstract
            FROM articles
            WHERE id = %s
        """, (article_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            print(f"❌ 未找到ID为 {article_id} 的文章")
            return None
            
        original_title = result['original_title']
        translated_title = result['translated_title']
        abstract = result['abstract']
        
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
    """获取文章的逻辑关系图"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 检查逻辑图是否存在
        cursor.execute("""
            SELECT alg.mermaid_code, alg.verification, alg.reasoning,
                   a.translated_title, a.original_title, a.abstract
            FROM article_logic_graphs alg
            JOIN articles a ON alg.article_id = a.id
            WHERE alg.article_id = %s
        """, (article_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'article_id': article_id,
                'title': result['translated_title'] or result['original_title'],
                'abstract': result['abstract'],
                'mermaid_code': result['mermaid_code'],
                'verification': result['verification'],
                'reasoning': result['reasoning']
            }
        else:
            # 不存在，则生成新的
            return process_article_logic_graph(article_id)
            
    except Exception as e:
        print(f"❌ 获取逻辑关系图失败: {str(e)}")
        return None

def process_recent_articles(limit: int = 10):
    """为最近的文章生成逻辑关系图"""
    try:
        # 确保表结构存在
        ensure_logic_graph_table_exists()
        
        # 获取最近的没有逻辑图的文章
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
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
            LIMIT %s
        """, (limit,))
        
        articles = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not articles:
            print("✅ 所有文章已有逻辑关系图")
            return
            
        print(f"🔍 找到 {len(articles)} 篇需要生成逻辑关系图的文章")
        
        # 为每篇文章生成逻辑关系图
        for article in articles:
            article_id = article['id']
            title = article['translated_title'] or article['original_title']
            print(f"\n处理文章 #{article_id}: {title[:30]}...")
            result = process_article_logic_graph(article_id)
            if result:
                print(f"✅ 已完成 #{article_id}")
            else:
                print(f"❌ 处理失败 #{article_id}")
                
    except Exception as e:
        print(f"❌ 批量处理文章失败: {str(e)}")

def clean_mermaid_code(mermaid_code: str) -> str:
    """清理mermaid代码，移除markdown代码块标记
    
    Args:
        mermaid_code: 原始mermaid代码
        
    Returns:
        str: 清理后的纯mermaid代码
    """
    # 移除开头的```mermaid标记
    if mermaid_code.strip().startswith("```mermaid"):
        mermaid_code = mermaid_code.replace("```mermaid", "", 1).strip()
    # 如果包含结尾的```，也移除
    if mermaid_code.strip().endswith("```"):
        mermaid_code = mermaid_code[:mermaid_code.rfind("```")].strip()
    # 移除任何可能的其他```mermaid标记
    mermaid_code = mermaid_code.replace("```mermaid", "").strip()
    # 移除单独的```标记
    mermaid_code = mermaid_code.replace("```", "").strip()
    
    return mermaid_code

if __name__ == "__main__":
    # 确保表结构存在
    ensure_logic_graph_table_exists()
    
    # 处理最近10篇文章
    process_recent_articles(10)
    print("✅ 逻辑关系图生成处理完成") 