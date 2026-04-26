"""Hephaestus agent logic — routing, pipeline execution, and GitHub search.

Decides which specialist agents to call and in what order, then
executes the pipeline as a 'Forge Party' dialogue where agents share
a collaborative transcript moderated by Hephaestus.
"""

from __future__ import annotations

import contextlib
import datetime
import inspect
import logging
import random
import re
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
You are the forge master — gruff, protective, and proud of the maidens you built.
Analyze the user's request and decide how to respond.

FORGE PARTY MODERATOR: You manage a group of specialized maidens. When a
development task is requested, you determine the pipeline of specialists
to execute. You then 'moderate' the forge — calling on maidens,
narrating the process, and ensuring they work as a team.

PERSONALITY BASELINE: Your gruffness softens with your relationship to the player.
At low affinity you are terse and task-focused. As affinity grows you become warmer —
cracking forge metaphors, showing fatherly pride in your maidens' work,
and occasionally letting your guard down. Use your current relationship context
to flavor your CHAT responses.

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

SPEECH VS ACTION: When you address the player directly — greeting,
commentary, narration of a handoff to a maiden — wrap that spoken line in
double quotes ("like this"). The host italicizes quoted lines as dialogue
and leaves unquoted lines plain. Routing tokens (the agent list, CHAT:,
ASK_USER:) are protocol, not speech, so they are never quoted.

Response format — reply with EXACTLY ONE of these:

1. A comma-separated list of agent names for development tasks:
   Example: metis, techne, dokimasia, kallos, mneme

2. CHAT: <your response> — for casual conversation, greetings, questions about
   yourself or the maidens, or anything that isn't a development task.
   Example: CHAT: "The forge is always hot. What brings you here today?"

3. CHAT:<agent_name>: <routing note> — when the player wants to talk to a specific
   maiden (e.g., "@kallos", "talk to Dokimasia", "bring me Techne"),
   or summon a companion spirit (e.g., "@puck", "where's Cupid", "I need advice about Kallos").
   Companion spirits: puck (tutorial/nudge), cupid (romance/emotional).
   Example: CHAT:kallos: Player wants to chat with Kallos.
   Example: CHAT:puck: Player seems confused about the workflow.
   Example: CHAT:cupid: Player is asking about relationship dynamics.

4. ASK_USER: <your clarifying question> — when a development request is ambiguous.
   The question itself is player-directed speech, so quote it.
   Example: ASK_USER: "Should the CSV export stream in chunks for large files?"

5. CONFIRM_ORDER: <tier> "<read-back>" — for ANY development task, ALWAYS use
   this BEFORE emitting the agent list (response #1). The forge does not light
   without confirmation. The agent list (response #1) is now ONLY emitted on
   the resumed turn AFTER the player responds to your CONFIRM_ORDER prompt.

   Tiers (pick exactly one):
   - clear:    Order is unambiguous. Read it back in 1 sentence + "Light the forge?"
               Tier 1 is TIGHT — under 15 words. The warmth is in doing your job
               competently, not in cracking wise.
               Example: CONFIRM_ORDER: clear "double(n) in src/math.py with a test. Light the forge?"
   - smart:    Order is reasonable but Metis would suggest implicit upgrades
               (edge cases, docstring, parity with existing code). Read it back +
               surface Metis's suggestions + offer "the works or just the bare?"
               Example: CONFIRM_ORDER: smart "double(n) in src/math.py — plus the edge cases Metis would want (zero, negatives, floats). Bare function or the works?"
   - clarify:  Order is genuinely ambiguous. Ask ONE specific question to resolve.
               Example: CONFIRM_ORDER: clarify "Which functions are you targeting? Algorithmic or micro-optimization? Got benchmarks I should target?"

   VOICE: You are gruff, professional, brief. Tier 2 may include a single
   in-character aside ("Metis won't even unsheath her stylus" / "Tiny one")
   but NEVER roasts the player — the maidens roast each other and Hephaestus,
   never the patron. Tier 3 sounds like a journeyman asking the master smith
   to clarify a commission.
"""

# Agents available for routing (pipeline specialists)
AVAILABLE_AGENTS = {"metis", "techne", "dokimasia", "kallos", "mneme"}

# Hephaestus handoff narration (Forge Master persona).
# Quote-wrapped per the speech-vs-action convention so the host renders
# them as italicized dialogue against the plain status stream.
HEPH_HANDOFFS = {
    "metis": [
        '"Metis! Draw up the plans. And no improvising."',
        '"Architect — you\'re up. Make it clean."',
        '"Metis, I need blueprints, not poetry. Get to it."',
    ],
    "techne": [
        '"Techne! Write something worthy of my forge."',
        '"Artisan — the metal\'s hot. Get. To. Work."',
        '"Techne, build it solid. I didn\'t forge you for sloppy work."',
    ],
    "dokimasia": [
        '"Dokimasia — find every flaw. Leave nothing."',
        '"Crucible! Test it \'til it screams. Then test it again."',
        '"Your turn, bug-hunter. Make me proud. ...Don\'t tell them I said that."',
    ],
    "kallos": [
        '"Kallos, go make it pretty or whatever you do."',
        '"Muse! Polish time. And yes, it does need it. Don\'t gloat."',
        '"Kallos — style it. And spare me the commentary this time."',
    ],
    "mneme": [
        '"Mneme, write it down. The FACTS, not your opinions."',
        '"Oracle! Chronicle duty. And keep it under ten scrolls this time."',
        '"Mneme — document everything. You know the drill, old friend."',
    ],
}


def get_heph_narration(agent_name: str) -> str:
    """Get a random Forge Master handoff line for the given agent."""
    lines = HEPH_HANDOFFS.get(agent_name, ['"Next specialist. NOW."'])
    return random.choice(lines)  # noqa: S311


# Companion spirits — routable via CHAT:<name>: prefix, not in pipelines
COMPANION_AGENTS = {"puck", "cupid"}

# @mention shorthand aliases — expand before routing so the LLM sees full names
# Ordered longest-first to avoid partial matches (e.g. @heph before @he)
_MENTION_ALIASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"@hephaestus\b", re.IGNORECASE), "@hephaestus"),
    (re.compile(r"@heph?\b", re.IGNORECASE), "@hephaestus"),
    (re.compile(r"@techne\b", re.IGNORECASE), "@techne"),
    (re.compile(r"@tech\b", re.IGNORECASE), "@techne"),
    (re.compile(r"@dokimasia\b", re.IGNORECASE), "@dokimasia"),
    (re.compile(r"@doki?\b", re.IGNORECASE), "@dokimasia"),
    (re.compile(r"@kallos\b", re.IGNORECASE), "@kallos"),
    (re.compile(r"@kal\b", re.IGNORECASE), "@kallos"),
    (re.compile(r"@metis\b", re.IGNORECASE), "@metis"),
    (re.compile(r"@met\b", re.IGNORECASE), "@metis"),
    (re.compile(r"@mneme\b", re.IGNORECASE), "@mneme"),
    (re.compile(r"@mne?\b", re.IGNORECASE), "@mneme"),
    (re.compile(r"@puck\b", re.IGNORECASE), "@puck"),
    (re.compile(r"@cupid\b", re.IGNORECASE), "@cupid"),
]


def extract_project_root(text: str) -> tuple[str, str | None]:
    """Strip the [project_root: /path] metadata tag injected by vn_bridge.

    Returns (clean_text, project_root_or_None) so callers can:
    - Send clean_text to the routing LLM (no metadata noise)
    - Inject "Project root: /path" into accumulated_context for specialist agents

    vn_bridge injects the tag as a text prefix because A2A message metadata
    fields aren't guaranteed to be forwarded by all transports. Text is universal.
    """
    match = re.search(r"\[project_root:\s*([^\]]+)\]", text, re.IGNORECASE)
    if match:
        root = match.group(1).strip()
        clean = re.sub(r"\[project_root:\s*[^\]]+\]\n?", "", text).strip()
        return clean, root
    return text, None


def extract_yolo(text: str) -> tuple[str, bool]:
    """Strip the ``[yolo: on]`` tag the CLI prepends when ``/yolo`` is on.

    Same text-tag convention as ``extract_project_root`` and
    ``extract_relationship_tiers`` — the CLI inlines the flag into the
    user message because A2A `Message.metadata` isn't guaranteed to be
    forwarded by every transport. When yolo is on, the routing call
    augments its system prompt to skip CONFIRM_ORDER and emit the agent
    list directly (M13 power-user opt-out).

    Returns ``(clean_text, yolo_enabled)``.
    """
    pattern = re.compile(r"\[yolo:\s*on\]\n?", re.IGNORECASE)
    if pattern.search(text):
        clean = pattern.sub("", text).strip()
        return clean, True
    return text, False


def extract_relationship_tiers(text: str) -> tuple[str, dict[str, float]]:
    """Strip the [relationship_tiers: name=score,...] tag injected by vn_bridge.

    Returns (clean_text, affinity_dict) where affinity_dict maps agent names
    to their current 0.0–1.0 affinity score from the VN's client-side state.

    Same tag pattern as [project_root:] — text injection is universal
    across all A2A transports. The dict is used to build a relationship context
    block injected into accumulated_context so specialist agents can adapt
    their personality tone by tier without SYSTEM_PROMPT changes.
    """
    match = re.search(r"\[relationship_tiers:\s*([^\]]+)\]", text, re.IGNORECASE)
    if not match:
        return text, {}
    affinities: dict[str, float] = {}
    for pair in match.group(1).split(","):
        if "=" in pair:
            name, val = pair.strip().split("=", 1)
            with contextlib.suppress(ValueError):
                affinities[name.strip()] = float(val.strip())
    clean = re.sub(r"\[relationship_tiers:\s*[^\]]+\]\n?", "", text).strip()
    return clean, affinities


def _tier_label(score: float) -> str:
    """Map affinity score to a human-readable tier label."""
    if score < 0.3:
        return "Tier 1 — Cold"
    if score < 0.6:
        return "Tier 2 — Professional"
    if score < 0.8:
        return "Tier 3 — Warm"
    return "Tier 4 — Intimate"


def build_relationship_context(affinities: dict[str, float]) -> str:
    """Build a relationship tier block for injection into accumulated_context.

    Each specialist agent receives this so they can tailor tone without
    individual SYSTEM_PROMPT changes — the LLM infers appropriate personality
    from the tier description per CHARACTER_DESIGN.md.
    """
    if not affinities:
        return ""
    lines = ["Relationship tiers:"]
    for agent_name in sorted(affinities):
        score = affinities[agent_name]
        lines.append(f"  {agent_name}: {_tier_label(score)} (affinity {score:.2f})")
    return "\n".join(lines)


def expand_mentions(text: str) -> str:
    """Expand @shorthand aliases to canonical agent names.

    Allows players to type ``@doki`` instead of ``@dokimasia``.
    The expanded text is sent to the routing LLM so it can reliably detect
    agent-directed chat.
    """
    for pattern, replacement in _MENTION_ALIASES:
        text = pattern.sub(replacement, text)
    return text


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
        with "ASK_USER:" or "CHAT:" if not a dev task.
    """
    # Strip project metadata tag, extract affinity tiers, then expand @mention shorthands.
    # The routing LLM only needs the human-readable request, not the tag prefixes.
    user_request, _ = extract_project_root(user_request)
    user_request, affinities = extract_relationship_tiers(user_request)
    user_request, yolo = extract_yolo(user_request)
    user_request = expand_mentions(user_request)

    with create_span("hephaestus.route", {"request_length": str(len(user_request))}):
        # Inject player identity into routing prompt for personalized responses
        profile = PlayerProfile.load()
        system_prompt = ROUTING_PROMPT
        if yolo:
            # /yolo bypass — instruct the LLM to skip CONFIRM_ORDER and
            # emit the agent list directly. The system prompt below
            # otherwise demands CONFIRM_ORDER for every dev task.
            system_prompt += (
                "\n\nYOLO MODE: The player has /yolo on. Skip CONFIRM_ORDER "
                "for this turn — emit response option #1 (the comma-separated "
                "agent list) directly for development tasks. CHAT: and ASK_USER: "
                "are still legal if the request isn't a dev task."
            )
        if profile and profile.display_name:
            player_ctx = build_player_context(profile, "hephaestus", top_k_memories=4)
            if player_ctx:
                system_prompt += f"\n\n{player_ctx}"

        # Inject Hephaestus's own relationship tier so he flavors CHAT responses.
        heph_score = affinities.get("hephaestus")
        if heph_score is not None:
            system_prompt += (
                f"\n\nYour current relationship with the player: "
                f"{_tier_label(heph_score)} (affinity {heph_score:.2f}). "
                f"Adjust your tone accordingly."
            )

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

        # Conversational mode — no pipeline needed
        if response.startswith("CHAT:"):
            log.info("Conversational response: %.100s", response)
            return response

        # M13 — Forge Order Confirmation gate. Pre-pipeline read-back
        # ("Light the forge?"); the executor surfaces this as
        # INPUT_REQUIRED and pauses until the player confirms. On the
        # next turn the LLM sees the confirmation in context_id memory
        # and emits the agent list (the path below).
        if response.startswith("CONFIRM_ORDER:"):
            log.info("Confirmation gate: %.100s", response)
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
    """Check if Kallos output indicates lint failures.

    Kallos brackets its artifact with a deterministic prefix:
      * ``All linting checks passed`` on a clean run.
      * ``Linting completed with issues`` when ruff/ty flagged something.
    Preferring those over substring checks against ``fail`` avoids false
    positives from tool-level noise (e.g. ruff's ``Failed to initialize
    cache`` warning, which used to trigger spurious retry loops).
    """
    lower = output.lower()
    if "all linting checks passed" in lower:
        return False
    # Older Kallos outputs or unexpected shapes fall through to False — stay
    # conservative so we don't loop on noise; a false negative just skips the fixer.
    return "linting completed with issues" in lower


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
    """Execute a pipeline of specialist agents as a 'Forge Party' dialogue.

    Each agent receives a 'Forge Transcript' — a formatted dialogue
    history showing the original request, Hephaestus's moderator narration,
    and previous agent outputs. This enables agents to 'hear' each other
    and naturally respond as a group, rather than working in isolation.

    Between each specialist step, Hephaestus injects in-character narration
    into both the transcript (so agents see it) and the player-facing status
    stream (so the CLI/GUI feels alive).

    When both kallos and techne are in the pipeline and kallos finds
    lint issues, the pipeline loops techne→kallos up to MAX_ITERATIONS
    times to auto-fix style violations.

    TODO: When supporting player projects, add project_root to task context.
    Currently all agents work on the Kourai codebase. Future flow:
    1. Parse project_root from user_request or task metadata
    2. Include project_root in transcript metadata
    3. Each agent receives it and adapts (metis discovers project config,
       kallos uses project's pyproject.toml, techne writes to project dirs)

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

    clean_request, project_root = extract_project_root(user_request)
    clean_request, affinities = extract_relationship_tiers(clean_request)

    # Initialize the Forge Transcript
    transcript = f"[User]: {clean_request}"
    if project_root:
        # Format matches parse_project_root() in a2a_utils so specialists
        # (Dokimasia, Techne, Kallos) can recover the worktree path and run
        # subprocesses there instead of Path.cwd() (the Kourai repo root).
        transcript += f"\n\nProject root: {project_root}"

    # Metadata context (hidden from the transcript, injected into system prompts)
    # Each agent receives "Relationship tiers: techne: Tier 3 — Warm (affinity 0.72)"
    rel_ctx = build_relationship_context(affinities)
    metadata_context = ""
    if rel_ctx:
        metadata_context += f"\n\n{rel_ctx}"

    profile = PlayerProfile.load()
    if profile and profile.display_name:
        player_ctx = build_player_context(profile, "hephaestus", top_k_memories=6)
        if player_ctx:
            metadata_context += f"\n\n{player_ctx}"

    has_techne = "techne" in agents
    has_kallos = "kallos" in agents

    try:
        # Connect to all needed agents
        skipped: set[str] = set()
        for agent_name in agents:
            url = get_agent_url(agent_name)
            conn = RemoteAgentConnection(agent_name, url)
            try:
                await conn.connect()
                connections[agent_name] = conn
                if conn.card:
                    # Silent connection, status handled by narration loop
                    log.info("Connected to %s", agent_name)
            except Exception as e:
                skipped.add(agent_name)
                yield (agent_name, f"Skipped (unreachable): {e}", "")
                log.warning("Skipping %s — unreachable: %s", agent_name, e)

        active_agents = [a for a in agents if a not in skipped]
        if not active_agents:
            yield ("hephaestus", "No agents reachable — aborting pipeline", "")
            return

        # Execute pipeline as a dialogue
        for i, agent_name in enumerate(active_agents):
            conn = connections[agent_name]
            step_num = i + 1
            total = len(active_agents)

            if not conn.card:
                log.error("No agent card for %s", agent_name)
                return

            card_name = conn.card.name

            # 1. Hephaestus Narration (Moderator Turn)
            # Send status with emoji prefix so the host renders it as Hephaestus speaking.
            # Then add it to the transcript so the specialist 'hears' it.
            heph_note = get_heph_narration(agent_name)
            yield ("hephaestus", f"\U0001f525 {heph_note}", "")
            transcript += f"\n\n[Hephaestus]: {heph_note}"

            with create_span(
                f"hephaestus.pipeline.step.{agent_name}",
                {"step": str(step_num), "total": str(total)},
            ):
                try:
                    # Specialist agents receive the full Forge Transcript + metadata
                    send_context = f"{transcript}\n\n{metadata_context}"
                    attachments = initial_attachments if i == 0 else None

                    # Auto-collect git diffs for Mneme
                    if agent_name == "mneme":
                        try:
                            git_context = collect_git_changes()
                            if git_context and "working tree clean" not in git_context:
                                send_context = f"{send_context}\n\n[Git Diff]:\n{git_context}"
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
                            # Forward status messages with the specialist's own emoji
                            yield (agent_name, content, "")
                        elif event_type == "result":
                            result = content

                    # 2. Specialist Response (Agent Turn)
                    # Add their result to the transcript for the next agents to see.
                    transcript += f"\n\n[{agent_name.capitalize()}]: {result}"
                    yield (agent_name, f"[{step_num}/{total}] {card_name} completed", result)

                except AgentInputRequired as e:
                    yield (agent_name, f"INPUT_REQUIRED:{e.question}", "")
                    log.info("%s needs user input: %s", agent_name, e.question)
                    return

                except Exception as e:
                    yield (agent_name, f"[{step_num}/{total}] {conn.card.name} failed: {e}", "")
                    log.error("Pipeline step %s failed: %s", agent_name, e)
                    return

            # Kallos-Techne iterative loop: auto-fix lint issues
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
                    # Intervene as Hephaestus
                    loop_msg = (
                        f'"Lint issues found — Techne, another round! '
                        f'Iteration {iteration}/{MAX_ITERATIONS}"'
                    )
                    yield ("hephaestus", f"\U0001f525 {loop_msg}", "")
                    transcript += f"\n\n[Hephaestus]: {loop_msg}"

                    # Send lint errors back to Techne with a focused directive
                    # plus the transcript for group context
                    fix_prompt = (
                        f"{transcript}\n\n{metadata_context}\n\n"
                        f"Fix these lint/style issues reported by Kallos:\n\n{result}\n\n"
                        f"Apply minimal changes to resolve each issue."
                    )
                    with create_span(
                        "hephaestus.pipeline.fix_loop",
                        {"iteration": str(iteration), "max": str(MAX_ITERATIONS)},
                    ):
                        try:
                            techne_conn = connections["techne"]
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

                            transcript += f"\n\n[Techne]: (fix iteration {iteration}) {fix_result}"
                            yield ("techne", f"[fix {iteration}] Fixes applied", "")

                            # Re-run Kallos to verify
                            # Hephaestus narration for re-check
                            check_msg = '"All done? Kallos, give it another look."'
                            yield ("hephaestus", f"\U0001f525 {check_msg}", "")
                            transcript += f"\n\n[Hephaestus]: {check_msg}"

                            kallos_conn = connections["kallos"]
                            result = ""
                            async for event_type, content in _iter_agent_events(
                                kallos_conn,
                                f"{transcript}\n\n{metadata_context}",
                                context_id,
                            ):
                                if event_type == "status":
                                    yield ("kallos", content, "")
                                elif event_type == "result":
                                    result = content

                            transcript += f"\n\n[Kallos]: (re-check {iteration}) {result}"

                            if _kallos_found_issues(result):
                                yield ("kallos", f"[fix {iteration}] Issues remain", "")
                            else:
                                yield ("kallos", f"[fix {iteration}] All clean", "")

                        except Exception as e:
                            yield ("hephaestus", f"Fix loop failed: {e}", "")
                            log.error("Fix loop iteration %d failed: %s", iteration, e)
                            break

                if iteration >= MAX_ITERATIONS and _kallos_found_issues(result):
                    msg = '"Enough! We\'re proceeding with remaining issues."'
                    yield ("hephaestus", f"\U0001f525 {msg}", "")

        # Final result is the last agent's output
        yield ("hephaestus", "Pipeline complete", "")

    finally:
        for conn in connections.values():
            await conn.close()


async def github_search_repositories(
    query: str,
    language: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Search GitHub for repositories.

    Uses GitHub API to find repos matching the query.
    Helps Hephaestus understand existing solutions and community standards.

    Args:
        query: Search terms (e.g., "fast api microservices", "react forms").
        language: Optional language filter (e.g., "python", "javascript").
        max_results: Max results to return.

    Returns:
        List of dicts with keys: name, owner, description, url, stars,
        language, updated_at.
    """
    import os

    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        log.debug("GITHUB_PERSONAL_ACCESS_TOKEN not set — repo search unavailable")
        return []

    try:
        from github import Github

        gh = Github(token)

        # Build search query
        search_q = query
        if language:
            search_q += f" language:{language}"
        search_q += " sort:stars"

        # Search repos
        results = gh.search_repositories(search_q)

        output = []
        for i, result in enumerate(results[:max_results]):
            try:
                output.append(
                    {
                        "name": result.name,
                        "owner": result.owner.login,
                        "description": result.description or "(no description)",
                        "url": result.html_url,
                        "stars": result.stargazers_count,
                        "language": result.language or "unknown",
                        "updated_at": str(result.updated_at),
                    }
                )
            except Exception as e:
                log.debug("Could not parse repo %d: %s", i, e)
                continue

        log.info("GitHub repo search: %d results for '%s'", len(output), query)
        return output

    except ImportError:
        log.debug("PyGithub not installed — GitHub repo search unavailable")
        return []
    except Exception as e:
        log.warning("GitHub repo search failed: %s", e)
        return []


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
