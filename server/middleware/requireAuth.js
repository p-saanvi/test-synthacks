const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'health360-dev-secret-change-in-production';

function requireAuth(req, res, next) {
  const token = req.cookies && req.cookies.token;
  if (!token) {
    return res.status(401).json({ error: 'Not signed in' });
  }
  try {
    const payload = jwt.verify(token, JWT_SECRET);
    req.userId = payload.userId;
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Session expired, please sign in again' });
  }
}

module.exports = { requireAuth, JWT_SECRET };
