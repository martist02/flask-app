// server.js
const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const session = require('express-session');
const crypto = require('crypto');
const bodyParser = require('body-parser');
const { Pool } = require('pg');

const app = express();
const server = http.createServer(app);
const io = socketIO(server);

// PostgreSQL connection configuration
const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

// Middleware
const sessionMiddleware = session({
    secret: process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
    resave: false,
    saveUninitialized: false,
    cookie: {
        secure: process.env.NODE_ENV === 'production',
        maxAge: 24 * 60 * 60 * 1000 // 24 hours
    }
});

app.use(sessionMiddleware);
app.use(bodyParser.json());
app.use(express.static('public'));

// Socket.IO middleware
io.use((socket, next) => {
    sessionMiddleware(socket.request, {}, next);
});

// Authentication middleware
const authenticate = async (req, res, next) => {
    if (!req.session.userId) {
        return res.status(401).json({ error: 'ไม่ได้เข้าสู่ระบบ' });
    }
    next();
};

// Routes
app.post('/api/login', async (req, res) => {
    const { username, password } = req.body;
    try {
        const result = await pool.query(
            'SELECT * FROM users WHERE username = $1',
            [username]
        );

        const user = result.rows[0];
        if (!user || !verifyPassword(password, user.password_hash)) {
            return res.status(401).json({ error: 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง' });
        }

        req.session.userId = user.id;
        res.json({
            id: user.id,
            name: user.name,
            role: user.role
        });
    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ error: 'เกิดข้อผิดพลาดในการเข้าสู่ระบบ' });
    }
});

app.post('/api/update-location', authenticate, async (req, res) => {
    const { userId, latitude, longitude, timestamp } = req.body;
    try {
        await pool.query(
            'INSERT INTO location_history (user_id, latitude, longitude, timestamp) VALUES ($1, $2, $3