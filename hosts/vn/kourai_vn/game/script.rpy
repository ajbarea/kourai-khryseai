## script.rpy — SPLIT INTO FOCUSED FILES
##
## All script content has been moved to:
##
##   script_data.rpy       — init python hide (sys.path), init python (Characters,
##                            constants, helpers, PUCK_NUDGES, GOSSIP_LINES),
##                            default store variables
##   script_start.rpy      — label start (bridge init, onboarding, persistent flags,
##                            wellness_warning, puck_tutorial)
##   script_main_loop.rpy  — label main_loop (input → bridge → beat rendering →
##                            affinity, gossip, spirits, virtue toasts)
##   script_labels.rpy     — label after_load, label project_input_label,
##                            label create_project_label, label portrait_debug,
##                            label quit
##
## Ren'Py loads all .rpy files in game/ automatically — no imports needed.
