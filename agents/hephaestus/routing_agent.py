"""Hephaestus routing logic — decides which specialist to call and in what order.

Uses the LLM to analyze user requests and determine the pipeline,
then executes the pipeline by calling specialists sequentially.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterable
from dataclasses import dataclass, field

from kourai_common.config import MAX_ITERATIONS, get_agent_url
from kourai_common.llm import chat
from kourai_common.tracing import create_span

from agents.hephaestus.remote_connections import AgentInputRequired, RemoteAgentConnection

log = logging.getLogger(__name__)

ROUTING_PROMPT = """\
You are Hephaestus, the orchestrator of Kourai Khryseai.
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


async def determine_pipeline(user_request: str) -> list[str] | str:
    """Use LLM to decide which agents to call and in what order.

    Args:
        user_request: The user's natural language request.

    Returns:
        List of agent names in execution order, or a string starting
        with "ASK_USER:" if clarification is needed.
    """
    with create_span("hephaestus.route", {"request_length": str(len(user_request))}):
        messages = [
            {"role": "system", "content": ROUTING_PROMPT},
            {"role": "user", "content": user_request},
        ]
        response = await chat("hephaestus", messages, temperature=0.1, max_tokens=200)
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


async def execute_pipeline(
    agents: list[str],
    user_request: str,
    context_id: str | None = None,
) -> AsyncIterable[tuple[str, str]]:
    """Execute a pipeline of specialist agents sequentially.

    Each agent receives the user request plus the accumulated output
    from previous agents. Yields (agent_name, status_message) tuples
    for real-time progress updates.

    When both kallos and techne are in the pipeline and kallos finds
    lint issues, the pipeline loops techne→kallos up to MAX_ITERATIONS
    times to auto-fix style violations.

    Args:
        agents: Ordered list of agent names to call.
        user_request: Original user request.
        context_id: Shared context ID for the conversation.

    Yields:
        Tuples of (agent_name, status_message) for progress tracking.
    """
    if not context_id:
        context_id = str(uuid.uuid4())

    connections: dict[str, RemoteAgentConnection] = {}
    accumulated_context = f"Original request: {user_request}"
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
                yield (agent_name, f"Connected to {conn.card.name}")
            except Exception as e:
                skipped.add(agent_name)
                yield (agent_name, f"Skipped (unreachable): {e}")
                log.warning("Skipping %s — unreachable: %s", agent_name, e)

        active_agents = [a for a in agents if a not in skipped]
        if not active_agents:
            yield ("hephaestus", "No agents reachable — aborting pipeline")
            return

        # Execute pipeline
        for i, agent_name in enumerate(active_agents):
            conn = connections[agent_name]
            step_num = i + 1
            total = len(active_agents)

            yield (agent_name, f"[{step_num}/{total}] Sending task to {conn.card.name}...")

            with create_span(
                f"hephaestus.pipeline.step.{agent_name}",
                {"step": str(step_num), "total": str(total)},
            ):
                try:
                    result = await conn.send(accumulated_context, context_id)
                    accumulated_context += f"\n\n--- Output from {agent_name} ---\n{result}"
                    yield (agent_name, f"[{step_num}/{total}] {conn.card.name} completed")

                except AgentInputRequired as e:
                    # Propagate clarification request back to the user
                    yield (agent_name, f"INPUT_REQUIRED:{e.question}")
                    log.info("%s needs user input: %s", agent_name, e.question)
                    return

                except Exception as e:
                    yield (agent_name, f"[{step_num}/{total}] {conn.card.name} failed: {e}")
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
                            yield ("techne", f"[fix {iteration}] Applying style fixes...")
                            fix_result = await techne_conn.send(fix_prompt, context_id)
                            accumulated_context += (
                                f"\n\n--- Techne fix iteration {iteration} ---\n{fix_result}"
                            )
                            yield ("techne", f"[fix {iteration}] Fixes applied")

                            # Re-run Kallos to verify
                            kallos_conn = connections["kallos"]
                            yield ("kallos", f"[fix {iteration}] Re-checking style...")
                            result = await kallos_conn.send(accumulated_context, context_id)
                            accumulated_context += (
                                f"\n\n--- Kallos recheck {iteration} ---\n{result}"
                            )

                            if _kallos_found_issues(result):
                                yield ("kallos", f"[fix {iteration}] Issues remain")
                            else:
                                yield ("kallos", f"[fix {iteration}] All clean")

                        except Exception as e:
                            yield ("hephaestus", f"Fix loop failed: {e}")
                            log.error("Fix loop iteration %d failed: %s", iteration, e)
                            break

                if iteration >= MAX_ITERATIONS and _kallos_found_issues(result):
                    yield (
                        "hephaestus",
                        f"Max fix iterations ({MAX_ITERATIONS}) reached — proceeding with remaining issues",
                    )

        # Final result is the last agent's output
        yield ("hephaestus", "Pipeline complete")

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
        pipeline = await determine_pipeline(user_request)

        if isinstance(pipeline, str):
            # LLM wants clarification
            result.final_output = pipeline
            return result

        # Execute the pipeline
        last_output = ""
        async for agent_name, status in execute_pipeline(pipeline, user_request, context_id):
            step = PipelineStep(agent_name=agent_name, status="completed")
            step.output_text = status
            result.steps.append(step)
            last_output = status

        result.final_output = last_output
        result.success = True
        return result
