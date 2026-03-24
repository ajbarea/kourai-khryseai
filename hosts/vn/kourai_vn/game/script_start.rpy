## Ren'Py Script Language
## script_start.rpy — label start: bridge init, profile setup, onboarding, persistent flag init, tutorials

# ── MAIN GAME FLOW ───────────────────────────────────────────────────────

label start:
    scene black
    "System" "Initializing the Forge Bridge..."

    # Polls until vn-bridge is healthy and connected to agents (status=ok)
    if not bridge.start():
        "ERROR" "Could not reach the agents. Run 'docker compose up' first, then relaunch."
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

        # Phase 7: Cupid first-appearance flag — fires once when affinity ≥ 0.6
        if not hasattr(persistent, "cupid_appeared"):
            persistent.cupid_appeared = False

        # Phase 10: Confession system — per-agent tracking
        if not hasattr(persistent, "pre_confession_seen"):
            persistent.pre_confession_seen = set()
        if not hasattr(persistent, "confessed_to"):
            persistent.confessed_to = set()
        if not hasattr(persistent, "confession_defer"):
            persistent.confession_defer = {}  # agent → turn counter threshold

        # Phase 11: Virtue milestone toasts — tracks which threshold moments have fired.
        # Keys are "virtue_name@threshold" e.g. "arete@0.3", "synergy@0.7"
        if not hasattr(persistent, "virtue_milestones"):
            persistent.virtue_milestones = set()

        # Phase 13: VN TTS — per-beat voice synthesis via vn-bridge /tts endpoint
        if not hasattr(persistent, "tts_enabled"):
            persistent.tts_enabled = False

        # Phase 20: Forge Virtues wellness guardrails
        if not hasattr(persistent, "wellness_warning_seen"):
            persistent.wellness_warning_seen = False
        if not hasattr(persistent, "virtue_tracking_enabled"):
            persistent.virtue_tracking_enabled = True

        # Phase 21: Puck tutorial — shown once to first-run players
        if not hasattr(persistent, "puck_tutorial_seen"):
            persistent.puck_tutorial_seen = False

        # Phase 21: Vulnerability moment cooldown — {agent_id: last_turn_fired}
        if not hasattr(persistent, "vulnerability_cooldown"):
            persistent.vulnerability_cooldown = {}

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

    "System" "Connection to Kourai Khryseai established."
    "System" "The Master of the Forge is listening."

    # Phase 20: Wellness warning — shown once per player, before the HUD appears.
    # Respects virtue_tracking_enabled (can opt-out via "Disable" button).
    if not persistent.wellness_warning_seen and persistent.virtue_tracking_enabled:
        call screen wellness_warning

    # Phase 21: Puck tutorial — first-run players only. Shown after wellness
    # warning so the player has context before Puck speaks.
    if not persistent.puck_tutorial_seen:
        $ renpy.call_screen("puck_tutorial")
        $ persistent.puck_tutorial_seen = True

    # Show the persistent affinity HUD — stays visible for the whole session
    $ renpy.show_screen("affinity_hud")

    jump main_loop
