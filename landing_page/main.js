// Scroll Animations
const observerOptions = {
  threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, observerOptions);

document.querySelectorAll('section').forEach(section => {
  section.classList.add('fade-in');
  observer.observe(section);
});

// OAuth Success Handling
const urlParams = new URLSearchParams(window.location.search);
const isConnected = urlParams.get('connected') === 'true';
const userEmail = urlParams.get('email');

if (isConnected && userEmail) {
  const authSection = document.getElementById('auth-section');
  const preferencesSection = document.getElementById('preferences-section');
  const connectionForm = document.getElementById('connection-form');
  const formTitle = document.getElementById('form-title');
  const emailInput = document.getElementById('user-email');
  const hiddenPrefEmail = document.getElementById('hidden-pref-email');

  if (authSection && preferencesSection && connectionForm && formTitle) {
    authSection.style.display = 'none';
    preferencesSection.style.display = 'block';
    formTitle.innerHTML = '✅ Calendar Connected';
    emailInput.value = userEmail;
    if (hiddenPrefEmail) hiddenPrefEmail.value = userEmail;
    
    // Smooth scroll to preferences
    preferencesSection.scrollIntoView({ behavior: 'smooth' });
  }
}

// Check for redirection back from preferences save
const isSaved = urlParams.get('saved') === 'true';
if (isSaved) {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('preferences-section').style.display = 'none';
    document.getElementById('connection-form').style.display = 'flex';
    document.getElementById('form-title').innerHTML = '🚀 ConvoSync AI Active';
}

// Form Submission Logic
const form = document.getElementById('connection-form');
const statusDiv = document.getElementById('form-status');
const submitBtn = document.getElementById('submit-btn');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const name = document.getElementById('user-name').value;
  const email = document.getElementById('user-email').value;
  const message = document.getElementById('user-message').value;

  statusDiv.innerHTML = 'Connecting to AI...';
  statusDiv.className = '';
  submitBtn.disabled = true;

  try {
    const response = await fetch('http://localhost:8000/send-to-ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, message })
    });

    const data = await response.json();

    if (response.ok) {
      statusDiv.innerHTML = '✅ Message delivered to ConvoSync AI!';
      statusDiv.className = 'status-success';
      form.reset();
    } else {
      throw new Error(data.detail || 'Failed to connect.');
    }
  } catch (error) {
    statusDiv.innerHTML = `❌ Error: ${error.message}`;
    statusDiv.className = 'status-error';
  } finally {
    submitBtn.disabled = false;
  }
});

// Simple Log
console.log('🚀 ConvoSync Landing Page Loaded with AI Connector');
