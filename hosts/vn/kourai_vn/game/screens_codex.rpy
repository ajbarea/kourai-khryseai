## Ren'Py Screen Language
## screens_codex.rpy — Mass Effect-inspired Codex system
##
## Three-panel layout: Category sidebar | Entry list | Content viewer
## Forge aesthetic: Dark background, orange/gold accents, Hades-inspired styling

# ══════════════════════════════════════════════════════════════════════
# CODEX MAIN SCREEN
# ══════════════════════════════════════════════════════════════════════

screen codex():
    """Main Codex screen with three-panel layout."""
    
    tag menu
    
    # Initialize selected category and entry in store if not set
    default selected_category = "Characters"
    default selected_entry_id = None
    
    # Dark background with subtle overlay
    add Solid("#0A0806")
    
    # Forge ambient glow effect (optional particle layer)
    if renpy.loadable("ember_particles"):
        add "ember_particles" alpha 0.3
    
    # ──────────────────────────────────────────────────────────────────
    # HEADER
    # ──────────────────────────────────────────────────────────────────
    
    frame:
        xalign 0.5
        ypos 40
        xsize 1840
        ysize 100
        background Solid("#1A1410CC")
        
        hbox:
            xalign 0.5
            yalign 0.5
            spacing 20
            
            text "CODEX" style "codex_title"
            
            # Total NEW badge
            $ total_new = get_codex_new_count()
            if total_new > 0:
                text "[total_new] NEW" style "codex_new_badge"
    
    # ──────────────────────────────────────────────────────────────────
    # THREE-PANEL LAYOUT
    # ──────────────────────────────────────────────────────────────────
    
    hbox:
        xpos 40
        ypos 160
        spacing 20
        
        # ═════════════════════════════════════════════════════════════
        # LEFT PANEL: Category Selection
        # ═════════════════════════════════════════════════════════════
        
        frame:
            xsize 300
            ysize 860
            background Solid("#1A1410DD")
            
            viewport:
                draggable True
                mousewheel True
                scrollbars "vertical"
                yinitial 0.0
                
                vbox:
                    spacing 10
                    xfill True
                    
                    for category in CODEX_CATEGORIES:
                        $ cat_new_count = get_codex_new_count(category)
                        $ cat_unlocked = len(get_unlocked_entries(category))
                        
                        # Only show categories with at least one unlocked entry
                        if cat_unlocked > 0:
                            button:
                                xfill True
                                ysize 70
                                
                                background Frame(
                                    Solid("#2A2010" if selected_category == category else "#1A1410"),
                                    Borders(5, 5, 5, 5)
                                )
                                hover_background Frame(Solid("#3A2818"), Borders(5, 5, 5, 5))
                                
                                action SetScreenVariable("selected_category", category), SetScreenVariable("selected_entry_id", None)
                                
                                hbox:
                                    xalign 0.5
                                    yalign 0.5
                                    spacing 10
                                    
                                    text category:
                                        style "codex_category_text"
                                        color gui.accent_color if selected_category == category else gui.idle_color
                                    
                                    if cat_new_count > 0:
                                        text "[cat_new_count]":
                                            style "codex_category_new_count"
        
        # ═════════════════════════════════════════════════════════════
        # MIDDLE PANEL: Entry List
        # ═════════════════════════════════════════════════════════════
        
        frame:
            xsize 500
            ysize 860
            background Solid("#1A1410DD")
            
            viewport:
                draggable True
                mousewheel True
                scrollbars "vertical"
                yinitial 0.0
                
                vbox:
                    spacing 8
                    xfill True
                    
                    $ unlocked_entries = get_unlocked_entries(selected_category)
                    
                    if unlocked_entries:
                        for entry in unlocked_entries:
                            $ is_new = is_codex_entry_new(entry["id"])
                            $ is_selected = selected_entry_id == entry["id"]
                            
                            button:
                                xfill True
                                
                                background Frame(
                                    Solid("#2A2010" if is_selected else "#0A0806"),
                                    Borders(5, 5, 5, 5)
                                )
                                hover_background Frame(Solid("#3A2818"), Borders(5, 5, 5, 5))
                                
                                action [
                                    SetScreenVariable("selected_entry_id", entry["id"]),
                                    Function(mark_codex_entry_read, entry["id"])
                                ]
                                
                                hbox:
                                    xfill True
                                    yalign 0.5
                                    spacing 10
                                    xpos 15
                                    
                                    # NEW indicator
                                    if is_new:
                                        text "◆":
                                            size 20
                                            color "#F5C842"
                                    
                                    vbox:
                                        spacing 3
                                        
                                        text entry["title"]:
                                            style "codex_entry_title"
                                            color gui.accent_color if is_selected else gui.text_color
                                        
                                        if entry.get("subtitle"):
                                            text entry["subtitle"]:
                                                style "codex_entry_subtitle"
                    else:
                        text "No entries unlocked yet.\n\nExplore the Forge to discover more.":
                            style "codex_empty_text"
                            xalign 0.5
                            yalign 0.5
        
        # ═════════════════════════════════════════════════════════════
        # RIGHT PANEL: Entry Content Viewer
        # ═════════════════════════════════════════════════════════════
        
        frame:
            xsize 980
            ysize 860
            background Solid("#1A1410DD")
            
            if selected_entry_id:
                # Find the selected entry
                $ entry_data = None
                $ for entry in get_unlocked_entries(selected_category):
                    if entry["id"] == selected_entry_id:
                        entry_data = entry
                        break
                
                if entry_data:
                    viewport:
                        draggable True
                        mousewheel True
                        scrollbars "vertical"
                        yinitial 0.0
                        
                        vbox:
                            spacing 20
                            xsize 920
                            xpos 30
                            ypos 30
                            
                            # Entry header
                            vbox:
                                spacing 8
                                
                                text entry_data["title"]:
                                    style "codex_content_title"
                                
                                if entry_data.get("subtitle"):
                                    text entry_data["subtitle"]:
                                        style "codex_content_subtitle"
                                
                                # Divider line
                                null height 10
                                frame:
                                    xsize 900
                                    ysize 2
                                    background Solid(gui.accent_color)
                                null height 10
                            
                            # Entry content
                            text entry_data["content"]:
                                style "codex_content_text"
                                xsize 900
            else:
                # Placeholder when no entry selected
                vbox:
                    xalign 0.5
                    yalign 0.5
                    spacing 20
                    
                    text "◊  SELECT AN ENTRY  ◊":
                        style "codex_placeholder"
                        xalign 0.5
                    
                    text "Choose a codex entry from the list\nto read its contents.":
                        style "codex_placeholder_sub"
                        xalign 0.5
    
    # ──────────────────────────────────────────────────────────────────
    # FOOTER: Navigation hints
    # ──────────────────────────────────────────────────────────────────
    
    frame:
        xalign 0.5
        ypos 1000
        xsize 1840
        ysize 60
        background Solid("#1A1410CC")
        
        hbox:
            xalign 0.5
            yalign 0.5
            spacing 40
            
            text "[ESC] Close":
                style "codex_hint"
            
            text "[C] Toggle Codex":
                style "codex_hint"
            
            text "[Mouse Wheel] Scroll":
                style "codex_hint"
    
    # Close button
    textbutton "X":
        style "codex_close_button"
        xalign 0.98
        yalign 0.04
        action Return()


# ══════════════════════════════════════════════════════════════════════
# CODEX NOTIFICATION OVERLAY
# ══════════════════════════════════════════════════════════════════════

screen codex_notification():
    """Toast notification for newly unlocked Codex entries."""
    
    zorder 200
    
    # Check for pending notifications
    $ notification = pop_codex_notification()
    
    if notification:
        # Play notification sound (if file exists)
        $ codex_sfx_path = "audio/sfx/codex_unlock.ogg"
        if renpy.loadable(codex_sfx_path):
            on "show" action Play("sound", codex_sfx_path)
        
        frame:
            xalign 0.5
            ypos 150
            xsize 600
            background Solid("#1A1410EE")
            
            at codex_notification_anim
            
            vbox:
                spacing 10
                xalign 0.5
                yalign 0.5
                xsize 560
                
                text "◆  NEW CODEX ENTRY  ◆":
                    style "codex_notification_header"
                    xalign 0.5
                
                text notification["title"]:
                    style "codex_notification_title"
                    xalign 0.5
                
                if notification.get("subtitle"):
                    text notification["subtitle"]:
                        style "codex_notification_subtitle"
                        xalign 0.5
                
                text "Category: [notification[category]]":
                    style "codex_notification_category"
                    xalign 0.5
        
        # Auto-dismiss after 4 seconds
        timer 4.0 action Hide("codex_notification")


# ══════════════════════════════════════════════════════════════════════
# ANIMATIONS & TRANSFORMS
# ══════════════════════════════════════════════════════════════════════

transform codex_notification_anim:
    # Fade in from top
    alpha 0.0
    yoffset -50
    easein 0.4 alpha 1.0 yoffset 0
    
    # Hold
    pause 3.2
    
    # Fade out
    easeout 0.4 alpha 0.0 yoffset -30


# ══════════════════════════════════════════════════════════════════════
# STYLES
# ══════════════════════════════════════════════════════════════════════

style codex_title:
    font gui.interface_text_font
    size 60
    color gui.accent_color
    bold True

style codex_new_badge:
    font gui.interface_text_font
    size 24
    color "#F5C842"
    background Solid("#3A2010")
    padding (10, 5)
    bold True

style codex_category_text:
    font gui.interface_text_font
    size 24
    bold False

style codex_category_new_count:
    font gui.interface_text_font
    size 18
    color "#F5C842"
    background Solid("#2A1808")
    padding (6, 3)
    bold True

style codex_entry_title:
    font gui.interface_text_font
    size 26
    bold False

style codex_entry_subtitle:
    font gui.interface_text_font
    size 18
    color gui.idle_color
    italic True

style codex_content_title:
    font gui.interface_text_font
    size 42
    color gui.accent_color
    bold True

style codex_content_subtitle:
    font gui.interface_text_font
    size 26
    color gui.hover_color
    italic True

style codex_content_text:
    font gui.text_font
    size 24
    color gui.text_color
    line_spacing 8
    justify True

style codex_empty_text:
    font gui.text_font
    size 22
    color gui.idle_color
    italic True
    text_align 0.5

style codex_placeholder:
    font gui.interface_text_font
    size 36
    color gui.idle_color
    bold True

style codex_placeholder_sub:
    font gui.text_font
    size 22
    color gui.idle_small_color
    text_align 0.5

style codex_hint:
    font gui.interface_text_font
    size 20
    color gui.idle_color

style codex_close_button:
    background Solid("#3A2010")
    hover_background Solid("#5A3818")
    padding (20, 10)

style codex_close_button_text:
    font gui.interface_text_font
    size 36
    color gui.accent_color
    hover_color gui.hover_color
    bold True

style codex_notification_header:
    font gui.interface_text_font
    size 20
    color "#F5C842"
    bold True

style codex_notification_title:
    font gui.interface_text_font
    size 32
    color gui.accent_color
    bold True

style codex_notification_subtitle:
    font gui.interface_text_font
    size 22
    color gui.hover_color
    italic True

style codex_notification_category:
    font gui.interface_text_font
    size 18
    color gui.idle_color


# ══════════════════════════════════════════════════════════════════════
# HOTKEY BINDING
# ══════════════════════════════════════════════════════════════════════

# Bind 'C' key to toggle Codex (added to keymap in script_data.rpy or options.rpy)
