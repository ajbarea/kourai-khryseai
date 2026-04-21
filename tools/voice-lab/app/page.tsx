"use client"

import * as React from "react"
import type { ElevenLabs } from "@elevenlabs/elevenlabs-js"

import {
  AudioPlayerButton,
  AudioPlayerDuration,
  AudioPlayerProgress,
  AudioPlayerProvider,
  AudioPlayerTime,
  AudioPlayerSpeed,
  useAudioPlayer,
} from "@/components/ui/audio-player"
import { Button, buttonVariants } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { VoicePicker } from "@/components/ui/voice-picker"
import { Waveform } from "@/components/ui/waveform"

const voices: ElevenLabs.Voice[] = [
  {
    voiceId: "JBFqnCBsd6RMkjVDRZzb",
    name: "George",
    category: "premade",
    labels: { accent: "british", age: "middle_aged", gender: "male", use_case: "narration" },
    description: "Warm, steady narrator voice",
  },
  {
    voiceId: "EXAVITQu4vr4xnSDxMaL",
    name: "Sarah",
    category: "premade",
    labels: { accent: "american", age: "young", gender: "female", use_case: "conversational" },
    description: "Soft, clear conversational delivery",
  },
  {
    voiceId: "onwK4e9ZLuTAKqWW03F9",
    name: "Daniel",
    category: "premade",
    labels: { accent: "american", age: "middle_aged", gender: "male", use_case: "announcements" },
    description: "Authoritative and direct",
  },
]

const log = (event: string, fields: Record<string, unknown> = {}) => {
  console.log(JSON.stringify({ scope: "tts", event, ...fields }))
}

function useAudioElementDebug(ref: React.RefObject<HTMLAudioElement | null>) {
  React.useEffect(() => {
    const el = ref.current ?? document.querySelector("audio")
    if (!el) {
      log("audio_element_missing")
      return
    }
    const events = [
      "loadstart",
      "loadedmetadata",
      "canplay",
      "play",
      "playing",
      "pause",
      "ended",
      "stalled",
      "suspend",
      "waiting",
      "error",
      "volumechange",
    ] as const
    const handlers = events.map((name) => {
      const handler = () =>
        log(`audio_${name}`, {
          currentTime: el.currentTime,
          duration: Number.isFinite(el.duration) ? el.duration : null,
          volume: el.volume,
          muted: el.muted,
          paused: el.paused,
          readyState: el.readyState,
          errorCode: el.error?.code ?? null,
        })
      el.addEventListener(name, handler)
      return [name, handler] as const
    })
    log("audio_element_attached", {
      volume: el.volume,
      muted: el.muted,
      readyState: el.readyState,
    })
    return () => {
      for (const [name, handler] of handlers) el.removeEventListener(name, handler)
    }
  }, [ref])
}

type Generation = {
  id: string
  url: string
  bytes: number
  voiceId: string
  voiceName: string
  text: string
  createdAt: number
}

const HISTORY_LIMIT = 10

const filenameFor = (g: Generation) => {
  const stamp = new Date(g.createdAt)
    .toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", "_")
    .slice(0, 19)
  const slug = g.voiceName.toLowerCase().replace(/[^a-z0-9]+/g, "-")
  return `${slug}-${stamp}.mp3`
}

function DemoSurface() {
  const [selectedVoice, setSelectedVoice] = React.useState(voices[0].voiceId!)
  const [text, setText] = React.useState("The first move is what sets everything in motion.")
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [history, setHistory] = React.useState<Generation[]>([])
  const player = useAudioPlayer<ElevenLabs.Voice>()

  useAudioElementDebug(player.ref)

  const selected = React.useMemo(
    () => voices.find((v) => v.voiceId === selectedVoice) ?? voices[0],
    [selectedVoice]
  )

  const historyRef = React.useRef(history)
  historyRef.current = history
  React.useEffect(() => {
    return () => {
      for (const g of historyRef.current) URL.revokeObjectURL(g.url)
    }
  }, [])

  const handleGenerate = async () => {
    const trimmed = text.trim()
    if (!trimmed || isGenerating) return

    setIsGenerating(true)
    setError(null)
    const started = performance.now()
    log("generate_start", { voiceId: selectedVoice, textLen: trimmed.length })
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed, voiceId: selectedVoice }),
      })
      log("response_received", {
        status: res.status,
        contentType: res.headers.get("content-type"),
        reqId: res.headers.get("x-request-id"),
        elapsedMs: Math.round(performance.now() - started),
      })
      if (!res.ok) {
        const { error: msg } = (await res.json().catch(() => ({}))) as { error?: string }
        throw new Error(msg ?? `Request failed (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      log("blob_ready", { bytes: blob.size, type: blob.type, url })

      const generation: Generation = {
        id: `gen-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        url,
        bytes: blob.size,
        voiceId: selected.voiceId!,
        voiceName: selected.name ?? "voice",
        text: trimmed,
        createdAt: Date.now(),
      }

      setHistory((prev) => {
        const next = [generation, ...prev]
        const evicted = next.slice(HISTORY_LIMIT)
        for (const g of evicted) URL.revokeObjectURL(g.url)
        return next.slice(0, HISTORY_LIMIT)
      })

      await player.setActiveItem({ id: generation.id, src: url, data: selected })
      log("active_item_set", { id: generation.id })
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Generation failed"
      log("generate_error", { message: msg })
      setError(msg)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleReplay = async (g: Generation) => {
    await player.setActiveItem({ id: g.id, src: g.url, data: selected })
    log("replay", { id: g.id })
  }

  const handleRemove = (g: Generation) => {
    if (player.activeItem?.id === g.id) {
      void player.setActiveItem(null)
    }
    setHistory((prev) => prev.filter((x) => x.id !== g.id))
    URL.revokeObjectURL(g.url)
    log("remove", { id: g.id })
  }

  const activeItem = player.activeItem

  return (
    <main className="min-h-svh bg-gradient-to-b from-background via-background to-muted/20 px-6 py-10">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <section className="rounded-xl border bg-card p-5">
          <h1 className="text-2xl font-semibold tracking-tight">Korai Voice Lab</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Type text, pick a voice, generate speech via ElevenLabs.
          </p>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="flex flex-col gap-4 rounded-xl border bg-card p-5">
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Voice
              </h2>
              <VoicePicker
                voices={voices}
                value={selectedVoice}
                onValueChange={setSelectedVoice}
                placeholder="Choose a voice"
              />
            </div>

            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Text
              </h2>
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                placeholder="Enter text to synthesize…"
              />
            </div>

            <div className="flex items-center gap-3">
              <Button onClick={handleGenerate} disabled={isGenerating || !text.trim()}>
                {isGenerating ? "Generating…" : "Generate speech"}
              </Button>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
          </div>

          <div className="rounded-xl border bg-card p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Playback
            </h2>
            <div className="space-y-4">
              <Waveform isPlaying={player.isPlaying} />

              <div className="flex items-center gap-3">
                <AudioPlayerButton item={activeItem ?? undefined} size="icon" />
                <AudioPlayerProgress className="flex-1" />
                <AudioPlayerSpeed />
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <AudioPlayerTime />
                <AudioPlayerDuration />
              </div>

              {!activeItem && (
                <p className="text-xs text-muted-foreground">
                  No audio yet — generate some speech to start.
                </p>
              )}
            </div>
          </div>
        </section>

        {history.length > 0 && (
          <section className="rounded-xl border bg-card p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Recent generations ({history.length}/{HISTORY_LIMIT})
            </h2>
            <ul className="divide-y">
              {history.map((g) => {
                const isActive = activeItem?.id === g.id
                const kb = (g.bytes / 1024).toFixed(1)
                const preview = g.text.length > 60 ? `${g.text.slice(0, 60)}…` : g.text
                return (
                  <li
                    key={g.id}
                    className={`flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between ${
                      isActive ? "bg-muted/40 -mx-5 px-5" : ""
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">
                        {g.voiceName}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {kb} KB · {new Date(g.createdAt).toLocaleTimeString()}
                        </span>
                      </p>
                      <p className="truncate text-xs text-muted-foreground">{preview}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant={isActive ? "secondary" : "outline"}
                        onClick={() => handleReplay(g)}
                      >
                        {isActive ? "Loaded" : "Replay"}
                      </Button>
                      <a
                        href={g.url}
                        download={filenameFor(g)}
                        className={buttonVariants({ size: "sm", variant: "outline" })}
                      >
                        Download
                      </a>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemove(g)}
                        aria-label="Remove generation"
                      >
                        ✕
                      </Button>
                    </div>
                  </li>
                )
              })}
            </ul>
          </section>
        )}
      </div>
    </main>
  )
}

export default function Page() {
  return (
    <AudioPlayerProvider>
      <DemoSurface />
    </AudioPlayerProvider>
  )
}
