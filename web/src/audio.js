// Sequential TTS playback — the maidens speak. Each dialogue line is synthesised
// by the gateway's POST /tts (WAV) and played one at a time so they never overlap.
//
// Web Audio, per 2026 best practice: the AudioContext must be created/resumed from
// inside a user gesture (autoplay policy), so `unlockAudio()` is called on the Forge
// click. One AudioBufferSourceNode per clip (they're single-use); the queue drains
// serially. `onSpeaking(fn)` fires (agentId | null) for portrait sync.

let ctx = null;
let enabled = false;
let queue = [];
let draining = false;
let current = null;
let onSpeak = null;

const _ctx = () => (ctx ||= new (window.AudioContext || window.webkitAudioContext)());

export const setVoice = (v) => {
  enabled = !!v;
  if (!enabled) stopVoice();
};
export const voiceOn = () => enabled;
export const onSpeaking = (fn) => {
  onSpeak = fn;
};

// Autoplay policy: resume from within a user gesture (the Forge / Send-answer click).
export const unlockAudio = () => {
  const c = _ctx();
  if (c.state === "suspended") c.resume().catch(() => {});
};

export function stopVoice() {
  queue = [];
  if (current) {
    try {
      current.stop();
    } catch {
      /* already ended */
    }
    current = null;
  }
  draining = false;
  onSpeak?.(null);
}

export function speak(text, agent) {
  if (!enabled || !text?.trim()) return;
  queue.push({ text, agent });
  if (!draining) _drain();
}

async function _drain() {
  draining = true;
  while (queue.length) {
    const { text, agent } = queue.shift();
    try {
      const res = await fetch("tts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text, agent }),
      });
      if (!res.ok) continue;
      const audio = await _ctx().decodeAudioData(await res.arrayBuffer());
      await _play(audio, agent);
    } catch {
      /* skip a line that won't synth — never wedge the queue */
    }
  }
  draining = false;
  onSpeak?.(null);
}

function _play(buffer, agent) {
  return new Promise((resolve) => {
    const c = _ctx();
    const src = c.createBufferSource();
    src.buffer = buffer;
    src.connect(c.destination);
    src.onended = () => {
      current = null;
      onSpeak?.(null);
      resolve();
    };
    current = src;
    onSpeak?.(agent);
    src.start();
  });
}
