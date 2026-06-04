import { type NextRequest, NextResponse } from 'next/server'
import { setToken } from '@/lib/session'

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token')

  if (!token) {
    return NextResponse.redirect(new URL('/?error=auth_failed', request.url))
  }

  await setToken(token)
  return NextResponse.redirect(new URL('/dashboard', request.url))
}
