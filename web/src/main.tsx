import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { captureShare } from './lib/share'
import { forgetOnSignOut } from './lib/pushReminders'
import { initTheme } from './lib/theme'

initTheme() // matches public/theme-init.js; adds the System listener
captureShare() // before the first render, so the app opens on the Notices page with the shared text
forgetOnSignOut() // D1b: signing out stops this browser's phone reminders

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
