const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/requireAuth');

const router = express.Router();

router.use(requireAuth);

router.get('/', (req, res) => {
  const profile = db
    .prepare(
      `SELECT name, gender, age, height_cm, weight_kg, location, insurance_provider
       FROM profiles WHERE user_id = ?`
    )
    .get(req.userId);

  if (!profile) {
    return res.json({ profile: null });
  }
  res.json({ profile });
});

router.post('/', (req, res) => {
  const { name, gender, age, heightCm, weightKg, location } = req.body;

  if (!name || !gender || !age || !heightCm || !weightKg || !location) {
    return res.status(400).json({
      error: 'name, gender, age, heightCm, weightKg, and location are all required',
    });
  }

  const existing = db.prepare('SELECT id FROM profiles WHERE user_id = ?').get(req.userId);

  if (existing) {
    db.prepare(
      `UPDATE profiles
       SET name = ?, gender = ?, age = ?, height_cm = ?, weight_kg = ?, location = ?,
           updated_at = datetime('now')
       WHERE user_id = ?`
    ).run(name, gender, age, heightCm, weightKg, location, req.userId);
  } else {
    db.prepare(
      `INSERT INTO profiles (user_id, name, gender, age, height_cm, weight_kg, location)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    ).run(req.userId, name, gender, age, heightCm, weightKg, location);
  }

  res.json({ ok: true });
});

module.exports = router;
