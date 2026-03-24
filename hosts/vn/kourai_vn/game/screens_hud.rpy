## Ren'Py Screen Language
## screens_hud.rpy — Persistent HUD overlays: quick_menu, affinity_hud, gossip_bubble, thinking

init offset = -1

## Quick Menu screen ###########################################################
##
## The quick menu is displayed in-game to provide easy access to the out-of-game
## menus.

screen quick_menu():

    ## Ensure this appears on top of other screens.
    zorder 100

    if quick_menu:

        hbox:
            style_prefix "quick"
            style "quick_menu"

            textbutton _("Back") action Rollback()
            textbutton _("History") action ShowMenu('history')
            textbutton _("Skip") action Skip() alternate Skip(fast=True, confirm=True)
            textbutton _("Auto") action Preference("auto-forward", "toggle")
            textbutton _("Save") action ShowMenu('save')
            textbutton _("Q.Save") action QuickSave()
            textbutton _("Q.Load") action QuickLoad()
            textbutton _("Prefs") action ShowMenu('preferences')
            textbutton _("Journal") action ShowMenu('forge_journal')
            textbutton _("Project") action ShowMenu('project_selection')


## This code ensures that the quick_menu screen is displayed in-game, whenever
## the player has not explicitly hidden the interface.
init python:
    config.overlay_screens.append("quick_menu")

default quick_menu = True

style quick_menu is hbox
style quick_button is default
style quick_button_text is button_text

style quick_menu:
    ## Right-aligned inside the dialogue area — unobtrusive, like Hades' subtle UI.
    xalign 1.0
    xoffset -20
    yalign 1.0
    yoffset -6

style quick_button:
    properties gui.button_properties("quick_button")

style quick_button_text:
    properties gui.text_properties("quick_button")


## Affinity HUD screen ###########################################################
##
## Persistent top-right overlay showing all six agents with their current
## affinity score as a fill bar and tier (1-4 hearts). Shown for the whole
## session once the connection is verified. Updated live as affinity changes.
##
## Data source: `affinity` store dict (client-side, +0.02 per interaction).
## Will reflect real backend affinity_delta events once RELATIONSHIP_SYSTEMS
## backend is implemented.

screen affinity_hud():
    zorder 40

    frame:
        xalign 1.0
        yalign 0.0
        xoffset -12
        yoffset 12
        background "#1A1610D0"
        padding (14, 10, 14, 10)

        vbox:
            spacing 3

            text "BONDS":
                size 17
                color gui.accent_color
                bold True
                xalign 0.5

            null height 5

            for agent_name in AGENT_ORDER:
                $ score     = affinity.get(agent_name, 0.5)
                $ ag_color  = AGENT_COLORS[agent_name]
                $ tier_num  = get_tier(score)
                $ filled    = "♥" * tier_num
                $ empty     = "♡" * (4 - tier_num)

                hbox:
                    spacing 8
                    ysize 24

                    ## 4-char abbreviated name in the agent's accent color
                    text agent_name[:4].upper():
                        size 15
                        color ag_color
                        bold True
                        xminimum 40
                        yalign 0.5

                    ## Affinity fill bar
                    bar:
                        value score
                        range 1.0
                        xsize 70
                        ysize 8
                        yalign 0.5
                        left_bar  Solid(ag_color)
                        right_bar Solid("#2A2018")

                    ## Tier hearts
                    text "[filled][empty]":
                        size 13
                        color ag_color
                        yalign 0.5


## Gossip bubble screen ##########################################################
##
## Transient bottom-left overlay showing a single in-character flavor line from
## an idle agent. Auto-dismisses after 8 seconds. Triggered every 3 player turns.
##
## Content: pre-authored lines in GOSSIP_LINES (script.rpy), grounded in each
## agent's CHARACTER_DESIGN.md voice. Upgrade path: replace with live agent
## gossip events once the gossip backend is built.

screen gossip_bubble(speaker_name, hint, line, color):
    zorder 45

    frame:
        xalign 0.0
        yalign 0.90
        xoffset 12
        background "#1A1610D0"
        padding (14, 10, 14, 10)
        xmaximum 400

        vbox:
            spacing 4

            ## Speaker name + stage direction on one line
            hbox:
                spacing 8

                text speaker_name:
                    color color
                    size 17
                    bold True
                    yalign 1.0

                text hint:
                    color "#7A6846"
                    size 14
                    yalign 1.0

            ## The actual gossip line
            text line:
                color "#F0E8D0"
                size gui.text_size - 6
                xmaximum 372

    ## Auto-dismiss — player doesn't need to interact with it
    timer 8.0 action Hide("gossip_bubble")


## Thinking screen ###############################################################
##
## Shown while the bridge is waiting for an agent response. The poll loop in
## script.rpy updates `thinking_status` with live pipeline status messages.
## The timer forces a redraw every 0.4s so the label changes are visible even
## when the player isn't interacting (Ren'Py only redraws on interactions by
## default).

screen thinking():
    zorder 50

    frame:
        xalign 0.5
        yalign 0.88
        background "#1A1610CC"
        padding (32, 14, 32, 14)

        hbox:
            spacing 14

            ## Forge hammer glyph as activity marker
            text "⚒" color gui.accent_color size 28 yalign 0.5

            text thinking_status:
                color "#F0E8D0"
                size gui.text_size - 4
                yalign 0.5

    ## Ren'Py only redraws when something changes; force periodic refresh so
    ## status text updates land immediately without requiring a click.
    timer 0.4 repeat True action Function(renpy.restart_interaction)
