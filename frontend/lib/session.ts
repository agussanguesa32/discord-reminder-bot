import 'server-only'
import { cookies } from 'next/headers'

const COOKIE_NAME = 'token'
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // 7 days
// Only mark the cookie as Secure when serving over HTTPS.
// On plain HTTP (local network, dev) the browser silently drops Secure cookies.
const IS_SECURE = (process.env.FRONTEND_URL ?? '').startsWith('https')

export async function getToken(): Promise<string | undefined> {
  const store = await cookies()
  return store.get(COOKIE_NAME)?.value
}

export async function setToken(token: string): Promise<void> {
  const store = await cookies()
  store.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: IS_SECURE,
    sameSite: 'lax',
    maxAge: COOKIE_MAX_AGE,
    path: '/',
  })
}

export async function clearToken(): Promise<void> {
  const store = await cookies()
  store.delete(COOKIE_NAME)
}
