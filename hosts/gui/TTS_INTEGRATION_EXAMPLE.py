"""Example integration of TTS into the main GUI loop.

This shows the minimal changes needed to add TTS to __main__.py.
Copy the relevant sections into your main() function.
"""

import asyncio
import queue

import pygame
from dialogue_pacing import PacingMode
from maidens import detect_agent
from tts_gui_integration import TTSGUIManager

# ============================================================================
# STEP 1: Add these imports to __main__.py
# ============================================================================
# from tts_gui_integration import TTSGUIManager
# from dialogue_pacing import PacingMode


# ============================================================================
# STEP 2: Initialize TTS manager in main()
# ============================================================================
def initialize_tts_manager(recv_q: queue.Queue) -> TTSGUIManager:
    """Create and configure the TTS manager.

    Add this to your main() function after creating recv_q.
    """
    tts_manager = TTSGUIManager(
        recv_q=recv_q,
        enable_tts=True,  # Set to False to disable TTS
        pacing_mode=PacingMode.NORMAL,  # INSTANT, FAST, NORMAL, SLOW, CUSTOM
    )
    return tts_manager


# ============================================================================
# STEP 3: Process events with TTS in the main loop
# ============================================================================
async def process_event_with_tts(
    event: dict,
    tts_manager: TTSGUIManager,
    dialogue_history,  # Your DialogueHistory instance
) -> None:
    """Process a received event with TTS and pacing.

    Replace your existing event processing with this.
    """
    event_type = event.get("type")

    if event_type == "connected":
        # Agent connected
        name = event.get("name", "Unknown")
        url = event.get("url", "")
        print(f"Connected to {name} at {url}")

    elif event_type == "status":
        # Agent is thinking/processing
        text = event.get("text", "")
        if text:
            # Detect which agent is speaking
            agent_name, _ = detect_agent(text)
            if agent_name:
                tts_manager.set_current_agent(agent_name)

            # Add to dialogue history
            dialogue_history.update_last_text(text)

            # Process with TTS and pacing
            await tts_manager.process_dialogue_event(event)

    elif event_type == "result":
        # Final response from agent
        text = event.get("text", "")
        if text:
            # Detect which agent is speaking
            agent_name, _ = detect_agent(text)
            if agent_name:
                tts_manager.set_current_agent(agent_name)

            # Add to dialogue history
            dialogue_history.update_last_text(text)

            # Process with TTS and pacing
            await tts_manager.process_dialogue_event(event)

    elif event_type == "complete":
        # Response complete
        elapsed = event.get("elapsed", 0.0)
        print(f"Response complete in {elapsed:.2f}s")

    elif event_type == "error":
        # Error occurred
        text = event.get("text", "Unknown error")
        print(f"Error: {text}")

    elif event_type == "disconnected":
        # Agent disconnected
        print("Disconnected from agent")


# ============================================================================
# STEP 4: Main loop integration
# ============================================================================
def main_loop_example(
    recv_q: queue.Queue,
    send_q: queue.Queue,
    dialogue_history,
    tts_manager: TTSGUIManager,
) -> None:
    """Example main loop with TTS integration.

    This shows how to integrate TTS into your existing event loop.
    """
    running = True
    clock = pygame.time.Clock()

    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Process received messages with TTS
        try:
            event = recv_q.get(timeout=0.05)

            # Run async TTS processing
            asyncio.run(process_event_with_tts(event, tts_manager, dialogue_history))

            # ... existing GUI rendering code ...

        except queue.Empty:
            pass

        # Render GUI
        # ... your existing rendering code ...

        pygame.display.flip()
        clock.tick(60)  # 60 FPS


# ============================================================================
# STEP 5: Settings integration
# ============================================================================
def handle_tts_settings_change(
    tts_manager: TTSGUIManager,
    setting_name: str,
    value,
) -> None:
    """Handle TTS settings changes from UI.

    Call this when user changes TTS settings.
    """
    if setting_name == "tts_enabled":
        tts_manager.set_tts_enabled(value)

    elif setting_name == "pacing_mode":
        # value should be a PacingMode enum
        tts_manager.set_pacing_mode(value)

    elif setting_name == "thinking_pause_enabled":
        tts_manager.pacer.set_thinking_pause(value)

    elif setting_name == "thinking_pause_duration":
        tts_manager.pacer.set_thinking_pause(
            tts_manager.pacer.config.enable_thinking_pause,
            value,
        )

    elif setting_name == "reading_speed":
        # value is characters per second
        tts_manager.pacer.config.min_chars_per_second = value


# ============================================================================
# STEP 6: Cleanup on exit
# ============================================================================
def cleanup_tts(tts_manager: TTSGUIManager) -> None:
    """Clean up TTS resources on exit.

    Call this in your main() function's finally block.
    """
    tts_manager.cleanup()


# ============================================================================
# COMPLETE EXAMPLE: Minimal main() modification
# ============================================================================
def main_with_tts_example(agent_url: str | None = None) -> None:
    """Complete example showing TTS integration in main().

    This is a template showing all the pieces together.
    """
    import sys

    # ... existing initialization code ...

    recv_q: queue.Queue[dict] = queue.Queue()
    queue.Queue()

    # NEW: Initialize TTS manager
    tts_manager = initialize_tts_manager(recv_q)

    # ... existing code to start client thread ...

    try:
        # Main loop
        running = True
        clock = pygame.time.Clock()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # NEW: Process events with TTS
            try:
                event = recv_q.get(timeout=0.05)
                # asyncio.run(process_event_with_tts(event, tts_manager, dialogue_history))
                # ... existing GUI code ...

            except queue.Empty:
                pass

            pygame.display.flip()
            clock.tick(60)

    finally:
        # NEW: Cleanup TTS
        cleanup_tts(tts_manager)
        pygame.quit()
        sys.exit()


# ============================================================================
# QUICK REFERENCE: Settings UI Options
# ============================================================================
"""
Add these to your settings_ui.py:

1. TTS Enable Toggle
   - Label: "Enable Text-to-Speech"
   - Type: Checkbox
   - Default: True
   - Callback: handle_tts_settings_change(tts_manager, "tts_enabled", value)

2. Pacing Mode Dropdown
   - Label: "Dialogue Pacing"
   - Options: ["INSTANT", "FAST", "NORMAL", "SLOW", "CUSTOM"]
   - Default: "NORMAL"
   - Callback: handle_tts_settings_change(tts_manager, "pacing_mode", PacingMode[value])

3. Thinking Pause Toggle
   - Label: "Show Thinking Pause"
   - Type: Checkbox
   - Default: True
   - Callback: handle_tts_settings_change(tts_manager, "thinking_pause_enabled", value)

4. Thinking Pause Duration Slider
   - Label: "Thinking Pause Duration (s)"
   - Range: 0.0 to 3.0
   - Default: 0.5
   - Callback: handle_tts_settings_change(tts_manager, "thinking_pause_duration", value)

5. Reading Speed Slider
   - Label: "Reading Speed (chars/sec)"
   - Range: 20 to 100
   - Default: 50
   - Callback: handle_tts_settings_change(tts_manager, "reading_speed", value)
"""
