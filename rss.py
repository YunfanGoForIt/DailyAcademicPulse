import feedparser
from datetime import datetime

def parse_entry_date(entry):
    """统一日期解析函数"""
    try:
        # 优先使用解析后的日期
        if hasattr(entry, 'published_parsed'):
            return datetime(*entry.published_parsed[:6])
        # 备选方案处理不同格式
        return datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
    except:
        return datetime.now()

def get_all_journal_articles(articles_num=3):
    """获取所有期刊的最新文章（修复参数问题）"""
    journals = {
        'Science': 'https://science.sciencemag.org/rss/current.xml',
        'Nature': 'https://www.nature.com/nature.rss',
        'Nature Biomedical Engineering': 'https://www.nature.com/natbiomedeng.rss',
        'Cell': 'https://www.cell.com/cell/current.rss'
    }
    
    all_entries = []
    today = datetime.now().date()
    
    for journal_name, feed_url in journals.items():
        try:
            feed = feedparser.parse(feed_url)
            valid_entries = [
                entry for entry in feed.entries
                if parse_entry_date(entry).date() == today
            ][:articles_num]  # 使用参数控制数量
            
            all_entries.extend(valid_entries)
            
            # 输出每个期刊获取到的文章条数
            print(f"{journal_name} 获取到 {len(valid_entries)} 篇文章")
            
        except Exception as e:
            print(f"处理 {journal_name} 时出错: {str(e)}")
            continue
            
    return all_entries

def main():
    get_all_journal_articles()

if __name__ == "__main__":
    main()
