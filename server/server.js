const path = require('path');
const express = require('express');
const cookieParser = require('cookie-parser');

require('./db'); // ensures tables exist on startup

const authRoutes = require('./routes/auth');
const profileRoutes = require('./routes/profile');
const contactsRoutes = require('./routes/contacts');
const aiRoutes = require('./routes/ai');

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.json());
app.use(cookieParser());
app.use(express.static(path.join(__dirname, '..', 'public')));

app.use('/api/auth', authRoutes);
app.use('/api/profile', profileRoutes);
app.use('/api/contacts', contactsRoutes);
app.use('/api/ai', aiRoutes);

app.listen(PORT, () => {
  console.log(`Health 360 server running at http://localhost:${PORT}`);
});
