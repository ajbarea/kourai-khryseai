## screens.rpy — SPLIT INTO FOCUSED FILES
##
## All screen definitions have been moved to:
##
##   screens_dialogue.rpy      — base styles, say, input, choice, agent_portrait
##   screens_hud.rpy           — quick_menu, affinity_hud, gossip_bubble, thinking
##   screens_menu.rpy          — navigation, main_menu, game_menu, save/load, preferences, history, help
##   screens_utilities.rpy     — confirm, skip_indicator, notify, nvl, bubble, forge_input
##   screens_menu_mobile.rpy   — mobile/touch variant style overrides
##   screens_relationships.rpy — agent_choice, forge_journal, project_selection, confession system
##   screens_companion_spirits.rpy — cupid_jealousy, tier_up, puck_nudge, cupid_intro,
##                                   wellness_warning, virtue_milestone_toast,
##                                   puck_tutorial, cupid_vulnerability
##
## Ren'Py loads all .rpy files in game/ automatically — no imports needed.
