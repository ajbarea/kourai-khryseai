## Ren'Py Screen Language
## screens_dialogue.rpy — Core dialogue UI: base styles, say, input, choice, agent_portrait

################################################################################
## Initialization
################################################################################

init offset = -1


################################################################################
## Styles
################################################################################

style default:
    properties gui.text_properties()
    language gui.language

style input:
    properties gui.text_properties("input", accent=True)
    adjust_spacing False

style hyperlink_text:
    properties gui.text_properties("hyperlink", accent=True)
    hover_underline True

style gui_text:
    properties gui.text_properties("interface")


style button:
    properties gui.button_properties("button")

style button_text is gui_text:
    properties gui.text_properties("button")
    yalign 0.5


style label_text is gui_text:
    properties gui.text_properties("label", accent=True)

style prompt_text is gui_text:
    properties gui.text_properties("prompt")


style bar:
    ysize gui.bar_size
    left_bar Frame("gui/bar/left.png", gui.bar_borders, tile=gui.bar_tile)
    right_bar Frame("gui/bar/right.png", gui.bar_borders, tile=gui.bar_tile)

style vbar:
    xsize gui.bar_size
    top_bar Frame("gui/bar/top.png", gui.vbar_borders, tile=gui.bar_tile)
    bottom_bar Frame("gui/bar/bottom.png", gui.vbar_borders, tile=gui.bar_tile)

style scrollbar:
    ysize gui.scrollbar_size
    base_bar Frame("gui/scrollbar/horizontal_[prefix_]bar.png", gui.scrollbar_borders, tile=gui.scrollbar_tile)
    thumb Frame("gui/scrollbar/horizontal_[prefix_]thumb.png", gui.scrollbar_borders, tile=gui.scrollbar_tile)

style vscrollbar:
    xsize gui.scrollbar_size
    base_bar Frame("gui/scrollbar/vertical_[prefix_]bar.png", gui.vscrollbar_borders, tile=gui.scrollbar_tile)
    thumb Frame("gui/scrollbar/vertical_[prefix_]thumb.png", gui.vscrollbar_borders, tile=gui.scrollbar_tile)

style slider:
    ysize gui.slider_size
    base_bar Frame("gui/slider/horizontal_[prefix_]bar.png", gui.slider_borders, tile=gui.slider_tile)
    thumb "gui/slider/horizontal_[prefix_]thumb.png"

style vslider:
    xsize gui.slider_size
    base_bar Frame("gui/slider/vertical_[prefix_]bar.png", gui.vslider_borders, tile=gui.slider_tile)
    thumb "gui/slider/vertical_[prefix_]thumb.png"


style frame:
    padding gui.frame_borders.padding
    background Frame("gui/frame.png", gui.frame_borders, tile=gui.frame_tile)



################################################################################
## In-game screens
################################################################################


## Say screen ##################################################################
##
## The say screen is used to display dialogue to the player. It takes two
## parameters, who and what, which are the name of the speaking character and
## the text to be displayed, respectively. (The who parameter can be None if no
## name is given.)
##
## This screen must create a text displayable with id "what", as Ren'Py uses
## this to manage text display. It can also create displayables with id "who"
## and id "window" to apply style properties.
##
## https://www.renpy.org/doc/html/screen_special.html#say

screen say(who, what):

    ## Gold accent line at the top edge of the dialogue box (Hades 1 warm-gold frame).
    add Solid("#C8B88A50", xysize=(1920, 2)):
        xalign 0.5
        yalign 1.0
        yoffset -(gui.textbox_height)

    ## Subtle gold line at the bottom edge — frames the dialogue box.
    add Solid("#C8B88A25", xysize=(1920, 1)):
        xalign 0.5
        yalign 1.0

    window:
        id "window"

        if who is not None:

            window:
                id "namebox"
                style "namebox"

                ## Gold left accent bar (Hades-style name plate indicator)
                add Solid("#C8B88A", xysize=(3, 200)):
                    xpos -18
                    ypos -8

                vbox:
                    spacing 2
                    text who id "who"

                    ## Hades-style epithet subtitle (e.g. "Artisan of Code")
                    if who in AGENT_EPITHETS:
                        text AGENT_EPITHETS[who]:
                            size 22
                            color "#C8B88A"
                            italic True

        text what id "what"


    ## If there's a side image, display it above the text. Do not display on the
    ## phone variant - there's no room.
    if not renpy.variant("small"):
        add SideImage() xalign 0.0 yalign 1.0


## Make the namebox available for styling through the Character object.
init python:
    config.character_id_prefixes.append('namebox')

style window is default
style say_label is default
style say_dialogue is default
style say_thought is say_dialogue

style namebox is default
style namebox_label is say_label


style window:
    xalign 0.5
    xfill True
    yalign gui.textbox_yalign
    ysize gui.textbox_height

    ## Deep warm charcoal with a faint amber undertone — forge at night.
    ## The gold border PNG (textbox.png) will replace this in the portrait pass.
    background "#1A1610EE"
    padding (50, 24, 50, 24)

style namebox:
    xpos gui.name_xpos
    xanchor gui.name_xalign
    xsize gui.namebox_width
    ypos gui.name_ypos
    ysize gui.namebox_height

    ## Dark amber forge tab — reads as a distinct "speaker plate" against the window.
    ## A gold-bordered namebox.png will replace this in the portrait pass.
    background "#2A1800F2"
    padding (20, 8, 20, 8)

style say_label:
    properties gui.text_properties("name", accent=True)
    xalign gui.name_xalign
    yalign 0.5
    bold True

style say_dialogue:
    properties gui.text_properties("dialogue")

    xpos gui.dialogue_xpos
    xsize gui.dialogue_width
    ypos gui.dialogue_ypos

    adjust_spacing False

## Input screen ################################################################
##
## This screen is used to display renpy.input. The prompt parameter is used to
## pass a text prompt in.
##
## This screen must create an input displayable with id "input" to accept the
## various input parameters.
##
## @mention autocomplete: when prompt starts with "You", watches for "@" in the
## live input text (via ScreenVariableInputValue) and shows a filtered popup of
## agent mentions above the textbox. Clicking a suggestion inserts it.
##
## https://www.renpy.org/doc/html/screen_special.html#input

screen input(prompt):
    style_prefix "input"
    default input_text = ""

    window:

        vbox:
            xanchor gui.dialogue_text_xalign
            xpos gui.dialogue_xpos
            xsize gui.dialogue_width
            ypos gui.dialogue_ypos

            text prompt style "input_prompt"
            ## ScreenVariableInputValue keeps input_text in sync with what
            ## the player is typing — enables live autocomplete filtering.
            input id "input" value ScreenVariableInputValue("input_text")

    ## @mention autocomplete — only shown during the main chat prompt
    if prompt.startswith("You"):
        python:
            _at_idx = input_text.rfind("@")
            if _at_idx >= 0:
                _frag = input_text[_at_idx + 1:].lower()
                ## Stop suggesting once the user has typed a space (mention done)
                _suggs = (
                    [(m, a) for m, a in sorted(MENTION_MAP.items()) if m.startswith(_frag)]
                    if " " not in _frag else []
                )
            else:
                _frag = ""
                _suggs = []

        if _suggs:
            frame:
                ## Anchor bottom of popup just above the textbox
                xalign 0.5
                ypos 0.82
                yanchor 1.0
                background "#1A1610F2"
                padding (16, 10, 16, 10)
                xmaximum 520

                vbox:
                    spacing 4

                    hbox:
                        spacing 8
                        text "@":
                            color gui.accent_color
                            size 18
                            bold True
                            yalign 0.5
                        text "Mention an agent":
                            color "#7A6846"
                            size 14
                            yalign 0.5

                    null height 2

                    for _m, _a in _suggs[:8]:
                        ## Compute label and completed text each iteration so
                        ## the SetScreenVariable action captures the right value.
                        $ _ac = AGENT_COLORS.get(_a, "#F0E8D0")
                        $ _label = "@" + _m + "  \u2192  " + _a.capitalize()
                        $ _done = input_text[:_at_idx + 1] + _m + " "
                        textbutton _label:
                            action SetScreenVariable("input_text", _done)
                            background "#1A1610"
                            hover_background "#FF950033"
                            padding (10, 6)
                            text_color _ac
                            text_hover_color gui.accent_color
                            xfill True

style input_prompt is default

style input_prompt:
    xalign gui.dialogue_text_xalign
    properties gui.text_properties("input_prompt")
    ## Gold prompt label so "You:" reads distinctly from the typed text
    color gui.accent_color
    bold True

style input:
    xalign gui.dialogue_text_xalign
    xmaximum gui.dialogue_width
    ## Parchment text for player input; color gui.text_color is the default
    color gui.text_color


## Choice screen ###############################################################
##
## This screen is used to display the in-game choices presented by the menu
## statement. The one parameter, items, is a list of objects, each with caption
## and action fields.
##
## https://www.renpy.org/doc/html/screen_special.html#choice

screen choice(items):
    style_prefix "choice"

    vbox:
        for i in items:
            textbutton i.caption action i.action


style choice_vbox is vbox
style choice_button is button
style choice_button_text is button_text

style choice_vbox:
    xalign 0.5
    ypos 405
    yanchor 0.5

    spacing gui.choice_spacing

style choice_button is default:
    properties gui.button_properties("choice_button")

style choice_button_text is default:
    properties gui.text_properties("choice_button")


## Agent Portrait screen ########################################################
##
## Transparent PNG sprite, lower-left, sits directly on the scene.
## All portrait assets are transparent — naming: {agent_id}_{state}.png
## Falls back to {agent_id}_neutral.png if a state asset isn't ready yet.
##
## Call: renpy.show_screen("agent_portrait", agent_id="techne", state="neutral")
## Hide: renpy.hide_screen("agent_portrait")

## Smooth entrance — fade in + slight slide from left (Hades-style reveal).
transform portrait_enter:
    alpha 0.0 xoffset -40
    ease 0.35 alpha 1.0 xoffset 0

screen agent_portrait(agent_id="hephaestus", state="neutral"):
    ## Below the say screen (zorder 0) so the textbox covers the character's
    ## lower body — same layering as Hades dialogue.
    zorder -1

    ## 760×760 @ 1920×1080 ≈ 40% width × 70% height — Hades-scale presence.
    ## Character rises above the textbox; lower portion hidden behind dialogue.
    add _portrait_image(agent_id, state) at portrait_enter:
        xalign 0.0
        yalign 1.0
        yoffset 160
        size (760, 760)
