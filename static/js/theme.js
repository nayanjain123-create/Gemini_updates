/**
 * Gemini Insights - Theme Toggle Engine & Interactive Helper Script
 */

(function () {
  const THEME_KEY = 'gemini_updates_theme';

  function getStoredTheme() {
    return localStorage.getItem(THEME_KEY);
  }

  function setStoredTheme(theme) {
    localStorage.setItem(THEME_KEY, theme);
  }

  function getPreferredTheme() {
    const stored = getStoredTheme();
    if (stored) {
      return stored;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-bs-theme', theme);
    const themeBtnIcon = document.getElementById('theme-toggle-icon');
    const themeToggleBtn = document.getElementById('theme-toggle');

    if (themeBtnIcon) {
      if (theme === 'dark') {
        themeBtnIcon.className = 'bi bi-sun-fill text-warning';
        if (themeToggleBtn) themeToggleBtn.title = 'Switch to Light Mode';
      } else {
        themeBtnIcon.className = 'bi bi-moon-stars-fill text-primary';
        if (themeToggleBtn) themeToggleBtn.title = 'Switch to Dark Mode';
      }
    }
  }

  // Apply immediately before DOM rendering to prevent flashing
  const currentTheme = getPreferredTheme();
  applyTheme(currentTheme);

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(getPreferredTheme());

    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const activeTheme = document.documentElement.getAttribute('data-theme');
        const nextTheme = activeTheme === 'dark' ? 'light' : 'dark';
        setStoredTheme(nextTheme);
        applyTheme(nextTheme);
      });
    }

    // Auto dismiss Django alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
      setTimeout(() => {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        if (bsAlert) bsAlert.close();
      }, 5000);
    });
  });
})();
