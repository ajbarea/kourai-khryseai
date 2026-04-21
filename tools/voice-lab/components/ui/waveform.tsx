"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

interface WaveformProps {
  isPlaying?: boolean
  bars?: number
  className?: string
}

function createBars(count: number) {
  return Array.from({ length: count }, (_, i) => {
    const base = 20 + ((i * 37) % 55)
    return Math.max(12, Math.min(88, base))
  })
}

export function Waveform({ isPlaying = false, bars = 48, className }: WaveformProps) {
  const heights = React.useMemo(() => createBars(bars), [bars])

  return (
    <div className={cn("flex h-24 items-end gap-1 overflow-hidden rounded-lg border bg-card px-4 py-3", className)}>
      {heights.map((height, index) => (
        <span
          key={index}
          className={cn(
            "w-1.5 rounded-full bg-foreground/25",
            isPlaying && "animate-pulse bg-foreground/70"
          )}
          style={{
            height: `${height}%`,
            animationDelay: `${index * 35}ms`,
            animationDuration: `${700 + (index % 7) * 120}ms`,
          }}
        />
      ))}
    </div>
  )
}
