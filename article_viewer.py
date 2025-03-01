import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

class ArticleViewer:
    def __init__(self, master):
        self.master = master
        master.title("科研论文数据库管理")
        master.geometry("1200x800")
        
        # 样式配置
        self.style = ttk.Style()
        self.style.configure("Treeview", font=('微软雅黑', 10), rowheight=25)
        self.style.configure("TButton", font=('微软雅黑', 10), padding=6)
        
        # 主框架
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 搜索栏
        self.search_frame = ttk.Frame(self.main_frame)
        self.search_frame.pack(fill=tk.X, pady=5)
        
        self.search_var = tk.StringVar()
        ttk.Label(self.search_frame, text="搜索:").pack(side=tk.LEFT, padx=5)
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.search_frame, text="搜索", command=self.load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.search_frame, text="重置", command=self.reset_search).pack(side=tk.LEFT, padx=5)
        
        # 文章列表
        self.tree = ttk.Treeview(self.main_frame, columns=(
            'id', 'journal', 'original_title', 'translated_title', 
            'publish_date', 'link', 'fields'), show='headings')
        
        # 列配置
        self.tree.heading('id', text='ID', anchor=tk.W)
        self.tree.heading('journal', text='期刊', anchor=tk.W)
        self.tree.heading('original_title', text='原文标题', anchor=tk.W)
        self.tree.heading('translated_title', text='中文标题', anchor=tk.W)
        self.tree.heading('publish_date', text='发布日期', anchor=tk.W)
        self.tree.heading('link', text='文章链接', anchor=tk.W)
        self.tree.heading('fields', text='领域', anchor=tk.W)
        
        # 列宽设置
        self.tree.column('id', width=50, anchor=tk.W)
        self.tree.column('journal', width=150, anchor=tk.W)
        self.tree.column('original_title', width=300, anchor=tk.W)
        self.tree.column('translated_title', width=300, anchor=tk.W)
        self.tree.column('publish_date', width=120, anchor=tk.W)
        self.tree.column('link', width=200, anchor=tk.W)
        self.tree.column('fields', width=200, anchor=tk.W)
        
        # 滚动条
        vsb = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.main_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 操作按钮
        self.btn_frame = ttk.Frame(self.main_frame)
        self.btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        ttk.Button(self.btn_frame, text="删除选中", command=self.delete_selected).pack(pady=5)
        ttk.Button(self.btn_frame, text="刷新数据", command=self.load_data).pack(pady=5)
        ttk.Button(self.btn_frame, text="导出CSV", command=self.export_csv).pack(pady=5)
        
        # 详情面板
        self.detail_frame = ttk.LabelFrame(self.main_frame, text="文章详情")
        self.detail_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.detail_text = tk.Text(self.detail_frame, wrap=tk.WORD, font=('微软雅黑', 10))
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 绑定事件
        self.tree.bind('<<TreeviewSelect>>', self.show_details)
        self.load_data()

    def load_data(self, search_term=None):
        """加载数据库数据"""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        
        try:
            query = '''SELECT 
                id, journal, original_title, translated_title, 
                publish_date, link 
                FROM articles'''
                
            params = ()
            if search_term:
                query += " WHERE original_title LIKE ? OR translated_title LIKE ?"
                params = (f'%{search_term}%', f'%{search_term}%')
                
            cursor.execute(query, params)
            
            for row in cursor.fetchall():
                # 获取领域信息
                cursor.execute("SELECT field FROM article_fields WHERE article_id=?", (row[0],))
                fields = [field[0] for field in cursor.fetchall()]
                fields_str = ', '.join(fields) if fields else '无'
                
                # 插入数据
                self.tree.insert('', 'end', values=row + (fields_str,))
                
        except Exception as e:
            messagebox.showerror("数据库错误", f"无法加载数据: {str(e)}")
        finally:
            cursor.close()
            conn.close()

    def reset_search(self):
        """重置搜索条件"""
        self.search_var.set('')
        self.load_data()

    def delete_selected(self):
        """删除选中条目"""
        selected = self.tree.selection()
        if not selected:
            return
            
        confirm = messagebox.askyesno("确认删除", "确定要删除选中的文章记录吗？")
        if not confirm:
            return
            
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        
        try:
            for item in selected:
                article_id = self.tree.item(item, 'values')[0]
                cursor.execute("DELETE FROM articles WHERE id=?", (article_id,))
            conn.commit()
            self.load_data()
            messagebox.showinfo("成功", f"已删除 {len(selected)} 条记录")
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
        finally:
            cursor.close()
            conn.close()

    def show_details(self, event):
        """显示文章详细信息"""
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        article_id = item['values'][0]
        
        conn = sqlite3.connect('journals.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''SELECT * FROM articles WHERE id=?''', (article_id,))
            article = cursor.fetchone()
            
            # 获取领域信息
            cursor.execute('''SELECT field FROM article_fields WHERE article_id=?''', (article_id,))
            fields = [field[0] for field in cursor.fetchall()]
            fields_str = ', '.join(fields) if fields else '无'
            
            # 获取列名
            col_names = [desc[0] for desc in cursor.description]
            
            # 构建详情文本
            self.detail_text.delete(1.0, tk.END)
            for name, value in zip(col_names, article):
                self.detail_text.insert(tk.END, f"{name}: \n{value}\n\n")
            self.detail_text.insert(tk.END, f"领域: \n{fields_str}\n\n")
            
        except Exception as e:
            messagebox.showerror("错误", f"无法获取详情: {str(e)}")
        finally:
            cursor.close()
            conn.close()

    def export_csv(self):
        """导出为CSV文件"""
        from tkinter import filedialog
        import csv
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 写入列头
                writer.writerow([
                    'ID', '期刊', '原文标题', '中文标题',
                    '发布日期', '链接', '摘要', '总结',
                    '原始作者', '翻译作者'
                ])
                
                conn = sqlite3.connect('journals.db')
                cursor = conn.cursor()
                cursor.execute('''SELECT 
                    id, journal, original_title, translated_title,
                    publish_date, link, abstract, summary,
                    original_authors, translated_authors
                    FROM articles''')
                    
                for row in cursor.fetchall():
                    writer.writerow(row)
                    
                messagebox.showinfo("导出成功", f"数据已导出到: {file_path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = ArticleViewer(root)
    root.mainloop() 