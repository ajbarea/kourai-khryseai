# The Forge — Kourai Khryseai demo app

An offline-ready, installable replay of a Kourai Khryseai forge session. One self-contained
`index.html`, **no build, no backend, no framework** — the same shape as
[periplus](https://github.com/ajbarea/periplus).

**Live (once deployed):** `https://ajbarea.github.io/kourai-khryseai/app/`

## What it is

A scripted walkthrough of the **Metis → Techne → Dokimasia → Kallos → Mneme** pipeline, narrated
by Hephaestus, with:

- streaming agent output and a glowing pipeline rail (View Transitions where supported),
- one branching decision — **JWT vs. server sessions** — so the viewer feels the human-on-the-loop loop,
- an affinity HUD that nods to the VN, and
- Play / Pause / Restart / speed controls.

It is a **demo**, not the engine: the real system runs ten agents locally over the
[A2A protocol](https://a2a-protocol.org). Voices are drawn from each maiden's `voice_examples.md`.

## Preview locally

```bash
python3 -m http.server 5173 --directory app
# open http://localhost:5173
```

The service worker and install prompt require http/https — `localhost` qualifies (`file://` will
still render, just without offline/install). The UI only claims "opens offline" once the service
worker actually controls the page, and the install button only appears when the browser reports the
app as installable — neither is asserted on faith.

### Portraits

The avatars come from `docs/assets/avatars/<agent>_neutral.png`; deploy copies them in
automatically. For local preview, sync them once (otherwise the maidens fall back to emoji glyphs):

```bash
mkdir -p app/assets/avatars && cp docs/assets/avatars/*_neutral.png app/assets/avatars/
```

## Edit the script

The entire session lives in three arrays near the top of the `<script>` in `index.html`:
`INTRO`, `BRANCH`, and `TAIL`. Each step is `{ agent, kind, text }` where `kind` is one of
`narration | say | ask | code | test | review | commit | system`. `{APPROACH}` is substituted
with the player's choice. Add an agent by extending the `AGENTS` registry.

## Deploy to GitHub Pages

Wired into the existing **`.github/workflows/docs.yml`**: after Zensical builds the docs into
`site/`, a `Render PWA icons` step rasterizes the icon set from SVG, then `Stage web app at /app`
copies this folder to `site/app/` and the agent portraits to `site/app/assets/avatars/`, so the app
ships at `https://ajbarea.github.io/kourai-khryseai/app/` on every push to `app/**` or `docs/**`.

The service worker is scoped to `./`, so it only ever controls `/app/` and never the docs at the
site root. The Actions-based Pages pipeline serves the uploaded artifact as-is, so no root
`.nojekyll` is required.

## Icons

Crisp on every platform, from two SVG sources rasterized to PNG at build time (no binaries in git):

- `assets/icon.svg` — rounded SVG favicon + manifest `any`.
- `assets/icon-solid.svg` — opaque, safe-zone-padded source for the maskable + iOS icons.
- `scripts/gen-icons.sh` renders `apple-touch-icon.png` (180, opaque — iOS rounds it), `icon-192/512.png` (`any`), and `icon-192/512-maskable.png` (art inside the 80% safe zone). CI runs it on deploy; run it locally to preview real icons (needs `rsvg-convert` from librsvg).

## Stack

HTML + vanilla JS. PWA via `manifest.webmanifest` + `sw.js` (versioned cache, network-first for
navigation, cache-first for static assets). Animations use the View Transitions API as progressive
enhancement and fully respect `prefers-reduced-motion`. No external requests; offline-capable once
the service worker has cached it.

MIT © 2026 AJ Barea
