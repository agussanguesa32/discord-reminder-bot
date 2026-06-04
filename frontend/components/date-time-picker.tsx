'use client'

import { useState } from 'react'
import { Calendar } from '@/components/ui/calendar'
import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

const HOURS = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
const MINUTES = [0, 15, 30, 45]

function fmtHour(h: number): string {
  if (h === 0) return '12am'
  if (h < 12) return `${h}am`
  if (h === 12) return '12pm'
  return `${h - 12}pm`
}

function buildPresets() {
  const now = new Date()
  const tom = new Date(now)
  tom.setDate(tom.getDate() + 1)

  function at(base: Date, h: number, m = 0) {
    const d = new Date(base)
    d.setHours(h, m, 0, 0)
    return d
  }

  return [
    { label: 'In 1 hour',      value: new Date(now.getTime() + 3_600_000) },
    { label: 'In 2 hours',     value: new Date(now.getTime() + 7_200_000) },
    { label: 'Tonight 8pm',    value: at(now, 20) },
    { label: 'Tonight 10pm',   value: at(now, 22) },
    { label: 'Tomorrow 9am',   value: at(tom, 9) },
    { label: 'Tomorrow 12pm',  value: at(tom, 12) },
    { label: 'Tomorrow 6pm',   value: at(tom, 18) },
  ].filter((p) => p.value > now)
}

function fmtSelected(d: Date): string {
  return d.toLocaleString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

interface Props {
  value: Date | undefined
  onChange: (d: Date) => void
}

export default function DateTimePicker({ value, onChange }: Props) {
  const [presets] = useState(buildPresets)
  const [calDate, setCalDate] = useState<Date | undefined>(value)
  const [hour, setHour] = useState(value?.getHours() ?? 9)
  const [minute, setMinute] = useState(value?.getMinutes() ?? 0)

  function emit(d: Date | undefined, h: number, m: number) {
    if (!d) return
    const r = new Date(d)
    r.setHours(h, m, 0, 0)
    onChange(r)
  }

  function applyPreset(p: Date) {
    setCalDate(p)
    setHour(p.getHours())
    setMinute(p.getMinutes())
    onChange(new Date(p))
  }

  function handleDay(d: Date | undefined) {
    setCalDate(d)
    emit(d, hour, minute)
  }

  function handleHour(h: number) {
    setHour(h)
    emit(calDate, h, minute)
  }

  function handleMinute(m: number) {
    setMinute(m)
    emit(calDate, hour, m)
  }

  const isPresetActive = (p: Date) =>
    !!value && Math.abs(value.getTime() - p.getTime()) < 60_000

  return (
    <div className="space-y-4">
      {/* Quick presets */}
      <div className="flex flex-wrap gap-1.5">
        {presets.map((p) => (
          <Button
            key={p.label}
            type="button"
            size="sm"
            variant={isPresetActive(p.value) ? 'default' : 'outline'}
            onClick={() => applyPreset(p.value)}
          >
            {p.label}
          </Button>
        ))}
      </div>

      <Separator />

      {/* Calendar */}
      <Calendar
        mode="single"
        selected={calDate}
        onSelect={handleDay}
        disabled={{ before: new Date() }}
        captionLayout="label"
        className="mx-auto w-fit"
      />

      <Separator />

      {/* Hour grid */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Hour</p>
        <div className="grid grid-cols-6 gap-1">
          {HOURS.map((h) => (
            <Button
              key={h}
              type="button"
              size="sm"
              variant={hour === h ? 'default' : 'outline'}
              className="text-xs px-0"
              onClick={() => handleHour(h)}
            >
              {fmtHour(h)}
            </Button>
          ))}
        </div>
      </div>

      {/* Minute */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Minute</p>
        <ToggleGroup
          type="single"
          variant="outline"
          spacing={0}
          value={String(minute)}
          onValueChange={(v) => { if (v) handleMinute(Number(v)) }}
          className="w-full"
        >
          {MINUTES.map((m) => (
            <ToggleGroupItem key={m} value={String(m)} className="flex-1 text-sm font-mono">
              :{m.toString().padStart(2, '0')}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      {/* Selected preview */}
      {value && (
        <>
          <Separator />
          <p className="text-sm font-medium text-foreground">
            {fmtSelected(value)}
          </p>
        </>
      )}
    </div>
  )
}
