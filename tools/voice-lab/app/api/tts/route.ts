import { NextRequest } from "next/server"
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js"

export const runtime = "nodejs"

type TtsRequest = {
  text: string
  voiceId: string
  modelId?: string
}

type LogFields = Record<string, string | number | boolean | undefined>

function log(level: "info" | "warn" | "error", event: string, fields: LogFields) {
  const entry = { t: new Date().toISOString(), level, scope: "tts", event, ...fields }
  const line = JSON.stringify(entry)
  if (level === "error") console.error(line)
  else if (level === "warn") console.warn(line)
  else console.log(line)
}

export async function POST(req: NextRequest) {
  const reqId = crypto.randomUUID().slice(0, 8)
  const started = Date.now()

  const apiKey = process.env.ELEVENLABS_API_KEY
  if (!apiKey) {
    log("error", "missing_api_key", { reqId })
    return Response.json(
      { error: "ELEVENLABS_API_KEY is not set on the server." },
      { status: 500 }
    )
  }

  let body: TtsRequest
  try {
    body = (await req.json()) as TtsRequest
  } catch {
    log("warn", "invalid_json", { reqId })
    return Response.json({ error: "Invalid JSON body." }, { status: 400 })
  }

  const text = body.text?.trim()
  const voiceId = body.voiceId?.trim()
  const modelId = body.modelId ?? "eleven_multilingual_v2"
  if (!text || !voiceId) {
    log("warn", "bad_request", { reqId, hasText: !!text, hasVoiceId: !!voiceId })
    return Response.json(
      { error: "Both `text` and `voiceId` are required." },
      { status: 400 }
    )
  }

  log("info", "request_received", { reqId, voiceId, modelId, textLen: text.length })

  const client = new ElevenLabsClient({ apiKey })

  try {
    const audio = await client.textToSpeech.convert(voiceId, {
      text,
      modelId,
      outputFormat: "mp3_44100_128",
    })

    let bytes = 0
    const source = audio as unknown as ReadableStream<Uint8Array>
    const tap = new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        bytes += chunk.byteLength
        controller.enqueue(chunk)
      },
      flush() {
        log("info", "stream_complete", {
          reqId,
          voiceId,
          bytes,
          durationMs: Date.now() - started,
        })
      },
    })

    return new Response(source.pipeThrough(tap), {
      headers: {
        "Content-Type": "audio/mpeg",
        "Cache-Control": "no-store",
        "X-Request-Id": reqId,
      },
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown TTS error"
    log("error", "elevenlabs_error", {
      reqId,
      voiceId,
      durationMs: Date.now() - started,
      message,
    })
    return Response.json({ error: message, reqId }, { status: 502 })
  }
}
