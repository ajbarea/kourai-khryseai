# game/script.rpy

# ── INITIALIZATION ───────────────────────────────────────────────────────

init python hide:
    import sys
    import os
    # Add game/libs to path so we can import our bridge
    # renpy.config.gamedir is the 'game/' folder
    libs_dir = os.path.join(renpy.config.gamedir, "libs")
    if libs_dir not in sys.path:
        sys.path.append(libs_dir)
    # Add shared/src so any screen or label can import kourai_common directly.
    # gamedir is  …/hosts/vn/kourai_vn/game/  →  ../../../../shared/src is the root
    _shared_src = os.path.abspath(os.path.join(renpy.config.gamedir, "..", "..", "..", "..", "shared", "src"))
    if _shared_src not in sys.path:
        sys.path.append(_shared_src)

init python:
    from bridge import RenPyBridge
    import json
    import random as _random

    # Global bridge instance (singleton)
    bridge = RenPyBridge(agent_script="agents/vn_bridge.py")

    # Character definitions — colors from FORGE_AESTHETIC.md agent personality colors
    h   = Character("Hephaestus", color="#FF9500", what_prefix='"', what_suffix='"')
    t   = Character("Techne",     color="#17A2B8", what_prefix='"', what_suffix='"')
    k   = Character("Kallos",     color="#D946EF", what_prefix='"', what_suffix='"')
    m   = Character("Metis",      color="#4C6EF5", what_prefix='"', what_suffix='"')
    d   = Character("Dokimasia",  color="#6C757D", what_prefix='"', what_suffix='"')
    mn  = Character("Mneme",      color="#B73E1D", what_prefix='"', what_suffix='"')
    pck = Character("Puck",       color="#7FBC8C", what_prefix='"', what_suffix='"')
    cpd = Character("Cupid",      color="#E8728C", what_prefix='"', what_suffix='"')
    p   = Character("Player",     color="#E8E8E8")

    # Agent ID → (Character, epithet) for dynamic dialogue routing
    AGENT_CHARS = {
        "hephaestus": (h,   "Master of the Forge"),
        "techne":     (t,   "Artisan of Code"),
        "kallos":     (k,   "Eye of Elegance"),
        "metis":      (m,   "Architect of Intent"),
        "dokimasia":  (d,   "Guardian of Standards"),
        "mneme":      (mn,  "Keeper of Memory"),
        "puck":       (pck, "Spirit of Mischief"),
        "cupid":      (cpd, "Arrow of the Heart"),
    }

    # Agent accent colors (mirrors AGENT_CHARS, used by HUD and gossip bubble)
    AGENT_COLORS = {
        "hephaestus": "#FF9500",
        "techne":     "#17A2B8",
        "kallos":     "#D946EF",
        "metis":      "#4C6EF5",
        "dokimasia":  "#6C757D",
        "mneme":      "#B73E1D",
        "puck":       "#7FBC8C",
        "cupid":      "#E8728C",
    }

    # Canonical display order for the affinity HUD (6 maidens only — spirits are sidebar)
    AGENT_ORDER = ["hephaestus", "techne", "kallos", "metis", "dokimasia", "mneme"]

    # Valid portrait states per agent — the "other" key maps agent-specific
    # states defined in PORTRAIT_GENERATION_GUIDE.md.
    PORTRAIT_STATES = {
        "hephaestus": {"neutral", "vulnerable", "approving"},
        "techne":     {"neutral", "vulnerable", "focused"},
        "kallos":     {"neutral", "vulnerable", "appraising"},
        "metis":      {"neutral", "vulnerable", "contemplating"},
        "dokimasia":  {"neutral", "vulnerable", "scrutinizing"},
        "mneme":      {"neutral", "vulnerable", "remembering"},
        "puck":       {"neutral", "mischievous", "smug"},
        "cupid":      {"neutral", "hopeful", "knowing"},
    }

    def validate_portrait_state(agent_id, state):
        """Return state if the PNG asset exists, else 'neutral'."""
        valid = PORTRAIT_STATES.get(agent_id, {"neutral"})
        if state not in valid:
            state = "neutral"
        path = "images/portraits/{}_{}.png".format(agent_id, state)
        if renpy.loadable(path):
            return state
        return None  # Asset missing entirely — caller should skip portrait

    def _portrait_image(agent_id, state):
        """Return an Image displayable for the given agent/state, or None."""
        path = "images/portraits/{}_{}.png".format(agent_id, state)
        if renpy.loadable(path):
            return Image(path)
        # Try neutral fallback
        neutral_path = "images/portraits/{}_neutral.png".format(agent_id)
        if renpy.loadable(neutral_path):
            return Image(neutral_path)
        return Null()

    def get_tier(score):
        """Map affinity 0.0-1.0 → tier 1-4 (matches RELATIONSHIP_SYSTEMS.md)."""
        if score < 0.3: return 1
        if score < 0.6: return 2
        if score < 0.8: return 3
        return 4

    def _get_virtue_text():
        """Load current virtue context for the Forge Journal screen.

        Called once each time the screen opens — not on every render frame.
        Relies on kourai_common being on sys.path (added in init python hide).
        """
        try:
            from kourai_common.virtues import get_virtue_context
            return get_virtue_context(renpy.persistent.player_id)
        except Exception as e:
            return "Error loading virtues: " + str(e)

    def _build_save_json():
        """Attach per-slot JSON data so save slots show the last active agent's portrait."""
        import store as _store
        agent_id = getattr(_store, "last_agent_id", "hephaestus")
        char_data = AGENT_CHARS.get(agent_id)
        epithet = char_data[1] if char_data else ""
        return {
            "agent_portrait": agent_id,
            "save_note": epithet,
        }

    config.save_json_callback = _build_save_json

    # Pre-authored gossip lines per agent — personality grounded in CHARACTER_DESIGN.md.
    # Each entry: (stage_direction, spoken_line).
    # Shown as flavor text from idle agents between player conversations.
    # Upgrade path: replace with live agent-to-agent gossip once backend supports it.
    GOSSIP_LINES = {
        "techne": [
            ("*glancing over*",   "Their commit messages are getting more descriptive. Not that I noticed."),
            ("*quietly*",         "Interesting approach. Wrong, but interesting."),
            ("*to herself*",      "They asked for help and then actually implemented it correctly. That's... new."),
        ],
        "kallos": [
            ("*under her breath*", "Four spaces. Four. It's not a suggestion, it's civilization."),
            ("*reviewing something*", "The naming is almost elegant. Almost."),
            ("*pausing*",          "They're learning. I can see it in the indentation."),
        ],
        "metis": [
            ("*thinking aloud*",  "Their architecture is becoming more deliberate. Patterns are forming."),
            ("*quietly*",         "They asked a better question today. The right question unlocks everything."),
            ("*considering*",     "Three sessions in and they're starting to think in systems. Good."),
        ],
        "dokimasia": [
            ("*running checks*",        "Fourteen tests. Up from nine. They're taking this seriously."),
            ("*flatly*",                "No regressions this session. Unusual. Noted."),
            ("*quietly satisfied*",     "They fixed the edge case I flagged. Without being asked twice."),
        ],
        "mneme": [
            ("*writing*",      "Seven sessions now. They return, always. The forge remembers."),
            ("*looking up*",   "They phrased that question differently today. They're growing."),
            ("*softly*",       "Some conversations deserve to be kept. I keep them all."),
        ],
        "hephaestus": [
            ("*watching*",       "Good work done today. The Maidens are pleased. So am I."),
            ("*to himself*",     "Another session. Another piece of the craft. This is how mastery is built."),
            ("*approvingly*",    "They didn't give up when it got hard. That matters more than they know."),
        ],
    }

# ── PERSISTENT VARIABLES ─────────────────────────────────────────────────
# These live in the Ren'Py save file. `default` means "set this if not already
# set" — safe across save/load cycles.

default thinking_status = "The forge stirs..."
default vn_response = None
default last_agent_id = "hephaestus"  # tracked for save slot portrait via save_json_callback

# ── Player Identity ───────────────────────────────────────────────────────────
# player_id persists ACROSS all save files (renpy.persistent) — it is the
# player's long-term identity with the agent swarm.
# context_id is PER SAVE — each save slot gets its own conversation thread.
# Both are set on first start; context_id is sent on resume so agents can
# recall the conversation history associated with that save slot.
default player_id = None
default context_id = None

# Affinity scores per agent — persisted in the Ren'Py save file.
# Starts at 0.5 (neutral/professional). Updated client-side each conversation.
# Backend will eventually send affinity_delta events; this will become the
# authoritative source once RELATIONSHIP_SYSTEMS.md backend is implemented.
default affinity = {
    "hephaestus": 0.5,
    "techne":     0.5,
    "kallos":     0.5,
    "metis":      0.5,
    "dokimasia":  0.5,
    "mneme":      0.5,
}
default gossip_turn_counter = 0

# ── MAIN GAME FLOW ───────────────────────────────────────────────────────

label start:
    scene black
    "System" "Initializing the Forge Bridge..."

    # Assign a persistent player_id on first ever launch.
    # Uses renpy.persistent so it survives across all save files.
    python:
        import uuid as _uuid
        if not renpy.persistent.player_id:
            renpy.persistent.player_id = _uuid.uuid4().hex
        player_id = renpy.persistent.player_id

        # New context_id per fresh start (not a load — that path is in after_load)
        context_id = _uuid.uuid4().hex

    # Start the agent subprocess — only verifies uv + process spawn
    if not bridge.start():
        "ERROR" "Could not start the agent process. Is uv installed? Run 'make up' to start the agents."
        return

    "System" "Verifying agent connection..."

    # Actually ping Hephaestus before claiming connected
    $ connection_error = bridge.check_connection(timeout=15.0)
    if connection_error:
        "ERROR" "Could not reach the agents: [connection_error]"
        "System" "Run 'make up' before launching the VN, then try again."
        return

    "System" "Connection to Kourai Khryseai established."
    "System" "The Master of the Forge is listening."

    # Show the persistent affinity HUD — stays visible for the whole session
    $ renpy.show_screen("affinity_hud")

    jump main_loop

label main_loop:
    # Check for any async bridge errors first
    $ error = bridge.get_error()
    if error:
        "BRIDGE ERROR" "[error]"

    # Get user input
    $ user_text = renpy.input("You: ", length=200)
    $ user_text = user_text.strip()

    if user_text:
        $ bridge.send_message({"action": "message", "text": user_text, "context_id": context_id or "", "player_id": player_id or "", "project_path": getattr(renpy.persistent, "project_path", "")})

        # Show the thinking indicator and poll for responses.
        # Status messages (action="status") update the label live.
        # The first non-status message is the final agent response.
        python:
            import time
            thinking_status = "The forge stirs..."
            vn_response = None
            renpy.show_screen("thinking")

            deadline = time.time() + 60.0
            while vn_response is None and time.time() < deadline:
                msg = bridge.get_message(timeout=0.0)  # non-blocking check
                if msg is None:
                    # Yield to Ren'Py briefly so the screen redraws
                    renpy.pause(0.05, hard=False)
                    continue
                if msg.get("action") == "status":
                    # Truncate long pipeline messages to fit the HUD
                    thinking_status = msg.get("message", "")[:80]
                    renpy.restart_interaction()
                else:
                    vn_response = msg

            renpy.hide_screen("thinking")

        # ── Handle choice events ─────────────────────────────────────────────
        # If the first message has action="choice", show the choice screen
        # and send the player's selection back before rendering dialogue.
        if vn_response and vn_response.get("action") == "choice":
            python:
                _choices = vn_response.get("choices", [])
                _choice_prompt = vn_response.get("prompt", "Choose your path")
                _choice_speaker = vn_response.get("agent", "hephaestus").capitalize()
                if _choices:
                    _selected = renpy.call_screen(
                        "agent_choice",
                        choices=_choices,
                        speaker_name=_choice_speaker,
                        prompt=_choice_prompt,
                    )
                    bridge.send_message({
                        "action": "choice",
                        "choice": _selected,
                        "context_id": context_id or "",
                        "player_id": player_id or "",
                    })
                    # The bridge will respond with a normal message; wait for it
                    vn_response = None
                    deadline = __import__("time").time() + 60.0
                    while vn_response is None and __import__("time").time() < deadline:
                        msg = bridge.get_message(timeout=0.0)
                        if msg is None:
                            renpy.pause(0.05, hard=False)
                            continue
                        if msg.get("action") == "status":
                            thinking_status = msg.get("message", "")[:80]
                            renpy.restart_interaction()
                        else:
                            vn_response = msg

        # ── Drain all beats the bridge queued (paginated sentences) ──────────
        # vn_response is the first non-status message. Subsequent beats from the
        # same agent response are already in the bridge inbox. We read them all
        # before jumping back to the input prompt.
        python:
            beat_queue = []
            if vn_response:
                beat_queue.append(vn_response)
                # Drain any immediately available follow-up beats (non-blocking)
                while True:
                    extra = bridge.get_message(timeout=0.0)
                    if extra is None:
                        break
                    # Stop draining if we hit a new user-action boundary
                    if extra.get("action") == "status":
                        continue  # skip stray status msgs between beats
                    beat_queue.append(extra)

        if beat_queue:
            python:
                # Track which agent gets the affinity bump this turn
                last_agent_id = beat_queue[-1].get("agent", "hephaestus")

            # Render each dialogue beat in sequence
            $ _beat_idx = 0
            while _beat_idx < len(beat_queue):
                $ _beat = beat_queue[_beat_idx]
                $ agent_id = _beat.get("agent", "hephaestus")
                $ message_text = _beat.get("message", "The forge is silent...")
                $ portrait_state = _beat.get("portrait", "neutral")
                $ char_info = AGENT_CHARS.get(agent_id)

                # Show/update portrait for speaking agent
                python:
                    resolved_state = validate_portrait_state(agent_id, portrait_state)
                    if resolved_state is not None:
                        renpy.show_screen("agent_portrait", agent_id=agent_id, state=resolved_state)
                    else:
                        renpy.hide_screen("agent_portrait")

                if char_info:
                    $ char_obj, epithet = char_info
                    char_obj "[message_text]"
                else:
                    "[agent_id]" "[message_text]"

                $ _beat_idx += 1

            # Hide portrait after the last beat in this turn
            $ renpy.hide_screen("agent_portrait")

            # ── Affinity update (client-side) ─────────────────────────────
            $ affinity[last_agent_id] = min(1.0, affinity.get(last_agent_id, 0.5) + 0.02)
            $ gossip_turn_counter += 1

            # ── Gossip trigger — every 3 turns, an idle agent speaks ──────
            if gossip_turn_counter % 3 == 0:
                python:
                    idle = [a for a in AGENT_ORDER if a != last_agent_id]
                    gossip_agent = _random.choice(idle)
                    hint, line = _random.choice(GOSSIP_LINES[gossip_agent])
                    renpy.show_screen(
                        "gossip_bubble",
                        speaker_name=gossip_agent.capitalize(),
                        hint=hint,
                        line=line,
                        color=AGENT_COLORS[gossip_agent],
                    )
        else:
            "System" "No response from the forge. The agents may be busy — try again."

    jump main_loop

# ── SAVE / LOAD ──────────────────────────────────────────────────────────
# Ren'Py calls `after_load` automatically after any save file is loaded.
# The bridge subprocess is dead at that point (it doesn't survive game close),
# so we restart it here and reconnect to the agents before resuming play.

label after_load:
    if not bridge.is_running:
        $ bridge_ok = bridge.start()
        if not bridge_ok:
            "System" "Could not restart the agent process after loading. Run 'make up' and relaunch."
            return
        $ connection_error = bridge.check_connection(timeout=15.0)
        if connection_error:
            "System" "Could not reconnect to agents after loading: [connection_error]"
            return

    # Send resume action with saved context_id so the bridge restores the
    # correct conversation thread for this save slot.
    python:
        resume_payload = {"action": "resume", "context_id": context_id or ""}
        if player_id:
            resume_payload["player_id"] = player_id
        bridge.send_message(resume_payload)

    "System" "The forge rekindles. The agents remember you."
    return


label project_input_label:
    $ new_path = renpy.input("Enter absolute path to project directory:", length=200)
    $ new_path = new_path.strip()
    if new_path:
        $ renpy.persistent.project_path = new_path
    return

# ── CLEANUP ──────────────────────────────────────────────────────────────

label quit:
    $ renpy.hide_screen("affinity_hud")
    $ renpy.hide_screen("gossip_bubble")
    $ bridge.shutdown()
    return
