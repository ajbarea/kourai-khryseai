# The Agents

<div class="grid cards" markdown>

-   :material-fire:{ .lg .middle } __Hephaestus — Orchestrator__

    ---

    Receives your request, decides which specialists to invoke. Manages pipelines, relays progress in real-time via SSE.

    `Port 10000`

-   :material-compass-rose:{ .lg .middle } __Metis — Planner__

    ---

    Transforms rough ideas into detailed implementation specs with file lists, acceptance criteria, and edge cases.

    `Port 10001`

-   :material-cog:{ .lg .middle } __Techne — Coder__

    ---

    Implements code from specs. Reads existing patterns first. Prefers editing over creating, removing over adding.

    `Port 10002`

-   :material-flask:{ .lg .middle } __Dokimasia — Tester__

    ---

    Writes pytest suites (unit → integration → performance). Targets 80%+ coverage. Runs `make test`.

    `Port 10003`

-   :material-auto-fix:{ .lg .middle } __Kallos — Stylist__

    ---

    Runs linters, cleans comments and docstrings. Hands off to Techne for logic fixes, max 3 iterations.

    `Port 10004`

-   :material-script-text:{ .lg .middle } __Mneme — Scribe__

    ---

    Generates grouped commit messages from `git diff`. Never commits — that's your job.

    `Port 10005`

</div>

---

## :material-star-shooting: Pipelines

| You say | Agents invoked |
|---------|---------------|
| *"implement feature X"* | Metis → Techne → Dokimasia → Kallos → Mneme |
| *"fix bug in X"* | Techne → Dokimasia → Kallos → Mneme |
| *"add tests for X"* | Dokimasia → Kallos → Mneme |
| *"clean up X"* | Kallos → Mneme |
| *"commit prep"* | Mneme |
