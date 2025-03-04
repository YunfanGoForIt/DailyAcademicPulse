// 获取推荐论文
router.get('/recommended', async (req, res) => {
  try {
    const user = await User.findById(req.session.userId);
    const papers = await Paper.find({ 
      field: { $in: user.selectedFields },
      publishDate: { $gte: new Date(Date.now() - 7*24*60*60*1000) }
    }).sort('-publishDate').limit(20);

    res.json(papers);
  } catch (error) {
    res.status(500).send('服务器错误');
  }
}); 