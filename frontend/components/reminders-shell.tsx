'use client'

import { useState, useTransition } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import ReminderCard from '@/components/reminder-card'
import ReminderForm, { type ReminderFormData } from '@/components/reminder-form'
import LogoutButton from '@/components/logout-button'
import { createReminderAction } from '@/app/actions'
import type { Reminder, UserProfile } from '@/lib/api'

interface Props {
  user: UserProfile
  reminders: Reminder[]
}

export default function RemindersShell({ user, reminders }: Props) {
  const [createOpen, setCreateOpen] = useState(false)
  const [isPending, startTransition] = useTransition()

  function handleCreate(data: ReminderFormData) {
    startTransition(async () => {
      await createReminderAction(data)
      setCreateOpen(false)
    })
  }

  const active = reminders.filter((r) => r.active)
  const paused = reminders.filter((r) => !r.active)

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Top bar */}
      <header className="sticky top-0 z-10 border-b border-border bg-background/90 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">⏰</span>
            <span className="font-semibold text-sm tracking-tight">Reminder Bot</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground sm:block">
              @{user.username}
            </span>
            <LogoutButton />
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-6 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {active.length === 0 && paused.length === 0
              ? 'No reminders yet'
              : `${active.length} active${paused.length > 0 ? ` · ${paused.length} paused` : ''}`}
          </p>
          <Button size="sm" className="gap-1.5" onClick={() => setCreateOpen(true)}>
            <Plus className="size-3.5" />
            New reminder
          </Button>
        </div>

        {reminders.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-20 text-center">
            <p className="text-sm text-muted-foreground">
              Create your first reminder here or with{' '}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">/reminder</code>{' '}
              in Discord.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {active.length > 0 && (
              <div className="space-y-2">
                {active.map((r) => (
                  <ReminderCard key={r.id} reminder={r} userTimezone={user.timezone} />
                ))}
              </div>
            )}

            {paused.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <Separator className="flex-1" />
                  <span className="text-xs text-muted-foreground">Paused</span>
                  <Separator className="flex-1" />
                </div>
                {paused.map((r) => (
                  <ReminderCard key={r.id} reminder={r} userTimezone={user.timezone} />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>New reminder</DialogTitle>
          </DialogHeader>
          <ReminderForm
            userTimezone={user.timezone}
            isPending={isPending}
            onSubmit={handleCreate}
            onCancel={() => setCreateOpen(false)}
            submitLabel="Create reminder"
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}
