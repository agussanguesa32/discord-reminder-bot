import { redirect } from 'next/navigation'
import { getToken } from '@/lib/session'
import { api } from '@/lib/api'
import RemindersShell from '@/components/reminders-shell'

export const dynamic = 'force-dynamic'

export default async function DashboardPage() {
  const token = await getToken()
  if (!token) redirect('/')

  const [user, reminders] = await Promise.all([
    api.users.me(token).catch(() => null),
    api.reminders.list(token, false).catch(() => []),
  ])

  if (!user) redirect('/')

  return <RemindersShell user={user} reminders={reminders} />
}
