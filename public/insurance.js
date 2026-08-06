(async function loadProfile() {
  try {
    const { profile } = await api.get('/api/profile');
    if (!isProfileComplete(profile)) {
      window.location.href = 'onboarding.html';
      return;
    }
    if (hasInsurance(profile)) {
      window.location.href = 'done.html';
      return;
    }
    document.getElementById('location-display').textContent = profile.location;
  } catch (e) {
    window.location.href = 'signin.html';
  }
})();

document.getElementById('insurance-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorMsg = document.getElementById('error-msg');
  errorMsg.textContent = '';

  const insuranceProvider = document.getElementById('insurance-provider').value.trim();

  try {
    // Insurance must be saved BEFORE the profile hand-off to the AI, so
    // hospital search can filter out hospitals that don't accept it.
    await api.post('/api/ai/send-insurance', { insuranceProvider });
    await api.post('/api/ai/send-profile', {});
    window.location.href = 'done.html';
  } catch (err) {
    errorMsg.textContent = err.message;
  }
});
