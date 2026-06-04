'use client'

import { useEffect, useState } from 'react'

function formatDiff(ms: number): string {
  if (ms < 0) return 'Overdue'
  const s = Math.floor(ms / 1000)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60

  if (d > 0) return `in ${d}d ${h}h`
  if (h > 0) return `in ${h}h ${m}m`
  if (m > 0) return `in ${m}m ${sec}s`
  if (s > 0) return `in ${s}s`
  return 'Now'
}

export default function Countdown({ nextRun }: { nextRun: string }) {
  const target = new Date(nextRun).getTime()
  const [text, setText] = useState(() => formatDiff(target - Date.now()))

  useEffect(() => {
    const tick = () => setText(formatDiff(target - Date.now()))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [target])

  const diff = target - Date.now()
  const isOverdue = diff < 0
  const isSoon = !isOverdue && diff < 3_600_000

  return (
    <span
      className={
        isOverdue
          ? 'text-sm font-semibold text-destructive'
          : isSoon
            ? 'text-sm font-semibold text-amber-400'
            : 'text-sm font-semibold text-foreground'
      }
    >
      {text}
    </span>
  )
}
