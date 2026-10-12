import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

// null when unconfigured: the app then behaves exactly as before, with no auth UI.
export const supabase = url && key ? createClient(url, key) : null

// gap: A7 supplies the Turnstile captchaToken (call setCaptchaToken from the widget)
let captchaToken: string | undefined
export const setCaptchaToken = (t?: string) => { captchaToken = t }
export const getCaptchaToken = () => captchaToken
