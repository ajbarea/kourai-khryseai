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

    ## Resolve the speaker's accent color + epithet for the name plaque.
    ## Non-agent speakers ("System", "Player") fall back to warm gold +
    ## empty epithet so the plaque still renders in a sensible default.
    $ _accent = AGENT_ACCENT_BY_NAME.get(who, "#C9944A") if who else "#C9944A"
    $ _epithet = AGENT_EPITHETS.get(who, "") if who else ""

    ## Hades-style name plaque — floats just above the dialogue window,
    ## centered over it, with a top hairline in the speaker's accent color
    ## and a warm-gold bottom hairline. NAME in gold caps, EPITHET in
    ## accent-color italic small-caps beneath — same plaque shape whether
    ## Hephaestus (amber), Metis (indigo), Kallos (magenta) is talking.
    if who is not None:
        frame:
            xalign gui.textbox_xalign
            yalign 1.0
            yoffset -(gui.textbox_height + 22)
            xsize 440
            ysize 92
            background Solid("#14100AEE")
            padding (0, 0, 0, 0)

            ## Accent-color hairline along the top — speaker-tinted.
            add Solid(_accent, xysize=(440, 2)):
                yalign 0.0
            ## Warm-gold hairline along the bottom — frame anchor.
            add Solid("#C9944A", xysize=(440, 1)):
                yalign 1.0

            ## Decorative corner notches — small bright-gold studs inset
            ## from each corner of the plaque. Sells a "crafted frame"
            ## feel without adding real rendering cost. Hades-style.
            add Solid("#F1D2A1", xysize=(4, 4)):
                xalign 0.0
                yalign 0.0
                xoffset 5
                yoffset 5
            add Solid("#F1D2A1", xysize=(4, 4)):
                xalign 1.0
                yalign 0.0
                xoffset -5
                yoffset 5
            add Solid("#F1D2A1", xysize=(4, 4)):
                xalign 0.0
                yalign 1.0
                xoffset 5
                yoffset -5
            add Solid("#F1D2A1", xysize=(4, 4)):
                xalign 1.0
                yalign 1.0
                xoffset -5
                yoffset -5

            vbox:
                xalign 0.5
                yalign 0.5
                spacing 1

                text who.upper():
                    size 40
                    color "#F1D2A1"
                    bold True
                    xalign 0.5
                    id "who"

                if _epithet:
                    ## Warm-cream epithet for consistent readability across
                    ## every agent — the accent color already rides the top
                    ## hairline as a solid shape, where it has room to breathe.
                    ## Tiny tracking bumps the small-caps' air-letter spacing.
                    text _epithet.upper():
                        size 18
                        color "#C8B88A"
                        italic True
                        xalign 0.5
                        kerning 2

    window:
        id "window"

        text what id "what"


    ## If there's a side image, display it above the text. Do not display on the
    ## phone variant - there's no room.
    if not renpy.variant("small"):
        add SideImage() xalign 0.0 yalign 1.0


## Click-to-continue marker — a small pulsing warm-gold triangle that
## appears at the bottom-right of the textbox once dialogue is ready
## for the player to click through. The `ctc` screen is a Ren'Py 8.x
## special screen: it renders whenever the engine wants to display the
## "ready for next line" affordance, and we override it here to show
## our own styled indicator. (In Ren'Py 6 this was `config.ctc`, but
## that variable was removed — the screen override is the modern API.)
image kourai_ctc:
    Text("▾", size=26, color="#E8C87A")
    pause 0.6
    alpha 0.35
    pause 0.4
    alpha 1.0
    repeat

screen ctc(arg=None):
    zorder 100
    add "kourai_ctc":
        ## Right-inside of the 1100px centered textbox on a 1920 stage:
        ## (1920/2 + 1100/2 - 30px padding) / 1920 ≈ 0.77.
        xalign 0.77
        yalign 1.0
        yoffset -28

style window is default
style say_label is default
style say_dialogue is default
style say_thought is say_dialogue


style window:
    xalign gui.textbox_xalign
    xsize gui.textbox_width
    yalign gui.textbox_yalign
    ysize gui.textbox_height

    ## Deep warm charcoal with a faint amber undertone — forge at night.
    ## Lower opacity (B0 = ~69%) so the portraits' silhouettes breathe
    ## through the textbox instead of being sharply cut off. Makes the
    ## panel feel like a UI layer on top of the scene rather than a chunk
    ## of screen that vanishes the characters from the waist down.
    background "#1A1610B0"
    padding (50, 20, 50, 20)

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

    ## Thin dark outline so dialogue stays legible when the textbox is
    ## partly transparent and a portrait's silhouette is visible behind
    ## the text. Cheap, subtle, huge readability win.
    outlines [ (1, "#00000099", 0, 0) ]

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
    ## Position the choice menu just above the floating name plaque so the
    ## stack reads top-to-bottom as: choices → plaque (who's asking) →
    ## dialogue (what they asked). textbox_height + 22px gap + 92px plaque
    ## + 24px margin lifts the buttons clear of the plaque.
    xalign 0.5
    yalign 1.0
    yoffset -(gui.textbox_height + 22 + 92 + 24)

    spacing 8

style choice_button is default:
    properties gui.button_properties("choice_button")
    ## Framed pill button — dark warm fill + dim-gold border so choices
    ## read as clickable affordances instead of free-floating text that
    ## blends into the scene / overlaps whoever's standing behind them.
    background Frame("#1A1610E8", 12, 6)
    hover_background Frame("#3A2A14F0", 12, 6)
    padding (28, 10, 28, 10)
    xminimum 420
    xmaximum 720
    xalign 0.5

style choice_button_text is default:
    properties gui.text_properties("choice_button")
    color "#C8B88A"
    hover_color "#F1D2A1"
    size 28
    xalign 0.5


## Agent Portrait screen ########################################################
##
## Transparent PNG sprite, lower-left, sits directly on the scene.
## All portrait assets are transparent — naming: {agent_id}_{state}.png
## Falls back to {agent_id}_neutral.png if a state asset isn't ready yet.
##
## Call: renpy.show_screen("agent_portrait", agent_id="techne", state="neutral")
## Hide: renpy.hide_screen("agent_portrait")

## Multi-slot portrait system — left / center / right slots can all be
## active at the same time so agent handoffs (Hephaestus → Metis, etc.)
## stay visible on screen instead of replacing each other. The current
## speaker is brightened while others dim, giving a visual read on who
## holds the floor without relying solely on the text box.
##
## Callers:
##   - Preferred:  kourai_show_agent(agent_id, slot, state)
##                 kourai_hide_agent(slot)
##                 kourai_set_speaker(agent_id)
##   - Direct:     renpy.show_screen("agent_portrait",
##                                    agent_id=..., state=..., slot="left",
##                                    tag="portrait_left")
##
## The `slot` argument defaults to "center" so legacy one-agent callers
## (``renpy.show_screen("agent_portrait", agent_id=..., state=...)``) keep
## working unchanged — they still get a single bottom-left portrait.

default current_speaker_id = None

## Entrance animations — side slots slide in from the matching edge so the
## motion reads as "they walked in from that side," while center keeps the
## original Hades-style left-slide reveal for single-agent scenes.
transform portrait_enter:
    alpha 0.0 xoffset -40
    ease 0.35 alpha 1.0 xoffset 0

transform portrait_enter_left:
    alpha 0.0 xoffset -40
    ease 0.35 alpha 1.0 xoffset 0

transform portrait_enter_right:
    alpha 0.0 xoffset 40
    ease 0.35 alpha 1.0 xoffset 0

## Speaker highlighting — the active speaker runs at full opacity, everyone
## else fades to ~70% so the viewer's eye tracks who's talking without
## making the non-speaker feel like a ghost. The plaque's accent-color
## hairline is the second speaker cue; together they carry the signal
## without needing a third (a backlight glow was tried and ripped — the
## painted forge lighting swallowed it at readable alphas, and louder
## alphas fought the scene).
transform portrait_active:
    ease 0.25 alpha 1.0

transform portrait_inactive:
    ease 0.25 alpha 0.7

screen agent_portrait(agent_id="hephaestus", state="neutral", slot="center"):
    ## Below the say screen (zorder 0) so the textbox covers the character's
    ## lower body — same layering as Hades dialogue.
    zorder -1

    ## All slots render at the original 760² size — matches the presence
    ## of the single-portrait scenes and is well within 1920×1080 (760+760
    ## = 1520, leaving 400px of breathing room in the middle). Position is
    ## the only thing that changes between slots.
    $ _size = (760, 760)
    $ _xalign = 1.0 if slot == "right" else 0.0
    $ _enter_t = {
        "left": portrait_enter_left,
        "right": portrait_enter_right,
        "center": portrait_enter,
    }[slot]
    $ _speaker_t = portrait_active if (
        current_speaker_id is None or current_speaker_id == agent_id
    ) else portrait_inactive

    add _portrait_image(agent_id, state):
        xalign _xalign
        yalign 1.0
        yoffset 160
        size _size
        at _enter_t, _speaker_t
