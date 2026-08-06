document.getElementById('signin-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorMsg = document.getElementById('error-msg');
  errorMsg.textContent = '';

  const identifier = document.getElementById('identifier').value.trim();
  const password = document.getElementById('password').value;

  try {
    await api.post('/api/auth/login', { identifier, password });
    await routeToNextStep();
  } catch (err) {
    errorMsg.textContent = err.message;
  }
});
