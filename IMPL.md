# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **M11 — GUI attachment send path**

---

## M11 plan-of-record

End state: the GUI matches the CLI's image-attachment story end-to-end.
Player Alt+V captures a clipboard image; an `[📎 image #N queued]`
placeholder lands in the input bar; on submit the captured pixels ride
the same A2A multi-part `Message` (`TextPart` + `FilePart`) the CLI
ships, so Hephaestus and the downstream specialists see the image
identically regardless of host. The user's bubble shows a thumbnail
strip so they can confirm exactly what was attached.

The clipboard-capture half (Alt+V → `_pending_images`) was already
shipped on 2026-04-23. M11 closes the send-path half:
`pygame_event_handler._submit_text` previously emitted a bare
`(target, text)` tuple on `send_q`, the captured image was held
on the handler indefinitely, and at pipeline completion it was
silently discarded.

### Step 1 — `send_q` carries a 3-tuple ✅ 2026-04-26

- [x] `hosts/gui/pygame_event_handler.py::_submit_text`: drains
      `self._pending_images` into a local `attachments` list, resets
      the handler list, then puts `(target, text, attachments)` on
      `send_q`. The drain happens BEFORE the put so a transient queue
      error doesn't strand the image and re-send it next turn (covered
      by `test_pending_images_drained_even_when_send_fails`).
- [x] `_submit_quick_action` puts `(action.agent, payload, [])` —
      quick actions never carry attachments today, but the slot keeps
      the consumer signature uniform.
- [x] `_paste_image_from_clipboard` docstring updated — the "send
      path is not yet wired" caveat is gone.

### Step 2 — `GuiClient` builds `[TextPart, FilePart, ...]` ✅ 2026-04-26

- [x] `hosts/gui/client.py::__init__`: typed `send_q` signature
      grew the attachments slot.
- [x] `run()` unpacks the 3-tuple and tolerates the legacy 2-tuple
      shape (any non-GUI caller that wires directly to `send_q` keeps
      working). Logs the attachment count at debug.
- [x] `_send_message()`: builds `Part(root=TextPart(text=user_text))`
      first, then one `Part(root=FilePart(file=FileWithBytes(bytes,
      mime_type, name="attachment.png")))` per attachment. Identical
      shape to `hosts/cli/streaming.py::send_and_stream` so
      Hephaestus can't tell host apart on the wire.

### Step 3 — `DemoGuiClient` accepts the 3-tuple ✅ 2026-04-26

- [x] `hosts/gui/demo_client.py`: docstring updated; the existing
      `len(item) >= 2` guard already tolerates 3-tuples and silently
      ignores `item[2]`. Demo mode has no real agent on the other
      end, so dropping attachments is the only sensible behaviour.

### Step 4 — Inline thumbnails in dialogue history ✅ 2026-04-26

- [x] `hosts/gui/dialogue.py::DialogueEntry`: new `attachments`
      parameter (kw-only, default `None`) plus a private
      `_attachment_thumbs` cache slot. `__slots__` extended.
- [x] New `DialogueHistory._entry_thumbnails()` lazily decodes
      `(b64, mime)` → PIL → `pygame.Surface`, thumbnails to 80px
      tall, caches on the entry. Bad attachments are silently
      dropped from the preview — the outgoing `FilePart` still ships.
- [x] `_entry_height()` reserves `_THUMB_H + _THUMB_GAP` of vertical
      room when an entry has attachments, so the next bubble doesn't
      stack over the strip.
- [x] `_draw_entry()` user branch renders the strip right-aligned
      below the bubble after blitting the bubble itself.

### Step 5 — Tests ✅ 2026-04-26

- [x] `tests/unit/test_gui_attachment_send_path.py`: 10 tests across
      5 classes:
      - `TestSubmitTextTupleShape` (3) — empty-list default, drain
        on submit, drain-before-put ordering.
      - `TestQuickActionTupleShape` (1) — quick actions emit
        `(target, text, [])`.
      - `TestDialogueEntryAttachments` (3) — default `None`, explicit
        value stored, `_entry_height` reserves the strip.
      - `TestGuiClientMultiPartSend` (2) — text-only path emits one
        `TextPart`; attachments produce TextPart + N FilePart with the
        b64 payload preserved.
      - `TestDemoGuiClientToleratesThreeTuple` (1) — drop-in 3-tuple
        doesn't crash; greeting still emits.
      Whole file passes in 0.79 s.

### Step 6 — Live smoke (queued for next interactive `make gui` session)

- [ ] Alt+V → type "describe this UI bug" → Enter. Confirm:
  - User bubble carries the placeholder text and a thumbnail strip
    underneath the message.
  - Hephaestus's first response references the screenshot (proves
    the FilePart reached the routing LLM).
- [ ] Alt+V three times in a row → submit. Confirm three thumbnails
      render side-by-side and three FilePart entries hit Hephaestus.
- [ ] After submit, Alt+V → confirm the placeholder counter resets
      to `image #1` (drain happened).
- [ ] `KOURAI_SANDBOX=container make gui-demo` → confirm DemoGuiClient
      tolerates the 3-tuple shape and the scripted scene still plays.

---

## Notes / open questions

- **Why not strip the `[📎 image #N queued]` placeholder before
  sending to the agent?** The CLI doesn't strip it either. The text
  carries the placeholder *and* the FilePart rides alongside, so the
  agent sees both: a textual hint that images were attached, plus the
  actual pixels. The user's bubble keeps the same text it submitted —
  no surprise at re-render time. If we ever want a clean separation,
  do it once in `a2a_utils` so both hosts strip identically.

- **Thumbnail strip placement.** Right-aligned beneath the bubble —
  same edge as the bubble itself. The alternative (left edge of
  bubble) splits the eye between text and image; right-aligning
  keeps the user's visual scan one column.

- **Pillow availability.** Both Alt+V capture and thumbnail decode
  require Pillow. It's already a hard dep in `hosts/gui/pyproject.toml`
  for the existing image rendering, so M11 doesn't add weight. The
  decode path silently degrades to "no thumbnail, FilePart still
  rides" if Pillow is missing — better than crashing the whole
  history render.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  also wants Round 6 smoke first.
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  zombie `.pytest_cache` mitigation. Container-plumbing work; tractable
  but not the highest leverage win available.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor
  on the board; high-DPI / accessibility win once it lands.
