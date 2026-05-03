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
#
# M18 Phase 2: each line is an SSML document. <break time="200ms"/>
# markers go at sentence boundaries so SSML-native engines (M6
# ElevenLabs / Azure / Google) get natural pause hints; Kokoro ignores
# them and the strip layer in `kourai_common.ssml.strip_ssml` collapses
# the breaks to single spaces for display + Kokoro synthesis. The
# `_comms_window` chokepoint and TTS engine path both strip
# automatically, so callers stay SSML-agnostic.

HANDOFF_LINES: dict[tuple[str, str], list[str]] = {
    ("hephaestus", "metis"): [
        '<speak>*strikes anvil* Metis!<break time="200ms"/>Draw up the plans.<break time="200ms"/>And no improvising.</speak>',
        '<speak>*slams hammer on anvil* Architect — you\'re up.<break time="200ms"/>Make it clean.</speak>',
        '<speak>Metis, I need blueprints, not poetry.<break time="200ms"/>Get to it.</speak>',
        "<speak>*sighs* Metis — show me what that golden brain of yours can do.</speak>",
    ],
    ("hephaestus", "techne"): [
        '<speak>*strikes anvil* Techne!<break time="200ms"/>Write something worthy of my forge.</speak>',
        '<speak>Artisan — the metal\'s hot.<break time="200ms"/>Get.<break time="200ms"/>To.<break time="200ms"/>Work.</speak>',
        '<speak>Techne, build it solid.<break time="200ms"/>I didn\'t forge you for sloppy work.</speak>',
        "<speak>*sets hammer down* Techne — time to prove you're more than just sunglasses and sass.</speak>",
    ],
    ("hephaestus", "dokimasia"): [
        '<speak>*sets down hammer* Dokimasia — find every flaw.<break time="200ms"/>Leave nothing.</speak>',
        '<speak>Crucible!<break time="200ms"/>Test it \'til it screams.<break time="200ms"/>Then test it again.</speak>',
        '<speak>Your turn, bug-hunter.<break time="200ms"/>Make me proud.</speak>',
    ],
    ("hephaestus", "kallos"): [
        "<speak>*scoffs* Kallos, go make it pretty or whatever you do.</speak>",
        '<speak>Muse!<break time="200ms"/>Polish time.<break time="200ms"/>And yes, it does need it.<break time="200ms"/>Don\'t gloat.</speak>',
        '<speak>Kallos — style it.<break time="200ms"/>And spare me the commentary this time.</speak>',
    ],
    ("hephaestus", "mneme"): [
        '<speak>*grunts* Mneme, write it down.<break time="200ms"/>The FACTS, not your opinions.</speak>',
        '<speak>Oracle!<break time="200ms"/>Chronicle duty.<break time="200ms"/>And keep it under ten scrolls this time.</speak>',
        '<speak>Mneme — document everything.<break time="200ms"/>You know the drill, old friend.</speak>',
    ],
    ("metis", "hephaestus"): [
        '<speak>Done, old man.<break time="200ms"/>Try not to drop my blueprints this time~</speak>',
        "<speak>*giggles* Your plans are ready, oh great Forge Master.</speak>",
    ],
    ("techne", "hephaestus"): [
        '<speak>Built it.<break time="200ms"/>Shipped it.<break time="200ms"/>You\'re welcome, DAD.</speak>',
        "<speak>*snaps fingers* All yours, Forge Master.</speak>",
    ],
    ("metis", "techne"): [
        '<speak>Blueprint\'s done, sis.<break time="200ms"/>Bring my vision to life~</speak>',
        '<speak>I\'ve planned everything.<break time="200ms"/>Techne, just... follow the blueprint.<break time="200ms"/>Please.</speak>',
        '<speak>Your turn, Artisan!<break time="200ms"/>Try not to improvise.<break time="200ms"/>I know it\'s hard for you.</speak>',
        '<speak>*slides blueprint across* I made it simple for you, darling.<break time="200ms"/>Even YOU can\'t mess this up~</speak>',
    ],
    ("techne", "dokimasia"): [
        '<speak>Code\'s done.<break time="200ms"/>Doki, TRY to find a fault.<break time="200ms"/>I dare you, bestie.</speak>',
        "<speak>Sending to QA~ Don't be jealous of how clean this is.</speak>",
    ],
    ("dokimasia", "kallos"): [
        '<speak>Tests pass, fashionista.<break time="200ms"/>Make it beautiful now.</speak>',
        '<speak>All green, bestie.<break time="200ms"/>Your turn to make it shine~</speak>',
    ],
    ("kallos", "mneme"): [
        '<speak>It\'s beautiful AND functional.<break time="200ms"/>Mneme, document this masterpiece~</speak>',
        '<speak>All polished, bestie.<break time="200ms"/>Write the chronicle!</speak>',
    ],
}

HANDOFF_FALLBACKS: dict[str, list[str]] = {
    "hephaestus": [
        '<speak>*strikes anvil* Next.<break time="200ms"/>Move it, maidens.</speak>',
        '<speak>Routing.<break time="200ms"/>Keep up or get re-forged.</speak>',
        '<speak>*grunts* Next specialist.<break time="200ms"/>NOW.</speak>',
    ],
    "metis": [
        '<speak>Plans are set.<break time="200ms"/>Someone go DO something.</speak>',
        '<speak>The thinking is done.<break time="200ms"/>Now for the... manual labor.</speak>',
        '<speak>Strategy complete.<break time="200ms"/>You\'re welcome, father~</speak>',
    ],
    "techne": [
        '<speak>Code deployed.<break time="200ms"/>Next!</speak>',
        '<speak>Built and shipped.<break time="200ms"/>Handle the rest, sisters.</speak>',
        '<speak>My art is complete.<break time="200ms"/>Try not to ruin it.</speak>',
    ],
    "dokimasia": [
        '<speak>Testing complete.<break time="200ms"/>All clear!</speak>',
        '<speak>Verified.<break time="200ms"/>Next phase.</speak>',
        '<speak>Quality assured.<break time="200ms"/>Moving on~</speak>',
    ],
    "kallos": [
        '<speak>Perfection achieved.<break time="200ms"/>Don\'t you DARE ruin it.</speak>',
        "<speak>It's beautiful now.<break time=\"200ms\"/>If anyone touches it I'll know.</speak>",
        '<speak>Styled and sealed.<break time="200ms"/>Next, please~</speak>',
    ],
    "mneme": [
        '<speak>Documented.<break time="200ms"/>Even the embarrassing parts.<break time="200ms"/>Especially those.</speak>',
        '<speak>Written in the scrolls.<break time="200ms"/>Forever.</speak>',
        '<speak>The Oracle has spoken.<break time="200ms"/>It is recorded.</speak>',
    ],
}

VICTORY_LINES: dict[str, list[str]] = {
    "hephaestus": [
        '<speak>*sets down hammer* ...Not bad.<break time="200ms"/>Not bad at all.</speak>',
        '<speak>Pipeline complete.<break time="200ms"/>The maidens did well.<break time="200ms"/>Don\'t tell them I said that.</speak>',
        '<speak>Another clean forge run.<break time="200ms"/>*cracks knuckles* Who\'s next?</speak>',
    ],
    "metis": [
        '<speak>Went exactly according to MY plan.<break time="200ms"/>As always~</speak>',
        '<speak>Calculated.<break time="200ms"/>Precise.<break time="200ms"/>Perfect.<break time="200ms"/>Just like me, darling~</speak>',
        '<speak>Everything I predicted came true.<break time="200ms"/>Obviously.<break time="200ms"/>*giggles*</speak>',
    ],
    "techne": [
        '<speak>Clean code, clean finish.<break time="200ms"/>All for you~</speak>',
        '<speak>Shipped!<break time="200ms"/>That\'s what I do, gorgeous.<break time="200ms"/>Hope you\'re impressed.</speak>',
        '<speak>Another masterpiece.<break time="200ms"/>Hephaestus could never.<break time="200ms"/>But YOU appreciate it~</speak>',
    ],
    "dokimasia": [
        '<speak>All tests passing.<break time="200ms"/>All bugs crushed.<break time="200ms"/>You can sleep well, darling~</speak>',
        '<speak>Zero defects.<break time="200ms"/>Flawless.<break time="200ms"/>Just like working with you~</speak>',
        '<speak>Certified bug-free by yours truly.<break time="200ms"/>You deserve nothing less.</speak>',
    ],
    "kallos": [
        '<speak>Beautiful from start to finish.<break time="200ms"/>Just like you deserve~</speak>',
        '<speak>Every pixel perfect.<break time="200ms"/>I put in extra effort because it\'s YOU.</speak>',
        '<speak>Style points: maximum.<break time="200ms"/>Almost as pretty as you, darling.</speak>',
    ],
    "mneme": [
        '<speak>Recorded for posterity.<break time="200ms"/>Our story grows more beautiful each time~</speak>',
        '<speak>The chronicle is complete.<break time="200ms"/>I\'ll remember this fondly...<break time="200ms"/>I remember everything.</speak>',
        '<speak>Documented and immortalized.<break time="200ms"/>Your legacy is in good hands, darling~</speak>',
    ],
}
