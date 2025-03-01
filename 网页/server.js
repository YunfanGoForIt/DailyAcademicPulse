const express = require('express');
const mongoose = require('mongoose');
const session = require('express-session');
const bcrypt = require('bcrypt');
const path = require('path');

const app = express();

// 连接MongoDB
mongoose.connect('mongodb://localhost:27017/academic_journal', {
    useNewUrlParser: true,
    useUnifiedTopology: true
});

// 中间件设置
app.use(express.json());
app.use(express.static('public'));
app.use(session({
    secret: 'your-secret-key',
    resave: false,
    saveUninitialized: false,
    cookie: { secure: false } // 开发环境下设为false
}));

// 导入模型
const User = require('./models/User');
const Paper = require('./models/Paper');

// 路由处理
app.post('/api/register', async (req, res) => {
    try {
        const { username, email, password, selectedFields } = req.body;
        
        // 检查用户名和邮箱是否已存在
        const existingUser = await User.findOne({ 
            $or: [{ username }, { email }] 
        });
        
        if (existingUser) {
            return res.status(400).json({ 
                error: '用户名或邮箱已被注册' 
            });
        }

        const hashedPassword = await bcrypt.hash(password, 10);
        const user = new User({
            username,
            email,
            password: hashedPassword,
            selectedFields
        });

        await user.save();
        res.status(201).json({ message: '注册成功' });
    } catch (error) {
        res.status(500).json({ error: '服务器错误' });
    }
});

app.post('/api/login', async (req, res) => {
    try {
        const { username, password } = req.body;
        const user = await User.findOne({ username });

        if (!user || !(await bcrypt.compare(password, user.password))) {
            return res.status(401).json({ error: '用户名或密码错误' });
        }

        req.session.userId = user._id;
        res.json({ 
            success: true, 
            username: user.username,
            selectedFields: user.selectedFields 
        });
    } catch (error) {
        res.status(500).json({ error: '服务器错误' });
    }
});

app.get('/api/papers', async (req, res) => {
    try {
        if (!req.session.userId) {
            return res.status(401).json({ error: '请先登录' });
        }

        const user = await User.findById(req.session.userId);
        const papers = await Paper.find({
            field: { $in: user.selectedFields }
        }).sort('-publishDate');

        res.json(papers);
    } catch (error) {
        res.status(500).json({ error: '服务器错误' });
    }
});

app.post('/api/logout', (req, res) => {
    req.session.destroy();
    res.json({ success: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
}); 