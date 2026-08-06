const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/requireAuth');

const router = express.Router();

router.use(requireAuth);

/**
 * Placeholder "AI slot" — send-insurance.
 * Real integration (planned: an open-source model like Qwen-12B) plugs in
 * here later. For now this just saves the insurance provider and logs what
 * would be sent to the AI.
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
 * Placeholder "AI slot" — send-profile.
 * Called AFTER insurance is saved, so the payload always includes insurance.
 * This is the hand-off point where the real AI should search for nearby
 * hospitals and filter out any hospital that does NOT accept the user's
 * insurance — only in-network hospitals should ever be returned.
 * Expected eventual response shape:
 *   { hospitals: [{ name, address, distanceKm, acceptsInsurance }, ...] }
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

  const payload = { userId: req.userId, ...profile, emergencyContacts: contacts };
  console.log('[AI SLOT] send-profile ->', payload);

  // Placeholder response until the real AI is plugged in.
  res.json({ ok: true, hospitals: [] });
});

module.exports = router;
