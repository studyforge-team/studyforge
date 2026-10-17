// D1b service worker: shows the reminder the server pushed and opens its page when tapped.
// Only push and notificationclick: no fetch handler and nothing cached, so the app itself is unchanged.

// Only StudyForge's own pages: a push can never open another site.
function samePage(u) {
  try {
    const url = new URL(typeof u === 'string' && u.startsWith('/') ? u : '/', self.location.origin)
    return url.origin === self.location.origin ? url.href : self.location.origin + '/'
  } catch {
    return self.location.origin + '/'
  }
}

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let m = {}
  try {
    const d = event.data ? event.data.json() : {}
    m = d && typeof d === 'object' ? d : {} // never a silent push: iOS revokes subscriptions that skip a notification
  } catch {
    m = {}
  }
  const title = typeof m.title === 'string' && m.title ? m.title.slice(0, 100) : 'StudyForge'
  const body = typeof m.body === 'string' ? m.body.slice(0, 300) : ''
  const url = samePage(m.url)
  // tag: a newer reminder for the same page replaces the older one instead of stacking
  event.waitUntil(self.registration.showNotification(title, { body, icon: '/icon-192.png', tag: url, data: { url } }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const stored = event.notification.data && event.notification.data.url
  let url = self.location.origin + '/'
  try {
    if (typeof stored === 'string' && new URL(stored).origin === self.location.origin) url = stored // set by samePage above
  } catch {
    // keep the home page
  }
  event.waitUntil((async () => {
    for (const w of await self.clients.matchAll({ type: 'window', includeUncontrolled: true })) {
      if (new URL(w.url).origin !== self.location.origin) continue
      try {
        await w.focus()
        await w.navigate(url) // an open StudyForge tab goes to the page
        return
      } catch {
        // an uncontrolled tab cannot be navigated from here: open a new one below
      }
    }
    await self.clients.openWindow(url)
  })())
})
