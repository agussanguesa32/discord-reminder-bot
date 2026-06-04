'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { getToken } from '@/lib/session'
import { api } from '@/lib/api'

async function requireToken() {
  const token = await getToken()
  if (!token) redirect('/')
  return token
}

export async function createReminderAction(data: {
  title: string
  description: string
  next_run: string
  repeat_type: string
  repeat_interval: number
  repeat_unit: string | null
  repeat_days: string | null
  advance_notice: number
  timezone: string
}) {
  const token = await requireToken()
  await api.reminders.create(token, {
    title: data.title,
    description: data.description || undefined,
    next_run: data.next_run,
    repeat_type: data.repeat_type,
    repeat_interval: data.repeat_interval,
    repeat_unit: data.repeat_unit ?? undefined,
    repeat_days: data.repeat_days ?? undefined,
    advance_notice: data.advance_notice,
    timezone: data.timezone,
  })
  revalidatePath('/dashboard')
}

export async function updateReminderAction(
  id: number,
  data: {
    title?: string
    description?: string
    next_run?: string
    repeat_type?: string
    repeat_interval?: number
    repeat_unit?: string | null
    repeat_days?: string | null
    advance_notice?: number
    timezone?: string
  }
) {
  const token = await requireToken()
  const { repeat_unit, repeat_days, ...rest } = data
  await api.reminders.update(token, id, {
    ...rest,
    repeat_unit: repeat_unit ?? undefined,
    repeat_days: repeat_days ?? undefined,
  })
  revalidatePath('/dashboard')
}

export async function deleteReminderAction(id: number) {
  const token = await requireToken()
  await api.reminders.delete(token, id)
  revalidatePath('/dashboard')
}

export async function toggleReminderAction(id: number, active: boolean) {
  const token = await requireToken()
  await api.reminders.update(token, id, { active })
  revalidatePath('/dashboard')
}
