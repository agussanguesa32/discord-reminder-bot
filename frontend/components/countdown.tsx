'use client'

import { useEffect, useState } from 'react'

function formatDiff(ms: number): string {
  if (ms < 0) return 'overdue'
  const totalSeconds = Math.floor(ms / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  if (days > 0) return `in ${days}d ${hours}h`
  if (hours > 0) return `in ${hours}h ${minutes}m`
  if (minutes > 0) return `in ${minutes}m ${seconds}s`
  if (totalSeconds > 0) return `in ${totalSeconds}s`
  return 'now'
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

  const isOverdue = text === 'overdue'
  const isSoon = !isOverdue && target - Date.now() < 3600000 // < 1h

  return (
    <span
      className={
        isOverdue
          ? 'text-destructive font-medium'
          : isSoon
            ? 'text-amber-400 font-medium'
            : 'text-muted-foreground'
      }
    >
      {text}
    </span>
  )
}
