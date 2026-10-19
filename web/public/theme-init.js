// Runs before the app so the saved theme paints with no flash. External file: the CSP allows script-src 'self' only.
try {
  var t = localStorage.getItem('sf-theme')
  if (t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark')
    document.querySelector('meta[name=theme-color]').content = '#171512'
  }
} catch (e) {}
