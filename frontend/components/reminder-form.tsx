'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import DateTimePicker from '@/components/date-time-picker'

const WEEKDAYS = [
  { value: 'monday',    label: 'Mon' },
  { value: 'tuesday',   label: 'Tue' },
  { value: 'wednesday', label: 'Wed' },
  { value: 'thursday',  label: 'Thu' },
  { value: 'friday',    label: 'Fri' },
  { value: 'saturday',  label: 'Sat' },
  { value: 'sunday',    label: 'Sun' },
]

const REPEAT_OPTIONS = [
  { value: 'none',     label: 'Once' },
  { value: 'daily',    label: 'Daily' },
  { value: 'weekly',   label: 'Weekly' },
  { value: 'monthly',  label: 'Monthly' },
  { value: 'yearly',   label: 'Yearly' },
  { value: 'interval', label: 'Custom' },
]

const INTERVAL_UNITS = ['minutes', 'hours', 'days', 'weeks']

const NOTICE_OPTIONS = [
  { value: '0',   label: 'Off' },
  { value: '5',   label: '5m' },
  { value: '15',  label: '15m' },
  { value: '30',  label: '30m' },
  { value: '60',  label: '1h' },
  { value: '120', label: '2h' },
]

export interface ReminderFormData {
  title: string
  description: string
  next_run: string
  repeat_type: string
  repeat_interval: number
  repeat_unit: string | null
  repeat_days: string | null
  advance_notice: number
  timezone: string
}

interface Props {
  defaultValues?: Partial<ReminderFormData>
  userTimezone: string
  isPending: boolean
  onSubmit: (data: ReminderFormData) => void
  onCancel: () => void
  submitLabel?: string
}

export default function ReminderForm({
  defaultValues,
  userTimezone,
  isPending,
  onSubmit,
  onCancel,
  submitLabel = 'Save',
}: Props) {
  const [title, setTitle] = useState(defaultValues?.title ?? '')
  const [description, setDescription] = useState(defaultValues?.description ?? '')
  const [dateTime, setDateTime] = useState<Date | undefined>(
    defaultValues?.next_run ? new Date(defaultValues.next_run) : undefined
  )
  const [repeatType, setRepeatType] = useState(defaultValues?.repeat_type ?? 'none')
  const [repeatInterval, setRepeatInterval] = useState(defaultValues?.repeat_interval ?? 1)
  const [repeatUnit, setRepeatUnit] = useState(defaultValues?.repeat_unit ?? 'hours')
  const [repeatDays, setRepeatDays] = useState<string[]>(
    defaultValues?.repeat_days
      ? defaultValues.repeat_days.split(',').map((d) => d.trim())
      : []
  )
  const [advanceNotice, setAdvanceNotice] = useState(
    String(defaultValues?.advance_notice ?? 0)
  )
  const [error, setError] = useState<string | null>(null)

  function toggleDay(day: string) {
    setRepeatDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    )
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!title.trim()) return setError('Title is required.')
    if (!dateTime) return setError('Pick a date and time.')
    if (repeatType === 'weekly' && repeatDays.length === 0)
      return setError('Select at least one day.')

    onSubmit({
      title: title.trim(),
      description: description.trim(),
      next_run: dateTime.toISOString(),
      repeat_type: repeatType,
      repeat_interval: repeatType === 'interval' ? repeatInterval : 0,
      repeat_unit: repeatType === 'interval' ? repeatUnit : null,
      repeat_days: repeatType === 'weekly' ? repeatDays.join(',') : null,
      advance_notice: Number(advanceNotice),
      timezone: userTimezone,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Title */}
      <div className="space-y-1.5">
        <Label htmlFor="title">What do you need to remember?</Label>
        <Input
          id="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Doctor appointment"
          autoFocus
        />
      </div>

      {/* Description */}
      <div className="space-y-1.5">
        <Label htmlFor="desc">
          Details{' '}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Textarea
          id="desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Any extra details..."
          rows={2}
          className="resize-none"
        />
      </div>

      <Separator />

      {/* Date & Time */}
      <div className="space-y-2">
        <Label>When?</Label>
        <DateTimePicker value={dateTime} onChange={setDateTime} />
      </div>

      <Separator />

      {/* Repeat */}
      <div className="space-y-3">
        <Label>Repeat</Label>
        <ToggleGroup
          type="single"
          value={repeatType}
          onValueChange={(v) => { if (v) setRepeatType(v) }}
          className="flex-wrap justify-start"
        >
          {REPEAT_OPTIONS.map((o) => (
            <ToggleGroupItem key={o.value} value={o.value} className="text-xs">
              {o.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        {repeatType === 'weekly' && (
          <div className="flex flex-wrap gap-3 pt-1">
            {WEEKDAYS.map((d) => (
              <label
                key={d.value}
                className="flex cursor-pointer items-center gap-1.5 text-sm select-none"
              >
                <Checkbox
                  checked={repeatDays.includes(d.value)}
                  onCheckedChange={() => toggleDay(d.value)}
                />
                {d.label}
              </label>
            ))}
          </div>
        )}

        {repeatType === 'interval' && (
          <div className="flex items-center gap-2 pt-1">
            <span className="text-sm text-muted-foreground">Every</span>
            <Input
              type="number"
              min={1}
              value={repeatInterval}
              onChange={(e) => setRepeatInterval(Number(e.target.value))}
              className="w-16"
            />
            <Select value={repeatUnit} onValueChange={setRepeatUnit}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INTERVAL_UNITS.map((u) => (
                  <SelectItem key={u} value={u}>{u}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <Separator />

      {/* Advance notice */}
      <div className="space-y-2">
        <Label>Advance notice</Label>
        <ToggleGroup
          type="single"
          value={advanceNotice}
          onValueChange={(v) => { if (v) setAdvanceNotice(v) }}
        >
          {NOTICE_OPTIONS.map((o) => (
            <ToggleGroupItem key={o.value} value={o.value} className="text-xs">
              {o.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      {/* Error */}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? 'Saving…' : submitLabel}
        </Button>
      </div>
    </form>
  )
}
