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

init python:
    from bridge import RenPyBridge
    import json
    import random as _random

    # Global bridge instance (singleton)
    bridge = RenPyBridge(agent_script="agents/vn_bridge.py")

    # Character definitions — colors from FORGE_AESTHETIC.md agent personality colors
    h  = Character("Hephaestus", color="#FF9500", what_prefix='"', what_suffix='"')
    t  = Character("Techne",     color="#17A2B8", what_prefix='"', what_suffix='"')
    k  = Character("Kallos",     color="#D946EF", what_prefix='"', what_suffix='"')
    m  = Character("Metis",      color="#4C6EF5", what_prefix='"', what_suffix='"')
    d  = Character("Dokimasia",  color="#6C757D", what_prefix='"', what_suffix='"')
    mn = Character("Mneme",      color="#B73E1D", what_prefix='"', what_suffix='"')
    p  = Character("Player",     color="#E8E8E8")

    # Agent ID → (Character, epithet) for dynamic dialogue routing
    AGENT_CHARS = {
        "hephaestus": (h,  "Master of the Forge"),
        "techne":     (t,  "Artisan of Code"),
        "kallos":     (k,  "Eye of Elegance"),
        "metis":      (m,  "Architect of Intent"),
        "dokimasia":  (d,  "Guardian of Standards"),
        "mneme":      (mn, "Keeper of Memory"),
    }

    # Agent accent colors (mirrors AGENT_CHARS, used by HUD and gossip bubble)
    AGENT_COLORS = {
        "hephaestus": "#FF9500",
        "techne":     "#17A2B8",
        "kallos":     "#D946EF",
        "metis":      "#4C6EF5",
        "dokimasia":  "#6C757D",
        "mneme":      "#B73E1D",
    }

    # Canonical display order for the affinity HUD
    AGENT_ORDER = ["hephaestus", "techne", "kallos", "metis", "dokimasia", "mneme"]

    def get_tier(score):
        """Map affinity 0.0-1.0 → tier 1-4 (matches RELATIONSHIP_SYSTEMS.md)."""
        if score < 0.3: return 1
        if score < 0.6: return 2
        if score < 0.8: return 3
        return 4

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
        $ bridge.send_message({"action": "message", "text": user_text})

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

        if vn_response:
            $ agent_id = vn_response.get("agent", "hephaestus")
            $ message_text = vn_response.get("message", "The forge is silent...")
            $ char_info = AGENT_CHARS.get(agent_id)

            if char_info:
                $ char_obj, epithet = char_info
                char_obj "[message_text]"
            else:
                "[agent_id]" "[message_text]"

            # ── Affinity update (client-side) ─────────────────────────────
            # +0.02 for the responding agent. Backend affinity_delta events
            # will replace this arithmetic once RELATIONSHIP_SYSTEMS is live.
            $ affinity[agent_id] = min(1.0, affinity.get(agent_id, 0.5) + 0.02)
            $ gossip_turn_counter += 1

            # ── Gossip trigger — every 3 turns, an idle agent speaks ──────
            if gossip_turn_counter % 3 == 0:
                python:
                    idle = [a for a in AGENT_ORDER if a != agent_id]
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

# ── CLEANUP ──────────────────────────────────────────────────────────────

label quit:
    $ renpy.hide_screen("affinity_hud")
    $ renpy.hide_screen("gossip_bubble")
    $ bridge.shutdown()
    return
