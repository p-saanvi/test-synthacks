const contactsContainer = document.getElementById('contacts-container');
const contactTemplate = document.getElementById('contact-template');

function addContactBlock() {
  const clone = contactTemplate.content.cloneNode(true);
  clone.querySelector('.remove-contact').addEventListener('click', (e) => {
    const block = e.target.closest('.contact-block');
    if (contactsContainer.children.length > 1) {
      block.remove();
    }
  });
  contactsContainer.appendChild(clone);
}

document.getElementById('add-contact').addEventListener('click', addContactBlock);

const sidebarContent = document.getElementById('profile-sidebar-content');

function updateSidebarFromForm() {
  const draftProfile = {
    name: document.getElementById('name').value.trim(),
    gender: document.getElementById('gender').value,
    age: document.getElementById('age').value,
    height_cm: document.getElementById('height').value,
    weight_kg: document.getElementById('weight').value,
    location: document.getElementById('location').value.trim(),
  };
  renderProfileSidebar(sidebarContent, { profile: draftProfile, contacts: collectContacts() });
}

document.getElementById('onboarding-form').addEventListener('input', updateSidebarFromForm);

function collectContacts() {
  return Array.from(contactsContainer.querySelectorAll('.contact-block')).map((block) => ({
    name: block.querySelector('.contact-name').value.trim(),
    relationship: block.querySelector('.contact-relationship').value.trim(),
    phone: block.querySelector('.contact-phone').value.trim(),
    email: block.querySelector('.contact-email').value.trim() || null,
  }));
}

// If this user already has a complete profile (e.g. they navigated back
// here directly), skip straight to wherever they actually still need to go.
(async function guardAlreadyOnboarded() {
  try {
    const { profile } = await api.get('/api/profile');
    if (isProfileComplete(profile)) {
      routeToNextStep();
    } else {
      addContactBlock();
    }
  } catch (e) {
    window.location.href = 'signin.html';
  }
})();

document.getElementById('onboarding-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorMsg = document.getElementById('error-msg');
  errorMsg.textContent = '';

  const name = document.getElementById('name').value.trim();
  const gender = document.getElementById('gender').value;
  const age = document.getElementById('age').value;
  const height = document.getElementById('height').value;
  const weight = document.getElementById('weight').value;
  const location = document.getElementById('location').value.trim();

  if (!name || !gender || !age || !height || !weight || !location) {
    errorMsg.textContent = 'Please fill in every personal info field.';
    return;
  }

  const contacts = collectContacts();
  if (contacts.length === 0 || contacts.some((c) => !c.name || !c.relationship || !c.phone)) {
    errorMsg.textContent = 'Please fill in name, relationship, and phone for every contact.';
    return;
  }
  if (contacts.some((c) => !isValidPhone(c.phone))) {
    errorMsg.textContent = 'Phone numbers can only contain digits (e.g. 555-123-4567).';
    return;
  }
  if (contacts.some((c) => c.email && !isValidEmail(c.email))) {
    errorMsg.textContent = 'Please enter a valid contact email address (e.g. name@example.com).';
    return;
  }

  try {
    await api.post('/api/profile', {
      name: document.getElementById('name').value.trim(),
      gender: document.getElementById('gender').value,
      age: Number(document.getElementById('age').value),
      heightCm: Number(document.getElementById('height').value),
      weightKg: Number(document.getElementById('weight').value),
      location: document.getElementById('location').value.trim(),
    });
    await api.post('/api/contacts', { contacts });
    window.location.href = 'insurance.html';
  } catch (err) {
    errorMsg.textContent = err.message;
  }
});
