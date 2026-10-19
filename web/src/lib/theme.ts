export type Theme = 'light' | 'dark' | 'system'

const KEY = 'sf-theme'
const dark = matchMedia('(prefers-color-scheme: dark)')

export function getTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch { return 'system' }
}

function paint() {
  const t = getTheme()
  const on = t === 'dark' || (t === 'system' && dark.matches)
  document.documentElement.classList.toggle('dark', on)
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', on ? '#171512' : '#0e6460')
}

// The system listener only exists while the choice is System.
export function setTheme(t: Theme) {
  try { localStorage.setItem(KEY, t) } catch { /* private mode: applies for this visit only */ }
  dark.removeEventListener('change', paint)
  if (t === 'system') dark.addEventListener('change', paint)
  paint()
}

export const initTheme = () => setTheme(getTheme())
