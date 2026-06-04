import { clearToken } from '@/lib/session'

export async function POST() {
  await clearToken()
  return new Response(null, { status: 200 })
}
