import tkinter as tk
from tkinter import ttk, messagebox
import argparse
import csv
import os
from typing import Dict, List
import mysql.connector  # 更新为使用MySQL
from config import FIELD_KEYWORDS, get_db_connection  # 更新为使用MySQL连接
import uuid

# 数据库文件
DB_FILE = "journals.db"

def load_subscriptions() -> List[Dict]:
    """加载所有订阅信息（新版）"""
    conn = get_db_connection()  # 使用MySQL连接
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, email, phone, field, password FROM subscriptions')
    subscriptions = []
    for row in cursor.fetchall():
        subscriptions.append({
            'user_id': row[0],
            'email': row[1],  # 存储邮箱
            'phone': row[2],  # 存储手机号
            'field': row[3],
            'password': row[4]
        })
    cursor.close()
    conn.close()
    return subscriptions

def add_subscription(email: str, phone: str, field: str) -> str:
    """新版添加订阅，返回生成的用户ID"""
    user_id = str(uuid.uuid4())  # 生成唯一UUID
    conn = get_db_connection()  # 使用MySQL连接
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subscriptions (user_id, email, phone, field, password)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, email, phone, field, ''))
        conn.commit()
        return user_id
    except mysql.connector.IntegrityError as e:
        print(f"添加失败: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

def update_subscription(user_id: str, email: str, phone: str, new_field: str) -> bool:
    """更新订阅领域"""
    subscriptions = load_subscriptions()
    updated = False
    
    for sub in subscriptions:
        if sub['user_id'] == user_id:
            sub['field'] = new_field
            updated = True
            break
    
    if updated:
        with open(EMAIL_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['user_id', 'email', 'phone', 'field'])
            writer.writeheader()
            writer.writerows([{'user_id': s['user_id'], 'email': s['email'], 'phone': s['phone'], 'field': s['field']} for s in subscriptions])
    return updated

def remove_subscription(user_id: str) -> bool:
    """取消订阅"""
    subscriptions = load_subscriptions()
    original_count = len(subscriptions)
    
    subscriptions = [s for s in subscriptions if s['user_id'] != user_id]
    
    if len(subscriptions) < original_count:
        with open(EMAIL_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['user_id', 'email', 'phone', 'field'])
            writer.writeheader()
            writer.writerows([{'user_id': s['user_id'], 'email': s['email'], 'phone': s['phone'], 'field': s['field']} for s in subscriptions])
        return True
    return False

class SubscriptionManager:
    def __init__(self, master):
        self.master = master
        master.title("科研论文订阅管理系统")
        master.geometry("800x600")
        
        # 样式配置
        self.style = ttk.Style()
        self.style.configure("Treeview", rowheight=25)
        self.style.configure("TButton", padding=6)
        
        # 主框架
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 订阅列表
        self.tree = ttk.Treeview(self.main_frame, columns=('user_id', 'email', 'phone', 'field', 'password'), show='headings')
        self.tree.heading('user_id', text='用户ID', anchor=tk.W)
        self.tree.heading('email', text='邮箱', anchor=tk.W)
        self.tree.heading('phone', text='手机号', anchor=tk.W)
        self.tree.heading('field', text='研究领域', anchor=tk.W)
        self.tree.heading('password', text='密码', anchor=tk.W)
        self.tree.column('user_id', width=150)
        self.tree.column('email', width=200)
        self.tree.column('phone', width=150)
        self.tree.column('field', width=150)
        self.tree.column('password', width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        # 操作面板
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, pady=5)
        
        # 添加订阅组件
        self.add_frame = ttk.LabelFrame(self.control_frame, text="添加/更新订阅")
        self.add_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.email_entry = tk.StringVar()
        self.phone_entry = tk.StringVar()
        self.field_var = tk.StringVar()
        
        ttk.Label(self.add_frame, text="邮箱:").grid(row=0, column=0, padx=2, pady=2, sticky=tk.W)
        self.email_entry = ttk.Entry(self.add_frame, textvariable=self.email_entry, width=30)
        self.email_entry.grid(row=0, column=1, padx=2, pady=2)
        
        ttk.Label(self.add_frame, text="手机号:").grid(row=0, column=2, padx=2, pady=2, sticky=tk.W)
        self.phone_entry = ttk.Entry(self.add_frame, textvariable=self.phone_entry, width=30)
        self.phone_entry.grid(row=0, column=3, padx=2, pady=2)
        
        ttk.Label(self.add_frame, text="领域:").grid(row=0, column=4, padx=2, pady=2, sticky=tk.W)
        self.field_combo = ttk.Combobox(self.add_frame, textvariable=self.field_var, 
                                      values=["无"] + list(FIELD_KEYWORDS.keys())[1:], state="readonly")
        self.field_combo.grid(row=0, column=5, padx=2, pady=2)
        
        self.add_btn = ttk.Button(self.add_frame, text="添加订阅", command=self.add_subscription)
        self.add_btn.grid(row=0, column=6, padx=5)
        
        self.update_btn = ttk.Button(self.add_frame, text="更新领域", command=self.update_subscription,
                                   state=tk.DISABLED)
        self.update_btn.grid(row=0, column=7, padx=5)
        
        # 删除订阅组件
        self.del_frame = ttk.LabelFrame(self.control_frame, text="删除订阅")
        self.del_frame.pack(side=tk.RIGHT, padx=5)
        
        self.del_btn = ttk.Button(self.del_frame, text="删除选中", command=self.remove_subscription,
                                 state=tk.DISABLED)
        self.del_btn.pack(padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(master, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 绑定事件
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.load_data()
    
    def load_data(self):
        """加载订阅数据（新版）"""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        subscriptions = load_subscriptions()
        for sub in subscriptions:
            self.tree.insert('', tk.END, values=(
                sub['user_id'],  # 仍然显示但不可编辑
                sub['email'],
                sub['phone'],
                sub['field'],
                sub['password']  # 显示密码
            ))
            
        self.status_var.set(f"已加载 {len(subscriptions)} 条订阅记录")
    
    def on_select(self, event):
        """选中行时更新表单"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            self.email_entry.delete(0, tk.END)
            self.email_entry.insert(0, item['values'][1])
            self.phone_entry.delete(0, tk.END)
            self.phone_entry.insert(0, item['values'][2])
            self.field_var.set(item['values'][3])
            self.update_btn.config(state=tk.NORMAL)
            self.del_btn.config(state=tk.NORMAL)
        else:
            self.update_btn.config(state=tk.DISABLED)
            self.del_btn.config(state=tk.DISABLED)
    
    def add_subscription(self):
        """添加新订阅（新版）"""
        email = self.email_entry.get().strip()
        phone = self.phone_entry.get().strip()
        field = self.field_var.get()
        
        if not email and not phone:
            messagebox.showerror("错误", "至少填写邮箱或手机号")
            return
            
        try:
            user_id = add_subscription(email, phone, field)
            if user_id:
                self.status_var.set(f"成功添加用户 {user_id}")
                self.load_data()
                self.clear_form()
            else:
                messagebox.showinfo("提示", "添加失败")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def update_subscription(self):
        """更新订阅领域"""
        user_id = self.tree.item(self.tree.selection()[0])['values'][0]
        email = self.email_entry.get().strip()
        phone = self.phone_entry.get().strip()
        new_field = self.field_var.get()
        
        if update_subscription(user_id, email, phone, new_field):
            self.load_data()
            self.status_var.set(f"成功更新 {user_id} 的领域为 {new_field}")
            self.clear_form()
        else:
            messagebox.showinfo("提示", "更新失败，用户ID不存在")
    
    def remove_subscription(self):
        """删除订阅"""
        selection = self.tree.selection()
        if not selection:
            return
            
        user_id = self.tree.item(selection[0])['values'][0]
        if messagebox.askyesno("确认", f"确定要删除用户 {user_id} 的订阅吗？"):
            conn = get_db_connection()  # 使用MySQL连接
            cursor = conn.cursor()
            cursor.execute('DELETE FROM subscriptions WHERE user_id=%s', (user_id,))
            conn.commit()
            conn.close()
            
            self.load_data()
            self.status_var.set(f"已删除订阅：{user_id}")
            self.clear_form()
    
    def clear_form(self):
        """清空输入表单"""
        self.email_entry.delete(0, tk.END)
        self.phone_entry.delete(0, tk.END)
        self.field_var.set('')
        self.tree.selection_remove(self.tree.selection())

def main_cli():
    """命令行接口"""
    parser = argparse.ArgumentParser(description="订阅管理命令行工具")
    subparsers = parser.add_subparsers(dest='command')
    
    # 添加订阅
    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('email', help="邮箱")
    add_parser.add_argument('phone', help="手机号")
    add_parser.add_argument('field', help="研究领域", choices=list(FIELD_KEYWORDS.keys()))
    
    # 更新领域
    update_parser = subparsers.add_parser('update')
    update_parser.add_argument('user_id', help="用户唯一ID")
    update_parser.add_argument('new_field', help="新研究领域", choices=list(FIELD_KEYWORDS.keys()))
    
    # 删除订阅
    del_parser = subparsers.add_parser('delete')
    del_parser.add_argument('user_id', help="用户唯一ID")
    
    # 列表查看
    subparsers.add_parser('list')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        user_id = add_subscription(args.email, args.phone, args.field)
        if user_id:
            print(f"成功添加：{user_id}")
        else:
            print("添加失败")
    elif args.command == 'update':
        if update_subscription(args.user_id, args.new_field):
            print(f"成功更新：{args.user_id} -> {args.new_field}")
        else:
            print("更新失败，用户ID不存在")
    elif args.command == 'delete':
        if remove_subscription(args.user_id):
            print(f"已删除：{args.user_id}")
        else:
            print("删除失败，用户ID不存在")
    elif args.command == 'list':
        subs = load_subscriptions()
        for sub in subs:
            print(f"{sub['user_id']:15} {sub['email']:20} {sub['phone']:15} {sub['field']:15}")
    else:
        parser.print_help()

if __name__ == "__main__":

    import sys
    if len(sys.argv) > 1:
        main_cli()
    else:
        root = tk.Tk()
        app = SubscriptionManager(root)
        root.mainloop() 