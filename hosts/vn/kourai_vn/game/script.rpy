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

    def _get_virtue_context_dict():
        """Build virtue data structure for Forge Journal visualization.

        Phase C12: Returns dict with virtue scores, session deltas, and discoveries.
        Queries the python agent subprocess via the bridge to avoid sqlite3 dependency issues.
        """
        try:
            player_id = persistent.player_id
            if not player_id:
                raise ValueError("No player ID")
                
            bridge.send_message({"action": "get_virtue_context", "player_id": player_id})
            
            import time as _time
            _deadline = _time.time() + 2.0
            _result = None
            while _time.time() < _deadline:
                msg = bridge.get_message(timeout=0.05)
                if msg and msg.get("action") == "virtue_context_result":
                    _result = msg
                    break
            
            if not _result:
                raise TimeoutError("Bridge did not return virtues")
                
            virtues = _result.get("virtues", {})
            deltas = _result.get("deltas", {})
            facts = _result.get("facts", [])

            # Format virtue scores (0.0-1.0 range)
            virtue_dict = {
                "arete": max(0.0, min(1.0, virtues.get("arete", 0.0))),
                "sophia": max(0.0, min(1.0, virtues.get("sophia", 0.0))),
                "synergy": max(0.0, min(1.0, virtues.get("synergy", 0.0))),
                "techne_v": max(0.0, min(1.0, virtues.get("techne_v", 0.0))),
                "mneia": max(0.0, min(1.0, virtues.get("mneia", 0.0))),
                "eros": max(0.0, min(1.0, virtues.get("eros", 0.0))),
            }

            # Session summary with deltas
            delta_lines = []
            for virtue_name, delta in deltas.items():
                if delta > 0:
                    delta_lines.append(f"+{delta:.3f} {virtue_name}")
                elif delta < 0:
                    delta_lines.append(f"{delta:.3f} {virtue_name}")

            if delta_lines:
                summary = "This session: " + ", ".join(delta_lines)
            else:
                summary = "No virtue changes this session."

            # Recent discoveries (new facts)
            recent_facts = [f.get("body", "")[:60] for f in facts if f]

            return {
                **virtue_dict,
                "session_summary": summary,
                "recent_facts": recent_facts,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "arete": 0.5,
                "sophia": 0.5,
                "synergy": 0.5,
                "techne_v": 0.5,
                "mneia": 0.5,
                "eros": 0.5,
                "session_summary": "The forge is quiet. No session data available.",
                "recent_facts": [],
            }

    def _build_save_json(d):
        """Attach per-slot JSON data so save slots show the last active agent's portrait."""
        import store as _store
        agent_id = getattr(_store, "last_agent_id", "hephaestus")
        char_data = AGENT_CHARS.get(agent_id)
        epithet = char_data[1] if char_data else ""
        d["agent_portrait"] = agent_id
        d["active_agent"] = agent_id
        d["save_note"] = epithet

    config.save_json_callbacks.append(_build_save_json)

    def _validate_and_set_project(project_path):
        """Validate project directory and add to recent projects.

        Phase C13: Checks if path exists and contains a git repo or valid project marker.
        """
        import os

        if not project_path or not os.path.isabs(project_path):
            renpy.notify("Please enter an absolute project path")
            return

        if not os.path.isdir(project_path):
            renpy.notify(f"Path does not exist: {project_path}")
            return

        # Check for git, pyproject.toml, or package.json as project markers
        has_git = os.path.isdir(os.path.join(project_path, ".git"))
        has_pyproject = os.path.isfile(os.path.join(project_path, "pyproject.toml"))
        has_package_json = os.path.isfile(os.path.join(project_path, "package.json"))

        if not (has_git or has_pyproject or has_package_json):
            renpy.notify(
                "Project not found — no .git, pyproject.toml, or package.json"
            )
            return

        # Set as current project
        persistent.project_path = project_path

        # Add to recent projects (avoid duplicates, limit to 10)
        recent = getattr(persistent, "recent_projects", []) or []
        if project_path in recent:
            recent.remove(project_path)
        recent.insert(0, project_path)
        persistent.recent_projects = recent[:10]

        renpy.notify(f"✓ Project set: {os.path.basename(project_path)}")

    def _create_new_project_workspace(project_name):
        """Create a new project workspace under Projects/<PlayerName>/<ProjectName>."""
        import os
        import getpass

        if not project_name:
            renpy.notify("Project name cannot be empty.")
            return

        # Sanitize the project name
        safe_name = "".join([c for c in project_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not safe_name:
            renpy.notify("Invalid project name.")
            return
            
        try:
            player_name = getpass.getuser()
        except:
            player_name = "Player"

        # Resolve path relative to the user's home directory
        home_dir = os.path.expanduser("~")
        
        # Build the path
        target_dir = os.path.join(home_dir, "Projects", player_name, safe_name)
        
        try:
            os.makedirs(target_dir, exist_ok=True)
            
            # Initialize a basic .git repository (optional, but requested by validation)
            git_dir = os.path.join(target_dir, ".git")
            if not os.path.exists(git_dir):
                 os.makedirs(git_dir)
                 
            # Create a basic pyproject.toml to satisfy validation
            pyproject_path = os.path.join(target_dir, "pyproject.toml")
            if not os.path.exists(pyproject_path):
                with open(pyproject_path, "w") as f:
                    f.write(f'[project]\nname = "{safe_name}"\nversion = "0.1.0"\n')

            # Use the existing validation function to set it
            _validate_and_set_project(target_dir)
            renpy.notify(f"✓ Created: {target_dir}")
        except Exception as e:
            renpy.notify(f"Error creating project: {e}")

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
# player_id persists ACROSS all save files (persistent) — it is the
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

    # Start the agent subprocess — only verifies uv + process spawn
    if not bridge.start():
        "ERROR" "Could not start the agent process. Is uv installed? Run 'make up' to start the agents."
        return

    # Assign a persistent player_id on first ever launch, integrating with shared DB via the bridge.
    python:
        import uuid as _uuid
        import time as _time
        
        _needs_onboarding = False
        
        # Check profiles via bridge
        bridge.send_message({"action": "get_profiles"})
        _deadline = _time.time() + 5.0
        _profiles = []
        while _time.time() < _deadline:
            msg = bridge.get_message(timeout=0.05)
            if msg and msg.get("action") == "profiles_result":
                _profiles = msg.get("profiles", [])
                break

        if _profiles:
            # Sync persistent to the active profile if we already have one
            _active = next((p for p in _profiles if p.get("is_active")), _profiles[0])
            persistent.player_id = _active["player_id"]
            bridge.send_message({"action": "set_active_profile", "player_id": persistent.player_id})
        elif not persistent.player_id:
            # No profiles exist at all, we must do onboarding
            _needs_onboarding = True

        # D4: Initialize romance mode (default enabled for new players)
        if not hasattr(persistent, "romance_mode_enabled"):
            persistent.romance_mode_enabled = True

        # New context_id per fresh start (not a load — that path is in after_load)
        context_id = _uuid.uuid4().hex

    if _needs_onboarding:
        "System" "The Forge requires an identity before you may enter."
        
        $ _display_name = ""
        while not _display_name:
            $ _display_name = renpy.input("What is your name? (Required):", length=50)
            $ _display_name = _display_name.strip()
            
        $ _pronouns = renpy.input("What are your pronouns? (Optional):", length=50)
        $ _pronouns = _pronouns.strip()
        
        "System" "How should the golden maidens address you?"
        menu:
            "As a fellow artisan (Mortal)":
                $ _role = "mortal"
                $ _title = "Artisan"
            "As a God among mortals (Divine)":
                $ _role = "divine"
                $ _title = "God"
            "As a proven champion (Hero)":
                $ _role = "hero"
                $ _title = "Champion"
            "As their beloved master (Devoted)":
                $ _role = "devoted"
                $ _title = "Master"
            "Just by my name":
                $ _role = "name_only"
                $ _title = ""

        python:
            # Send profile creation request to the bridge
            bridge.send_message({
                "action": "create_profile",
                "display_name": _display_name,
                "tts_name": _display_name,
                "title": _title,
                "role": _role,
                "pronouns": _pronouns
            })
            
            _deadline = _time.time() + 5.0
            while _time.time() < _deadline:
                msg = bridge.get_message(timeout=0.05)
                if msg and msg.get("action") == "create_profile_result":
                    persistent.player_id = msg.get("player_id")
                    break

            if not persistent.player_id:
                # Fallback if bridge failed
                persistent.player_id = _uuid.uuid4().hex

    python:
        player_id = persistent.player_id

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
        $ bridge.send_message({"action": "message", "text": user_text, "context_id": context_id or "", "player_id": player_id or "", "project_path": getattr(persistent, "project_path", "")})

        # Show the thinking indicator and poll for responses.
        # Status messages (action="status") update the label live.
        # The first non-status message is the final agent response.
        python:
            import time as _time
            thinking_status = "The forge stirs..."
            vn_response = None
            renpy.show_screen("thinking")

            _deadline = _time.time() + 60.0
            while vn_response is None and _time.time() < _deadline:
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
                    _deadline = _time.time() + 60.0
                    while vn_response is None and _time.time() < _deadline:
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
                # Phase F3: Persist active agent across save/load cycles
                persistent.active_agent = last_agent_id

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
                    $ _char_obj, _epithet = char_info
                    _char_obj "[message_text]"
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

    # Drain any stale messages in the queue from before the save occurred.
    # This prevents mid-dialogue saves from replaying buffered responses.
    python:
        import time as _time
        _timeout = 0.5
        _deadline = _time.time() + _timeout
        while _time.time() < _deadline:
            stale = bridge.get_message(timeout=0.05)
            if stale is None:
                break

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
        $ persistent.project_path = new_path
    return

label create_project_label:
    $ new_project_name = renpy.input("Enter new project name:", length=50)
    $ new_project_name = new_project_name.strip()
    if new_project_name:
        $ _create_new_project_workspace(new_project_name)
    return

# ── CLEANUP ──────────────────────────────────────────────────────────────

label quit:
    $ renpy.hide_screen("affinity_hud")
    $ renpy.hide_screen("gossip_bubble")
    $ bridge.shutdown()
    return
