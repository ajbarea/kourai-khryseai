## Ren'Py Script Language
## script_labels.rpy — Utility labels: after_load, project_input_label, create_project_label,
##                      portrait_debug, quit

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

# ── PORTRAIT DEBUG ───────────────────────────────────────────────────────
# Accessible from the main menu without Docker running.
# Loops through every agent, shows their neutral portrait, and has them say
# a quick intro line so you can preview all character art in one pass.

label portrait_debug:
    ## Warm forge-dark instead of pure black — matches the forge atmosphere.
    scene expression "#0D0A07"

    python:
        # AGENT_CHARS covers all ten agents (script_data.rpy). Hades-style
        # convention (per ROADMAP M10): the name plaque already signals the
        # speaker, so dialogue is NOT auto-wrapped in literal quote marks —
        # agent outputs decide per-line whether a line is quoted, matching
        # the CLI / GUI convention.
        _dbg_agents = list(AGENT_CHARS.items())

    "Entering portrait debug mode. No Docker required — press to step through each character."

    python:
        for agent_id, (char, _epithet) in _dbg_agents:
            resolved = validate_portrait_state(agent_id, "neutral")
            if resolved is not None:
                renpy.show_screen("agent_portrait", agent_id=agent_id, state=resolved)
            else:
                renpy.hide_screen("agent_portrait")
            renpy.say(char, "Hi! My name is {}!".format(char.name))
        renpy.hide_screen("agent_portrait")

    "All portraits reviewed."

    return


# ── CLEANUP ──────────────────────────────────────────────────────────────

label quit:
    $ renpy.hide_screen("affinity_hud")
    $ renpy.hide_screen("gossip_bubble")
    $ bridge.shutdown()
    return
