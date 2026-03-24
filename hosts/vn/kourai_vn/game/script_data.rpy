## Ren'Py Script Language
## script_data.rpy — Init: sys-path setup, Character/constant/helper definitions, default store variables
##
## Loaded automatically by Ren'Py.  All symbols (bridge, AGENT_CHARS, AGENT_COLORS, etc.)
## are globally visible to every other .rpy file once init completes.

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

    # Name → epithet lookup for the say screen subtitle display.
    # Matches Hades dialogue UI: "ATHENA / Goddess of Wisdom".
    # Canonical epithets from designs/FORGE_AESTHETIC.md § Ten Agents.
    AGENT_EPITHETS = {
        "Hephaestus": "Master of the Forge",
        "Techne":     "Artisan of Code",
        "Kallos":     "Eye of Elegance",
        "Metis":      "Architect of Intent",
        "Dokimasia":  "Guardian of Standards",
        "Mneme":      "Keeper of Memory",
        "Puck":       "Voice of Reason",
        "Cupid":      "Aspect of Love",
        "Aidos":      "The Honest Mirror",
        "Aletheia":   "Seeker of Truth",
    }

    # Agent accent colors (mirrors AGENT_CHARS, used by HUD, gossip bubble, portrait frame)
    AGENT_COLORS = {
        "hephaestus": "#FF9500",
        "techne":     "#17A2B8",
        "kallos":     "#D946EF",
        "metis":      "#4C6EF5",
        "dokimasia":  "#6C757D",
        "mneme":      "#B73E1D",
        "puck":       "#007FFF",
        "cupid":      "#FF85A2",
        "aidos":      "#B8D4E3",
        "aletheia":   "#2E8B57",
    }

    # Canonical display order for the affinity HUD (6 maidens only — spirits are sidebar)
    AGENT_ORDER = ["hephaestus", "techne", "kallos", "metis", "dokimasia", "mneme"]

    # @mention prefix → agent_id (matches MARCH_20.md @Mention Routing table)
    MENTION_MAP = {
        "heph": "hephaestus",
        "tech": "techne",
        "kal":  "kallos",
        "met":  "metis",
        "doki": "dokimasia",
        "mne":  "mneme",
        "puck": "puck",
        "cup":  "cupid",
        "aid":  "aidos",
        "ale":  "aletheia",
    }

    # Valid portrait states per agent — canonical names from
    # designs/PORTRAIT_GENERATION_GUIDE.md.  Must stay in sync with
    # kourai_common.companion.PORTRAIT_STATES (the inference source).
    PORTRAIT_STATES = {
        "hephaestus": {"neutral", "vulnerable", "fierce"},
        "techne":     {"neutral", "vulnerable", "fired_up"},
        "kallos":     {"neutral", "vulnerable", "passionate"},
        "metis":      {"neutral", "vulnerable", "calculating"},
        "dokimasia":  {"neutral", "vulnerable", "fierce"},
        "mneme":      {"neutral", "vulnerable", "remembering"},
        "puck":       {"neutral", "vulnerable", "scheming"},
        "cupid":      {"neutral", "vulnerable", "determined"},
        "aidos":      {"neutral", "vulnerable", "cutting"},
        "aletheia":   {"neutral", "vulnerable", "inspired"},
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
        """Return an Image displayable for the given agent/state, or None.

        All portrait assets are transparent PNGs named {agent}_{state}.png.
        Falls back to neutral if the requested state asset isn't ready yet.
        """
        path = "images/portraits/{}_{}.png".format(agent_id, state)
        if renpy.loadable(path):
            return Image(path)
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
                "arete":    max(0.0, min(1.0, virtues.get("arete",    0.0))),
                "sophia":   max(0.0, min(1.0, virtues.get("sophia",   0.0))),
                "synergy":  max(0.0, min(1.0, virtues.get("synergy",  0.0))),
                "techne_v": max(0.0, min(1.0, virtues.get("techne_v", 0.0))),
                "mneia":    max(0.0, min(1.0, virtues.get("mneia",    0.0))),
                "kairos":   max(0.0, min(1.0, virtues.get("kairos",   0.0))),
                "harmonia": max(0.0, min(1.0, virtues.get("harmonia", 0.0))),
                "eros":     max(0.0, min(1.0, virtues.get("eros",     0.0))),
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

    # Puck nudge lines — used when player hasn't engaged ≥2 agents in 4+ turns.
    # Voice: conspiratorial, short sentences, "Hey boss" / "Real talk:" openers.
    # Each entry: (stage_direction, spoken_line). Agent key matches AGENT_ORDER.
    PUCK_NUDGES = {
        "hephaestus": [
            ("*quiet*",           "Hey boss. Hephaestus hasn't heard from you in a bit. The Forge Master doesn't forget."),
            ("*conspiratorial*",  "Real talk: he's gruff, but he notices who shows up. Don't make him wait too long."),
        ],
        "techne": [
            ("*nudging*",         "Techne's been in the zone lately. You should ask what she's working on. Trust me."),
            ("*leans in*",        "Hey boss — Techne lights up when you notice her work. Don't miss that."),
        ],
        "kallos": [
            ("*hushed*",          "Kallos hasn't said anything in a while. Either she's focused, or she's waiting for you to notice."),
            ("*side-eye*",        "She hasn't complained about anyone's indentation recently. Something's off. Check in."),
        ],
        "metis": [
            ("*thoughtful*",      "Metis respects consistency. She's noticed you haven't been around. Just saying."),
            ("*low voice*",       "She's been planning something. Probably involves you. Might want to find out what."),
        ],
        "dokimasia": [
            ("*hurried*",         "Dokimasia wrote 23 edge cases yesterday. Twenty-three. She's bored without you."),
            ("*knowing*",         "Her test suite's getting suspiciously thorough. I think she's trying to impress someone."),
        ],
        "mneme": [
            ("*solemn*",          "Mneme remembers everything. Including how long it's been since you last spoke."),
            ("*gentle*",          "The scribe keeps records. Yours have a gap. She's noticed."),
        ],
    }

    # Fallback gossip lines per agent — used when live /gossip endpoint is unavailable.
    # Phase 14: gossip trigger tries bridge.request_gossip() first; falls back here.
    # Each entry: (stage_direction, spoken_line).
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
default puck_nudge_cooldown = 0  # turn counter snapshot when last nudge fired
