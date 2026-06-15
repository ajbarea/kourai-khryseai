# Web GUI (Host B)

A browser GUI host for Kourai Khryseai, served **same-origin by the host gateway** (the evolved
`vn_bridge`) so there's no CORS or mixed-content problem at runtime. Full design:
[`docs/architecture/2026-06-14-web-gui-scope.md`](../docs/architecture/2026-06-14-web-gui-scope.md).

## Status — M4 (projects + worktrees)

Pick or create a project, forge into a git worktree, and accept or discard it — all from the browser.
Plus everything from M3: stream a real forge into the terminal and answer the confirm gate / planner
questions in a modal without leaving the page.

- **Frontend:** buildless [lit](https://lit.dev) Web Components (light DOM + one `styles.css`), loaded
  via an import map from a CDN. Components: `kk-app`, `kk-rail`, `kk-terminal`, `kk-hud`, `kk-prompt`.
- **Transport:** `src/gateway.js` streams `POST /message` NDJSON (`fetch` + `ReadableStream`) and maps
  events → UI (`{agent,message}` → bubble, `{action:"status"}` → rail + status line,
  `{action:"jealousy"}` → affinity).
- **Portraits:** served by the gateway at `/avatars/<id>_neutral.png` (single source of truth:
  `docs/assets/avatars`), with an emoji-glyph fallback so it never shows broken images.
- **Decisions:** when a forge hits the confirm gate or a planner question, a `kk-decision` modal opens
  with the prompt — approve ("light the forge"), type a free-text answer, or cancel. The reply resumes
  the **same task** (`context_id` + `task_id` + `original_request`) so the router relays the real ask
  instead of re-routing on "yes".
- **Permissions:** `YOLO` (skip the confirm gate) and `reads` (auto-approve read-only tool calls),
  off by default, persisted in `localStorage`, forwarded as metadata; YOLO shows a warning.
- **Projects & worktrees:** a project switcher (with template-based create) sets the active project,
  sent as `project_id` on each forge; the gateway starts a `ForgeSession` worktree (exactly as the CLI
  host does) and runs the forge inside it. The session tray lists pending worktrees with **Accept**
  (fast-forward merge) / **Discard** (drop it). Decision resumes reuse the same worktree — no double
  sessions. Needs an active player profile (the CLI/VN onboarding creates one).

## Run it

```bash
uv run kourai-dev up        # build + start the stack (agents + gateway)
# open http://localhost:10010/
```

Pick or **+ new** a project up top to forge into a worktree; after a run, **Accept** or **Discard** it
in the tray. Type something like `add user authentication` and hit Forge. With YOLO **off**, a
decision pauses and a modal opens — approve or answer to continue. Flip YOLO **on** for a hands-off run.

Files: `index.html` (shell + import map), `styles.css` (forge theme), `src/agents.js` (registry),
`src/gateway.js` (NDJSON client), `src/app.js` (components).

## Next

- **M5** — polish: TTS playback, vendored lit for offline, `kourai-dev web` launcher, mobile pass,
  `@agent` targeting, and a profile-create step for first-run web users.
