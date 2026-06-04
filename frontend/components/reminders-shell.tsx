'use client'

import { useState, useTransition } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
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
    <div className="mx-auto max-w-xl w-full px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">Signed in as</p>
          <p className="font-semibold">@{user.username}</p>
        </div>
        <LogoutButton />
      </div>

      <Separator />

      {/* Reminders list */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Reminders
          </h1>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="gap-1.5">
                <Plus className="size-3.5" />
                New
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>New reminder</DialogTitle>
              </DialogHeader>
              <ReminderForm
                userTimezone={user.timezone}
                isPending={isPending}
                onSubmit={handleCreate}
                onCancel={() => setCreateOpen(false)}
                submitLabel="Create"
              />
            </DialogContent>
          </Dialog>
        </div>

        {reminders.length === 0 ? (
          <div className="rounded-lg border border-dashed py-16 text-center text-sm text-muted-foreground">
            No reminders yet.<br />
            Create one here or use <code className="font-mono">/reminder</code> in Discord.
          </div>
        ) : (
          <div className="space-y-2">
            {active.length > 0 && (
              <ul className="divide-y divide-border rounded-lg border">
                {active.map((r) => (
                  <ReminderCard key={r.id} reminder={r} userTimezone={user.timezone} />
                ))}
              </ul>
            )}

            {paused.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground px-1">Paused</p>
                <ul className="divide-y divide-border rounded-lg border">
                  {paused.map((r) => (
                    <ReminderCard key={r.id} reminder={r} userTimezone={user.timezone} />
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
