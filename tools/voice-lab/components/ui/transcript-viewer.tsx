"use client"

import { cn } from "@/lib/utils"

export interface TranscriptEntry {
  start: number
  end: number
  text: string
}

interface TranscriptViewerProps {
  entries: TranscriptEntry[]
  currentTime: number
  className?: string
}

function formatTime(seconds: number) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

export function TranscriptViewer({ entries, currentTime, className }: TranscriptViewerProps) {
  return (
    <div className={cn("rounded-lg border bg-card", className)}>
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Transcript</h3>
      </div>
      <div className="max-h-64 space-y-1 overflow-y-auto p-2">
        {entries.map((entry, idx) => {
          const active = currentTime >= entry.start && currentTime < entry.end
          return (
            <div
              key={`${entry.start}-${idx}`}
              className={cn(
                "flex items-start gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active ? "bg-primary/10 text-foreground" : "text-muted-foreground"
              )}
            >
              <span className="w-12 shrink-0 font-mono text-xs">{formatTime(entry.start)}</span>
              <span>{entry.text}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
