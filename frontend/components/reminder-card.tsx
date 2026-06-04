'use client'

import { useTransition, useState } from 'react'
import { Pencil, Trash2, PauseCircle, PlayCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import Countdown from '@/components/countdown'
import ReminderForm, { type ReminderFormData } from '@/components/reminder-form'
import { deleteReminderAction, toggleReminderAction, updateReminderAction } from '@/app/actions'
import type { Reminder } from '@/lib/api'

function formatRepeatBadge(r: Reminder): string {
  switch (r.repeat_type) {
    case 'none': return 'Once'
    case 'daily': return 'Daily'
    case 'monthly': return 'Monthly'
    case 'yearly': return 'Yearly'
    case 'weekly': {
      const short: Record<string, string> = {
        monday: 'Mo', tuesday: 'Tu', wednesday: 'We',
        thursday: 'Th', friday: 'Fr', saturday: 'Sa', sunday: 'Su',
      }
      const days = (r.repeat_days ?? '').split(',').map((d) => short[d.trim()] ?? d).join(' ')
      return `Weekly · ${days}`
    }
    case 'interval':
      return `Every ${r.repeat_interval} ${r.repeat_unit}`
    default:
      return r.repeat_type
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function ReminderCard({
  reminder,
  userTimezone,
}: {
  reminder: Reminder
  userTimezone: string
}) {
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [isPending, startTransition] = useTransition()

  function handleDelete() {
    startTransition(async () => {
      await deleteReminderAction(reminder.id)
      setDeleteOpen(false)
    })
  }

  function handleToggle() {
    startTransition(() => toggleReminderAction(reminder.id, !reminder.active))
  }

  function handleEdit(data: ReminderFormData) {
    startTransition(async () => {
      await updateReminderAction(reminder.id, data)
      setEditOpen(false)
    })
  }

  return (
    <>
      <li
        className={`px-4 py-3 space-y-2 transition-opacity ${
          !reminder.active ? 'opacity-50' : ''
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-medium text-sm truncate">{reminder.title}</span>
            {!reminder.active && (
              <Badge variant="secondary" className="text-xs shrink-0">paused</Badge>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={handleToggle}
              disabled={isPending}
              title={reminder.active ? 'Pause' : 'Resume'}
            >
              {reminder.active
                ? <PauseCircle className="size-3.5 text-muted-foreground" />
                : <PlayCircle className="size-3.5 text-muted-foreground" />}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setEditOpen(true)}
              disabled={isPending}
              title="Edit"
            >
              <Pencil className="size-3.5 text-muted-foreground" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setDeleteOpen(true)}
              disabled={isPending}
              title="Delete"
            >
              <Trash2 className="size-3.5 text-muted-foreground" />
            </Button>
          </div>
        </div>

        {reminder.description && (
          <p className="text-xs text-muted-foreground">{reminder.description}</p>
        )}

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <Countdown nextRun={reminder.next_run} />
          <span className="text-muted-foreground/40">·</span>
          <span className="text-muted-foreground">{formatDate(reminder.next_run)}</span>
          <span className="text-muted-foreground/40">·</span>
          <span className="text-muted-foreground">{formatRepeatBadge(reminder)}</span>
          {reminder.advance_notice > 0 && (
            <>
              <span className="text-muted-foreground/40">·</span>
              <span className="text-muted-foreground">{reminder.advance_notice}m notice</span>
            </>
          )}
        </div>
      </li>

      {/* Delete dialog */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete reminder?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">{reminder.title}</span> will be permanently deleted.
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isPending ? 'Deleting…' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit reminder</DialogTitle>
          </DialogHeader>
          <ReminderForm
            defaultValues={{
              ...reminder,
              description: reminder.description ?? undefined,
              repeat_unit: reminder.repeat_unit ?? undefined,
              repeat_days: reminder.repeat_days ?? undefined,
            }}
            userTimezone={userTimezone}
            isPending={isPending}
            onSubmit={handleEdit}
            onCancel={() => setEditOpen(false)}
            submitLabel="Save changes"
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
