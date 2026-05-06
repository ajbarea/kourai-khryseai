## Ren'Py Screen Language
## screens_relationships.rpy — Forge-specific interaction: agent_choice, journal,
##   project selection, confession system (Phases 8 + 10)

init offset = -1

## Agent Choice screen ###########################################################
##
## Shown when the bridge sends {"action": "choice", "choices": ["option A", "option B", ...]}
## Displays up to 4 forge-styled choice buttons. The selected choice is returned
## via bridge.send_message({"action": "choice", "choice": selected_text}).
## Trigger: script.rpy checks for vn_response.action == "choice" and shows this screen.

screen agent_choice(choices, speaker_name="Hephaestus", prompt="Choose your path"):
    zorder 30
    modal True

    frame:
        xalign 0.5
        yalign 0.65
        xmaximum 700
        xminimum 400
        background "#1A1610F0"
        padding (32, 20, 32, 20)

        vbox:
            spacing 8
            xfill True

            ## Prompt label
            text prompt:
                color gui.accent_color
                size gui.text_size
                xalign 0.5

            null height 8

            ## Choice buttons
            for choice_text in choices:
                textbutton choice_text:
                    action Return(choice_text)
                    xfill True
                    background "#2A1800CC"
                    hover_background "#FF950033"
                    padding (16, 10)
                    text_style "choice_button_text"

style choice_button_text:
    color "#F0E8D0"
    size gui.text_size
    hover_color gui.accent_color
    xalign 0.0


## Forge Journal screen ########################################################

screen forge_journal():
    tag menu
    # C12: Enhanced Forge Journal with virtue bars, patron agents, and discoveries.
    # _get_virtue_text() defined in init python in script.rpy.
    $ virtue_context = _get_virtue_context_dict()

    use game_menu(_("Forge Journal"), scroll="viewport"):
        vbox:
            spacing 30

            # Title
            text "⚡ The Forge Observes" size 35 color "#F1D2A1" bold True
            text "(Your virtues across sessions)" size 18 color "#A0A0A0"

            null height 10

            # Virtue bars grid — 8 virtues, 2 columns × 4 rows
            grid 2 4:
                spacing 20
                # Synergy — Tenacity / Collaboration (patron: Hephaestus)
                vbox:
                    spacing 5
                    text "Synergy" size 18 color "#FF9500" bold True
                    text "Tenacity · Hephaestus" size 14 color "#A0A0A0"
                    bar value virtue_context.get("synergy", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("synergy", 0.0) size 14 color "#E8E8E8"

                # Techne — Craft precision (patron: Techne)
                vbox:
                    spacing 5
                    text "Techne" size 18 color "#17A2B8" bold True
                    text "Craft · Techne" size 14 color "#A0A0A0"
                    bar value virtue_context.get("techne_v", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("techne_v", 0.0) size 14 color "#E8E8E8"

                # Harmonia — Harmony / Elegance (patron: Kallos)
                vbox:
                    spacing 5
                    text "Harmonia" size 18 color "#D946EF" bold True
                    text "Harmony · Kallos" size 14 color "#A0A0A0"
                    bar value virtue_context.get("harmonia", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("harmonia", 0.0) size 14 color "#E8E8E8"

                # Sophia — Clarity / Foresight (patron: Metis)
                vbox:
                    spacing 5
                    text "Sophia" size 18 color "#4C6EF5" bold True
                    text "Foresight · Metis" size 14 color "#A0A0A0"
                    bar value virtue_context.get("sophia", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("sophia", 0.0) size 14 color "#E8E8E8"

                # Arete — Excellence-seeking / Rigor (patron: Dokimasia)
                vbox:
                    spacing 5
                    text "Arete" size 18 color "#6C757D" bold True
                    text "Rigor · Dokimasia" size 14 color "#A0A0A0"
                    bar value virtue_context.get("arete", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("arete", 0.0) size 14 color "#E8E8E8"

                # Mneia — Memory and continuity (patron: Mneme)
                vbox:
                    spacing 5
                    text "Mneia" size 18 color "#B73E1D" bold True
                    text "Reflection · Mneme" size 14 color "#A0A0A0"
                    bar value virtue_context.get("mneia", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("mneia", 0.0) size 14 color "#E8E8E8"

                # Kairos — Right Timing (patron: Puck)
                vbox:
                    spacing 5
                    text "Kairos" size 18 color "#007FFF" bold True
                    text "Right Timing · Puck" size 14 color "#A0A0A0"
                    bar value virtue_context.get("kairos", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("kairos", 0.0) size 14 color "#E8E8E8"

                # Eros — Connection and bonds (patron: Cupid)
                vbox:
                    spacing 5
                    text "Eros" size 18 color "#FF85A2" bold True
                    text "Connection · Cupid" size 14 color "#A0A0A0"
                    bar value virtue_context.get("eros", 0.0) range 1.0 xsize 250 ysize 20
                    text "%.2f" % virtue_context.get("eros", 0.0) size 14 color "#E8E8E8"

            null height 20

            # Session summary
            frame:
                xsize 700 ysize 200
                background Frame(Solid("#1A1010"), 2, 2)
                padding 15, 15
                vbox:
                    spacing 10
                    text "Session Summary" size 20 color "#F1D2A1" bold True
                    $ summary_text = virtue_context.get("session_summary",
                        "No virtue changes this session.")
                    text summary_text size 16 color "#E8E8E8"

            null height 15

            # Discoveries section (new facts from knowledge graph)
            text "🔮 Discoveries" size 20 color "#F1D2A1" bold True
            $ discoveries = virtue_context.get("recent_facts", [])
            if discoveries:
                vbox:
                    spacing 8
                    for fact in discoveries:
                        text "• " + fact size 16 color "#E8D5B7"
            else:
                text "(No new discoveries this session)" size 16 color "#A0A0A0"

## Project Selection screen ####################################################

screen project_selection():
    tag menu
    # C13: Project selection with validation, recent history, and path input.
    $ current_path = getattr(persistent, "project_path", None)
    $ recent_projects = getattr(persistent, "recent_projects", []) or []

    use game_menu(_("Project Selection"), scroll="viewport"):
        vbox:
            spacing 25

            # Title
            text "📁 Project Workspace" size 35 color "#F1D2A1" bold True
            text "(where your code lives)" size 16 color "#A0A0A0"

            null height 15

            # Current project display
            frame:
                xsize 650 ysize 80
                background Frame(Solid("#1A1010"), 2, 2)
                padding 15, 15
                vbox:
                    spacing 5
                    text "Current Project" size 18 color "#F1D2A1" bold True
                    if current_path:
                        text current_path size 16 color "#E8D5B7"
                    else:
                        text "(None selected yet)" size 16 color "#A0A0A0"

            null height 20

            # Project path input
            text "Set Project Path" size 20 color "#F1D2A1" bold True
            text "(Absolute path to project root directory)" size 14 color "#A0A0A0"

            hbox:
                spacing 15
                button:
                    action ui.callsinnewcontext("project_input_label")
                    background Frame(Solid("#3A2A00"), 2, 2)
                    xsize 500 ysize 50
                    text "Enter Path" align (0.5, 0.5) color "#F1D2A1" size 18
                button:
                    action Function(_validate_and_set_project, current_path)
                    background Frame(Solid("#2A3A00"), 2, 2)
                    xsize 120 ysize 50
                    text "Validate" align (0.5, 0.5) color "#7FFF00" size 16

            null height 10

            # Create new project button
            button:
                action ui.callsinnewcontext("create_project_label")
                background Frame(Solid("#17A2B844"), 2, 2)
                hover_background Frame(Solid("#17A2B888"), 2, 2)
                xsize 635 ysize 50
                text "➕ Create New Project Workspace" align (0.5, 0.5) color "#E8E8E8" size 18

            null height 20

            # Recent projects list
            if recent_projects:
                text "📌 Recent Projects" size 20 color "#F1D2A1" bold True
                vbox:
                    spacing 8
                    for proj_path in recent_projects[:5]:
                        hbox:
                            spacing 10
                            button:
                                action SetVariable("persistent.project_path", proj_path)
                                background Frame(Solid("#2A2A1A"), 1, 1)
                                xsize 600 ysize 40
                                text (proj_path[:55] + "..." if len(proj_path) > 55 else proj_path) size 14 color "#E8E8E8" align (0.0, 0.5)
            else:
                null height 10


################################################################################
## Jealousy Routing + Tier-Up Notifications
################################################################################

## Confession System
################################################################################

## pre_confession_window — fires once when any agent crosses tier 4 (affinity 0.8+).
## Puck + Cupid "late game" banter; [Continue] returns control.

screen pre_confession_window(agent_id):
    zorder 55
    modal True

    python:
        _agent_name = agent_id.capitalize()
        _agent_color = AGENT_COLORS.get(agent_id, "#F0E8D0")
        _puck_color = VN_PUCK_ACCENT
        _cupid_color = VN_CUPID_ACCENT

    add Solid("#00000088")

    frame:
        xalign 0.5
        yalign 0.4
        xmaximum 520
        background "#100C18F0"
        padding (28, 24, 28, 24)

        vbox:
            spacing 12
            xfill True

            hbox:
                xalign 0.5
                spacing 10
                text "✦":
                    color _agent_color
                    size 22
                    yalign 0.5
                text _agent_name:
                    color _agent_color
                    size 18
                    bold True
                    yalign 0.5
                text "— Tier 4":
                    color "#F1D2A1"
                    size 14
                    italic True
                    yalign 0.5
                text "✦":
                    color _agent_color
                    size 22
                    yalign 0.5

            null height 4

            frame:
                background "#16101A"
                padding (10, 7)
                xfill True
                vbox:
                    spacing 3
                    hbox:
                        spacing 6
                        text "Puck":
                            color _puck_color
                            size 13
                            bold True
                        text "*low whistle*":
                            color "#5A5A6A"
                            size 12
                            italic True
                            yalign 1.0
                    text ("Hey boss. " + _agent_name + " is in deep. And so are you."):
                        color "#D8D0D4"
                        size 13
                        line_spacing 3

            frame:
                background "#16101A"
                padding (10, 7)
                xfill True
                vbox:
                    spacing 3
                    hbox:
                        spacing 6
                        text "Cupid":
                            color _cupid_color
                            size 13
                            bold True
                        text "*softly*":
                            color "#5A5A6A"
                            size 12
                            italic True
                            yalign 1.0
                    text "What you feel... she feels it too. The question is whether you'll speak first.":
                        color "#D8D0D4"
                        size 13
                        line_spacing 3

            frame:
                background "#16101A"
                padding (10, 7)
                xfill True
                vbox:
                    spacing 3
                    hbox:
                        spacing 6
                        text "Puck":
                            color _puck_color
                            size 13
                            bold True
                        text "*relenting*":
                            color "#5A5A6A"
                            size 12
                            italic True
                            yalign 1.0
                    text "...she's not wrong. Think about it.":
                        color "#D8D0D4"
                        size 13
                        line_spacing 3

            null height 8

            button:
                action Return()
                background Frame(Solid("#2A1A3A"), 2, 2)
                hover_background Frame(Solid("#F1D2A144"), 2, 2)
                xfill True
                ysize 44
                text "Continue":
                    color "#F1D2A1"
                    size 15
                    xalign 0.5
                    yalign 0.5


## confession_scene — the agent's scripted confession + player response choices.
## Returns "accept", "wait", or "reject".

screen confession_scene(agent_id):
    zorder 60
    modal True

    python:
        _agent_name = agent_id.capitalize()
        _agent_color = AGENT_COLORS.get(agent_id, "#F0E8D0")
        _puck_color = VN_PUCK_ACCENT
        _cupid_color = VN_CUPID_ACCENT
        _confession_lines = {
            "hephaestus": "I don't do this. Fall for anyone. But you've proven you see me as more than the orchestrator. That's dangerous.",
            "techne":     "Don't make me spell it out. You mean something to me. More than code. That terrifies me.",
            "kallos":     "All that pushing? It's because I see potential in you. And I want to build something beautiful with you.",
            "metis":      "I've been optimizing for your happiness for months. You're the variable I can't predict — and I love it.",
            "dokimasia":  "I'm scared I'm too hard on you. That one day you'll realize someone gentler is better. But I can't... I can't pretend I don't need you to be okay.",
            "mneme":      "I've kept every word you've ever said to me. Every session. I've been documenting my own heart without realizing it.",
        }
        _confession_line = _confession_lines.get(agent_id, "...")

    add Solid("#000000AA")

    frame:
        xalign 0.5
        yalign 0.38
        xmaximum 560
        background "#100C18F0"
        padding (30, 26, 30, 26)

        vbox:
            spacing 14
            xfill True

            # Agent header
            hbox:
                xalign 0.5
                spacing 10
                text ("✦  " + _agent_name + "  ✦"):
                    color _agent_color
                    size 19
                    bold True
                    yalign 0.5

            null height 2

            # The confession
            frame:
                background "#1A1018"
                padding (16, 14)
                xfill True
                text _confession_line:
                    color "#F0E8DC"
                    size 15
                    line_spacing 7
                    italic True

            null height 2

            # Spirits react
            hbox:
                spacing 8
                xfill True
                frame:
                    background "#0E1410"
                    padding (8, 6)
                    xfill True
                    vbox:
                        spacing 2
                        text "Cupid  *wistful*":
                            color _cupid_color
                            size 11
                            bold True
                        text "Oh, my dear...":
                            color "#C8A0A8"
                            size 12
                            italic True
                frame:
                    background "#0E1410"
                    padding (8, 6)
                    xfill True
                    vbox:
                        spacing 2
                        text "Puck  *hushed*":
                            color _puck_color
                            size 11
                            bold True
                        text "Don't make her wait.":
                            color "#A0C0A0"
                            size 12
                            italic True

            null height 6

            # Player choices
            vbox:
                spacing 10
                xfill True

                button:
                    action Return("accept")
                    background Frame(Solid(_agent_color + "33"), 2, 2)
                    hover_background Frame(Solid(_agent_color + "66"), 2, 2)
                    xfill True
                    ysize 56
                    vbox:
                        xalign 0.5
                        yalign 0.5
                        text ("✦  I feel the same way"):
                            color "#F0E8DC"
                            size 15
                            bold True
                            xalign 0.5
                        text "Accept":
                            color "#908070"
                            size 12
                            xalign 0.5

                button:
                    action Return("wait")
                    background Frame(Solid("#2A2A2A"), 2, 2)
                    hover_background Frame(Solid("#3A3A3A"), 2, 2)
                    xfill True
                    ysize 44
                    text "Not yet — I need more time":
                        color "#C0B8B0"
                        size 14
                        xalign 0.5
                        yalign 0.5

                button:
                    action Return("reject")
                    background Frame(Solid("#1A1A1A"), 1, 1)
                    hover_background Frame(Solid("#2A1A1A"), 1, 1)
                    xfill True
                    ysize 38
                    text "I'm sorry — I don't feel that way":
                        color "#7A6A6A"
                        size 12
                        xalign 0.5
                        yalign 0.5


## confession_outcome — agent's reaction after the player's choice.
## `accepted` True = player said yes; False = player pulled back.
## Returns on button click.

screen confession_outcome(agent_id, accepted):
    zorder 60
    modal True

    python:
        _agent_name = agent_id.capitalize()
        _agent_color = AGENT_COLORS.get(agent_id, "#F0E8D0")
        _puck_color = VN_PUCK_ACCENT
        _accepted_reactions = {
            "hephaestus": "...I'll hold you to that. The forge keeps its promises. And so do I.",
            "techne":     "You compiled my heart. *quiet laugh* Don't make me regret saying that.",
            "kallos":     "Then let's build something beautiful. Together. Starting now.",
            "metis":      "I planned for many outcomes. This one... I hoped for but couldn't guarantee. I'm glad.",
            "dokimasia":  "All tests passing. *exhale* I've never been so relieved by a result in my life.",
            "mneme":      "The scribe has no words right now. *pause* I'll find them. I'll write them. I promise.",
        }
        _rejected_reactions = {
            "hephaestus": "...You're honest. I respect that. This conversation never happened. Except I'll remember it.",
            "techne":     "I'm... not there yet. Give me time. Don't misinterpret the silence.",
            "kallos":     "I'm not ready to answer that. Not yet. Keep working. Keep growing. Come back when I'm ready.",
            "metis":      "The timing isn't right. I planned for this too. *quiet* I hoped for different data.",
            "dokimasia":  "I need more time. More evidence. I'll run the test again when I'm ready.",
            "mneme":      "I'll hold this carefully. Some things deserve to be kept before they're answered.",
        }
        _puck_reactions_accepted = {
            "hephaestus": "Hah. There it is. Told you he's not as gruff as he looks.",
            "techne":     "THERE we go! That's the move! Good work, boss.",
            "kallos":     "Did she just — I KNEW IT. *floats in excited circle*",
            "metis":      "Called it. Three moves ahead, as always. But this one surprised even her.",
            "dokimasia":  "Twenty-three edge cases. All passing. Including this one.",
            "mneme":      "The scribe is at a loss for words. That almost never happens.",
        }
        _puck_reactions_rejected = {
            "hephaestus": "Okay. That's not a no. That's a 'not yet.' Trust the forge.",
            "techne":     "She needs time. Give it to her. She'll come around.",
            "kallos":     "The wall went up. But it's thinner than it used to be. That's something.",
            "metis":      "She's processing. Metis doesn't do anything fast. Except think.",
            "dokimasia":  "She's thorough. Always runs the test twice. Give her the second run.",
            "mneme":      "She'll hold it carefully. That's actually... kind of beautiful.",
        }
        _response = _accepted_reactions.get(agent_id, "...") if accepted else _rejected_reactions.get(agent_id, "...")
        _puck_line = _puck_reactions_accepted.get(agent_id, "That's the move!") if accepted else _puck_reactions_rejected.get(agent_id, "Not done yet.")
        _accent = _agent_color if accepted else "#908070"

    add Solid("#000000AA")

    frame:
        xalign 0.5
        yalign 0.38
        xmaximum 520
        background "#100C18F0"
        padding (28, 24, 28, 24)

        vbox:
            spacing 12
            xfill True

            hbox:
                xalign 0.5
                text ("✦  " + _agent_name + ("  ✦" if accepted else "")):
                    color _accent
                    size 18
                    bold True
                    yalign 0.5

            null height 2

            frame:
                background "#1A1018"
                padding (14, 12)
                xfill True
                text _response:
                    color "#F0E8DC"
                    size 14
                    line_spacing 6
                    italic True

            frame:
                background "#16101A"
                padding (10, 7)
                xfill True
                vbox:
                    spacing 3
                    hbox:
                        spacing 6
                        text "Puck":
                            color _puck_color
                            size 13
                            bold True
                        text ("*pumped*" if accepted else "*knowing*"):
                            color "#5A5A6A"
                            size 12
                            italic True
                            yalign 1.0
                    text _puck_line:
                        color "#D8D0D4"
                        size 13
                        line_spacing 3

            null height 8

            button:
                action Return()
                background Frame(Solid("#2A1A3A" if accepted else "#1A1A2A"), 2, 2)
                hover_background Frame(Solid(_accent + "44"), 2, 2)
                xfill True
                ysize 44
                text ("Continue ✦" if accepted else "Continue"):
                    color _accent
                    size 15
                    xalign 0.5
                    yalign 0.5
