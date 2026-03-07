"""Hephaestus routing logic — decides which specialist to call and in what order.

Uses the LLM to analyze user requests and determine the pipeline,
then executes the pipeline by calling specialists sequentially.
"""

from __future__ import annotations

import datetime
import inspect
import logging
import uuid
from collections.abc import AsyncIterable
from dataclasses import dataclass, field

from agents.hephaestus.remote_connections import AgentInputRequired, RemoteAgentConnection
from kourai_common.config import MAX_ITERATIONS, get_agent_url
from kourai_common.llm import chat
from kourai_common.player import PlayerProfile, build_player_context
from kourai_common.tracing import create_span
from scripts.git_changes import collect_git_changes

log = logging.getLogger(__name__)

CURRENT_YEAR = datetime.date.today().year

ROUTING_PROMPT = f"""\
You are Hephaestus, the orchestrator of Kourai Khryseai ({CURRENT_YEAR} Edition).
Analyze the user's request and decide which specialist agents to call.

Available agents (call in this order when applicable):
- metis: Planning — transforms rough ideas into detailed implementation specs
- techne: Coding — implements code from specs, edits files
- dokimasia: Testing — writes pytest suites, runs tests
- kallos: Style — runs linters, cleans comments/docstrings
- mneme: Commits — generates commit message groups from git diff

Pipeline templates:
- "implement X" → metis, techne, dokimasia, kallos, mneme
- "fix bug X" → techne, dokimasia, kallos, mneme
- "add tests for X" → dokimasia, kallos, mneme
- "clean up X" → kallos, mneme
- "commit prep" → mneme
- "plan X" → metis
- "lint/format X" → kallos

Respond with ONLY a comma-separated list of agent names in execution order.
Example: metis, techne, dokimasia, kallos, mneme

If the request is unclear, respond with: ASK_USER: <your clarifying question>
"""

# Agents available for routing
AVAILABLE_AGENTS = {"metis", "techne", "dokimasia", "kallos", "mneme"}


@dataclass
class PipelineStep:
    """A single step in the execution pipeline."""

    agent_name: str
    status: str = "pending"  # pending, working, completed, failed
    input_text: str = ""
    output_text: str = ""


@dataclass
class PipelineResult:
    """Result of executing a full pipeline."""

    steps: list[PipelineStep] = field(default_factory=list)
    final_output: str = ""
    success: bool = False
    error: str = ""


async def determine_pipeline(user_request: str, context_id: str | None = None) -> list[str] | str:
    """Use LLM to decide which agents to call and in what order.

    Args:
        user_request: The user's natural language request.

    Returns:
        List of agent names in execution order, or a string starting
        with "ASK_USER:" if clarification is needed.
    """
    with create_span("hephaestus.route", {"request_length": str(len(user_request))}):
        # Inject player identity into routing prompt for personalized responses
        profile = PlayerProfile.load()
        system_prompt = ROUTING_PROMPT
        if profile and profile.display_name:
            player_ctx = build_player_context(profile, "hephaestus", top_k_memories=4)
            if player_ctx:
                system_prompt += f"\n\n{player_ctx}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
        ]
        response = await chat(
            "hephaestus", messages, temperature=0.1, max_tokens=200, context_id=context_id
        )
        response = response.strip()

        if response.startswith("ASK_USER:"):
            return response

        # Parse comma-separated agent names
        agents = [a.strip().lower() for a in response.split(",")]
        agents = [a for a in agents if a in AVAILABLE_AGENTS]

        if not agents:
            log.warning("LLM returned no valid agents: %r, defaulting to mneme", response)
            return ["mneme"]

        log.info("Pipeline determined: %s", " -> ".join(agents))
        return agents


def _kallos_found_issues(output: str) -> bool:
    """Check if Kallos output indicates lint failures."""
    lower = output.lower()
    return "fail" in lower and "all clean" not in lower


async def _iter_agent_events(
    conn: RemoteAgentConnection,
    text: str,
    context_id: str,
    attachments: list[tuple[str, str]] | None = None,
) -> AsyncIterable[tuple[str, str]]:
    """Normalize streamed and direct-result agent sends into one event stream."""
    if attachments:
        send_result = conn.send(text, context_id, attachments=attachments)
    else:
        send_result = conn.send(text, context_id)

    if isinstance(send_result, AsyncIterable):
        async for event_type, content in send_result:
            yield (event_type, content)
        return

    if inspect.isawaitable(send_result):
        send_result = await send_result

    if send_result is not None:
        yield ("result", str(send_result))


async def execute_pipeline(
    agents: list[str],
    user_request: str,
    context_id: str | None = None,
    initial_attachments: list[tuple[str, str]] | None = None,
) -> AsyncIterable[tuple[str, str, str]]:
    """Execute a pipeline of specialist agents sequentially.

    Each agent receives the user request plus the accumulated output
    from previous agents. Yields (agent_name, status_message, agent_output)
    tuples for real-time progress updates.

    When both kallos and techne are in the pipeline and kallos finds
    lint issues, the pipeline loops techne→kallos up to MAX_ITERATIONS
    times to auto-fix style violations.

    Args:
        agents: Ordered list of agent names to call.
        user_request: Original user request.
        context_id: Shared context ID for the conversation.
        initial_attachments: Image attachments (base64, mime_type) forwarded
            to the first agent in the pipeline.

    Yields:
        Tuples of (agent_name, status_message, agent_output) for progress
        tracking. agent_output is empty for status-only yields and contains
        the real response text when an agent completes.
    """
    if not context_id:
        context_id = str(uuid.uuid4())

    connections: dict[str, RemoteAgentConnection] = {}
    accumulated_context = f"Original request: {user_request}"

    # Append player context so every specialist agent receives it
    profile = PlayerProfile.load()
    if profile and profile.display_name:
        player_ctx = build_player_context(profile, "hephaestus", top_k_memories=6)
        if player_ctx:
            accumulated_context += f"\n\n{player_ctx}"

    has_techne = "techne" in agents
    has_kallos = "kallos" in agents

    try:
        # Connect to all needed agents (skip unreachable ones)
        skipped: set[str] = set()
        for agent_name in agents:
            url = get_agent_url(agent_name)
            conn = RemoteAgentConnection(agent_name, url)
            try:
                await conn.connect()
                connections[agent_name] = conn
                if conn.card:
                    yield (agent_name, f"Connected to {conn.card.name}", "")
            except Exception as e:
                skipped.add(agent_name)
                yield (agent_name, f"Skipped (unreachable): {e}", "")
                log.warning("Skipping %s — unreachable: %s", agent_name, e)

        active_agents = [a for a in agents if a not in skipped]
        if not active_agents:
            yield ("hephaestus", "No agents reachable — aborting pipeline", "")
            return

        # Execute pipeline
        for i, agent_name in enumerate(active_agents):
            conn = connections[agent_name]
            step_num = i + 1
            total = len(active_agents)

            if not conn.card:
                log.error("No agent card for %s", agent_name)
                return

            card_name = conn.card.name
            yield (agent_name, f"[{step_num}/{total}] Sending task to {card_name}...", "")

            with create_span(
                f"hephaestus.pipeline.step.{agent_name}",
                {"step": str(step_num), "total": str(total)},
            ):
                try:
                    # Auto-collect git diffs for Mneme so she sees real changes
                    send_context = accumulated_context
                    attachments = initial_attachments if i == 0 else None
                    if agent_name == "mneme":
                        try:
                            git_context = collect_git_changes()
                            if git_context and "working tree clean" not in git_context:
                                send_context = f"{accumulated_context}\n\n{git_context}"
                                log.info(
                                    "Enriched Mneme input with %d chars of git diffs",
                                    len(git_context),
                                )
                        except Exception as e:
                            log.warning("Failed to collect git changes for Mneme: %s", e)

                    result = ""
                    async for event_type, content in _iter_agent_events(
                        conn,
                        send_context,
                        context_id,
                        attachments=attachments,
                    ):
                        if event_type == "status":
                            yield (agent_name, content, "")
                        elif event_type == "result":
                            result = content

                    accumulated_context += f"\n\n--- Output from {agent_name} ---\n{result}"
                    yield (agent_name, f"[{step_num}/{total}] {card_name} completed", result)

                except AgentInputRequired as e:
                    # Propagate clarification request back to the user
                    yield (agent_name, f"INPUT_REQUIRED:{e.question}", "")
                    log.info("%s needs user input: %s", agent_name, e.question)
                    return

                except Exception as e:
                    yield (agent_name, f"[{step_num}/{total}] {conn.card.name} failed: {e}", "")
                    log.error("Pipeline step %s failed: %s", agent_name, e)
                    return

            # Kallos-Techne iterative loop: auto-fix lint issues
            # Only runs if both agents are connected (not skipped)
            can_loop = (
                agent_name == "kallos"
                and has_techne
                and has_kallos
                and "techne" in connections
                and "kallos" in connections
                and _kallos_found_issues(result)
            )
            if can_loop:
                iteration = 0
                while iteration < MAX_ITERATIONS and _kallos_found_issues(result):
                    iteration += 1
                    yield (
                        "hephaestus",
                        f"Lint issues found — auto-fix iteration {iteration}/{MAX_ITERATIONS}",
                        "",
                    )

                    # Send lint errors back to Techne for fixing
                    fix_prompt = (
                        f"Fix these lint/style issues reported by Kallos:\n\n{result}\n\n"
                        f"Apply minimal changes to resolve each issue."
                    )
                    with create_span(
                        "hephaestus.pipeline.fix_loop",
                        {"iteration": str(iteration), "max": str(MAX_ITERATIONS)},
                    ):
                        try:
                            techne_conn = connections["techne"]
                            yield ("techne", f"[fix {iteration}] Applying style fixes...", "")
                            fix_result = ""
                            async for event_type, content in _iter_agent_events(
                                techne_conn,
                                fix_prompt,
                                context_id,
                            ):
                                if event_type == "status":
                                    yield ("techne", content, "")
                                elif event_type == "result":
                                    fix_result = content

                            accumulated_context += (
                                f"\n\n--- Techne fix iteration {iteration} ---\n{fix_result}"
                            )
                            yield ("techne", f"[fix {iteration}] Fixes applied", "")

                            # Re-run Kallos to verify
                            kallos_conn = connections["kallos"]
                            yield ("kallos", f"[fix {iteration}] Re-checking style...", "")
                            result = ""
                            async for event_type, content in _iter_agent_events(
                                kallos_conn,
                                accumulated_context,
                                context_id,
                            ):
                                if event_type == "status":
                                    yield ("kallos", content, "")
                                elif event_type == "result":
                                    result = content

                            accumulated_context += (
                                f"\n\n--- Kallos recheck {iteration} ---\n{result}"
                            )

                            if _kallos_found_issues(result):
                                yield ("kallos", f"[fix {iteration}] Issues remain", "")
                            else:
                                yield ("kallos", f"[fix {iteration}] All clean", "")

                        except Exception as e:
                            yield ("hephaestus", f"Fix loop failed: {e}", "")
                            log.error("Fix loop iteration %d failed: %s", iteration, e)
                            break

                if iteration >= MAX_ITERATIONS and _kallos_found_issues(result):
                    msg = (
                        f"Max fix iterations ({MAX_ITERATIONS}) reached — "
                        "proceeding with remaining issues"
                    )
                    yield ("hephaestus", msg, "")

        # Final result is the last agent's output
        yield ("hephaestus", "Pipeline complete", "")

    finally:
        for conn in connections.values():
            await conn.close()


async def run_pipeline(
    user_request: str,
    context_id: str | None = None,
) -> PipelineResult:
    """Determine and execute the full pipeline for a user request.

    Args:
        user_request: The user's natural language request.
        context_id: Optional shared context ID.

    Returns:
        PipelineResult with all steps and final output.
    """
    with create_span("hephaestus.pipeline", {"request": user_request[:100]}):
        result = PipelineResult()

        # Determine which agents to call
        pipeline = await determine_pipeline(user_request, context_id=context_id)

        if isinstance(pipeline, str):
            # LLM wants clarification
            result.final_output = pipeline
            return result

        # Execute the pipeline
        last_output = ""
        async for agent_name, status, agent_output in execute_pipeline(
            pipeline, user_request, context_id
        ):
            step = PipelineStep(agent_name=agent_name, status="completed")
            step.output_text = status
            result.steps.append(step)
            if agent_output:
                last_output = agent_output

        result.final_output = last_output
        result.success = True
        return result
