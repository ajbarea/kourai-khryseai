## Ren'Py Script Language
## script_data.rpy — Init: sys-path setup, Character/constant/helper definitions, default store variables
##
## Loaded automatically by Ren'Py.  All symbols (bridge, AGENT_CHARS, AGENT_COLORS, etc.)
## are globally visible to every other .rpy file once init completes.

# ── PERSISTENT DEFAULTS ──────────────────────────────────────────────────
# Ensure codex state is always a usable collection — the Codex screen can be
# opened straight from the main menu (before `start` runs), so lazy init in
# `start` / `unlock_codex_entry` isn't enough. Without these defaults,
# is_codex_entry_unlocked() hits ``None in persistent.codex_unlocked`` and
# TypeErrors. Default statements only set the value when it's unset on
# disk, so existing saves are preserved.
default persistent.codex_unlocked = set()
default persistent.codex_read = set()
default persistent.codex_new_notifications = []

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
    from kourai_common.agents import AGENT_METADATA, AGENT_QUOTES

    # Global bridge instance (singleton)
    bridge = RenPyBridge(agent_script="agents/vn_bridge.py")

    # Character definitions — derived from AGENT_METADATA
    # We still define short handles for script writing.
    # Hades-style convention (per ROADMAP M10): the name plaque already
    # signals the speaker, so dialogue is NOT auto-wrapped in literal
    # quote marks. Agent outputs decide per-line whether a line is
    # quoted, matching the CLI/GUI convention.
    h   = Character("Hephaestus", color=AGENT_METADATA["hephaestus"]["hex_color"])
    t   = Character("Techne",     color=AGENT_METADATA["techne"]["hex_color"])
    k   = Character("Kallos",     color=AGENT_METADATA["kallos"]["hex_color"])
    m   = Character("Metis",      color=AGENT_METADATA["metis"]["hex_color"])
    d   = Character("Dokimasia",  color=AGENT_METADATA["dokimasia"]["hex_color"])
    mn  = Character("Mneme",      color=AGENT_METADATA["mneme"]["hex_color"])
    pck = Character("Puck",       color=AGENT_METADATA["puck"]["hex_color"])
    cpd = Character("Cupid",      color=AGENT_METADATA["cupid"]["hex_color"])
    p   = Character("Player",     color="#E8E8E8")

    # Agent ID → (Character, epithet) for dynamic dialogue routing
    AGENT_CHARS = {
        "hephaestus": (h,   AGENT_METADATA["hephaestus"]["epithet"]),
        "techne":     (t,   AGENT_METADATA["techne"]["epithet"]),
        "kallos":     (k,   AGENT_METADATA["kallos"]["epithet"]),
        "metis":      (m,   AGENT_METADATA["metis"]["epithet"]),
        "dokimasia":  (d,   AGENT_METADATA["dokimasia"]["epithet"]),
        "mneme":      (mn,  AGENT_METADATA["mneme"]["epithet"]),
        "puck":       (pck, AGENT_METADATA["puck"]["epithet"]),
        "cupid":      (cpd, AGENT_METADATA["cupid"]["epithet"]),
    }

    # Name → epithet lookup for the say screen subtitle display.
    AGENT_EPITHETS = {meta["title"]: meta["epithet"] for name, meta in AGENT_METADATA.items()}
    # Fallbacks for titles used as names
    for name, meta in AGENT_METADATA.items():
        AGENT_EPITHETS[name.capitalize()] = meta["epithet"]

    # Agent accent colors (mirrors AGENT_CHARS, used by HUD, gossip bubble, portrait frame)
    AGENT_COLORS = {name: meta["hex_color"] for name, meta in AGENT_METADATA.items()}

    # Display-name → accent color lookup for the Hades-style name plaque in
    # the say screen: the plaque's hairline border takes the current
    # speaker's color so "Metis" reads indigo, "Hephaestus" amber, etc.
    AGENT_ACCENT_BY_NAME = {meta["title"]: meta["hex_color"] for name, meta in AGENT_METADATA.items()}
    for name, meta in AGENT_METADATA.items():
        AGENT_ACCENT_BY_NAME[name.capitalize()] = meta["hex_color"]

    # Some agents' canonical accent colors (Metis indigo #4C6EF5, Dokimasia
    # gray #6C757D, Mneme brown-red #B73E1D) are too dark to read cleanly
    # against the #14100AEE plaque fill and the parchment dialogue background.
    # _bright_hex shifts HSL-lightness up to a legibility floor so the same
    # color identity still reads, just with enough contrast to be scannable.
    # Keep the original accent for HUD bars + plaque hairlines (solid shapes
    # where the darker value works); use the brightened variant wherever the
    # accent is rendered as *text*.
    import colorsys as _colorsys

    def _bright_hex(hex_color, min_l=0.70):
        if not hex_color or not hex_color.startswith("#") or len(hex_color) < 7:
            return hex_color
        r = int(hex_color[1:3], 16) / 255.0
        g = int(hex_color[3:5], 16) / 255.0
        b = int(hex_color[5:7], 16) / 255.0
        h, l, s = _colorsys.rgb_to_hls(r, g, b)
        l = max(l, min_l)
        # Pull saturation up slightly too — pure lightness alone can wash out.
        s = min(1.0, s + 0.05)
        r, g, b = _colorsys.hls_to_rgb(h, l, s)
        return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))

    AGENT_ACCENT_BRIGHT_BY_NAME = {
        name: _bright_hex(hex_color)
        for name, hex_color in AGENT_ACCENT_BY_NAME.items()
    }

    # ──────────────────────────────────────────────────────────────────────
    # Inline agent-name colorization in dialogue — when Hephaestus says
    # "Metis — draw up the plans," *Metis* renders in her indigo accent
    # color while the rest stays default parchment. Reinforces the sense
    # that agents are people you're collaborating with, and gives the
    # viewer's eye a second anchor beyond the name plaque for who's on
    # stage.
    #
    # Hook: ``config.say_menu_text_filter`` (Ren'Py 8.5) runs on say and
    # menu text only — the plaque, HUD, namebox, and UI chrome all use
    # direct screen-level ``text`` displayables and are not filtered.
    # See renpy.org/doc/html/config.html#var-say_menu_text_filter.
    # ──────────────────────────────────────────────────────────────────────
    import re as _re

    # Longest names first so "Hephaestus" matches before a (hypothetical)
    # shorter name that is a prefix. \b word boundaries keep possessives
    # (``Metis'``) and punctuation (``Metis,``) from breaking the match.
    _agent_name_pattern = _re.compile(
        r"\b(" + "|".join(
            _re.escape(name)
            for name in sorted(AGENT_ACCENT_BY_NAME.keys(), key=len, reverse=True)
        ) + r")\b"
    )

    def _colorize_agent_names(s):
        if not s:
            return s
        def _repl(match):
            name = match.group(1)
            # Use the brightened variant so "Metis" in Hephaestus's line
            # actually stands out on the parchment dialogue fill; the
            # original darker accent is reserved for plaque hairlines and
            # HUD bars where solid-color shapes have room to breathe.
            color = AGENT_ACCENT_BRIGHT_BY_NAME.get(name, "#F5F0E1")
            return "{color=" + color + "}" + name + "{/color}"
        return _agent_name_pattern.sub(_repl, s)

    config.say_menu_text_filter = _colorize_agent_names

    # Canonical display order for the affinity HUD (6 maidens only — spirits are sidebar)
    AGENT_ORDER = ["hephaestus", "techne", "kallos", "metis", "dokimasia", "mneme"]

    # @mention prefix → agent_id
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

    # Valid portrait states per agent
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

    # ──────────────────────────────────────────────────────────────────────
    # Multi-slot portrait helpers — left/center/right, with active-speaker
    # tracking. Lets the Forge Master and a Specialist stand on screen
    # together during a handoff instead of one replacing the other.
    # ──────────────────────────────────────────────────────────────────────
    _VN_SLOT_TAGS = {"left": "portrait_left", "right": "portrait_right", "center": "portrait_center"}

    def kourai_show_agent(agent_id, slot="center", state="neutral"):
        """Show ``agent_id`` in the named slot (``left`` / ``right`` / ``center``).

        Each slot has its own screen tag, so multiple slots can hold
        different agents at once. Calling this again with the same slot
        swaps the occupant in place.
        """
        tag = _VN_SLOT_TAGS.get(slot, "portrait_center")
        renpy.show_screen(
            "agent_portrait",
            agent_id=agent_id,
            state=state,
            slot=slot,
            _tag=tag,
        )

    def kourai_hide_agent(slot):
        """Hide whoever is standing in the named slot."""
        tag = _VN_SLOT_TAGS.get(slot)
        if tag:
            renpy.hide_screen(tag)

    def kourai_set_speaker(agent_id):
        """Mark ``agent_id`` as the current speaker. Other slots dim."""
        store.current_speaker_id = agent_id
        # Force a re-render so the dim/bright transforms swap immediately
        # rather than waiting for the next player interaction.
        renpy.restart_interaction()

    def kourai_clear_stage():
        """Hide every slot and clear the current speaker — back to a blank stage."""
        for _slot_tag in _VN_SLOT_TAGS.values():
            renpy.hide_screen(_slot_tag)
        store.current_speaker_id = None

    def kourai_present_agent(agent_id, state="neutral"):
        """Smart entrypoint used by the pipeline loop.

        Keeps up to two agents visible (left + right) and alternates slots
        on handoff. If the agent is already on-screen the existing slot is
        reused and the speaker marker is just updated; if both slots are
        full, the non-speaking occupant is evicted to make room.
        """
        slots = getattr(store, "_vn_slots", None)
        if slots is None:
            slots = {}
            store._vn_slots = slots

        # Already on stage — just refresh state and mark as speaker.
        for slot, aid in list(slots.items()):
            if aid == agent_id:
                kourai_show_agent(agent_id, slot=slot, state=state)
                kourai_set_speaker(agent_id)
                return

        # Pick a slot — prefer left for the first agent, right for the second,
        # evict the non-speaker if both are already occupied.
        if "left" not in slots:
            slot = "left"
        elif "right" not in slots:
            slot = "right"
        else:
            evict = next(
                (s for s, a in slots.items() if a != store.current_speaker_id),
                "right",
            )
            kourai_hide_agent(evict)
            slots.pop(evict, None)
            slot = evict

        slots[slot] = agent_id
        kourai_show_agent(agent_id, slot=slot, state=state)
        kourai_set_speaker(agent_id)

    def get_tier(score):
        """Map affinity 0.0-1.0 → tier 1-4 (matches RELATIONSHIP_SYSTEMS.md)."""
        if score < 0.3: return 1
        if score < 0.6: return 2
        if score < 0.8: return 3
        return 4

    def _get_virtue_context_dict():
        """Build virtue data structure for Forge Journal visualization.

        Returns dict with virtue scores, session deltas, and discoveries.
        Queries the python agent subprocess via the bridge to avoid sqlite3 dependency issues.
        """
        # Fast path: no player_id means we're outside a live session
        # (demo mode, pre-onboarding, main menu before Start). That's a
        # *normal* state — not an error — so return the fallback dict
        # silently instead of spamming tracebacks once per frame.
        if not getattr(persistent, "player_id", None):
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

        try:
            player_id = persistent.player_id

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
            affinities = _result.get("affinities", {})

            # Sync authoritative affinity scores back to the Ren'Py store
            import store as _store
            for agent_name, aff_data in affinities.items():
                # aff_data is a dict with affinity_score, romance_stage etc.
                if agent_name in _store.affinity:
                    _store.affinity[agent_name] = aff_data.get("affinity_score", 0.5)

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

    # ═══════════════════════════════════════════════════════════════
    # CODEX SYSTEM — Persistence & Unlock Logic
    # ═══════════════════════════════════════════════════════════════

    def unlock_codex_entry(entry_id, silent=False):
        """Unlock a Codex entry and optionally queue a notification.
        
        Args:
            entry_id: Unique entry identifier from CODEX_ENTRIES
            silent: If True, skip notification toast (for bulk unlocks)
        
        Returns:
            True if newly unlocked, False if already unlocked
        """
        if not hasattr(persistent, 'codex_unlocked'):
            persistent.codex_unlocked = set()
        
        if entry_id in persistent.codex_unlocked:
            return False  # Already unlocked
        
        # Find the entry to get its title
        entry_data = None
        for category in CODEX_ENTRIES.values():
            for entry in category:
                if entry["id"] == entry_id:
                    entry_data = entry
                    break
            if entry_data:
                break
        
        if not entry_data:
            return False  # Entry doesn't exist
        
        persistent.codex_unlocked.add(entry_id)
        
        if not silent:
            # Queue notification for display
            if not hasattr(persistent, 'codex_new_notifications'):
                persistent.codex_new_notifications = []
            persistent.codex_new_notifications.append({
                "id": entry_id,
                "title": entry_data["title"],
                "subtitle": entry_data.get("subtitle", ""),
                "category": _get_entry_category(entry_id)
            })
        
        return True
    
    def _get_entry_category(entry_id):
        """Find which category an entry belongs to."""
        for category_name, entries in CODEX_ENTRIES.items():
            for entry in entries:
                if entry["id"] == entry_id:
                    return category_name
        return "Unknown"
    
    def mark_codex_entry_read(entry_id):
        """Mark a Codex entry as read (removes NEW badge)."""
        if not hasattr(persistent, 'codex_read'):
            persistent.codex_read = set()
        persistent.codex_read.add(entry_id)
    
    def is_codex_entry_unlocked(entry_id):
        """Check if a Codex entry is unlocked."""
        if not hasattr(persistent, 'codex_unlocked'):
            return False
        return entry_id in persistent.codex_unlocked
    
    def is_codex_entry_new(entry_id):
        """Check if a Codex entry has a NEW badge (unlocked but not read)."""
        if not hasattr(persistent, 'codex_read'):
            persistent.codex_read = set()
        return is_codex_entry_unlocked(entry_id) and entry_id not in persistent.codex_read
    
    def get_codex_new_count(category=None):
        """Get count of NEW (unread) entries in a category or total.
        
        Args:
            category: Category name (e.g., "Characters"), or None for total
        
        Returns:
            Count of unread entries
        """
        if not hasattr(persistent, 'codex_unlocked'):
            return 0
        if not hasattr(persistent, 'codex_read'):
            persistent.codex_read = set()
        
        count = 0
        entries_to_check = []
        
        if category:
            entries_to_check = CODEX_ENTRIES.get(category, [])
        else:
            for cat_entries in CODEX_ENTRIES.values():
                entries_to_check.extend(cat_entries)
        
        for entry in entries_to_check:
            if is_codex_entry_new(entry["id"]):
                count += 1
        
        return count
    
    def get_unlocked_entries(category):
        """Get list of unlocked entries for a category.
        
        Returns:
            List of entry dicts that are unlocked
        """
        if not hasattr(persistent, 'codex_unlocked'):
            return []
        
        unlocked = []
        for entry in CODEX_ENTRIES.get(category, []):
            if entry["id"] in persistent.codex_unlocked:
                unlocked.append(entry)
        
        return unlocked
    
    def pop_codex_notification():
        """Get and remove the next pending Codex notification.
        
        Returns:
            Notification dict or None if queue is empty
        """
        if not hasattr(persistent, 'codex_new_notifications'):
            persistent.codex_new_notifications = []
        
        if persistent.codex_new_notifications:
            return persistent.codex_new_notifications.pop(0)
        
        return None

# ── CODEX HOTKEY BINDING ─────────────────────────────────────────────

init python:
    # Add 'c' key binding to toggle Codex
    config.keymap['codex_toggle'] = ['c', 'C']
    config.underlay.append(
        renpy.Keymap(
            codex_toggle=ShowMenu("codex")
        )
    )

# ─────────────────────────────────────────────────────────────────────

init python:
    def _validate_and_set_project(project_path):
        """Validate project directory and add to recent projects.

        Checks if path exists and contains a git repo or valid project marker.
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
    # Gossip trigger tries bridge.request_gossip() first; falls back here.
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
