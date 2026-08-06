const overlay = document.getElementById('terms-overlay');
const panel = document.getElementById('terms-panel');
const fields = document.getElementById('signup-fields');
const termsStatus = document.getElementById('terms-status');

function closePanel() {
  overlay.classList.remove('open');
  panel.classList.remove('open');
}

document.getElementById('accept-terms').addEventListener('click', () => {
  closePanel();
  fields.disabled = false;
  termsStatus.textContent = 'Thanks — you accepted the Terms & Conditions.';
});

document.getElementById('decline-terms').addEventListener('click', () => {
  window.location.href = 'index.html';
});

document.getElementById('signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorMsg = document.getElementById('error-msg');
  errorMsg.textContent = '';

  const email = document.getElementById('email').value.trim();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const confirmPassword = document.getElementById('confirm-password').value;

  if (password !== confirmPassword) {
    errorMsg.textContent = 'Passwords do not match.';
    return;
  }

  try {
    await api.post('/api/auth/signup', { email, username, password });
    window.location.href = 'onboarding.html';
  } catch (err) {
    errorMsg.textContent = err.message;
  }
});
