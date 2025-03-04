import feedparser
from datetime import datetime
from config import JOURNALS_CONFIG

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
    """获取所有期刊的最新文章，使用配置文件中的期刊信息"""
    all_entries = []
    today = datetime.now().date()
    
    for journal_id, config in JOURNALS_CONFIG.items():
        try:
            feed_url = config['rss_url']
            journal_name = config.get('journal_name', journal_id)
            
            print(f"正在获取 {journal_name} 的RSS feed...")
            feed = feedparser.parse(feed_url)
            
            valid_entries = [
                entry for entry in feed.entries
                if parse_entry_date(entry).date() == today
            ][:articles_num]  # 使用参数控制数量
            
            # 为每个条目添加期刊信息
            for entry in valid_entries:
                entry.journal = journal_name
            
            all_entries.extend(valid_entries)
            
            # 输出每个期刊获取到的文章条数
            print(f"{journal_name} 获取到 {len(valid_entries)} 篇文章")
            
        except Exception as e:
            print(f"处理 {journal_name} 时出错: {str(e)}")
            continue
            
    return all_entries

def main():
    get_all_journal_articles()

def test_journal_configs():
    """测试所有期刊配置的有效性"""
    print("开始测试所有期刊配置...")
    
    for journal_id, config in JOURNALS_CONFIG.items():
        journal_name = config.get('journal_name', journal_id)
        rss_url = config.get('rss_url', '')
        
        print(f"\n测试 {journal_name} ({rss_url}):")
        
        try:
            feed = feedparser.parse(rss_url)
            entry_count = len(feed.entries)
            
            if entry_count > 0:
                print(f"✅ 成功 - 找到 {entry_count} 条目")
                
                # 测试第一条内容
                if feed.entries:
                    entry = feed.entries[0]
                    print(f"  示例标题: {getattr(entry, 'title', '无标题')[:50]}...")
                    
                    # 测试日期解析
                    try:
                        date = parse_entry_date(entry)
                        print(f"  日期解析: {date.strftime('%Y-%m-%d')}")
                    except Exception as e:
                        print(f"  ⚠️ 日期解析失败: {str(e)}")
            else:
                print("⚠️ 警告 - 未找到任何条目")
        
        except Exception as e:
            print(f"❌ 错误 - {str(e)}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    # 取消注释以下行来测试期刊配置
    # test_journal_configs()
    main()
