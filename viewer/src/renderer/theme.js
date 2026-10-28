'use strict';

// Sets data-theme on the html element from the Mac's light or dark setting,
// before the first paint and again when the setting changes. main.js sets
// nativeTheme.themeSource, so --theme light or dark reaches the page through
// the same media query. The page loads this in its head as a classic script,
// so it adds one global, TremorTheme.

(function () {
  const query = window.matchMedia('(prefers-color-scheme: dark)');
  const listeners = [];

  function apply() {
    document.documentElement.dataset.theme = query.matches ? 'dark' : 'light';
  }

  // The tokens of design/colors.css that the canvases draw with.
  const TOKENS = {
    ink: '--ink',
    inkSecondary: '--ink-secondary',
    inkMuted: '--ink-muted',
    border: '--border',
    borderStrong: '--border-strong',
    borderControl: '--border-control',
    surfaceCard: '--surface-card',
    surfaceSunken: '--surface-sunken',
    link: '--link',
    warning: '--warning',
    success: '--success',
    fontSans: '--font-sans',
  };

  /** Read the current value of each token the canvases use. */
  function palette() {
    const style = getComputedStyle(document.documentElement);
    const values = { theme: document.documentElement.dataset.theme };
    for (const [key, name] of Object.entries(TOKENS)) {
      values[key] = style.getPropertyValue(name).trim();
    }
    return values;
  }

  /** Call back after each change of the setting, once data-theme has changed. */
  function onChange(callback) {
    listeners.push(callback);
  }

  apply();
  query.addEventListener('change', () => {
    apply();
    for (const callback of listeners) {
      callback();
    }
  });

  window.TremorTheme = { palette, onChange };
})();
