const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
    username: { 
        type: String, 
        required: true,
        unique: true 
    },
    email: {
        type: String,
        required: true,
        unique: true
    },
    password: { 
        type: String, 
        required: true 
    },
    selectedFields: [{ 
        type: String,
        enum: ['计算机科学', '医学', '工程学', '物理学', '化学', '生物学']
    }],
    createdAt: {
        type: Date,
        default: Date.now
    }
});

module.exports = mongoose.model('User', userSchema); 