const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/requireAuth');

const router = express.Router();

router.use(requireAuth);

router.get('/', (req, res) => {
  const contacts = db
    .prepare(
      `SELECT id, name, relationship, phone, email
       FROM emergency_contacts WHERE user_id = ? ORDER BY id`
    )
    .all(req.userId);
  res.json({ contacts });
});

router.post('/', (req, res) => {
  const { contacts } = req.body;

  if (!Array.isArray(contacts) || contacts.length === 0) {
    return res.status(400).json({ error: 'At least one emergency contact is required' });
  }

  for (const contact of contacts) {
    if (!contact.name || !contact.relationship || !contact.phone) {
      return res.status(400).json({
        error: 'Each contact needs a name, relationship, and phone number',
      });
    }
  }

  const insert = db.prepare(
    `INSERT INTO emergency_contacts (user_id, name, relationship, phone, email)
     VALUES (?, ?, ?, ?, ?)`
  );

  // Replace any existing contacts for this user with the newly submitted set.
  db.exec('BEGIN');
  try {
    db.prepare('DELETE FROM emergency_contacts WHERE user_id = ?').run(req.userId);
    for (const c of contacts) {
      insert.run(req.userId, c.name, c.relationship, c.phone, c.email || null);
    }
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }

  res.json({ ok: true });
});

module.exports = router;
