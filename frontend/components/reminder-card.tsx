'use client'

import { useTransition, useState } from 'react'
import { Pencil, Trash2, PauseCircle, PlayCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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

function repeatLabel(r: Reminder): string {
  switch (r.repeat_type) {
    case 'none':     return 'One time'
    case 'daily':    return 'Daily'
    case 'monthly':  return 'Monthly'
    case 'yearly':   return 'Yearly'
    case 'weekly': {
      const map: Record<string, string> = {
        monday: 'Mo', tuesday: 'Tu', wednesday: 'We',
        thursday: 'Th', friday: 'Fr', saturday: 'Sa', sunday: 'Su',
      }
      const days = (r.repeat_days ?? '').split(',').map((d) => map[d.trim()] ?? d).join(' ')
      return `Weekly — ${days}`
    }
    case 'interval': return `Every ${r.repeat_interval} ${r.repeat_unit}`
    default:         return r.repeat_type
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
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
      <Card className={`transition-opacity ${!reminder.active ? 'opacity-50' : ''}`}>
        <CardHeader className="flex flex-row items-start justify-between gap-3 px-4 pt-4 pb-2">
          <div className="min-w-0 space-y-0.5">
            <p className="font-medium leading-snug truncate">{reminder.title}</p>
            {reminder.description && (
              <p className="text-xs text-muted-foreground">{reminder.description}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-0.5">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={handleToggle}
              disabled={isPending}
              title={reminder.active ? 'Pause' : 'Resume'}
            >
              {reminder.active
                ? <PauseCircle className="size-4 text-muted-foreground" />
                : <PlayCircle className="size-4 text-muted-foreground" />}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setEditOpen(true)}
              disabled={isPending}
              title="Edit"
            >
              <Pencil className="size-4 text-muted-foreground" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setDeleteOpen(true)}
              disabled={isPending}
              title="Delete"
            >
              <Trash2 className="size-4 text-muted-foreground" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="px-4 pb-4 space-y-1">
          <Countdown nextRun={reminder.next_run} />
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
            <span>{formatDate(reminder.next_run)}</span>
            <span>·</span>
            <span>{repeatLabel(reminder)}</span>
            {reminder.advance_notice > 0 && (
              <>
                <span>·</span>
                <span>{reminder.advance_notice}m notice</span>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete reminder?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">{reminder.title}</span>{' '}
              will be permanently deleted and cannot be recovered.
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

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-md max-h-[92vh] overflow-y-auto">
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
