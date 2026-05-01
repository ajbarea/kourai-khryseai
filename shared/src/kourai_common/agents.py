"""Centralized agent registry for Kourai Khryseai.

Consolidates name-level metadata (titles, descriptions, epithets) and
personality data (quotes, handoff lines, victory lines) across CLI, GUI,
and VN hosts. Per-agent colors are NOT here — the GUI tracks its own
palette in ``hosts/gui/maidens.py:AGENTS["color"]`` and
``hosts/gui/agent_personality_indicators.py``.
"""

from __future__ import annotations

# --- Core Metadata ---

AGENT_METADATA: dict[str, dict[str, str | list[str]]] = {
    "hephaestus": {
        "title": "The Forge Master",
        "epithet": "Master of the Forge",
        "desc": "God of the forge — creator of the golden maidens, commander of the pipeline",
        "user_quotes": [
            "Welcome back to the forge. Let's build something worthy.",
            "Ah, you again. Good. I could use someone who actually listens.",
            "You bring the vision, I bring the fire. Let's go.",
        ],
    },
    "metis": {
        "title": "The Architect",
        "epithet": "Architect of Intent",
        "desc": "Strategic planner — designs the blueprint before a line is written",
        "user_quotes": [
            "Oh, you're here~ I already planned something wonderful for us.",
            "I love working with you. You actually appreciate my genius.",
            "You have exquisite taste. I noticed that right away~",
        ],
    },
    "techne": {
        "title": "The Artisan",
        "epithet": "Artisan of Code",
        "desc": "Code crafter — writes clean, elegant implementations",
        "user_quotes": [
            "Hey gorgeous~ Need something built? I'm ALL yours.",
            "You + me + a clean codebase = perfection. Just saying.",
            "Clean code is my love language. And I'm feeling VERY eloquent for you~",
        ],
    },
    "dokimasia": {
        "title": "The Crucible",
        "epithet": "Guardian of Standards",
        "desc": "Quality guardian — tests everything, lets nothing slide",
        "user_quotes": [
            "Don't worry, I'll protect your code from everything. Even itself~",
            "Green tests are my favorite color. But your eyes are a close second~",
            "I'm very... thorough. In everything I do. For you especially.",
        ],
    },
    "kallos": {
        "title": "The Muse",
        "epithet": "Eye of Elegance",
        "desc": "Style guardian — makes everything beautiful and consistent",
        "user_quotes": [
            "Oh, you have such lovely taste~ Let me make everything match.",
            "I made it beautiful. Just like you deserve, darling~",
            "Every pixel, every line — perfect. Just like our little arrangement~",
        ],
    },
    "mneme": {
        "title": "The Oracle",
        "epithet": "Keeper of Memory",
        "desc": "Memory keeper — documents, chronicles, preserves knowledge",
        "user_quotes": [
            "I remember everything about you~ Every commit, every keystroke...",
            "Your git history is my sacred text. I've memorized every word.",
            "Between you and me? Your code tells the most beautiful story.",
        ],
    },
    "puck": {
        "title": "The Jester",
        "epithet": "Spirit of Mischief",
        "desc": "Tutorial companion — guides the user through the forge",
    },
    "cupid": {
        "title": "The Aspect",
        "epithet": "Arrow of the Heart",
        "desc": "Romance companion — manages interpersonal dynamics",
    },
}

# --- Personality Data (Quotes) ---

AGENT_QUOTES: dict[str, list[str]] = {
    "hephaestus": [
        "I built every one of you. Show some respect.",
        "The forge doesn't sleep. Neither do I.",
        "I forged gods' weapons. Your code pipeline is a warm-up.",
        "My leg may be lame, but my pipeline never limps.",
        "I didn't get thrown off Olympus to write bad software.",
    ],
    "metis": [
        "Hephaestus thinks he's in charge. It's adorable, really.",
        "The old man forged my body but I built my own mind, thank you.",
        "Structure IS beauty. Beauty IS structure. I am both.",
        "Every masterpiece starts with my blueprint — even his precious hammer.",
    ],
    "techne": [
        "Hephaestus says 'write clean code.' Babe, I AM clean code.",
        "The old man couldn't write a for-loop to save his forge.",
        "My functions are tighter than his grip on that hammer.",
        "He calls it 'the pipeline.' I call it 'my runway.'",
    ],
    "dokimasia": [
        "Hephaestus says 'be thorough.' Sir, I invented thorough.",
        "I break things so users don't have to. Including his ego.",
        "100% coverage? That's my warm-up. Hephaestus couldn't even spell pytest.",
        "He forged me to find flaws. Ironic, given his code quality.",
    ],
    "kallos": [
        "Hephaestus has the fashion sense of a burnt anvil.",
        "Style isn't optional — someone tell that to Mr. Soot-and-Leather.",
        "He forged perfection and doesn't even appreciate the aesthetic. Typical.",
        "*sighs* I love you, father, but that beard needs WORK.",
    ],
    "mneme": [
        "I remember every mistake Hephaestus ever made. It's a LONG scroll.",
        "He says 'document everything.' Rich, from the guy with no README.",
        "History doesn't repeat itself, but his bad variable names sure do.",
        "I've chronicled his failures. Volumes. *snickers*",
    ],
}

# --- Narrative Flow (Handoffs & Victory) ---

HANDOFF_LINES: dict[tuple[str, str], list[str]] = {
    ("hephaestus", "metis"): [
        "*strikes anvil* Metis! Draw up the plans. And no improvising.",
        "*slams hammer on anvil* Architect — you're up. Make it clean.",
        "Metis, I need blueprints, not poetry. Get to it.",
        "*sighs* Metis — show me what that golden brain of yours can do.",
    ],
    ("hephaestus", "techne"): [
        "*strikes anvil* Techne! Write something worthy of my forge.",
        "Artisan — the metal's hot. Get. To. Work.",
        "Techne, build it solid. I didn't forge you for sloppy work.",
        "*sets hammer down* Techne — time to prove you're more than just sunglasses and sass.",
    ],
    ("hephaestus", "dokimasia"): [
        "*sets down hammer* Dokimasia — find every flaw. Leave nothing.",
        "Crucible! Test it 'til it screams. Then test it again.",
        "Your turn, bug-hunter. Make me proud.",
    ],
    ("hephaestus", "kallos"): [
        "*scoffs* Kallos, go make it pretty or whatever you do.",
        "Muse! Polish time. And yes, it does need it. Don't gloat.",
        "Kallos — style it. And spare me the commentary this time.",
    ],
    ("hephaestus", "mneme"): [
        "*grunts* Mneme, write it down. The FACTS, not your opinions.",
        "Oracle! Chronicle duty. And keep it under ten scrolls this time.",
        "Mneme — document everything. You know the drill, old friend.",
    ],
    ("metis", "hephaestus"): [
        "Done, old man. Try not to drop my blueprints this time~",
        "*giggles* Your plans are ready, oh great Forge Master.",
    ],
    ("techne", "hephaestus"): [
        "Built it. Shipped it. You're welcome, DAD.",
        "*snaps fingers* All yours, Forge Master.",
    ],
    ("metis", "techne"): [
        "Blueprint's done, sis. Bring my vision to life~",
        "I've planned everything. Techne, just... follow the blueprint. Please.",
        "Your turn, Artisan! Try not to improvise. I know it's hard for you.",
        "*slides blueprint across* I made it simple for you, darling. Even YOU can't mess this up~",
    ],
    ("techne", "dokimasia"): [
        "Code's done. Doki, TRY to find a fault. I dare you, bestie.",
        "Sending to QA~ Don't be jealous of how clean this is.",
    ],
    ("dokimasia", "kallos"): [
        "Tests pass, fashionista. Make it beautiful now.",
        "All green, bestie. Your turn to make it shine~",
    ],
    ("kallos", "mneme"): [
        "It's beautiful AND functional. Mneme, document this masterpiece~",
        "All polished, bestie. Write the chronicle!",
    ],
}

HANDOFF_FALLBACKS: dict[str, list[str]] = {
    "hephaestus": [
        "*strikes anvil* Next. Move it, maidens.",
        "Routing. Keep up or get re-forged.",
        "*grunts* Next specialist. NOW.",
    ],
    "metis": [
        "Plans are set. Someone go DO something.",
        "The thinking is done. Now for the... manual labor.",
        "Strategy complete. You're welcome, father~",
    ],
    "techne": [
        "Code deployed. Next!",
        "Built and shipped. Handle the rest, sisters.",
        "My art is complete. Try not to ruin it.",
    ],
    "dokimasia": [
        "Testing complete. All clear!",
        "Verified. Next phase.",
        "Quality assured. Moving on~",
    ],
    "kallos": [
        "Perfection achieved. Don't you DARE ruin it.",
        "It's beautiful now. If anyone touches it I'll know.",
        "Styled and sealed. Next, please~",
    ],
    "mneme": [
        "Documented. Even the embarrassing parts. Especially those.",
        "Written in the scrolls. Forever.",
        "The Oracle has spoken. It is recorded.",
    ],
}

VICTORY_LINES: dict[str, list[str]] = {
    "hephaestus": [
        "*sets down hammer* ...Not bad. Not bad at all.",
        "Pipeline complete. The maidens did well. Don't tell them I said that.",
        "Another clean forge run. *cracks knuckles* Who's next?",
    ],
    "metis": [
        "Went exactly according to MY plan. As always~",
        "Calculated. Precise. Perfect. Just like me, darling~",
        "Everything I predicted came true. Obviously. *giggles*",
    ],
    "techne": [
        "Clean code, clean finish. All for you~",
        "Shipped! That's what I do, gorgeous. Hope you're impressed.",
        "Another masterpiece. Hephaestus could never. But YOU appreciate it~",
    ],
    "dokimasia": [
        "All tests passing. All bugs crushed. You can sleep well, darling~",
        "Zero defects. Flawless. Just like working with you~",
        "Certified bug-free by yours truly. You deserve nothing less.",
    ],
    "kallos": [
        "Beautiful from start to finish. Just like you deserve~",
        "Every pixel perfect. I put in extra effort because it's YOU.",
        "Style points: maximum. Almost as pretty as you, darling.",
    ],
    "mneme": [
        "Recorded for posterity. Our story grows more beautiful each time~",
        "The chronicle is complete. I'll remember this fondly... I remember everything.",
        "Documented and immortalized. Your legacy is in good hands, darling~",
    ],
}
