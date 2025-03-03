const mongoose = require('mongoose');

const paperSchema = new mongoose.Schema({
  title: { type: String, required: true },
  authors: [String],
  abstract: String,
  journal: String,
  publishDate: Date,
  field: { 
    type: String,
    enum: ['计算机科学', '医学', '工程学', '物理学', '化学', '生物学'],
    required: true
  }
});

module.exports = mongoose.model('Paper', paperSchema); 