const API_URL = process.env.API_URL ?? 'http://localhost:8000'

export interface Reminder {
  id: number
  user_id: string
  title: string
  description: string | null
  next_run: string
  repeat_type: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'interval'
  repeat_interval: number
  repeat_unit: string | null
  repeat_days: string | null
  advance_notice: number
  timezone: string
  active: boolean
  created_at: string
}

export interface UserProfile {
  discord_user_id: string
  username: string
  avatar: string | null
  timezone: string
}

export interface ReminderCreate {
  title: string
  description?: string
  next_run: string
  repeat_type?: string
  repeat_interval?: number
  repeat_unit?: string
  repeat_days?: string
  advance_notice?: number
  timezone?: string
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
    cache: 'no-store',
  })

  if (res.status === 204) return undefined as T

  const data = await res.json()
  if (!res.ok) throw new ApiError(res.status, data.detail ?? res.statusText)
  return data
}

export const api = {
  reminders: {
    list: (token: string, activeOnly = true) =>
      apiFetch<Reminder[]>(`/api/reminders?active_only=${activeOnly}`, token),
    get: (token: string, id: number) =>
      apiFetch<Reminder>(`/api/reminders/${id}`, token),
    create: (token: string, body: ReminderCreate) =>
      apiFetch<Reminder>('/api/reminders', token, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    update: (
      token: string,
      id: number,
      body: Partial<ReminderCreate & { active: boolean }>
    ) =>
      apiFetch<Reminder>(`/api/reminders/${id}`, token, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    delete: (token: string, id: number) =>
      apiFetch<void>(`/api/reminders/${id}`, token, { method: 'DELETE' }),
  },
  users: {
    me: (token: string) => apiFetch<UserProfile>('/api/users/me', token),
    updateTimezone: (token: string, timezone: string) =>
      apiFetch('/api/users/me/timezone', token, {
        method: 'PATCH',
        body: JSON.stringify({ timezone }),
      }),
  },
}
