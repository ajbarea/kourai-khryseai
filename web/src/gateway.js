// Host-gateway client. The app is served same-origin by the gateway, so these
// are relative fetches (no CORS, no mixed content).

// Synchronous JSON action (projects, sessions, profiles). Returns the parsed body.
export async function action(name, params = {}) {
  try {
    const res = await fetch("action", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: name, ...params }),
    });
    return await res.json().catch(() => ({}));
  } catch {
    return { action: "error", message: "gateway unreachable" };
  }
}

// Liveness: { ok } = gateway reachable; { agents } = agents connected too.
export async function getHealth() {
  try {
    const res = await fetch("health", { headers: { accept: "application/json" } });
    const body = await res.json().catch(() => ({}));
    return { ok: res.ok, agents: res.ok && body.status === "ok" };
  } catch {
    return { ok: false, agents: false };
  }
}

// Stream a forge. Yields parsed NDJSON events from POST /message:
//   { agent, message, portrait }            — a dialogue / artifact beat
//   { action: "status",  message }          — pipeline status line
//   { action: "jealousy", agent, score }    — affinity update (0..1)
//   { agent: "system", message }            — system / error notice
export async function* streamMessage(text, opts = {}) {
  const payload = {
    text,
    context_id: opts.contextId || undefined,
    task_id: opts.taskId || undefined,
    original_request: opts.originalRequest || undefined,
    project_id: opts.projectId || undefined,
    project_path: opts.projectPath || undefined,
    yolo: !!opts.yolo,
    auto_approve_reads: !!opts.autoApproveReads,
    affinity: opts.affinity || undefined,
  };
  const res = await fetch("message", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok || !res.body) throw new Error("gateway " + res.status);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      try { yield JSON.parse(line); } catch { /* skip malformed line */ }
    }
  }
  const tail = buf.trim();
  if (tail) { try { yield JSON.parse(tail); } catch { /* ignore */ } }
}
