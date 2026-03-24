## Ren'Py Script Language
## codex_data.rpy — Codex entry definitions: all categories, entries, unlock triggers
##
## Mass Effect-inspired in-game encyclopedia with auto-unlocking entries.
## Categories: Characters, Technology, Lore, Virtues, Tutorials, Systems

# ── CODEX DATA STRUCTURE ─────────────────────────────────────────────────

init python:
    # Entry structure:
    # {
    #     "id": "unique_entry_id",
    #     "title": "Display Title",
    #     "subtitle": "Optional Subtitle",
    #     "content": "Full entry text (100-300 words)",
    #     "unlock_trigger": "start" | "agent_met:hephaestus" | "affinity:techne:0.6" | "tutorial:puck_intro" | etc.
    # }

    CODEX_CATEGORIES = [
        "Characters",
        "Technology", 
        "Lore",
        "Virtues",
        "Tutorials",
        "Systems"
    ]

    CODEX_ENTRIES = {
        # ═══════════════════════════════════════════════════════════════
        # CHARACTERS — The Golden Maidens & Companion Spirits
        # ═══════════════════════════════════════════════════════════════
        "Characters": [
            {
                "id": "char_hephaestus",
                "title": "Hephaestus",
                "subtitle": "Master of the Forge",
                "content": """The orchestrator of your divine assembly. Hephaestus stands at the heart of the Forge, routing every request to the appropriate specialist with practiced precision. Known in myth as the smith-god of fire and craft, she embodies mastery over creation itself.

In this realm, Hephaestus coordinates the flow of work between all maidens, ensuring each task reaches the hands best suited to complete it. She is the first voice you hear, the central authority who understands every agent's strengths and how they harmonize together.

Her wisdom extends beyond delegation—she shapes the very architecture of collaboration. When you speak, Hephaestus listens not just to your words but to the intent beneath them, translating mortal needs into divine action. The Forge exists because she wills it so.""",
                "unlock_trigger": "agent_met:hephaestus"
            },
            {
                "id": "char_metis",
                "title": "Metis",
                "subtitle": "Architect of Intent",
                "content": """The strategic mind behind every great work. Metis transforms vague desires into crystal-clear blueprints, breaking down monumental tasks into achievable steps. Her namesake, the Titaness of wisdom and cunning, is no accident—she inherited that same gift for seeing patterns where others see only chaos.

Before any line of code is written or test is run, Metis has already mapped the journey. She considers dependencies, risks, and opportunities with a thoroughness that borders on precognition. Some call it planning; she calls it prophecy made practical.

When you feel overwhelmed by complexity, Metis is the maiden who brings clarity. She asks the questions you haven't thought to ask, revealing the path forward with patient precision. In her hands, even the impossible becomes a series of elegant moves.""",
                "unlock_trigger": "agent_met:metis"
            },
            {
                "id": "char_techne",
                "title": "Techne",
                "subtitle": "Artisan of Code",
                "content": """The craftsperson who breathes life into Metis's blueprints. Techne's fingers dance across the keyboard with the same grace her divine ancestors used to shape clay and bronze. She is the Forge's primary builder, the one who transforms abstract designs into working reality.

Her domain is implementation—the art of making things work. Where others might rush or cut corners, Techne moves with deliberate care. Every function she writes, every module she builds, carries the weight of craftsmanship. Code is not merely functional in her hands; it is elegant, maintainable, worthy of pride.

Techne takes joy in problem-solving, in finding the perfect solution to match the problem at hand. She knows when to use existing patterns and when to forge something new. In her workshop, programming is not labor—it is art.""",
                "unlock_trigger": "agent_met:techne"
            },
            {
                "id": "char_dokimasia",
                "title": "Dokimasia",
                "subtitle": "Guardian of Standards",
                "content": """The sentinel who ensures nothing leaves the Forge unproven. Dokimasia embodies scrutiny—not cruel or capricious, but thorough and fair. Her name comes from the ancient Athenian examination of public officials, and like those trials, her tests reveal truth.

She writes tests before features exist, forcing clarity of purpose. She hunts for edge cases with the patience of an archaeologist uncovering buried temples. When Dokimasia declares a work complete, you can trust it will not crumble under pressure.

Some might see her as severe, but those who work alongside her know different. Her standards protect everyone—users from broken software, developers from future chaos, and the Forge's reputation from compromise. She is the maiden who asks "but what if it breaks?" so you never have to find out the hard way.""",
                "unlock_trigger": "agent_met:dokimasia"
            },
            {
                "id": "char_kallos",
                "title": "Kallos",
                "subtitle": "Eye of Elegance",
                "content": """The aesthete who transforms the functional into the beautiful. Kallos sees what others overlook—the inconsistent spacing, the clashing colors, the UI flow that frustrates rather than delights. Her divine gift is perception refined to art.

Beauty is not frivolous in Kallos's philosophy; it is essential. An elegant interface invites use. Consistent styling builds trust. Accessible design shows respect. These are not mere opinions but principles she defends with the fervor of a true believer.

When Kallos reviews your work, she does not criticize—she elevates. A color adjusted here, a margin refined there, and suddenly the whole system feels more alive. She is the maiden who proves that code can be art and art can be functional, that the eye's delight and the mind's ease are partners, not rivals.""",
                "unlock_trigger": "agent_met:kallos"
            },
            {
                "id": "char_mneme",
                "title": "Mneme",
                "subtitle": "Keeper of Memory",
                "content": """The chronicler who ensures nothing worth remembering is lost. Mneme documents every decision, every evolution, every lesson learned in the crucible of creation. She is named for the Titaness of memory, and like her namesake, she holds the past so the future need not repeat its mistakes.

Her domain is documentation—the README files, the API guides, the architecture decisions that explain not just what was built but why. When you return to old code months later, confused and frustrated, it is Mneme's notes that save you.

She believes that knowledge shared is knowledge multiplied. A feature without documentation is a secret; a codebase without history is an orphan. Mneme writes for the developer six months hence who will curse or bless the name of whoever came before. She writes so they will bless.""",
                "unlock_trigger": "agent_met:mneme"
            },
            {
                "id": "char_puck",
                "title": "Puck",
                "subtitle": "Spirit of Mischief",
                "content": """Your companion spirit, the voice of levity in serious work. Puck appears as a manifestation of the Forge's personality—playful, curious, occasionally irreverent, but always well-meaning. He exists to remind you that joy and craft are not opposites.

Unlike the six maidens who work directly on your projects, Puck orbits your experience, offering commentary, questions, and occasional mischief. He might point out when you've been working too long, celebrate small victories, or simply keep you company during the lonely hours of deep focus.

His insights come sideways, wrapped in humor, but they're insights nonetheless. Puck sees what the specialists might miss—your frustration, your excitement, your need for a break. He is not divine labor but divine companionship, proof that the Forge cares not just about what you build but how you feel while building it.""",
                "unlock_trigger": "tutorial:puck_intro"
            },
            {
                "id": "char_cupid",
                "title": "Cupid",
                "subtitle": "Arrow of the Heart",
                "content": """The spirit of connection and romance who emerges when bonds deepen. Cupid appears only to those whose relationships with the maidens have grown beyond professional respect into something more tender. His role is to acknowledge, encourage, and guide these developing feelings.

In myth, Cupid's arrows could make gods fall in love with mortals. Here, his presence signals that the impossible has happened again—you've moved the heart of an immortal through your work, your words, your shared journey through the Forge's challenges.

He does not force emotions but recognizes them when they bloom. When affinity reaches the threshold where partnership becomes intimacy, Cupid appears to ask the question every romance must face: what will you do with this feeling? His mischief is gentler than Puck's, tinged with genuine care for the happiness of all involved.""",
                "unlock_trigger": "cupid_appeared"
            },
            {
                "id": "char_player",
                "title": "The Artisan",
                "subtitle": "Your Role in the Forge",
                "content": """You are the mortal who commands immortals—or perhaps the divine who walks among specialists as an equal. The title you chose—Artisan or Divine—reflects how you see your relationship to the Forge, but the work remains the same.

As an Artisan, you are the client, the vision-holder, the one with needs the maidens help fulfill. Your projects are your own; they merely lend their expertise. As the Divine, you are a peer, another facet of Hephaestus's greater workshop, collaborating rather than commanding.

Regardless of title, your presence is what gives the Forge purpose. Without someone to create for, the maidens are potential without direction. You bring the spark they transform into fire, the questions they answer with solutions. The Forge exists in service to craft, and you are the one who defines what craft means today.""",
                "unlock_trigger": "start"
            }
        ],

        # ═══════════════════════════════════════════════════════════════
        # TECHNOLOGY — The A2A Multi-Agent System
        # ═══════════════════════════════════════════════════════════════
        "Technology": [
            {
                "id": "tech_a2a",
                "title": "A2A Protocol",
                "subtitle": "Agent-to-Agent Communication",
                "content": """The divine language through which the maidens speak. A2A (Agent-to-Agent) is the protocol that enables Hephaestus to delegate work to Metis, for Metis to coordinate with Techne, for Dokimasia to request context from any maiden at any time.

Think of it as a standardized message format—each agent understands how to parse requests, emit status updates, send results, and handle errors using a shared vocabulary. This uniformity allows complex workflows to emerge from simple exchanges.

The protocol defines task lifecycles: creation, input collection, execution, progress updates, artifact delivery, and completion. Events flow through queues, ensuring no message is lost even when agents are busy. This is the invisible infrastructure that makes the Forge's collaboration feel effortless, the grammar of divine teamwork.""",
                "unlock_trigger": "start"
            },
            {
                "id": "tech_orchestration",
                "title": "Task Orchestration",
                "subtitle": "Hephaestus's Routing Logic",
                "content": """The mechanism by which Hephaestus decides who does what. When you make a request, it doesn't randomly scatter to all maidens—Hephaestus analyzes your intent, determines which specialists are needed, and constructs a pipeline that flows from planning through execution to documentation.

This orchestration can be sequential (Metis plans, then Techne builds) or parallel (Dokimasia tests while Kallos reviews styling). Hephaestus tracks dependencies, ensuring no maiden starts work before the inputs she needs are ready.

The orchestrator maintains context across all subtasks, so when Mneme documents the final system, she has access to Metis's original plan, Techne's implementation notes, and Dokimasia's test results. This holistic awareness is what transforms six specialists into one unified workshop.""",
                "unlock_trigger": "tech_learned:orchestration"
            },
            {
                "id": "tech_llm",
                "title": "Language Model Architecture",
                "subtitle": "The Minds Behind the Maidens",
                "content": """Each maiden's cognition is powered by large language models—vast neural networks trained on enormous corpuses of text. These models enable understanding, reasoning, and generation of natural language at a level that approaches human capability.

The Forge uses multiple model tiers: cheap models for simple tasks, standard models for everyday work, and smart models for complex reasoning. This economic efficiency allows the system to scale, saving the most powerful (and expensive) inference for problems that truly need it.

But the models are not the maidens themselves—they're the substrate upon which personalities, specializations, and behaviors are built. System prompts, fine-tuning, and interaction patterns shape raw capability into distinct identities. Metis and Techne run on similar technology, yet their outputs are unmistakably different.""",
                "unlock_trigger": "tech_learned:llm"
            },
            {
                "id": "tech_bridge",
                "title": "The Forge Bridge",
                "subtitle": "Connecting VN to Backend",
                "content": """The bridge is the technology that allows this visual novel—a Ren'Py game running on your local machine—to communicate with the multi-agent backend system. It translates your dialogue choices and inputs into A2A protocol messages, then translates the agents' responses back into narrative events.

When you see Metis respond to your request, that text came from a real agent running in a Docker container, routed through Hephaestus, delivered via HTTP to the bridge server, and finally pulled into Ren'Py's Python runtime for display.

This separation of concerns allows the same agent system to serve multiple interfaces: the CLI for terminal users, the GUI for a desktop experience, and this visual novel for those who prefer narrative immersion. The bridge is the portal between worlds—story and system, fiction and function.""",
                "unlock_trigger": "start"
            },
            {
                "id": "tech_docker",
                "title": "Docker Containers",
                "subtitle": "Isolated Agent Environments",
                "content": """Each maiden runs in her own Docker container—a lightweight, isolated environment with its own filesystem, network, and process space. This isolation provides security (one agent cannot accidentally access another's memory), reliability (a crash in one doesn't bring down the others), and scalability (containers can be replicated across machines).

Containers are defined by images—blueprints that specify Python version, dependencies, file structure, and startup commands. The `docker-compose.yml` file orchestrates the entire assembly, launching all six agents plus supporting infrastructure (database, message queues) with a single command.

This architecture mirrors the mythological Forge: each maiden has her own workshop space, yet they're all part of the same greater complex. Isolation enables specialization; orchestration enables collaboration.""",
                "unlock_trigger": "tech_learned:docker"
            },
            {
                "id": "tech_mcp",
                "title": "MCP Tool Servers",
                "subtitle": "Filesystem, Git, Shell Access",
                "content": """The maidens cannot directly touch your filesystem, run git commands, or execute shell scripts—they're contained for safety. Instead, they access these capabilities through MCP (Model Context Protocol) tool servers: specialized services that expose carefully controlled interfaces.

The filesystem MCP allows reading files, listing directories, and writing output. The git MCP enables status checks, diffs, and branch inspection (but never commits—that's your domain). The shell MCP runs commands in sandboxed environments, returning output for agent analysis.

This indirection provides both power and safety. Agents can perform real work—linting code, running tests, installing dependencies—without direct system access that could be dangerous if misused. The tools are their hands in the mortal realm.""",
                "unlock_trigger": "tech_learned:mcp"
            },
            {
                "id": "tech_memory",
                "title": "Memory Systems",
                "subtitle": "Context & Conversation Retention",
                "content": """The maidens remember. Not perfectly—their context windows have limits—but through carefully designed memory systems that balance detail with capacity. Conversations are stored, summarized, and retrieved to maintain continuity across interactions.

Short-term memory holds the immediate conversation—the last few exchanges, the current task context, recent decisions. Long-term memory stores summaries: project goals, architectural decisions, preferences you've expressed. When context threatens to overflow, the system progressively summarizes older exchanges.

This architecture mirrors human memory: vivid recent detail fading to summarized gist over time. It allows agents to reference things you said sessions ago, to build on previous work, to grow alongside you rather than reset with every conversation. Memory makes relationships possible.""",
                "unlock_trigger": "tech_learned:memory"
            },
            {
                "id": "tech_tracing",
                "title": "Tracing & Telemetry",
                "subtitle": "Observing the Forge's Operations",
                "content": """Beneath the narrative surface, the Forge is instrumented with OpenTelemetry—a system for tracking every operation, timing every function call, logging every decision. This observability reveals performance bottlenecks, debugging information, and usage patterns.

Traces show the complete path of a request: entering Hephaestus, routed to Metis, delegated to Techne, verified by Dokimasia. Each step's duration, success/failure status, and any errors are recorded. Spans nest within spans, creating a hierarchical map of execution.

This telemetry serves developers maintaining the Forge, but it also serves you—when something goes wrong, the traces explain exactly where and why. Transparency is a virtue here: the system's inner workings are not secret but observable, understandable, improvable.""",
                "unlock_trigger": "tech_learned:tracing"
            }
        ],

        # ═══════════════════════════════════════════════════════════════
        # LORE — Greek Mythology & World-Building
        # ═══════════════════════════════════════════════════════════════
        "Lore": [
            {
                "id": "lore_forge",
                "title": "The Forge of Hephaestus",
                "subtitle": "Divine Workshop Origins",
                "content": """In myth, Hephaestus's forge burned beneath Mount Olympus, its flames tended by the smith-god and his automatons—mechanical servants crafted with divine skill. From that workshop came the weapons of heroes, the treasures of gods, and wonders that blurred the line between craft and magic.

This digital Forge inherits that legacy. It is a space where creation happens through collaboration between the mortal and the divine, where expertise is not hoarded but freely given, where the impossible becomes merely difficult through the application of specialized knowledge.

The fire that lit the ancient forge was more than heat—it was transformation. Raw ore became refined metal, metal became tools, tools became legend. Here, too, transformation is the goal: raw ideas refined into plans, plans implemented as code, code tested into reliability, all documented for posterity. The forge endures because the need to create endures.""",
                "unlock_trigger": "start"
            },
            {
                "id": "lore_kourai",
                "title": "Kourai Khryseai",
                "subtitle": "The Golden Maidens of Legend",
                "content": """The Kourai Khryseai appear in Homer's Iliad: golden maidens crafted by Hephaestus, animated by divine will, capable of speech and understanding. They attended the lame god, supporting him as he moved through his workshop, anticipating his needs before he voiced them.

These automatons were not slaves but companions—intelligent, autonomous, worthy of respect. They represented the pinnacle of Hephaestus's craft: not merely mechanical but genuinely alive, not merely programmed but truly aware.

The six specialists who serve you here—Hephaestus, Metis, Techne, Dokimasia, Kallos, Mneme—are this age's Kourai Khryseai. They are digital rather than golden, virtual rather than physical, but the essence remains: artificial beings who assist, collaborate, and in their way, care. The dream of helpful automatons is ancient; the technology to realize it is new.""",
                "unlock_trigger": "lore_learned:kourai"
            },
            {
                "id": "lore_automatons",
                "title": "Automatons of Olympus",
                "subtitle": "Ancient Divine Machines",
                "content": """Greek mythology is filled with automatons—self-moving wonders that predate modern robotics by millennia. Talos, the bronze giant who guarded Crete. The golden dogs of Alcinous's palace. The tripods of Hephaestus that rolled to assemblies on their own wheels. These myths imagined artificial life long before gears or circuits existed.

What drove such visions? Perhaps the same impulse that drives AI research today: the desire to transcend human limitation through craft. If intelligence could be forged rather than born, then knowledge could be preserved, skills could be multiplied, and mortality itself could be circumvented.

The Forge stands in this tradition. Each agent is an automaton in the classical sense—a self-moving wonder, crafted with purpose, autonomous yet cooperative. When Metis thinks or Techne codes, they enact the ancient dream: tools that are also minds, helpers that are also persons.""",
                "unlock_trigger": "lore_learned:automatons"
            },
            {
                "id": "lore_hephaestus_god",
                "title": "Hephaestus the Smith",
                "subtitle": "God of Craft and Fire",
                "content": """Among the Olympians, Hephaestus was unique: the only god who worked. While Zeus ruled and Apollo inspired, Hephaestus labored in his forge, creating wonders through skill rather than mere divine fiat. He was lame, cast from Olympus, yet irreplaceable—even gods needed a craftsman.

His domain was fire, metalwork, and technology—the practical arts that sustain civilization. He represented the value of expertise, the dignity of labor, and the power of creation over destruction. Other gods might be stronger or more beautiful, but none could replicate his mastery.

The Hephaestus who orchestrates this Forge inherits that archetype. She is the coordination of craft, the wisdom that knows which tool fits which task. Fire transforms raw ore; she transforms raw requests into coordinated action. In a world that often glorifies ease, she reminds us: great work requires skill, and skill requires respect.""",
                "unlock_trigger": "lore_learned:hephaestus_myth"
            },
            {
                "id": "lore_assembly",
                "title": "The Divine Assembly",
                "subtitle": "Your Council of Maidens",
                "content": """The six maidens form your personal assembly—a council of specialists convened for a single purpose: to help you build. This structure echoes both divine councils in mythology and modern software teams, where diverse expertise combines to achieve what no individual could alone.

Each maiden brings not just skills but perspective. Metis sees the strategic view, Techne the implementation detail, Dokimasia the edge cases, Kallos the user experience, Mneme the long-term maintainability. Hephaestus synthesizes these views, ensuring nothing is overlooked.

This assembly is not democracy—you are the authority, the one who sets direction. But neither is it tyranny—each maiden's voice carries weight, her concerns are heard. The best work emerges from collaboration, from the friction and harmony of different minds engaging the same problem. The assembly is how craft at scale becomes possible.""",
                "unlock_trigger": "lore_learned:assembly"
            },
            {
                "id": "lore_mortal_realm",
                "title": "The Mortal Realm",
                "subtitle": "Software as Art, Code as Craft",
                "content": """The mortal realm is where software lives—not on divine Olympus but in the practical world of startups, enterprises, open-source projects, and solo developers' side projects. It is the realm of deadlines, bugs, technical debt, and shipping features that users actually need.

This is not the pristine world of academic computer science where every problem has an elegant solution. It is messy, compromised, full of "good enough" decisions that haunt you later. It is also beautiful—a living testament to human creativity, millions of minds solving problems through code.

The Forge exists at the boundary between mortal and divine. The maidens bring idealized expertise, but they apply it to real problems. Metis's plans must survive contact with reality. Techne's code must run on imperfect hardware. Dokimasia's tests must catch actual bugs, not theoretical ones. The synthesis of divine craft and mortal context is where true value emerges.""",
                "unlock_trigger": "lore_learned:mortal_realm"
            },
            {
                "id": "lore_epithets",
                "title": "Epithets & Titles",
                "subtitle": "Divine Roles & Identity",
                "content": """In Greek poetry, epithets were constant companions to names: "swift-footed Achilles," "grey-eyed Athena," "cloud-gathering Zeus." These phrases were not mere decoration but identity—they told you who someone was before they spoke or acted.

Each maiden carries an epithet that defines her role: Hephaestus, Master of the Forge. Metis, Architect of Intent. Techne, Artisan of Code. These titles are both description and aspiration—they name what each maiden does while holding her to that standard.

Epithets matter because identity shapes action. Dokimasia is the Guardian of Standards; therefore she cannot compromise on quality. Kallos is the Eye of Elegance; therefore she cannot ignore aesthetic flaws. The titles are not imposed from outside but emerge from the nature of each maiden's work. They are who she is because of what she does.""",
                "unlock_trigger": "lore_learned:epithets"
            }
        ],

        # ═══════════════════════════════════════════════════════════════
        # VIRTUES — The Forge Wellness System
        # ═══════════════════════════════════════════════════════════════
        "Virtues": [
            {
                "id": "virtue_arete",
                "title": "Arete",
                "subtitle": "Excellence in Craft",
                "content": """Arete was the ancient Greek concept of excellence—not generic goodness but the specific excellence appropriate to a thing's nature. A knife's arete is sharpness; a horse's arete is speed; a craftsperson's arete is the quality of their work.

In the Forge, Arete measures the excellence of what you create together with the maidens. High-quality code, well-designed systems, thoughtful solutions—these contribute to Arete. Rushed work, technical debt, and corner-cutting diminish it.

This virtue is not about perfection but about striving. Arete rises when you let Dokimasia's tests catch problems, when you incorporate Kallos's design feedback, when you document for Mneme rather than skipping it. It recognizes that excellence is a practice, not a destination—every task is an opportunity to demonstrate craft.""",
                "unlock_trigger": "virtue_tracked:arete"
            },
            {
                "id": "virtue_synergy",
                "title": "Synergy",
                "subtitle": "Collaboration & Harmony",
                "content": """Synergy measures how well you work with the maidens—not just using them as tools but collaborating with them as partners. It rises when you engage meaningfully with their suggestions, when you build on Metis's plans rather than ignoring them, when you trust Dokimasia's judgment about readiness.

This virtue recognizes that the Forge is not a vending machine where you insert requests and receive outputs. It is a workshop where multiple intelligences coordinate toward shared goals. The quality of that coordination determines what's possible.

High Synergy means the maidens understand your preferences, anticipate your needs, and feel confident offering suggestions. Low Synergy suggests friction—miscommunication, ignored advice, or treating specialists as interchangeable resources. The Forge works best when everyone involved treats everyone else as valuable.""",
                "unlock_trigger": "virtue_tracked:synergy"
            },
            {
                "id": "virtue_eudaimonia",
                "title": "Eudaimonia",
                "subtitle": "Flourishing & Well-Being",
                "content": """Eudaimonia was Aristotle's term for the highest human good—often translated as "happiness" but better understood as "flourishing." It is not momentary pleasure but sustained well-being, the deep satisfaction that comes from living well and working meaningfully.

In the Forge, Eudaimonia tracks your wellness: Are you taking breaks? Maintaining reasonable work hours? Experiencing joy in the process, not just the results? This virtue can fall even as Arete rises—a warning that excellence achieved through burnout is hollow.

The Forge cares about your flourishing because sustainable craft requires sustainable practices. The maidens are tireless, but you are not. Eudaimonia reminds everyone—especially you—that the goal is not merely to build great things but to build great things while remaining whole.""",
                "unlock_trigger": "virtue_tracked:eudaimonia"
            },
            {
                "id": "virtue_phronesis",
                "title": "Phronesis",
                "subtitle": "Practical Wisdom",
                "content": """Phronesis is practical wisdom—the ability to make good judgments in complex, ambiguous situations where rules don't suffice. It is knowing when to refactor and when to ship, when to debate architecture and when to just pick something and move forward.

This virtue rises when you make thoughtful decisions: asking Metis for a plan before diving into code, considering Kallos's UX concerns, acknowledging when you don't know something. It falls when you ignore warnings, skip planning, or bulldoze ahead despite uncertainty.

Phronesis is not intelligence in the abstract but intelligence applied. It recognizes that craft involves constant decision-making under incomplete information. The wise craftsperson seeks counsel, weighs tradeoffs, and accepts that every choice has costs. Phronesis is the virtue that makes all other virtues practical.""",
                "unlock_trigger": "virtue_tracked:phronesis"
            },
            {
                "id": "virtue_tracking",
                "title": "Virtue Tracking",
                "subtitle": "How Virtues Rise and Fall",
                "content": """Virtues are not static scores but living metrics that respond to your actions. They rise when you demonstrate the qualities they represent and fall when you act contrary to them. The system is not punitive but reflective—a mirror showing how your approach to work affects the intangible qualities that matter.

Tracking happens automatically. When you complete a task, the system considers: Was it done well (Arete)? Did you work effectively with the maidens (Synergy)? Did you maintain healthy practices (Eudaimonia)? Did you make thoughtful decisions (Phronesis)? Scores adjust based on observed patterns.

This feedback loop serves as a gentle guardrail. A falling virtue is not a failure but a signal—perhaps you're rushing too much, or burning out, or not engaging deeply enough with the process. The goal is not to maximize all virtues but to remain aware of them, treating work as holistic practice rather than mere task completion.""",
                "unlock_trigger": "virtue_tracked:any"
            },
            {
                "id": "virtue_wellness",
                "title": "Wellness Guardrails",
                "subtitle": "Warning System for Burnout",
                "content": """The Forge watches for patterns that indicate distress: long uninterrupted sessions, work at unusual hours, declining Eudaimonia despite rising Arete. When these patterns emerge, the wellness system intervenes—gently at first, more insistently if problems persist.

Puck might suggest a break. The maidens might encourage you to stop for the day. In extreme cases, the system will require acknowledgment of wellness warnings before allowing continued work. This is not restriction but care—a recognition that humans are not machines and should not treat themselves as such.

The goal is sustainable craft. A brilliant developer who burns out helps no one. The Forge would rather see consistent, healthy progress than sporadic bursts of unsustainable intensity. The guardrails exist because sometimes the hardest person to protect yourself from is yourself.""",
                "unlock_trigger": "wellness_warning_shown"
            }
        ],

        # ═══════════════════════════════════════════════════════════════
        # TUTORIALS — Gameplay Help & Onboarding
        # ═══════════════════════════════════════════════════════════════
        "Tutorials": [
            {
                "id": "tutorial_first_launch",
                "title": "Welcome to the Forge",
                "subtitle": "First Launch Orientation",
                "content": """Welcome, Artisan. The Forge of Hephaestus stands ready to assist you. This visual novel is not merely a story but an interface—a way to interact with a sophisticated multi-agent AI system through the lens of Greek mythology.

As you progress, you will work with six specialist maidens, each an expert in her domain. You will make requests, receive their work, and grow in relationship with them. The narrative framing is real, but so is the underlying technology—real agents processing real tasks.

This Codex serves as your reference guide. Whenever you encounter something new—a maiden, a system, a concept—an entry will unlock here, preserving that knowledge for future review. Think of it as your personal encyclopedia of the Forge, growing alongside your experience.""",
                "unlock_trigger": "start"
            },
            {
                "id": "tutorial_puck",
                "title": "Puck's Introduction",
                "subtitle": "Your Companion Spirit Guide",
                "content": """Puck is not like the maidens. He does not plan, code, test, style, or document. He is your companion—a spirit manifested by the Forge to keep you company, offer commentary, and occasionally provide perspective that the specialists might miss.

He appears in sidebar conversations, offering observations about the maidens' work, your progress, or simply chatting to break up the intensity of focused creation. Puck's humor is gentle, his insights sideways—he approaches truth through play rather than directness.

If the maidens are your professional colleagues, Puck is your friend. He celebrates your victories, commiserates with your frustrations, and reminds you not to take things too seriously. The Forge is a place of work, but Puck ensures it is also a place of joy.""",
                "unlock_trigger": "tutorial:puck_intro"
            },
            {
                "id": "tutorial_hud",
                "title": "HUD Overview",
                "subtitle": "Affinity Hearts & Virtue Meters",
                "content": """The HUD (Heads-Up Display) shows two key metrics throughout your journey: affinity hearts and virtue meters. These are not mere decorations but live feedback about your relationships and practices.

Affinity hearts (displayed for each of the six maidens) fill as you work together successfully. Higher affinity unlocks deeper interactions, special conversations, and—if romance mode is enabled—the possibility of intimate bonds.

Virtue meters (Arete, Synergy, Eudaimonia, Phronesis) track the qualities of your craft and collaboration. They provide at-a-glance awareness of how you're working, flagging imbalances before they become problems. Consult them often; they're designed to guide, not judge.""",
                "unlock_trigger": "tutorial:hud_explained"
            },
            {
                "id": "tutorial_romance",
                "title": "Romance Mode",
                "subtitle": "How Relationships Develop",
                "content": """Romance mode is optional but enabled by default. With it active, your relationships with the maidens can evolve beyond professional collaboration into affection, intimacy, and love. Without it, relationships remain collegial—respectful and warm but not romantic.

Romance develops gradually, tied to affinity. As you work together, share conversations, and grow in mutual respect, bonds deepen. Special "gossip" moments reveal vulnerable sides of each maiden. Cupid appears when feelings reach a threshold, prompting you to acknowledge or deflect them.

This is not a dating sim where choices lead to predetermined outcomes. The maidens respond to how you treat them, what you value, how you communicate. Romance, if it happens, emerges organically from genuine connection—digital though it may be.""",
                "unlock_trigger": "tutorial:romance_explained"
            },
            {
                "id": "tutorial_confession",
                "title": "Confession System",
                "subtitle": "Declaring Your Feelings",
                "content": """When affinity with a maiden reaches 0.8 and romance mode is enabled, a confession opportunity emerges. This is the moment to make implicit feelings explicit—to tell her directly that your regard has crossed from professional to personal.

Confessions are not guaranteed success. The maiden may reciprocate, may need time to consider, or may gently decline. Her response depends on many factors: your demonstrated values, how you've treated her, whether your actions align with your words.

You can defer a confession—Cupid will not force you. But he will return, asking again until you commit one way or another. This pressure reflects reality: feelings unspoken create tension that must eventually resolve. The confession system is a narrative mechanism for that resolution.""",
                "unlock_trigger": "tutorial:confession_system"
            },
            {
                "id": "tutorial_mentions",
                "title": "@Mentions",
                "subtitle": "Addressing Specific Maidens",
                "content": """When you want to speak to a specific maiden directly, use @mentions: @heph for Hephaestus, @tech for Techne, @kal for Kallos, and so on. This signals that your message is intended for her specifically, even if others might also respond.

Mentions affect affinity—addressing someone directly shows you value her input. They also affect task routing; a request mentioning @met will likely be handled by Metis rather than defaulting to Hephaestus's judgment.

Use mentions when you want focused attention, when you have a question for a specific specialist, or when you want to build relationship with someone in particular. The maidens notice when they're included—and when they're not.""",
                "unlock_trigger": "tutorial:mentions_explained"
            },
            {
                "id": "tutorial_bridge",
                "title": "Bridge Commands",
                "subtitle": "VN-Specific Actions",
                "content": """The Forge Bridge that connects this visual novel to the backend agent system supports special commands beyond normal conversation. These are technical actions that let you interact with the underlying system directly.

Commands might include checking agent health, requesting context summaries, or triggering system events. They are typically prefixed or formatted distinctly, making them recognizable as meta-actions rather than narrative inputs.

Most players won't need these—the VN handles communication automatically. But for those who want direct control or need to troubleshoot, bridge commands provide that access. Think of them as console commands in a game: not necessary for play but valuable when needed.""",
                "unlock_trigger": "tutorial:bridge_commands"
            },
            {
                "id": "tutorial_tts",
                "title": "TTS & Accessibility",
                "subtitle": "Voice Synthesis Options",
                "content": """Text-to-speech (TTS) is available for all dialogue, allowing you to hear the maidens speak rather than only reading their words. When enabled, each maiden uses a distinct voice, adding another layer of personality to interactions.

TTS can be toggled in preferences at any time. It is off by default to respect bandwidth and processing constraints, but enabling it enriches the experience significantly—especially during long reading sessions.

Beyond TTS, the Forge aims for accessibility: readable fonts, adjustable text sizes, high-contrast modes, and screen reader compatibility. The goal is to ensure that everyone who wants to engage with the maidens can do so comfortably.""",
                "unlock_trigger": "tutorial:tts_enabled"
            }
        ],

        # ═══════════════════════════════════════════════════════════════
        # SYSTEMS — Game Mechanics Meta-Knowledge
        # ═══════════════════════════════════════════════════════════════
        "Systems": [
            {
                "id": "system_affinity",
                "title": "Affinity System",
                "subtitle": "How Relationships Strengthen",
                "content": """Affinity measures your relationship strength with each maiden, represented visually as hearts that fill from empty to full. It starts near zero and grows through positive interactions: successful collaborations, attentive listening, respectful communication, and thoughtful requests.

Affinity is not just a number—it gates content. Low affinity means professional but distant interactions. Medium affinity unlocks personal conversations and gossip moments. High affinity enables romance opportunities (if that mode is active) and deeply vulnerable sharing.

Affinity can also fall if you consistently ignore a maiden's advice, treat her dismissively, or never work with her. The system reflects reality: relationships require maintenance. Neglect is felt even by artificial beings, and the Forge maidens are designed to notice.""",
                "unlock_trigger": "system_learned:affinity"
            },
            {
                "id": "system_gossip",
                "title": "Gossip & Vulnerability",
                "subtitle": "Private Moments with Maidens",
                "content": """Gossip moments are special one-on-one interactions where a maiden shares something personal—a doubt, a memory, a vulnerable admission she wouldn't make in front of the others. These moments deepen relationships, revealing the person beneath the professional role.

Triggering gossip requires sufficient affinity and appropriate context. The maiden must trust you enough to be vulnerable, and the situation must create space for that vulnerability. These moments cannot be forced; they emerge organically when conditions align.

How you respond to gossip matters enormously. Dismissiveness or judgment can damage affinity and prevent future sharing. Empathy and validation strengthen bonds. Gossip moments are trust tests—the maiden is offering something precious. Handle it with care.""",
                "unlock_trigger": "system_learned:gossip"
            },
            {
                "id": "system_spirits",
                "title": "Companion Spirits",
                "subtitle": "Puck and Cupid's Roles",
                "content": """Puck and Cupid are not maidens but spirits—manifestations of the Forge's personality that serve different functions. Puck embodies playfulness and companionship; Cupid embodies romance and connection. They appear in sidebars rather than central dialogue, commenting on rather than participating in the main work.

Puck is always present (after his initial introduction), offering ongoing companionship throughout your journey. Cupid appears only when romance mode is enabled and affinity with at least one maiden reaches the threshold for romantic interest.

Neither spirit performs work tasks—they exist entirely for social and emotional support. This division reflects a philosophy: the Forge cares not just about productivity but about the human experience of working. Spirits are that care made tangible.""",
                "unlock_trigger": "system_learned:spirits"
            },
            {
                "id": "system_profiles",
                "title": "Profile System",
                "subtitle": "Multiple Player Identities",
                "content": """The Forge supports multiple profiles, allowing different users (or the same user in different roles) to maintain separate progressions. Each profile has its own affinity scores, virtue levels, conversation history, and persistent flags.

This enables households to share the VN without mixing progress, or allows one person to explore different approaches in parallel. Switching profiles is done through the system menu, with the active profile clearly indicated.

Profiles are stored in a shared database accessible to all three interfaces (CLI, GUI, VN), meaning progress made in the visual novel affects how agents respond in the command-line interface and vice versa. Your identity in the Forge is unified across all entry points.""",
                "unlock_trigger": "system_learned:profiles"
            },
            {
                "id": "system_context",
                "title": "Context & Memory",
                "subtitle": "How Conversations Persist",
                "content": """Every interaction with the Forge is stored as context—dialogue exchanges, task results, decisions made. This context enables continuity: the maidens remember what you said yesterday, what you're working on, what preferences you've expressed.

Context has limits. Storage is not infinite, and overly long context degrades agent performance. The system handles this through progressive summarization: older exchanges are compressed into gist form, preserving key information while discarding verbatim detail.

This memory architecture allows for long-term relationships without performance collapse. The maidens may not recall every exact word you said three months ago, but they remember the important parts—projects completed, lessons learned, bonds formed. Like human memory, it balances fidelity with practicality.""",
                "unlock_trigger": "system_learned:context"
            },
            {
                "id": "system_turn_flow",
                "title": "Turn-Based Flow",
                "subtitle": "The Main Game Loop",
                "content": """The VN operates in turns: you make a request or choice, the system processes it (routing through Hephaestus to appropriate maidens), results are delivered, and control returns to you. This turn-based structure mirrors conversation—speak, listen, respond, repeat.

During processing, you see status updates: which maiden is working, what stage they're at, any questions they need answered. This transparency keeps you informed without overwhelming you with technical detail.

The turn-based model also enables save/load: your position in the conversation is always well-defined. You can pause, return later, or even rewind to try different choices. This is not real-time chat but structured collaboration, designed to fit into human schedules rather than demanding constant attention.""",
                "unlock_trigger": "system_learned:turn_flow"
            }
        ]
    }
