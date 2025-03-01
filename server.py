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
        query = "SELECT user_id, email, phone, field, password FROM subscriptions WHERE "
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
            if user[4] != hashed_password:
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
                'INSERT INTO subscriptions (user_id, email, phone, field, password) VALUES (?, ?, ?, ?, ?) ',
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