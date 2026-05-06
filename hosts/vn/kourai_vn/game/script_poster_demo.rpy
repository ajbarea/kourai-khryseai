## Ren'Py Script Language
## script_poster_demo.rpy — scripted demo scene for poster screenshots.
##
## Launches when KOURAI_POSTER_DEMO=1 is set in the environment.
## No bridge / no Docker / no LLM — pure scripted frames.
## Ends at a Metis clarifying question with menu choices visible — screenshot
## that moment: both Hephaestus (right) and Metis (left) visible, Metis lit
## as active speaker, dialogue box showing the CSV question, affinity HUD on
## the right.
##
## Uses the real multi-slot portrait system from screens_dialogue.rpy so the
## scene you capture for the poster is faithful to live VN behaviour — not a
## screenshot-only fiction.
##
## Canonical script source: shared/src/kourai_common/demo_script.py
## (CSV_DEMO_TURNS / CSV_DEMO_CHOICES). CLI demo.py + GUI demo_client.py
## iterate that list directly; this .rpy hand-codes the same beats because
## Ren'Py can't cleanly import Python at script-time. If the canonical
## script changes, mirror the edit here too — there's no auto-sync.

## The painted forge-atelier background source PNG is 1672×941; scale it
## to the canonical 1920×1080 stage so it fills the scene without the
## default black-bar letterbox around a smaller source. ATL image-with-
## transform is Ren'Py 8.x canonical for this — see renpy.org/doc/html/
## atl.html and renpy.org/doc/html/displayables.html#Transform.
image forge_hades:
    "images/forge_hades_src.png"
    xysize (1920, 1080)


init python:
    # Redirect the normal `start` label to `poster_demo` when the env flag
    # is set. In Ren'Py 8.x config.start_label was removed; the canonical
    # replacement is config.label_overrides (see the Developer Compatibility
    # section of renpy.org/doc/html/config.html). Default init priority (0)
    # is fine — all init blocks complete before the `start` jump fires.
    import os as _poster_os
    if _poster_os.environ.get("KOURAI_POSTER_DEMO"):
        config.label_overrides["start"] = "poster_demo"


label poster_demo:
    ## Hide the quick menu (Back · History · Skip · Auto · Save · ...) for
    ## the whole demo run — it reads as UI chrome in screenshots and fights
    ## with the Hades-style dialogue composition. Restored on exit.
    $ quick_menu = False

    ## Painted forge-atelier backdrop — warm forge upper-left, indigo
    ## moonlit window upper-right, quiet flagstones center-bottom for
    ## standing sprites. Soft fade-in gives the scene a cinematic opener
    ## rather than a hard cut from the main menu.
    scene forge_hades with fade

    ## Seed a believable affinity snapshot so the BONDS HUD renders with
    ## varied, interesting numbers instead of all 0.5. Demo-only override.
    python:
        affinity["hephaestus"] = 0.71
        affinity["metis"]      = 0.68
        affinity["kallos"]     = 0.63
        affinity["techne"]     = 0.58
        affinity["mneme"]      = 0.52
        affinity["dokimasia"]  = 0.44
        last_agent_id = "metis"

    ## Show the affinity HUD — reinforces the VN's per-agent relationship
    ## angle without relying on the bridge.
    show screen affinity_hud

    ## Opening beat — narrator (no speaker), so the say screen skips the
    ## plaque entirely and the line reads as a setting card, not a
    ## speaker with nothing to say. Escaped `[[` renders as `[`.
    "[[ poster demo · scripted · no bridge ]"

    ## Hephaestus enters stage-right first. He's the Forge Master kicking
    ## off the pipeline, so the viewer sees him before the handoff.
    $ kourai_present_agent("hephaestus", "neutral")
    h "The forge is hot. What are we building?"
    h "Metis — draw up the plans. And no improvising."

    ## Metis enters stage-left. Hephaestus dims automatically (he's no
    ## longer the speaker), but stays visible — the viewer reads the scene
    ## as "Hephaestus has just routed to Metis" rather than "Metis, alone."
    $ kourai_present_agent("metis", "neutral")
    m "Analysing the events module…"
    m "Found three models with datetime fields — nested relationships in {b}Attendance{/b} and {b}Session{/b}."

    ## The clarifying question — the screenshot moment. Metis is active,
    ## Hephaestus is present but dimmed on the right, and the menu below
    ## pauses execution so the user can capture the frame with the question,
    ## dialogue box, both portraits, and the affinity HUD all visible.
    m "One decision before I draft the spec."

    menu:
        m "Should CSV export stream chunked I/O for large files? events.json has ~420k rows in production — loading all at once would spike memory. Streaming stays constant-memory but adds ~3ms/row of overhead."

        "Yes, stream chunked.":
            m "Noted. Drafting spec with streaming I/O."
            "[[ demo stops here — real pipeline would resume ]"

        "No, load in memory.":
            m "Noted. Drafting spec with in-memory load."
            "[[ demo stops here — real pipeline would resume ]"

        "Explain the trade-offs.":
            m "Streaming keeps memory flat but adds a small per-row cost. In-memory is faster for files under ~100MB and simpler to test, but RAM scales with row count. For events.json at 420k rows, streaming is the right call."
            "[[ demo exits after the explanation ]"

    ## Clean up on exit so returning to the main menu is tidy.
    $ kourai_clear_stage()
    hide screen affinity_hud
    $ quick_menu = True
    return
