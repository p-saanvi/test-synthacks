const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/requireAuth');

const router = express.Router();

router.use(requireAuth);

// The AI triage app (Flask, Python) — symptom analysis via qwen_triage.py
// (Qwen3-14B) and hospital contact. It shares this same SQLite database
// (server/health360.db), so it reads a user's profile directly instead of
// this endpoint needing to push data to it over HTTP.
const TRIAGE_APP_URL = process.env.TRIAGE_APP_URL || 'http://localhost:5000';

/**
 * send-insurance — saves the insurance provider. Called before send-profile
 * so the AI triage app always has insurance on file before it needs it
 * (hospital selection there isn't insurance-filtered yet, but this ordering
 * keeps the data available for whenever that's added).
 */
router.post('/send-insurance', (req, res) => {
  const { insuranceProvider } = req.body;

  if (!insuranceProvider) {
    return res.status(400).json({ error: 'insuranceProvider is required' });
  }

  const existing = db.prepare('SELECT id FROM profiles WHERE user_id = ?').get(req.userId);
  if (!existing) {
    return res.status(400).json({ error: 'Complete onboarding before adding insurance' });
  }

  db.prepare(
    `UPDATE profiles SET insurance_provider = ?, updated_at = datetime('now') WHERE user_id = ?`
  ).run(insuranceProvider, req.userId);

  console.log('[AI SLOT] send-insurance ->', { userId: req.userId, insuranceProvider });
  res.json({ ok: true });
});

/**
 * send-profile — called after insurance is saved. Confirms the profile is
 * complete and hands back the URL to the AI triage app; it reads this same
 * user's profile straight out of the shared database (see
 * database/db.py / qwen_triage.py on the Python side) rather than this
 * endpoint pushing the data over HTTP.
 */
router.post('/send-profile', (req, res) => {
  const profile = db
    .prepare(
      `SELECT name, gender, age, height_cm, weight_kg, location, insurance_provider
       FROM profiles WHERE user_id = ?`
    )
    .get(req.userId);

  if (!profile) {
    return res.status(400).json({ error: 'Complete onboarding before submitting to the AI' });
  }

  const contacts = db
    .prepare('SELECT name, relationship, phone, email FROM emergency_contacts WHERE user_id = ?')
    .all(req.userId);

  console.log('[AI SLOT] send-profile ->', { userId: req.userId, ...profile, emergencyContacts: contacts });

  res.json({ ok: true, triageUrl: `${TRIAGE_APP_URL}/?user_id=${req.userId}` });
});

module.exports = router;
