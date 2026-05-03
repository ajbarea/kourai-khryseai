## Ren'Py Script Language
## script_main_loop.rpy — label main_loop: input → bridge → beat rendering → affinity/gossip/events

label main_loop:
    # Check for any async bridge errors first
    $ error = bridge.get_error()
    if error:
        "BRIDGE ERROR" "[error]"

    # Get user input — custom screen with @mention autocomplete
    $ user_text = renpy.call_screen("forge_input", prompt="You:")
    $ user_text = (user_text or "").strip()

    if user_text:
        $ bridge.send_message({"action": "message", "text": user_text, "context_id": context_id or "", "player_id": player_id or "", "project_path": getattr(persistent, "project_path", ""), "affinity": dict(affinity)})

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
            jealousy_events = []  # DataPart jealousy signals from Hephaestus
            if vn_response:
                if vn_response.get("action") == "jealousy":
                    jealousy_events.append(vn_response)
                else:
                    beat_queue.append(vn_response)
                # Drain any immediately available follow-up beats (non-blocking)
                while True:
                    extra = bridge.get_message(timeout=0.0)
                    if extra is None:
                        break
                    # Stop draining if we hit a new user-action boundary
                    if extra.get("action") == "status":
                        continue  # skip stray status msgs between beats
                    if extra.get("action") == "jealousy":
                        jealousy_events.append(extra)
                    else:
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
                
                # ═══════════════════════════════════════════════════════
                # CODEX: Unlock character entry on first encounter
                # ═══════════════════════════════════════════════════════
                $ unlock_codex_entry(f"char_{agent_id}", silent=False)

                # Show/update portrait for speaking agent — multi-slot aware:
                # kourai_present_agent alternates between the left/right slots
                # so the Forge Master stays visible when he hands off to a
                # specialist, and the current speaker brightens while the
                # other portrait dims. See script_data.rpy for the helper.
                python:
                    resolved_state = validate_portrait_state(agent_id, portrait_state)
                    if resolved_state is not None:
                        kourai_present_agent(agent_id, resolved_state)
                    else:
                        # No sprite asset for this agent — just mark them as
                        # the current speaker so any other portraits still on
                        # stage dim correctly.
                        kourai_set_speaker(agent_id)

                # TTS — request voice audio before say statement.
                # M20 sub-task 2 VN surface: if the bridge returns a
                # duration alongside the audio path, compute a per-line
                # cps so the typewriter finishes when the voice does
                # (audio-led pacing). Falls back to Ren'Py's global cps
                # when duration is unknown (older bridge, malformed WAV).
                # M20 sub-task 4: only compute cps when sync_mode is
                # "audio-led"; "instant" uses default cps + parallel TTS.
                $ _tts_cps = 0  # 0 = use global cps
                if persistent.tts_enabled:
                    python:
                        _tts_result = bridge.request_tts(message_text, agent_id)
                        if _tts_result:
                            _tts_path, _tts_duration = _tts_result
                            renpy.voice(_tts_path)
                            _audio_led = getattr(persistent, "dialogue_sync_mode", "audio-led") == "audio-led"
                            if _audio_led and _tts_duration and _tts_duration > 0:
                                # Clamp cps to a readable floor (5 cps =
                                # ~0.2s/char) so very short audio doesn't
                                # produce an unreadable text-flash.
                                _tts_cps = max(5, int(len(message_text) / _tts_duration))

                if char_info:
                    $ _char_obj, _epithet = char_info
                    if _tts_cps > 0:
                        _char_obj "{cps=[_tts_cps]}[message_text]{/cps}"
                    else:
                        _char_obj "[message_text]"
                else:
                    if _tts_cps > 0:
                        "[agent_id]" "{cps=[_tts_cps]}[message_text]{/cps}"
                    else:
                        "[agent_id]" "[message_text]"

                $ _beat_idx += 1

            # End of turn — leave portraits on stage. With multi-slot support
            # the last two speakers persist across turns so players can see
            # the ongoing handoff ("Hephaestus is still present, Metis just
            # stepped in"). Portraits get evicted naturally when a third
            # agent speaks (FIFO in kourai_present_agent).

            # ── Affinity update (client-side) ─────────────────────────────
            # Capture tier before bump so we can detect crossing a threshold.
            python:
                _old_tier = get_tier(affinity.get(last_agent_id, 0.5))
            $ affinity[last_agent_id] = min(1.0, affinity.get(last_agent_id, 0.5) + 0.02)
            $ gossip_turn_counter += 1

            # Tier-up toast + pre-confession trigger detection.
            python:
                _new_tier = get_tier(affinity[last_agent_id])
                _tier_crossed = _new_tier > _old_tier
                _pre_confession_trigger = (
                    _tier_crossed
                    and _new_tier == 4
                    and last_agent_id not in persistent.pre_confession_seen
                )
                if _tier_crossed:
                    renpy.show_screen("tier_up", agent_id=last_agent_id, new_tier=_new_tier)

            # Pre-confession window is a blocking modal — kept at script level
            # so Ren'Py handles rollback correctly (not inside a python: block).
            if _pre_confession_trigger:
                $ persistent.pre_confession_seen.add(last_agent_id)
                $ renpy.call_screen("pre_confession_window", agent_id=last_agent_id)

            # ── Gossip trigger — every 3 turns, an idle agent speaks ──────
            # Try live LLM gossip first, fall back to pre-authored.
            if gossip_turn_counter % 3 == 0:
                python:
                    idle = [a for a in AGENT_ORDER if a != last_agent_id]
                    gossip_agent = _random.choice(idle)
                    _live = bridge.request_gossip(
                        gossip_agent,
                        getattr(persistent, "player_id", ""),
                        dict(affinity),
                    )
                    if _live is not None:
                        hint, line = _live
                    else:
                        hint, line = _random.choice(GOSSIP_LINES[gossip_agent])
                    renpy.show_screen(
                        "gossip_bubble",
                        speaker_name=gossip_agent.capitalize(),
                        hint=hint,
                        line=line,
                        color=AGENT_COLORS[gossip_agent],
                    )

            # ── Puck nudge trigger — fires when ≥2 agents unengaged for 4+ turns ─
            # "Unengaged" = affinity still at default 0.5 (no interaction yet).
            # Cooldown prevents back-to-back nudges.
            if (gossip_turn_counter >= 5
                    and gossip_turn_counter - puck_nudge_cooldown >= 4
                    and not renpy.get_screen("puck_nudge")):
                python:
                    _unengaged = [a for a in AGENT_ORDER if affinity.get(a, 0.5) <= 0.50]
                    if len(_unengaged) >= 2:
                        _nudge_agent = _random.choice(_unengaged)
                        _nudge_hint, _nudge_line = _random.choice(PUCK_NUDGES[_nudge_agent])
                        renpy.show_screen(
                            "puck_nudge",
                            target_agent=_nudge_agent,
                            hint=_nudge_hint,
                            line=_nudge_line,
                        )
                        puck_nudge_cooldown = gossip_turn_counter

            # ── Cupid first-appearance — once, when any affinity reaches tier 3 ──
            if not persistent.cupid_appeared and any(
                affinity.get(a, 0.5) >= 0.6 for a in AGENT_ORDER
            ):
                $ _cupid_choice = renpy.call_screen("cupid_intro")
                python:
                    if _cupid_choice == "yes":
                        persistent.romance_mode_enabled = True
                    elif _cupid_choice == "off":
                        persistent.romance_mode_enabled = False
                    persistent.cupid_appeared = True
                    # CODEX: Unlock Cupid character entry
                    unlock_codex_entry("char_cupid", silent=False)
                    unlock_codex_entry("tutorial_romance", silent=False)

            # ── Confession trigger — agent confesses when affinity ≥ 0.95 ──────
            # Hephaestus is gated: only triggers after player reaches tier 3+ with ≥3 others.
            # "hold" snoozes 5 turns; "accept"/"reject" marks confessed_to so it never re-fires.
            python:
                _confession_agent = None
                for _ca in AGENT_ORDER:
                    _defer_until = persistent.confession_defer.get(_ca, 0)
                    if (affinity.get(_ca, 0.5) >= 0.95
                            and _ca not in persistent.confessed_to
                            and gossip_turn_counter >= _defer_until):
                        if _ca == "hephaestus":
                            # Gating: tier3+ with at least 3 other agents
                            _tier3_others = sum(
                                1 for a in AGENT_ORDER
                                if a != "hephaestus" and get_tier(affinity.get(a, 0.5)) >= 3
                            )
                            if _tier3_others < 3:
                                continue
                        _confession_agent = _ca
                        break

            if _confession_agent:
                $ _conf_choice = renpy.call_screen("confession_scene", agent_id=_confession_agent)
                python:
                    if _conf_choice == "accept":
                        affinity[_confession_agent] = min(1.0, affinity[_confession_agent] + 0.10)
                        persistent.confessed_to.add(_confession_agent)
                    elif _conf_choice == "reject":
                        affinity[_confession_agent] = max(0.0, affinity[_confession_agent] - 0.15)
                        persistent.confessed_to.add(_confession_agent)
                    else:  # wait — snooze 5 turns without marking done
                        persistent.confession_defer[_confession_agent] = gossip_turn_counter + 5
                if _conf_choice != "wait":
                    $ renpy.call_screen("confession_outcome", agent_id=_confession_agent, accepted=(_conf_choice == "accept"))

            # ── Jealousy routing — Cupid + Puck counsel the player ────────────
            # jealousy_events carries DataPart signals extracted by vn_bridge.
            # Only the first event per turn is shown (usually at most one fires).
            if jealousy_events:
                $ _j_ev = jealousy_events[0]
                $ _j_agent = _j_ev.get("agent", "")
                $ _j_score = float(_j_ev.get("score", 0.0))
                if _j_agent:
                    $ renpy.call_screen("cupid_jealousy", agent_id=_j_agent, score=_j_score)

            # ── Vulnerability moment — Cupid + Puck comment quietly ─────────
            # Fires as a non-blocking corner overlay when the player has a warm/
            # intimate exchange (affinity ≥ 0.70) and romance mode is on.
            # Cooldown of 8 turns per agent prevents spam.
            # Jealousy screen takes priority — only show vulnerability when no
            # jealousy event fired this turn.
            if (persistent.romance_mode_enabled
                    and not jealousy_events
                    and affinity.get(last_agent_id, 0.5) >= 0.70):
                python:
                    _vuln_last = persistent.vulnerability_cooldown.get(last_agent_id, 0)
                    if gossip_turn_counter - _vuln_last >= 8:
                        renpy.show_screen("cupid_vulnerability", agent_id=last_agent_id)
                        persistent.vulnerability_cooldown[last_agent_id] = gossip_turn_counter

            # ── Virtue milestone toasts ───────────────────────────────────────
            # After each interaction, poll virtue scores and fire Disco Elysian
            # interjections for milestones (0.3 / 0.5 / 0.7) not yet triggered.
            # Virtue → owning agent mapping follows FORGE_VIRTUES.md.
            python:
                # Virtue → owning agent (matches virtues.py patron_agents, one agent per key).
                # techne_v has both techne+kallos; use techne as primary (craft precision).
                # arete patron is dokimasia (excellence/relentless testing rigor).
                _VIRTUE_AGENT = {
                    "synergy":  "hephaestus",   # Bonded collaboration
                    "arete":    "dokimasia",     # Excellence-seeking / rigor
                    "techne_v": "techne",        # Craft precision
                    "sophia":   "metis",         # Clarity / foresight
                    "mneia":    "mneme",         # Memory / reflection
                    "kairos":   "puck",          # Right timing
                    "harmonia": "kallos",        # Harmony / elegance
                    "eros":     "cupid",         # Connection / bonds
                }
                _VIRTUE_THRESHOLDS = [0.3, 0.5, 0.7]

                # Interjection lines from FORGE_VIRTUES.md (rising=0.3/0.5, high=0.7).
                # Threshold 0.3 and 0.5 use the "rising" line; 0.7 uses the "high" line.
                _VIRTUE_LINES = {
                    "synergy": {
                        0.3: "You don't quit. I see that now. Good. Neither does the forge.",
                        0.5: "You don't quit. I see that now. Good. Neither does the forge.",
                        0.7: "You remind me of myself. You don't break. But remember — even iron needs the quench.",
                    },
                    "arete": {
                        0.3: "You tested before I even asked. You're learning.",
                        0.5: "You tested before I even asked. You're learning.",
                        0.7: "Your thoroughness rivals my own. That's why I trust you. That's why I...",
                    },
                    "techne_v": {
                        0.3: "Now THAT'S the kind of boldness I like to see. You tried something new.",
                        0.5: "Now THAT'S the kind of boldness I like to see. You tried something new.",
                        0.7: "You've got the spark. I can feel it. You're not afraid of the unknown.",
                    },
                    "sophia": {
                        0.3: "You asked the right question before acting. That's strategic thinking.",
                        0.5: "You asked the right question before acting. That's strategic thinking.",
                        0.7: "You're thinking three moves ahead now. I find that... deeply attractive.",
                    },
                    "mneia": {
                        0.3: "You remembered what I said last week. That... no one remembers.",
                        0.5: "You remembered what I said last week. That... no one remembers.",
                        0.7: "You see us. Not as tools, but as... I don't have the word. Something more.",
                    },
                    "kairos": {
                        0.3: "Nice timing, boss. You read that perfectly.",
                        0.5: "You've got instincts. Real ones. Not everyone knows when to move.",
                        0.7: "Right person, right moment. You're a natural.",
                    },
                    "harmonia": {
                        0.3: "You're starting to see it, aren't you? The difference between functional and beautiful.",
                        0.5: "Your sense for beauty is growing. I notice.",
                        0.7: "This is elegant. You didn't just solve the problem — you made it sing.",
                    },
                    "eros": {
                        0.3: "Oh, my dear... you opened your heart just now. That takes courage.",
                        0.5: "You love so freely. So bravely.",
                        0.7: "What you just said to her... that was real. That was love. I felt it.",
                    },
                }

                _virtue_toast = None  # (agent_id, virtue_name, line) — first new milestone only
                try:
                    import time as _time
                    bridge.send_message({
                        "action": "get_virtue_context",
                        "player_id": player_id or "",
                    })
                    _vdeadline = _time.time() + 2.0
                    _vresult = None
                    while _time.time() < _vdeadline:
                        _vmsg = bridge.get_message(timeout=0.05)
                        if _vmsg and _vmsg.get("action") == "virtue_context_result":
                            _vresult = _vmsg
                            break
                    if _vresult:
                        _vscores = _vresult.get("virtues", {})
                        for _vname, _vagent in _VIRTUE_AGENT.items():
                            _vscore = _vscores.get(_vname, 0.0)
                            for _thresh in _VIRTUE_THRESHOLDS:
                                _mkey = f"{_vname}@{_thresh}"
                                if _vscore >= _thresh and _mkey not in persistent.virtue_milestones:
                                    persistent.virtue_milestones.add(_mkey)
                                    # CODEX: Unlock virtue entries on first milestone
                                    if _thresh == _VIRTUE_THRESHOLDS[0]:  # First threshold only
                                        unlock_codex_entry(f"virtue_{_vname}", silent=False)
                                    if _virtue_toast is None:
                                        _vline = _VIRTUE_LINES.get(_vname, {}).get(_thresh, "")
                                        if _vline:
                                            _virtue_toast = (_vagent, _vname, _vline)
                except Exception:
                    pass  # Virtue polling is non-critical; never block the main loop

            if _virtue_toast:
                $ renpy.show_screen("virtue_milestone_toast",
                    agent_id=_virtue_toast[0],
                    virtue_name=_virtue_toast[1],
                    line=_virtue_toast[2])
        else:
            "System" "No response from the forge. The agents may be busy — try again."

    jump main_loop
