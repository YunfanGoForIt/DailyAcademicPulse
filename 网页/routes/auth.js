// 用户注册路由
router.post('/register', async (req, res) => {
  try {
    const { username, password, field } = req.body;
    const hashedPassword = await bcrypt.hash(password, 10);
    
    const user = new User({
      username,
      password: hashedPassword,
      selectedFields: field
    });

    await user.save();
    res.status(201).send('用户注册成功');
  } catch (error) {
    res.status(500).send('注册失败');
  }
});

// 用户登录路由
router.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const user = await User.findOne({ username });
  
  if (user && await bcrypt.compare(password, user.password)) {
    req.session.userId = user._id;
    res.json({ success: true, fields: user.selectedFields });
  } else {
    res.status(401).json({ success: false });
  }
}); 