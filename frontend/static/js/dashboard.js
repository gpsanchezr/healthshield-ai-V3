// HealthShield AI — Global JS utilities
const API = '/api';

function token() {
  return localStorage.getItem('access_token') || '';
}

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta?.content && meta.content !== 'NOTPROVIDED') return meta.content;

  const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : null;
}

function authHeaders(includeJson = true) {
  const headers = {
    'Authorization': 'Bearer ' + token()
  };
  if (includeJson) headers['Content-Type'] = 'application/json';

  const csrf = csrfToken();
  if (csrf) headers['X-CSRFToken'] = csrf;

  return headers;
}

function logout() {
  const refresh = localStorage.getItem('refresh_token');
  fetch(`${API}/auth/logout/`, {
    method: 'POST',
    headers: authHeaders(),
    credentials: 'same-origin',
    body: JSON.stringify({ refresh })
  }).finally(() => {
    localStorage.clear();
    window.location.href = '/login/';
  });
}

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-bs-theme') === 'dark';
  const newTheme = isDark ? 'light' : 'dark';
  html.setAttribute('data-bs-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  const icon = document.getElementById('themeIcon');
  const toggleIcon = document.getElementById('themeToggleIcon');
  if (icon) icon.className = isDark ? 'bi bi-moon-fill' : 'bi bi-sun-fill';
  if (toggleIcon) toggleIcon.textContent = isDark ? '🌙' : '☀️';
}

// Restore theme on load
(function () {
  const saved = localStorage.getItem('theme');
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const theme = saved || preferred;
  document.documentElement.setAttribute('data-bs-theme', theme);
  const icon = document.getElementById('themeIcon');
  const toggleIcon = document.getElementById('themeToggleIcon');
  if (icon) icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
  if (toggleIcon) toggleIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
})();

// Check if token is present, redirect to login if not
function requireAuth() {
  if (!token()) {
    window.location.href = '/login/';
    return false;
  }
  return true;
}

// Load user info into navbar
window.addEventListener('DOMContentLoaded', async () => {
  if (!token()) {
    if (!window.location.pathname.includes('/login/')) {
      window.location.href = '/login/';
    }
    return;
  }
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const el = document.getElementById('userName');
  if (el && user.nombre) el.textContent = user.nombre;

  // Check alerts
  try {
    const r = await fetch(`${API}/etl/alertas/`, { headers: authHeaders() });
    const d = await r.json();
    const count = d.count || (d.results && d.results.length) || 0;
    if (count > 0) {
      const el = document.getElementById('alertaCount');
      const banner = document.getElementById('alertaBanner');
      if (el) el.textContent = count;
      if (banner) banner.classList.remove('d-none');
    }
  } catch (e) { /* no alert info */ }
});
