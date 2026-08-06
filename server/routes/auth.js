const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../db');
const { JWT_SECRET } = require('../middleware/requireAuth');

const router = express.Router();

const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax',
  maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
};

function issueSession(res, userId) {
  const token = jwt.sign({ userId }, JWT_SECRET, { expiresIn: '7d' });
  res.cookie('token', token, COOKIE_OPTIONS);
}

function isValidEmail(email) {
  return typeof email === 'string' && /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/.test(email.trim());
}

router.post('/signup', (req, res) => {
  const { email, username, password } = req.body;

  if (!email || !username || !password) {
    return res.status(400).json({ error: 'Email, username, and password are all required' });
  }
  if (!isValidEmail(email)) {
    return res.status(400).json({ error: 'Please enter a valid email address (e.g. name@example.com)' });
  }
  if (password.length < 6) {
    return res.status(400).json({ error: 'Password must be at least 6 characters' });
  }

  const existing = db
    .prepare('SELECT id FROM users WHERE email = ? OR username = ?')
    .get(email, username);
  if (existing) {
    return res.status(409).json({ error: 'An account with that email or username already exists' });
  }

  const passwordHash = bcrypt.hashSync(password, 10);
  const result = db
    .prepare('INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)')
    .run(email, username, passwordHash);

  issueSession(res, result.lastInsertRowid);
  res.status(201).json({ userId: result.lastInsertRowid, email, username });
});

router.post('/login', (req, res) => {
  const { identifier, password } = req.body;

  if (!identifier || !password) {
    return res.status(400).json({ error: 'Email/username and password are required' });
  }

  const user = db
    .prepare('SELECT * FROM users WHERE email = ? OR username = ?')
    .get(identifier, identifier);

  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    return res.status(401).json({ error: 'Incorrect email/username or password' });
  }

  issueSession(res, user.id);
  res.json({ userId: user.id, email: user.email, username: user.username });
});

router.post('/logout', (req, res) => {
  res.clearCookie('token');
  res.json({ ok: true });
});

module.exports = router;
