// D1b: turn phone reminders on or off for this browser. The server sends them (api/app/push.py);
// public/sw.js shows them. iPhone: only from the Home Screen app (iOS 16.4+).
import { deletePushSubscription, getPushKey, savePushSubscription } from '@/api/client'
import { PlainError } from '@/lib/errors'
import { supabase } from '@/lib/supabase'

export const pushSupported = (): boolean =>
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

const fromB64u = (s: string): Uint8Array<ArrayBuffer> => {
  const b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4))
  return Uint8Array.from(b, (c) => c.charCodeAt(0))
}
const sameKey = (sub: PushSubscription, key: Uint8Array) => {
  const k = sub.options.applicationServerKey
  return !!k && new Uint8Array(k).every((x, i) => x === key[i]) && k.byteLength === key.length
}

async function current(): Promise<PushSubscription | null> {
  const reg = await navigator.serviceWorker.getRegistration('/')
  return reg ? reg.pushManager.getSubscription() : null
}

export async function pushIsOn(): Promise<boolean> {
  if (!pushSupported() || Notification.permission !== 'granted') return false
  return !!(await current())
}

// Done before the tap where possible (iOS wants the subscribe to follow the tap closely):
// the server's key and the service worker registration.
export async function prepare(): Promise<{ key: Uint8Array<ArrayBuffer>; reg: ServiceWorkerRegistration }> {
  const key = fromB64u(await getPushKey()) // 503 here: the server has no keys yet
  const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
  await navigator.serviceWorker.ready
  return { key, reg }
}

export async function turnOn(ready?: Promise<{ key: Uint8Array<ArrayBuffer>; reg: ServiceWorkerRegistration }>): Promise<void> {
  if (Notification.permission === 'denied') throw new PlainError('Notifications are blocked for StudyForge. Allow them in the browser’s site settings, then try again.')
  if ((await Notification.requestPermission()) !== 'granted') throw new PlainError('Phone reminders need permission to show notifications.')
  const { key, reg } = await (ready ?? prepare())
  let sub = await reg.pushManager.getSubscription()
  if (sub && !sameKey(sub, key)) { // the server's keys changed: drop the old device record too
    await deletePushSubscription(sub.endpoint).catch(() => {})
    await sub.unsubscribe()
    sub = null
  }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })
  await savePushSubscription(sub.toJSON())
}

export async function turnOff(): Promise<void> {
  const sub = await current()
  if (!sub) return
  await deletePushSubscription(sub.endpoint) // first, so the server stops sending even if unsubscribe fails
  await sub.unsubscribe().catch(() => {}) // the server already forgot it; nothing more to tell the student
}

// Fallback for a session that ends without the Sign out button (e.g. an expired refresh token):
// this browser must stop showing that account's reminders. The token is gone by then, so the
// subscription is dropped here only; the server forgets the device on the push service's next 410.
// The Sign out button turns reminders off on the server first (components/Auth.tsx).
export function forgetOnSignOut(): void {
  if (!supabase || !pushSupported()) return
  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT') void current().then((sub) => sub?.unsubscribe()).catch(() => {})
  })
}
