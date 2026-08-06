async function apiRequest(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    credentials: 'same-origin',
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }

  if (!res.ok) {
    const message = (data && data.error) || 'Something went wrong. Please try again.';
    throw new Error(message);
  }
  return data;
}

const api = {
  get: (url) => apiRequest('GET', url),
  post: (url, body) => apiRequest('POST', url, body),
};

// Profile completeness is what decides whether onboarding/insurance get
// skipped for a returning user — every already-saved field lives here.
function isProfileComplete(profile) {
  return Boolean(
    profile &&
      profile.name &&
      profile.gender &&
      profile.age &&
      profile.height_cm &&
      profile.weight_kg &&
      profile.location
  );
}

function hasInsurance(profile) {
  return Boolean(profile && profile.insurance_provider);
}

// Sends the logged-in user to whichever page reflects what's still missing,
// so nothing already stored in the database gets asked again.
async function routeToNextStep() {
  let profile = null;
  try {
    const data = await api.get('/api/profile');
    profile = data.profile;
  } catch (e) {
    window.location.href = 'signin.html';
    return;
  }

  if (!isProfileComplete(profile)) {
    window.location.href = 'onboarding.html';
  } else if (!hasInsurance(profile)) {
    window.location.href = 'insurance.html';
  } else {
    window.location.href = 'done.html';
  }
}
