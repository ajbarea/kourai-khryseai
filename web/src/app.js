// Kourai Khryseai — web GUI (Host B), M4 projects + forge sessions.
// Buildless lit: static class fields + customElements.define (no decorators).
// Light DOM (createRenderRoot returns this) so styles.css applies globally.
import { LitElement, html, nothing } from "lit";
import { repeat } from "lit/directives/repeat.js";
import { AGENTS, PIPELINE, agentFromText } from "./agents.js";
import { streamMessage, getHealth, action } from "./gateway.js";
import { speak, setVoice, unlockAudio, stopVoice, onSpeaking } from "./audio.js";

const TEMPLATES = ["empty", "python", "node", "backend", "frontend"];

class Light extends LitElement {
  createRenderRoot() { return this; }
}

// Portrait with emoji-glyph fallback: glyph sits underneath; the <img> covers
// it on success and removes itself on error (404 / no avatar synced).
function avatar(id) {
  const a = AGENTS[id] || { glyph: "•", color: "#888", name: id };
  return html`<span class="av" style="--accent:${a.color}">
    <span class="glyph">${a.glyph}</span>
    <img class="por" src="/avatars/${id}_neutral.png" alt="" loading="lazy" @error=${(e) => e.target.remove()} />
  </span>`;
}

function messageRow(m) {
  if (m.kind === "user") return html`<div class="urow"><span class="ubub">You ❯ ${m.text}</span></div>`;
  if (m.kind === "status") return html`<div class="srow">${m.text}</div>`;
  if (m.kind === "system") return html`<div class="sysrow">${m.text}</div>`;
  const a = AGENTS[m.agent] || { name: m.agent, role: "", color: "#888" };
  return html`<div class="msg" style="--accent:${a.color}">
    ${avatar(m.agent)}
    <div class="body">
      <div class="who"><span class="name">${a.name}</span><span class="role">${a.role}</span></div>
      <div class="text">${m.text}</div>
    </div>
  </div>`;
}

class KkRail extends Light {
  static properties = { states: { type: Object }, speaking: { type: String } };
  constructor() { super(); this.states = {}; this.speaking = null; }
  _node(id) {
    const a = AGENTS[id];
    return html`<div class="node" data-state=${this.states[id] || "idle"} ?data-speaking=${this.speaking === id} style="--accent:${a.color}">
      ${avatar(id)}<span class="nm">${a.name}</span>
    </div>`;
  }
  render() {
    return html`<div class="rail">
      ${this._node("hephaestus")}<span class="arrow">⟶</span>
      ${PIPELINE.map((id, i) => html`${this._node(id)}${i < PIPELINE.length - 1 ? html`<span class="arrow">→</span>` : nothing}`)}
    </div>`;
  }
}
customElements.define("kk-rail", KkRail);

class KkTerminal extends Light {
  static properties = { transcript: { type: Array }, busy: { type: Boolean } };
  constructor() { super(); this.transcript = []; this.busy = false; }
  render() {
    return html`<div class="term">
      <div class="term-bar">
        <span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="term-title">kourai — forge · A2A</span>
        ${this.busy ? html`<span class="term-busy">forging…</span>` : nothing}
      </div>
      <div class="term-body" id="body" aria-live="polite">
        ${this.transcript.length === 0
          ? html`<div class="empty">Type a request below to light the forge.</div>`
          : repeat(this.transcript, (m) => m.id, (m) => messageRow(m))}
      </div>
    </div>`;
  }
  updated() { const b = this.querySelector("#body"); if (b) b.scrollTop = b.scrollHeight; }
}
customElements.define("kk-terminal", KkTerminal);

class KkHud extends Light {
  static properties = { affinity: { type: Object } };
  constructor() { super(); this.affinity = {}; }
  render() {
    return html`<div class="hud">
      <h2>Affinity · the maidens warm to good work</h2>
      <div class="meters">
        ${Object.keys(AGENTS).map((id) => {
          const a = AGENTS[id];
          const v = Math.round(this.affinity[id] || 0);
          return html`<div class="meter" style="--accent:${a.color}">
            <div class="top"><span class="g">${a.glyph}</span><span class="n">${a.name}</span>
              <span class="h">${v >= 70 ? "♥" : "♡"} ${v}</span></div>
            <div class="bar"><i style="width:${v}%"></i></div>
          </div>`;
        })}
      </div>
    </div>`;
  }
}
customElements.define("kk-hud", KkHud);

class KkProjects extends Light {
  static properties = {
    projects: { type: Array }, activeId: { type: String }, err: { type: String },
    busy: { type: Boolean }, creating: { state: true },
  };
  constructor() { super(); this.projects = []; this.activeId = null; this.err = ""; this.busy = false; this.creating = false; }
  _use(e) { this.dispatchEvent(new CustomEvent("use-project", { detail: { id: e.target.value || null }, bubbles: true, composed: true })); }
  _create() {
    const name = (this.querySelector("input.pname").value || "").trim();
    const template = this.querySelector("select.ptmpl").value;
    if (!name) return;
    this.dispatchEvent(new CustomEvent("new-project", { detail: { name, template }, bubbles: true, composed: true }));
    this.creating = false;
  }
  render() {
    return html`<div class="projects">
      <span class="plabel">Project</span>
      <select class="psel" @change=${this._use} ?disabled=${this.busy}>
        <option value="" ?selected=${!this.activeId}>— none (scratch) —</option>
        ${this.projects.map((p) => html`<option value=${p.project_id} ?selected=${p.project_id === this.activeId}>${p.name}</option>`)}
      </select>
      <button class="pnew" @click=${() => { this.creating = !this.creating; }}>${this.creating ? "×" : "+ new"}</button>
      ${this.creating
        ? html`<span class="pform">
            <input class="pname" type="text" placeholder="project name" @keydown=${(e) => { if (e.key === "Enter") this._create(); }} />
            <select class="ptmpl">${TEMPLATES.map((t) => html`<option value=${t}>${t}</option>`)}</select>
            <button class="pcreate" @click=${this._create}>create</button>
          </span>`
        : nothing}
      ${this.err ? html`<span class="perr">${this.err}</span>` : nothing}
    </div>`;
  }
}
customElements.define("kk-projects", KkProjects);

class KkSessionTray extends Light {
  static properties = { sessions: { type: Array }, busy: { type: Boolean } };
  constructor() { super(); this.sessions = []; this.busy = false; }
  render() {
    if (!this.sessions.length) return nothing;
    return html`<div class="tray">
      <h2>Forge worktrees · pending your call</h2>
      ${this.sessions.map((s) => html`<div class="trow">
        <span class="tbranch">${s.branch}</span>
        <span class="tmeta">${(s.session_id || "").slice(0, 8)} · ${(s.started_at || "").slice(0, 16).replace("T", " ")}</span>
        <span class="tbtns">
          <button class="discard" ?disabled=${this.busy} @click=${() => this.dispatchEvent(new CustomEvent("discard-session", { detail: { id: s.session_id }, bubbles: true, composed: true }))}>Discard</button>
          <button class="accept" ?disabled=${this.busy} @click=${() => this.dispatchEvent(new CustomEvent("accept-session", { detail: { id: s.session_id }, bubbles: true, composed: true }))}>Accept ▸</button>
        </span>
      </div>`)}
    </div>`;
  }
}
customElements.define("kk-session-tray", KkSessionTray);

class KkPrompt extends Light {
  static properties = { busy: { type: Boolean }, yolo: { type: Boolean }, autoReads: { type: Boolean }, voice: { type: Boolean } };
  constructor() { super(); this.busy = false; this.yolo = false; this.autoReads = false; this.voice = false; }
  _send() {
    const inp = this.querySelector("input.text");
    const text = (inp.value || "").trim();
    if (!text || this.busy) return;
    this.dispatchEvent(new CustomEvent("send", { detail: { text }, bubbles: true, composed: true }));
    inp.value = "";
  }
  _key(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this._send(); } }
  _perm(key, value) { this.dispatchEvent(new CustomEvent("perm", { detail: { key, value }, bubbles: true, composed: true })); }
  render() {
    return html`<div class="prompt">
        <span class="you">You ❯</span>
        <input class="text" type="text" autocomplete="off"
          placeholder=${this.busy ? "forging…" : "add user authentication"}
          ?disabled=${this.busy} @keydown=${this._key} />
        <label class="perm" title="The maidens speak their lines aloud (neural TTS).">
          <input type="checkbox" .checked=${this.voice} @change=${(e) => this._perm("voice", e.target.checked)} /> 🔊
        </label>
        <label class="perm" title="Auto-approve read-only tool calls (file reads, listings).">
          <input type="checkbox" .checked=${this.autoReads} @change=${(e) => this._perm("autoReads", e.target.checked)} /> reads
        </label>
        <label class="perm" title="Skip the confirm gate entirely — runs without asking. Use with care.">
          <input type="checkbox" .checked=${this.yolo} @change=${(e) => this._perm("yolo", e.target.checked)} /> YOLO
        </label>
        <button class="send" ?disabled=${this.busy} @click=${this._send}>Forge ▸</button>
      </div>
      ${this.yolo ? html`<div class="yolo-warn">YOLO on — confirm gate skipped, tool calls auto-approve. Turn off to keep the human-in-the-loop.</div>` : nothing}`;
  }
}
customElements.define("kk-prompt", KkPrompt);

class KkDecision extends Light {
  static properties = { prompt: { type: String } };
  _approve() { this._emit("yes, light it"); }
  _send() { const v = (this.querySelector("input.dtext").value || "").trim(); if (v) this._emit(v); }
  _emit(answer) { this.dispatchEvent(new CustomEvent("decide", { detail: { answer }, bubbles: true, composed: true })); }
  _cancel() { this.dispatchEvent(new CustomEvent("cancel", { bubbles: true, composed: true })); }
  _key(e) { if (e.key === "Enter") { e.preventDefault(); this._send(); } }
  render() {
    return html`<div class="modal-bg" @click=${(e) => { if (e.target === e.currentTarget) this._cancel(); }}>
      <div class="modal" role="dialog" aria-modal="true">
        <div class="modal-h">🔥 Hephaestus needs your call</div>
        <div class="modal-prompt">${this.prompt}</div>
        <input class="dtext" type="text" placeholder="Answer the question, or just light the forge…" @keydown=${this._key} />
        <div class="modal-row">
          <button class="ghost" @click=${this._cancel}>Cancel</button>
          <button class="send2" @click=${this._send}>Send answer</button>
          <button class="approve" @click=${this._approve}>Light the forge ▸</button>
        </div>
      </div>
    </div>`;
  }
  updated() { const i = this.querySelector("input.dtext"); if (i) i.focus(); }
}
customElements.define("kk-decision", KkDecision);

class KkApp extends Light {
  static properties = {
    transcript: { type: Array }, railStates: { type: Object }, affinity: { type: Object },
    busy: { type: Boolean }, conn: { type: String }, decision: { type: Object },
    yolo: { type: Boolean }, autoReads: { type: Boolean }, voice: { type: Boolean }, speakingAgent: { type: String },
    projects: { type: Array }, activeProjectId: { type: String }, projectErr: { type: String }, sessions: { type: Array },
  };
  constructor() {
    super();
    this.transcript = []; this.railStates = {}; this.affinity = {};
    this.busy = false; this.conn = "checking"; this.decision = null;
    this.yolo = this._loadPerm("yolo"); this.autoReads = this._loadPerm("autoReads"); this.voice = this._loadPerm("voice");
    this.speakingAgent = null;
    setVoice(this.voice);
    onSpeaking((id) => { this.speakingAgent = id; });
    this.projects = []; this.sessions = []; this.projectErr = "";
    this.activeProjectId = this._loadStr("kk-active-project") || null;
    this.contextId = (globalThis.crypto?.randomUUID?.() || String(Date.now()));
    this._originalRequest = ""; this._taskId = null; this._projectRoot = null; this._counter = 0;
  }
  connectedCallback() { super.connectedCallback(); this._checkHealth(); this._loadProjects(); }
  async _checkHealth() {
    const h = await getHealth();
    this.conn = h.agents ? "ok" : h.ok ? "degraded" : "down";
  }

  _loadStr(k) { try { return localStorage.getItem(k); } catch { return null; } }
  _saveStr(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* ignore */ } }
  _loadPerm(k) { return this._loadStr("kk-perm-" + k) === "1"; }
  _setPerm(k, v) { this[k] = v; this._saveStr("kk-perm-" + k, v ? "1" : "0"); if (k === "voice") setVoice(v); }

  // ── projects + sessions ──
  async _loadProjects() {
    const r = await action("list_projects");
    this.projects = r.projects || [];
    this.projectErr = r.error === "no_profile" ? "No player profile — create one via the CLI/VN onboarding." : "";
    if (this.activeProjectId && !this.projects.some((p) => p.project_id === this.activeProjectId)) {
      this.activeProjectId = null; this._saveStr("kk-active-project", null);
    }
    this._loadSessions();
  }
  async _loadSessions() {
    if (!this.activeProjectId) { this.sessions = []; return; }
    const r = await action("list_sessions", { project_id: this.activeProjectId });
    this.sessions = r.sessions || [];
  }
  _useProject(e) {
    this.activeProjectId = e.detail.id || null;
    this._saveStr("kk-active-project", this.activeProjectId);
    this._loadSessions();
  }
  async _newProject(e) {
    const r = await action("new_project", { name: e.detail.name, template: e.detail.template });
    if (r.action === "project_created" && r.project) {
      this.projects = [...this.projects, r.project];
      this.activeProjectId = r.project.project_id;
      this._saveStr("kk-active-project", this.activeProjectId);
      this._push({ kind: "system", text: `Project "${r.project.name}" created (${r.project.template}).` });
      this._loadSessions();
    } else {
      this._push({ kind: "system", text: "Couldn't create project: " + (r.message || "unknown error") });
    }
  }
  async _acceptSession(e) { await this._sessionAction("accept_session", e.detail.id); }
  async _discardSession(e) { await this._sessionAction("discard_session", e.detail.id); }
  async _sessionAction(name, id) {
    const r = await action(name, { session_id: id });
    if (r.action === "session_done") this._push({ kind: "system", text: `Worktree ${r.result} (${(id || "").slice(0, 8)}).` });
    else this._push({ kind: "system", text: "Session action failed: " + (r.message || "unknown error") });
    this._loadSessions();
  }

  // ── transcript + rail + affinity ──
  _push(item) { this.transcript = [...this.transcript, { id: ++this._counter, ...item }]; }
  _activate(id) {
    if (!AGENTS[id]?.pipeline) return;
    const s = { ...this.railStates };
    for (const p of PIPELINE) { if (p === id) s[p] = "active"; else if (s[p] === "active") s[p] = "done"; }
    this.railStates = s;
  }
  _finishRail() { const s = { ...this.railStates }; for (const p of PIPELINE) if (s[p] === "active") s[p] = "done"; this.railStates = s; }
  _bump(id, n) { if (!AGENTS[id]) return; this.affinity = { ...this.affinity, [id]: Math.min(100, (this.affinity[id] || 0) + n) }; }
  _setAffinity(id, v) { if (!AGENTS[id]) return; this.affinity = { ...this.affinity, [id]: Math.max(0, Math.min(100, v)) }; }
  _affinityFractions() { const o = {}; for (const k in this.affinity) o[k] = this.affinity[k] / 100; return o; }

  _handle(ev) {
    if (ev.action === "status") { const id = agentFromText(ev.message); if (id) this._activate(id); this._push({ kind: "status", text: ev.message }); return; }
    if (ev.action === "jealousy") { this._setAffinity(ev.agent, Math.round((ev.score || 0) * 100)); return; }
    if (ev.agent) {
      if (ev.agent === "system") { this._push({ kind: "system", text: ev.message }); return; }
      this._activate(ev.agent);
      if (ev.message && ev.message.trim()) { this._push({ kind: "agent", agent: ev.agent, text: ev.message }); speak(ev.message, ev.agent); }
      this._bump(ev.agent, 6);
    }
  }

  // One leg of a (possibly multi-turn) forge. First turn starts a worktree for
  // the active project; resume turns reuse the same worktree (no new session).
  async _runStream(text, opts = {}) {
    this.busy = true;
    const streamOpts = {
      contextId: this.contextId, taskId: this._taskId, originalRequest: this._originalRequest,
      yolo: this.yolo, autoApproveReads: this.autoReads, affinity: this._affinityFractions(),
    };
    if (opts.resume) streamOpts.projectPath = this._projectRoot || undefined;
    else streamOpts.projectId = this.activeProjectId || undefined;

    let pending = null;
    try {
      for await (const ev of streamMessage(text, streamOpts)) {
        if (ev.action === "input_required") { pending = ev; continue; }
        this._handle(ev);
      }
      this.conn = "ok";
    } catch {
      this._push({ kind: "system", text: "Couldn't reach the gateway — is the stack up? (uv run kourai-dev up)" });
      this.conn = "down";
    } finally {
      this.busy = false;
    }
    if (pending) {
      this._taskId = pending.task_id || this._taskId;
      this._projectRoot = pending.project_root || this._projectRoot;
      this.decision = { prompt: pending.prompt };
    } else {
      this._finishRail();
      this._loadSessions();
    }
  }

  async _send(e) {
    const text = e.detail.text;
    if (!text || this.busy) return;
    unlockAudio(); stopVoice();
    this._originalRequest = text;
    this._taskId = null;
    this._projectRoot = null;
    this._push({ kind: "user", text });
    await this._runStream(text);
  }
  async _decide(e) {
    const answer = e.detail.answer;
    unlockAudio();
    this.decision = null;
    this._push({ kind: "user", text: answer });
    await this._runStream(answer, { resume: true });
  }
  _cancelDecision() {
    this.decision = null;
    this._push({ kind: "system", text: "Cancelled. The forge is paused — send a new request to start over." });
    this._finishRail();
    this._loadSessions();
  }

  render() {
    const dot = this.conn === "ok" ? "ok" : this.conn === "checking" ? "" : "bad";
    const label = { ok: "agents connected", degraded: "gateway up · agents disconnected", down: "gateway unreachable", checking: "connecting…" }[this.conn];
    return html`
      <header class="app">
        <h1 class="brand">🏛️ Kourai Khryseai</h1>
        <div class="conn"><span class="cdot ${dot}"></span>${label}</div>
      </header>
      <kk-projects .projects=${this.projects} .activeId=${this.activeProjectId} .err=${this.projectErr} .busy=${this.busy}
        @use-project=${this._useProject} @new-project=${this._newProject}></kk-projects>
      <kk-rail .states=${this.railStates} .speaking=${this.speakingAgent}></kk-rail>
      <kk-terminal .transcript=${this.transcript} .busy=${this.busy}></kk-terminal>
      <kk-prompt .busy=${this.busy} .yolo=${this.yolo} .autoReads=${this.autoReads} .voice=${this.voice}
        @send=${this._send} @perm=${(e) => this._setPerm(e.detail.key, e.detail.value)}></kk-prompt>
      <kk-session-tray .sessions=${this.sessions} .busy=${this.busy}
        @accept-session=${this._acceptSession} @discard-session=${this._discardSession}></kk-session-tray>
      <kk-hud .affinity=${this.affinity}></kk-hud>
      <footer class="app">M4 · projects + worktrees — forge into a session, accept or discard from the browser</footer>
      ${this.decision
        ? html`<kk-decision .prompt=${this.decision.prompt} @decide=${this._decide} @cancel=${this._cancelDecision}></kk-decision>`
        : nothing}`;
  }
}
customElements.define("kk-app", KkApp);
