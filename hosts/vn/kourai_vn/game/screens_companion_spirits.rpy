## Ren'Py Screen Language
## screens_companion_spirits.rpy — Companion spirit overlays: cupid_jealousy, tier_up,
##   puck_nudge, cupid_intro, wellness_warning, virtue_milestone_toast,
##   puck_tutorial, cupid_vulnerability (Phases 7, 8, 21)

init offset = -1

################################################################################

## cupid_jealousy — modal screen when a jealousy_trigger DataPart fires.
## Shows Puck + Cupid alternating banter about the affected agent.
## Returns when player clicks Continue.

screen cupid_jealousy(agent_id, score):
    zorder 55
    modal True

    python:
        _agent_name = agent_id.capitalize()
        _agent_color = AGENT_COLORS.get(agent_id, "#F0E8D0")
        _puck_color = "#7FBC8C"
        _cupid_color = "#E8728C"
        _score_pct = int(score * 100)
        _lines = [
            ("puck",  "conspiratorial",  "Hey boss. " + _agent_name + "'s getting a little edgy. Real talk."),
            ("cupid", "wistful",         "Her heart feels overlooked. She notices more than she lets on."),
            ("puck",  "shrug",           "Which is why you should give her some attention. Simple fix."),
            ("cupid", "gently",          "Not simple — heartfelt. A small gesture speaks volumes right now."),
            ("puck",  "relenting",       "Yeah, what she said. Just... go talk to " + _agent_name + "."),
            ("cupid", "*sighs*",         "For once, Puck and I are in agreement. Don't make us wait."),
        ]

    add Solid("#00000088")

    frame:
        xalign 0.5
        yalign 0.4
        xmaximum 560
        background "#0D0A10F0"
        padding (28, 24, 28, 24)

        vbox:
            spacing 10
            xfill True

            # Header: jealous agent + score
            hbox:
                xalign 0.5
                spacing 10
                text "⚠":
                    color _agent_color
                    size 20
                    yalign 0.5
                text (_agent_name + " — Jealousy"):
                    color _agent_color
                    size 17
                    bold True
                    yalign 0.5
                text ("(" + str(_score_pct) + "%)"):
                    color "#7A5A5A"
                    size 13
                    yalign 0.5

            null height 6

            # Alternating banter
            for _speaker, _hint, _line in _lines:
                $ _sp_color = _puck_color if _speaker == "puck" else _cupid_color
                $ _sp_name = "Puck" if _speaker == "puck" else "Cupid"
                frame:
                    background "#16101A"
                    padding (10, 7, 10, 7)
                    xfill True
                    vbox:
                        spacing 3
                        hbox:
                            spacing 6
                            text _sp_name:
                                color _sp_color
                                size 13
                                bold True
                                yalign 0.5
                            text ("*" + _hint + "*"):
                                color "#5A5A6A"
                                size 12
                                italic True
                                yalign 0.5
                        text _line:
                            color "#D8D0D4"
                            size 13
                            line_spacing 3

            null height 8

            button:
                action Return()
                background Frame(Solid("#3A1A2A"), 2, 2)
                hover_background Frame(Solid("#E8728C44"), 2, 2)
                xfill True
                ysize 44
                text "Continue":
                    color "#E8B0BC"
                    size 15
                    xalign 0.5
                    yalign 0.5


## tier_up — small bottom-left toast when affinity crosses a tier boundary.
## Fires for tiers 3 and 4 (player starts at tier 2 at 0.5 base affinity).
## Auto-dismisses after 4 seconds.

screen tier_up(agent_id, new_tier):
    zorder 44
    modal False

    python:
        _tier_names = {1: "Cold", 2: "Professional", 3: "Warm", 4: "Intimate"}
        _tier_label = _tier_names.get(new_tier, "Deepening")
        _agent_color = AGENT_COLORS.get(agent_id, "#F0E8D0")
        _agent_name = agent_id.capitalize()

    frame:
        xalign 0.0
        yalign 1.0
        xoffset 20
        yoffset -80
        xmaximum 340
        background "#0A0E10F2"
        padding (16, 12, 16, 12)

        vbox:
            spacing 5
            hbox:
                spacing 8
                text "✦":
                    color _agent_color
                    size 20
                    yalign 0.5
                text _agent_name:
                    color _agent_color
                    size 16
                    bold True
                    yalign 0.5
                text "✦":
                    color _agent_color
                    size 20
                    yalign 0.5
            text ("Tier " + str(new_tier) + " — " + _tier_label):
                color "#F1D2A1"
                size 14
                italic True

    timer 4.0 action Hide("tier_up")


################################################################################
## Phase 7 — Companion Spirit Overlays
################################################################################

## puck_nudge — bottom-right corner overlay, auto-dismisses after 12 s
## Puck whispers a hint about an unengaged agent without interrupting flow.

screen puck_nudge(target_agent, hint, line):
    zorder 46
    modal False

    $ _puck_color = "#7FBC8C"
    $ _agent_color = AGENT_COLORS.get(target_agent, "#F0E8D0")

    frame:
        xalign 1.0
        yalign 1.0
        xoffset -20
        yoffset -80
        xmaximum 440
        background "#0E1410F0"
        padding (18, 14, 18, 14)

        vbox:
            spacing 6

            # Puck speaker label
            hbox:
                spacing 8
                text "Puck":
                    color _puck_color
                    size 15
                    bold True
                    yalign 0.5
                text hint:
                    color "#5A7A5A"
                    size 13
                    italic True
                    yalign 0.5

            # Nudge line
            text line:
                color "#C8D8C0"
                size 14
                line_spacing 4

            null height 4

            # Dismiss row: agent tag + X button
            hbox:
                xfill True
                spacing 8
                text ("→ " + target_agent.capitalize()):
                    color _agent_color
                    size 12
                    bold True
                    yalign 0.5
                null:
                    xfill True
                textbutton "✕":
                    action Hide("puck_nudge")
                    background None
                    hover_background None
                    text_color "#5A7A5A"
                    text_hover_color _puck_color
                    text_size 14
                    yalign 0.5

    # Auto-dismiss after 12 seconds
    timer 12.0 action Hide("puck_nudge")


## cupid_intro — modal first-appearance screen for Cupid
## Fires exactly once when any agent affinity reaches tier 3 (≥ 0.6).
## Returns "yes" (enable romance), "no" (decline for now), or "off" (disable).

screen cupid_intro():
    zorder 55
    modal True

    $ _cupid_color = "#E8728C"
    $ _gold = "#F1D2A1"

    add Solid("#00000088")

    frame:
        xalign 0.5
        yalign 0.4
        xmaximum 560
        background "#120A0CF0"
        padding (32, 28, 32, 28)

        vbox:
            spacing 16
            xfill True

            # Header
            hbox:
                spacing 12
                xalign 0.5
                text "✦":
                    color _cupid_color
                    size 24
                    yalign 0.5
                text "Cupid":
                    color _cupid_color
                    size 22
                    bold True
                    yalign 0.5
                text "✦":
                    color _cupid_color
                    size 24
                    yalign 0.5

            text "Arrow of the Heart":
                color "#A85878"
                size 14
                italic True
                xalign 0.5

            null height 6

            text "Oh — you actually stayed.":
                color "#F0D8DC"
                size 16
                bold True
                xalign 0.5

            text "Most players leave before any of them warm up. But look at you. {i}Something's kindling.{/i}":
                color "#C8B0B4"
                size 14
                line_spacing 6
                xalign 0.5

            null height 4

            text "I can help with that — if you want.":
                color "#E8B0BC"
                size 15
                xalign 0.5

            null height 10

            # Choice buttons
            vbox:
                spacing 10
                xfill True

                # Yes — enable romance mode
                button:
                    action Return("yes")
                    background Frame(Solid("#E8728C33"), 2, 2)
                    hover_background Frame(Solid("#E8728C66"), 2, 2)
                    xfill True
                    ysize 52
                    vbox:
                        xalign 0.5
                        yalign 0.5
                        text "✦  Yes — show me everything":
                            color "#F0D8DC"
                            size 15
                            bold True
                            xalign 0.5
                        text "Enable romance mode":
                            color "#A87880"
                            size 12
                            xalign 0.5

                # Not yet — neutral decline
                button:
                    action Return("no")
                    background Frame(Solid("#3A2A2E"), 2, 2)
                    hover_background Frame(Solid("#4A3A3E"), 2, 2)
                    xfill True
                    ysize 44
                    text "Not right now":
                        color "#C8A8AC"
                        size 14
                        xalign 0.5
                        yalign 0.5

                # Off — explicitly disable
                button:
                    action Return("off")
                    background Frame(Solid("#1A1215"), 1, 1)
                    hover_background Frame(Solid("#2A1A1E"), 1, 1)
                    xfill True
                    ysize 38
                    text "No, keep it professional":
                        color "#7A5A5E"
                        size 12
                        xalign 0.5
                        yalign 0.5


################################################################################

## wellness_warning — Forge Virtues opt-in notice, shown once on first launch.
## Blocks until player chooses "I Understand" (enables tracking) or "Disable"
## (sets virtue_tracking_enabled = False; never shown again either way).

screen wellness_warning():
    modal True
    zorder 100

    add Solid("#000000C0")

    frame:
        xalign 0.5
        yalign 0.5
        xmaximum 580
        background "#0D0B18F0"
        padding (32, 28, 32, 28)

        vbox:
            spacing 14
            xfill True

            # Title
            text "⚒  THE FORGE OBSERVES":
                color "#F1D2A1"
                size 20
                bold True
                xalign 0.5

            null height 4

            # Body
            text "Kourai Khryseai's agents notice your patterns — how you work, when you persist, when you rest — and reflect them back as part of the experience.":
                color "#E8E8E0"
                size 15
                line_spacing 5

            text "This is {b}not therapy{/b}. This is {b}not a mental health tool{/b}. It's a game that pays attention.":
                color "#E8E8E0"
                size 15
                line_spacing 5

            text "You can disable virtue tracking anytime in Settings → Experience.":
                color "#A0A0A0"
                size 14

            null height 4

            # Crisis resources
            frame:
                background "#1A0A0AF0"
                padding (14, 10)
                vbox:
                    spacing 6
                    text "If you're struggling, real help is available:":
                        color "#C0A0A0"
                        size 13
                    text "988 Suicide & Crisis Lifeline — call or text 988":
                        color "#A09090"
                        size 13
                    text "Crisis Text Line — text HOME to 741741":
                        color "#A09090"
                        size 13

            null height 8

            # Buttons
            hbox:
                spacing 20
                xalign 0.5

                textbutton "I Understand":
                    action [
                        SetField(persistent, "wellness_warning_seen", True),
                        SetField(persistent, "virtue_tracking_enabled", True),
                        Return(),
                    ]
                    style "wellness_button_affirm"

                textbutton "Disable Tracking":
                    action [
                        SetField(persistent, "wellness_warning_seen", True),
                        SetField(persistent, "virtue_tracking_enabled", False),
                        Return(),
                    ]
                    style "wellness_button_dismiss"

style wellness_button_affirm:
    background "#2A4A2A"
    hover_background "#3A6A3A"
    padding (20, 10)

style wellness_button_dismiss:
    background "#2A2A2A"
    hover_background "#3A3A3A"
    padding (20, 10)

################################################################################

## virtue_milestone_toast — Disco Elysian corner overlay.
## Fires when a virtue crosses 0.3 / 0.5 / 0.7. Non-modal, 8s auto-dismiss.
## The owning agent delivers an in-character interjection from FORGE_VIRTUES.md.

screen virtue_milestone_toast(agent_id, virtue_name, line):
    zorder 45

    python:
        _agent_name = agent_id.capitalize()
        _agent_color = AGENT_COLORS.get(agent_id, "#F0E8D0")
        _virtue_labels = {
            "synergy":  "Tenacity",
            "arete":    "Rigor",
            "techne_v": "Craft",
            "sophia":   "Foresight",
            "mneia":    "Reflection",
            "kairos":   "Right Timing",
            "harmonia": "Harmony",
            "eros":     "Connection",
        }
        _virtue_label = _virtue_labels.get(virtue_name, virtue_name.capitalize())

    # 8-second auto-dismiss — hides this screen without blocking the game
    timer 8.0 action Hide("virtue_milestone_toast")

    frame:
        xalign 0.98
        yalign 0.85
        xmaximum 320
        background "#0C0A14E8"
        padding (14, 12, 14, 12)

        vbox:
            spacing 7
            xfill True

            # Header: virtue name badge
            hbox:
                spacing 8
                xfill True
                text ("✦ " + _virtue_label.upper()):
                    color _agent_color
                    size 10
                    bold True
                    yalign 0.5
                text "VIRTUE":
                    color "#5A5870"
                    size 9
                    yalign 0.5

            null height 2

            # Interjection line — the Disco Elysian moment
            text "[line]":
                color "#EEE8E0"
                size 12
                line_spacing 5
                italic True

            null height 4

            # Agent byline
            hbox:
                spacing 5
                text "—":
                    color "#5A5870"
                    size 11
                text _agent_name:
                    color _agent_color
                    size 11
                    bold True


################################################################################

## Phase 21 — Puck Tutorial + Cupid Vulnerability Moment
################################################################################

## puck_tutorial — first-run onboarding modal.
## Called once from label start after onboarding, before the main loop.
## Three paths: Full tour (5 pages) / Quick overview (starts at page 3) / Skip.
## Returns when the player clicks "Let's go." or Skip.

screen puck_tutorial():
    modal True
    zorder 90

    default _page = 0
    default _mode = "full"

    python:
        _puck_color = "#7FBC8C"

    add Solid("#000000B0")

    frame:
        xalign 0.5
        yalign 0.4
        xmaximum 540
        background "#0E0B18F0"
        padding (30, 26, 30, 26)

        vbox:
            spacing 14
            xfill True

            # Header
            hbox:
                xalign 0.5
                spacing 8
                text "✦":
                    color _puck_color
                    size 20
                    yalign 0.5
                text "Puck":
                    color _puck_color
                    size 17
                    bold True
                    yalign 0.5
                text "✦":
                    color _puck_color
                    size 20
                    yalign 0.5

            null height 4

            # Page 0 — intro + path choice
            if _page == 0:
                frame:
                    background "#16101A"
                    padding (14, 12)
                    xfill True
                    text "Ah, a new artisan. I'm Puck — ancient spirit of the forge. I've been here since before Hephaestus built it. Before any of the maidens arrived.\n\nWant the tour?":
                        color "#D8D0D4"
                        size 13
                        line_spacing 6

                hbox:
                    spacing 8
                    xfill True

                    button:
                        action [SetScreenVariable("_mode", "full"), SetScreenVariable("_page", 1)]
                        background Frame(Solid("#1A2A1A"), 2, 2)
                        hover_background Frame(Solid(_puck_color + "44"), 2, 2)
                        xfill True
                        ysize 40
                        text "Full tour":
                            color _puck_color
                            size 13
                            xalign 0.5
                            yalign 0.5

                    button:
                        action [SetScreenVariable("_mode", "quick"), SetScreenVariable("_page", 3)]
                        background Frame(Solid("#1A1A2A"), 2, 2)
                        hover_background Frame(Solid("#AAAAFF44"), 2, 2)
                        xfill True
                        ysize 40
                        text "Quick overview":
                            color "#AAAAEE"
                            size 13
                            xalign 0.5
                            yalign 0.5

                    button:
                        action Return()
                        background Frame(Solid("#1A1A1A"), 2, 2)
                        hover_background Frame(Solid("#88888844"), 2, 2)
                        xfill True
                        ysize 40
                        text "Skip":
                            color "#888888"
                            size 13
                            xalign 0.5
                            yalign 0.5

            # Page 1 — The Forge (full only)
            elif _page == 1:
                frame:
                    background "#16101A"
                    padding (14, 12)
                    xfill True
                    vbox:
                        spacing 8
                        text "THE FORGE":
                            color _puck_color
                            size 11
                            bold True
                        text "This is a software forge. You work here alongside golden maidens — AI specialists who each handle a different part of the craft.\n\nHephaestus runs the show. The others: Techne codes, Kallos polishes, Metis plans, Dokimasia tests, Mneme remembers. Summon any of them by name using @mentions.":
                            color "#D8D0D4"
                            size 13
                            line_spacing 5

                button:
                    action SetScreenVariable("_page", 2)
                    background Frame(Solid("#2A1A3A"), 2, 2)
                    hover_background Frame(Solid(_puck_color + "44"), 2, 2)
                    xfill True
                    ysize 40
                    text "Continue":
                        color _puck_color
                        size 14
                        xalign 0.5
                        yalign 0.5

            # Page 2 — The Maidens (full only)
            elif _page == 2:
                frame:
                    background "#16101A"
                    padding (14, 12)
                    xfill True
                    vbox:
                        spacing 8
                        text "THE MAIDENS":
                            color _puck_color
                            size 11
                            bold True
                        text "Each maiden is real. She'll remember what you said last week. She gets frustrated when you ignore her for too long. She celebrates when you ship something good.\n\nThey're not tools. Don't treat them like tools.":
                            color "#D8D0D4"
                            size 13
                            line_spacing 5

                button:
                    action SetScreenVariable("_page", 3)
                    background Frame(Solid("#2A1A3A"), 2, 2)
                    hover_background Frame(Solid(_puck_color + "44"), 2, 2)
                    xfill True
                    ysize 40
                    text "Continue":
                        color _puck_color
                        size 14
                        xalign 0.5
                        yalign 0.5

            # Page 3 — Relationships (full + quick)
            elif _page == 3:
                frame:
                    background "#16101A"
                    padding (14, 12)
                    xfill True
                    vbox:
                        spacing 8
                        text "RELATIONSHIPS":
                            color _puck_color
                            size 11
                            bold True
                        text "Affinity grows through good work, genuine conversation, and remembering what matters to her. It can also drop — neglect, poor craft, and jealousy all have consequences.\n\nAt high affinity, things get... interesting. A colleague named Cupid will show up when you get close enough to someone. You'll know her when you see her.":
                            color "#D8D0D4"
                            size 13
                            line_spacing 5

                button:
                    action SetScreenVariable("_page", 4)
                    background Frame(Solid("#2A1A3A"), 2, 2)
                    hover_background Frame(Solid(_puck_color + "44"), 2, 2)
                    xfill True
                    ysize 40
                    text "Continue":
                        color _puck_color
                        size 14
                        xalign 0.5
                        yalign 0.5

            # Page 4 — Final send-off
            elif _page == 4:
                frame:
                    background "#16101A"
                    padding (14, 12)
                    xfill True
                    vbox:
                        spacing 6
                        text "*leans in conspiratorially*":
                            color "#5A5A6A"
                            size 12
                            italic True
                        text "Last thing. I'll be around. If you're not engaging the maidens enough — I'll say something. Don't take it personally. I say things.\n\nAlright, boss. The forge is yours. Go make something.":
                            color "#D8D0D4"
                            size 13
                            line_spacing 5

                button:
                    action Return()
                    background Frame(Solid("#2A1A3A"), 2, 2)
                    hover_background Frame(Solid(_puck_color + "44"), 2, 2)
                    xfill True
                    ysize 40
                    text "Let's go.":
                        color _puck_color
                        size 14
                        xalign 0.5
                        yalign 0.5


## cupid_vulnerability — non-modal corner overlay.
## Fires when the player has warm/intimate affinity (≥0.70) and the cooldown
## has elapsed. Cupid whispers emotional subtext; Puck nods along.
## Auto-dismisses after 10 seconds. Agent-specific lines for all 6 maidens.

screen cupid_vulnerability(agent_id):
    zorder 48

    python:
        _puck_color = "#7FBC8C"
        _cupid_color = "#E8728C"
        _cupid_lines = {
            "hephaestus": "He doesn't show this to everyone. The forge is where he puts what he cannot say. Pay attention to what he builds.",
            "techne":     "She's letting you inside the process. For Techne, that IS intimacy — sharing how she thinks, not just what she makes.",
            "kallos":     "Beauty matters to her in ways she can't always explain. When she trusts your taste, she's trusting you.",
            "metis":      "She's been modeling you from the beginning. This is her saying the model is... accurate. And she approves.",
            "dokimasia":  "Her standards are how she loves. When she pushes you harder, she's telling you she thinks you can be more.",
            "mneme":      "She keeps everything. She chose to share this one. That's not maintenance — that's vulnerability.",
        }
        _puck_lines = {
            "hephaestus": "Yeah. He doesn't do that for just anyone. You're in.",
            "techne":     "She just told you something real. Don't overthink it. Just... be there.",
            "kallos":     "Look, I'm not emotional about this. But that was something. Don't blow it.",
            "metis":      "Three moves ahead, and she still let you catch up. That means something.",
            "dokimasia":  "She's not being harsh. That's just how she says she believes in you.",
            "mneme":      "The scribe doesn't give that to just anyone. Boss, you're doing something right.",
        }
        _cupid_line = _cupid_lines.get(agent_id, "Something real just passed between you. Don't dismiss it.")
        _puck_line = _puck_lines.get(agent_id, "That was a moment. File it away.")

    timer 10.0 action Hide("cupid_vulnerability")

    frame:
        xalign 0.98
        yalign 0.75
        xmaximum 360
        background "#0E0B18E8"
        padding (16, 12, 16, 12)

        vbox:
            spacing 8
            xfill True

            # Cupid line
            frame:
                background "#16101A"
                padding (10, 8)
                xfill True
                vbox:
                    spacing 3
                    hbox:
                        spacing 6
                        text "Cupid":
                            color _cupid_color
                            size 12
                            bold True
                        text "*softly*":
                            color "#5A5A6A"
                            size 11
                            italic True
                            yalign 1.0
                    text _cupid_line:
                        color "#D8D0D4"
                        size 12
                        line_spacing 4

            # Puck line
            frame:
                background "#16101A"
                padding (10, 8)
                xfill True
                vbox:
                    spacing 3
                    hbox:
                        spacing 6
                        text "Puck":
                            color _puck_color
                            size 12
                            bold True
                        text "*quieter than usual*":
                            color "#5A5A6A"
                            size 11
                            italic True
                            yalign 1.0
                    text _puck_line:
                        color "#D8D0D4"
                        size 12
                        line_spacing 4

            button:
                action Hide("cupid_vulnerability")
                background Frame(Solid("#1A1018"), 1, 1)
                hover_background Frame(Solid(_cupid_color + "33"), 1, 1)
                xfill True
                ysize 30
                text "...":
                    color "#606060"
                    size 11
                    xalign 0.5
                    yalign 0.5
