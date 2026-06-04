import { type NextRequest, NextResponse } from 'next/server'
import { setToken } from '@/lib/session'

const SITE_URL = process.env.FRONTEND_URL ?? 'http://localhost:3000'

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token')

  if (!token) {
    return NextResponse.redirect(`${SITE_URL}/?error=auth_failed`)
  }

  await setToken(token)
  return NextResponse.redirect(`${SITE_URL}/dashboard`)
}
