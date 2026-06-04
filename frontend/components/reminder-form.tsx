'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Calendar } from '@/components/ui/calendar'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

/* ── Constants ──────────────────────────────────────────────────── */

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
  { value: '5',   label: '5 min' },
  { value: '15',  label: '15 min' },
  { value: '30',  label: '30 min' },
  { value: '60',  label: '1 hour' },
  { value: '120', label: '2 hours' },
]

const HOURS = Array.from({ length: 24 }, (_, i) => i)
const MINUTES = [0, 15, 30, 45]

function fmtHour(h: number): string {
  if (h === 0) return '12 am'
  if (h < 12) return `${h} am`
  if (h === 12) return '12 pm'
  return `${h - 12} pm`
}

function buildPresets() {
  const now = new Date()
  const tom = new Date(now)
  tom.setDate(tom.getDate() + 1)
  function at(base: Date, h: number, m = 0) {
    const d = new Date(base); d.setHours(h, m, 0, 0); return d
  }
  return [
    { label: 'In 1 hour',     value: new Date(now.getTime() + 3_600_000) },
    { label: 'In 2 hours',    value: new Date(now.getTime() + 7_200_000) },
    { label: 'Tonight 8pm',   value: at(now, 20) },
    { label: 'Tonight 10pm',  value: at(now, 22) },
    { label: 'Tomorrow 9am',  value: at(tom, 9) },
    { label: 'Tomorrow 12pm', value: at(tom, 12) },
    { label: 'Tomorrow 6pm',  value: at(tom, 18) },
  ].filter((p) => p.value > now)
}

function fmtPreview(d: Date): string {
  return d.toLocaleString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

/* ── Types ──────────────────────────────────────────────────────── */

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

/* ── Component ──────────────────────────────────────────────────── */

export default function ReminderForm({
  defaultValues,
  userTimezone,
  isPending,
  onSubmit,
  onCancel,
  submitLabel = 'Save',
}: Props) {
  const [presets] = useState(buildPresets)

  // Form state
  const [title, setTitle]       = useState(defaultValues?.title ?? '')
  const [description, setDesc]  = useState(defaultValues?.description ?? '')
  const [repeatType, setRepeat] = useState(defaultValues?.repeat_type ?? 'none')
  const [repeatInterval, setRI] = useState(defaultValues?.repeat_interval ?? 1)
  const [repeatUnit, setRU]     = useState(defaultValues?.repeat_unit ?? 'hours')
  const [repeatDays, setRD]     = useState<string[]>(
    defaultValues?.repeat_days?.split(',').map((d) => d.trim()) ?? []
  )
  const [advanceNotice, setAN]  = useState(String(defaultValues?.advance_notice ?? 0))
  const [error, setError]       = useState<string | null>(null)

  // Date/time state
  const initDate = defaultValues?.next_run ? new Date(defaultValues.next_run) : undefined
  const [calDate, setCalDate]   = useState<Date | undefined>(initDate)
  const [hour, setHour]         = useState(initDate?.getHours() ?? 9)
  const [minute, setMinute]     = useState(initDate?.getMinutes() ?? 0)

  // Derived selected datetime
  const dateTime: Date | undefined = calDate
    ? (() => { const d = new Date(calDate); d.setHours(hour, minute, 0, 0); return d })()
    : undefined

  function emit(d: Date | undefined, h: number, m: number) {
    if (d) { const r = new Date(d); r.setHours(h, m, 0, 0) }
  }

  function applyPreset(p: Date) {
    setCalDate(p); setHour(p.getHours()); setMinute(p.getMinutes())
  }

  function toggleDay(day: string) {
    setRD((prev) => prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day])
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!title.trim())                            return setError('Title is required.')
    if (!dateTime)                                return setError('Pick a date and time.')
    if (repeatType === 'weekly' && !repeatDays.length) return setError('Select at least one day.')

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

  const isPresetActive = (p: Date) =>
    !!dateTime && Math.abs(dateTime.getTime() - p.getTime()) < 60_000

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* ── Two-column body ── */}
      <div className="flex gap-0 min-h-0">

        {/* LEFT — Details */}
        <div className="flex flex-1 min-w-0 flex-col gap-4 pr-6">
          <div className="space-y-1.5">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Doctor appointment"
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="desc">
              Description{' '}
              <span className="text-xs font-normal text-muted-foreground">(optional)</span>
            </Label>
            <Textarea
              id="desc"
              value={description}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Extra details..."
              rows={3}
              className="resize-none"
            />
          </div>

          <div className="space-y-2">
            <Label>Repeat</Label>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              value={repeatType}
              onValueChange={(v) => { if (v) setRepeat(v) }}
              className="w-full"
            >
              {REPEAT_OPTIONS.map((o) => (
                <ToggleGroupItem key={o.value} value={o.value} className="flex-1 text-xs">
                  {o.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>

            {repeatType === 'weekly' && (
              <div className="flex flex-wrap gap-x-4 gap-y-2 pt-1">
                {WEEKDAYS.map((d) => (
                  <label key={d.value} className="flex cursor-pointer items-center gap-1.5 text-sm select-none">
                    <Checkbox checked={repeatDays.includes(d.value)} onCheckedChange={() => toggleDay(d.value)} />
                    {d.label}
                  </label>
                ))}
              </div>
            )}

            {repeatType === 'interval' && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-sm text-muted-foreground shrink-0">Every</span>
                <Input
                  type="number"
                  min={1}
                  value={repeatInterval}
                  onChange={(e) => setRI(Number(e.target.value))}
                  className="w-20"
                />
                <Select value={repeatUnit} onValueChange={setRU}>
                  <SelectTrigger className="flex-1">
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

          <div className="space-y-2">
            <Label>Advance notice</Label>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              value={advanceNotice}
              onValueChange={(v) => { if (v) setAN(v) }}
              className="w-full"
            >
              {NOTICE_OPTIONS.map((o) => (
                <ToggleGroupItem key={o.value} value={o.value} className="flex-1 text-xs">
                  {o.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        </div>

        {/* Vertical divider */}
        <div className="w-px shrink-0 bg-border" />

        {/* RIGHT — When */}
        <div className="flex w-72 shrink-0 flex-col gap-3 pl-6">
          <Label>When?</Label>

          {/* Quick presets */}
          <div className="flex flex-wrap gap-1.5">
            {presets.map((p) => (
              <Button
                key={p.label}
                type="button"
                size="sm"
                variant={isPresetActive(p.value) ? 'default' : 'outline'}
                onClick={() => applyPreset(p.value)}
                className="text-xs"
              >
                {p.label}
              </Button>
            ))}
          </div>

          {/* Calendar */}
          <Calendar
            mode="single"
            selected={calDate}
            onSelect={setCalDate}
            disabled={{ before: new Date() }}
            captionLayout="label"
          />

          {/* Hour + Minute selects */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Time</Label>
            <div className="flex gap-2">
              <Select value={String(hour)} onValueChange={(v) => setHour(Number(v))}>
                <SelectTrigger className="flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-48">
                  {HOURS.map((h) => (
                    <SelectItem key={h} value={String(h)}>{fmtHour(h)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={String(minute)} onValueChange={(v) => setMinute(Number(v))}>
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MINUTES.map((m) => (
                    <SelectItem key={m} value={String(m)}>
                      :{m.toString().padStart(2, '0')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Preview */}
          {dateTime && (
            <p className="text-xs font-medium text-foreground">
              {fmtPreview(dateTime)}
            </p>
          )}
        </div>
      </div>

      {/* ── Footer ── */}
      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}
      <div className="flex justify-end gap-2 border-t border-border pt-4">
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
