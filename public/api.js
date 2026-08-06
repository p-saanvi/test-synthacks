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

// Requires an @ and a proper domain suffix (e.g. .com, .org, .in) — rejects
// anything without both, so junk text can't be saved as an email address.
function isValidEmail(email) {
  if (typeof email !== 'string') return false;
  return /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/.test(email.trim());
}

// Digits only (plus common formatting characters like +, -, spaces, parens) —
// rejects letters so a phone field can't be filled with junk text.
function isValidPhone(phone) {
  if (typeof phone !== 'string') return false;
  const trimmed = phone.trim();
  if (!/^\+?[0-9\s()\-]+$/.test(trimmed)) return false;
  const digitCount = (trimmed.match(/\d/g) || []).length;
  return digitCount >= 7 && digitCount <= 15;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

// Renders the "Your Profile" side panel from whatever profile/contacts data
// is available — used on onboarding (live draft as the user types) and on
// insurance/done (the saved record) so users can always see what's on file.
function renderProfileSidebar(container, { profile, contacts }) {
  const hasAnything =
    profile && (profile.name || profile.location || profile.age || profile.gender);

  if (!hasAnything) {
    container.innerHTML = '<p class="empty-hint">Fill in the form to see your profile here.</p>';
    return;
  }

  const rows = [
    ['Name', profile.name],
    ['Gender', profile.gender],
    ['Age', profile.age],
    ['Height', profile.height_cm ? `${profile.height_cm} cm` : ''],
    ['Weight', profile.weight_kg ? `${profile.weight_kg} kg` : ''],
    ['Location', profile.location],
    ['Insurance', profile.insurance_provider],
  ].filter(([, value]) => value);

  let html =
    '<dl>' +
    rows.map(([label, value]) => `<dt>${label}</dt><dd>${escapeHtml(value)}</dd>`).join('') +
    '</dl>';

  const namedContacts = (contacts || []).filter((c) => c.name || c.phone);
  if (namedContacts.length) {
    html += '<dt class="contacts-heading">Emergency Contacts</dt>';
    html += namedContacts
      .map(
        (c) => `
        <div class="contact-item">
          <strong>${escapeHtml(c.name)}</strong>${c.relationship ? ` (${escapeHtml(c.relationship)})` : ''}<br/>
          ${escapeHtml(c.phone)}${c.email ? ' · ' + escapeHtml(c.email) : ''}
        </div>`
      )
      .join('');
  }

  container.innerHTML = html;
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
