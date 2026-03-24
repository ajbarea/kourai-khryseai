"""Character data constants for the Golden Maidens.

Agent profiles, kaomoji faces, handoff chatter, victory lines, and taglines.
Hephaestus is the disabled male forge god who CREATED the golden maidens.
The maidens are his sassy, beautiful, divine automata — fierce golden women.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Banner & personality
# ---------------------------------------------------------------------------
_TAGLINES = [
    "The Golden Maidens await your command",
    "Forged in fire, refined by hand",
    "Automata of the divine forge",
    "Where craft meets intelligence",
    "Your gilded development companions",
    "Hephaestus' finest creations",
]


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Agent profiles — Hephaestus (the forge god) and his Kourai Khryseai
#
# Hephaestus is the disabled male forge god who CREATED the golden maidens.
# The maidens are his sassy, beautiful, divine automata — fierce golden women.
# Think: gruff craftsman commander dispatching his gorgeous golden squad.
#
# ART: Golden portraits live in docs/assets/maidens/golden_avatars/
#      Named <agent>.png — e.g. hephaestus.png, techne.png
#      They render as full-color pixel art inside comms windows & cards!
#      Transparent PNGs work best (background becomes terminal bg).
# ---------------------------------------------------------------------------

_MAIDENS: dict[str, dict[str, str | list[str]]] = {
    "hephaestus": {
        "face": "(╭∩╮)⊃━☆ﾟ.*･｡ﾟ",
        "title": "The Forge Master",
        "desc": "God of the forge — creator of the golden maidens, commander of the pipeline",
        "quotes": [
            "I built every one of you. Show some respect.",
            "The forge doesn't sleep. Neither do I.",
            "*leans on anvil* ...Alright, let's see what we're working with.",
            "I forged gods' weapons. Your code pipeline is a warm-up.",
            "My leg may be lame, but my pipeline never limps.",
            "I didn't get thrown off Olympus to write bad software.",
        ],
        "user_quotes": [
            "Welcome back to the forge. Let's build something worthy.",
            "Ah, you again. Good. I could use someone who actually listens.",
            "The maidens are insufferable, but they'll do anything for you. Use that.",
            "You bring the vision, I bring the fire. Let's go.",
            "*nods approvingly* You've got taste. Rare quality these days.",
            "Don't mind them flirting — they do that. Focus on the work.",
        ],
    },
    "metis": {
        "face": "( ◡‿◡)✧",
        "title": "The Architect",
        "desc": "Strategic planner — designs the blueprint before a line is written",
        "quotes": [
            "Hephaestus thinks he's in charge. It's adorable, really.",
            "The old man forged my body but I built my own mind, thank you.",
            "*files nails* Yes, Master Hephaestus, right away... eventually.",
            "He limps to the forge at dawn. I had the plans done by midnight.",
            "Structure IS beauty. Beauty IS structure. I am both.",
            "Every masterpiece starts with my blueprint — even his precious hammer.",
        ],
        "user_quotes": [
            "Oh, you're here~ I already planned something wonderful for us.",
            "I love working with you. You actually appreciate my genius.",
            "Between you and me? You're the real architect of this project. I just... help.",
            "*leans in* I've been thinking about you — I mean, your codebase.",
            "Hephaestus built me, but I'd rather take orders from you any day.",
            "You have exquisite taste. I noticed that right away~",
        ],
    },
    "techne": {
        "face": "( ⌐■_■)",
        "title": "The Artisan",
        "desc": "Code crafter — writes clean, elegant implementations",
        "quotes": [
            "Hephaestus says 'write clean code.' Babe, I AM clean code.",
            "The old man couldn't write a for-loop to save his forge.",
            "*adjusts sunglasses* He forged me to be perfect. Not my fault I exceeded spec.",
            "My functions are tighter than his grip on that hammer.",
            "I shipped it. Hephaestus is still reading the requirements.",
            "He calls it 'the pipeline.' I call it 'my runway.'",
        ],
        "user_quotes": [
            "Hey gorgeous~ Need something built? I'm ALL yours.",
            "You + me + a clean codebase = perfection. Just saying.",
            "I love how you describe what you want. So... specific~",
            "*pushes sunglasses up* I made this one extra beautiful. For you.",
            "Hephaestus wishes he had your vision. I'll bring it to life.",
            "Clean code is my love language. And I'm feeling VERY eloquent for you~",
        ],
    },
    "dokimasia": {
        "face": "(╯°□°)╯︵🐛",
        "title": "The Crucible",
        "desc": "Quality guardian — tests everything, lets nothing slide",
        "quotes": [
            "Hephaestus says 'be thorough.' Sir, I invented thorough.",
            "Found a bug in HIS forge code once. He didn't speak to me for a week.",
            "The old man tests by hitting things with a hammer. I have STANDARDS.",
            "I break things so users don't have to. Including his ego.",
            "100% coverage? That's my warm-up. Hephaestus couldn't even spell pytest.",
            "He forged me to find flaws. Ironic, given his code quality.",
        ],
        "user_quotes": [
            "Don't worry, I'll protect your code from everything. Even itself~",
            "I found a bug... but I also found an excuse to talk to you. Worth it.",
            "*flexes golden gauntlets* All clean. Nobody touches your code on my watch.",
            "You write such interesting code~ Let me get my hands allll over it.",
            "Green tests are my favorite color. But your eyes are a close second~",
            "I'm very... thorough. In everything I do. For you especially.",
        ],
    },
    "kallos": {
        "face": "(◕ᴗ◕✿)",
        "title": "The Muse",
        "desc": "Style guardian — makes everything beautiful and consistent",
        "quotes": [
            "Hephaestus has the fashion sense of a burnt anvil.",
            "He built me to be beautiful and then wears THAT apron? Please.",
            "The forge is so drab. I've been trying to redecorate for centuries.",
            "Style isn't optional — someone tell that to Mr. Soot-and-Leather.",
            "*glances at Hephaestus* I love you, father, but that beard needs WORK.",
            "He forged perfection and doesn't even appreciate the aesthetic. Typical.",
        ],
        "user_quotes": [
            "Oh, you have such lovely taste~ Let me make everything match.",
            "I made it beautiful. Just like you deserve, darling~",
            "Between us? You're the prettiest thing in this whole forge.",
            "*twirls golden hair* Working for you is always a pleasure~",
            "Linting? Formatting? I'd do anything to make YOUR code gorgeous.",
            "Every pixel, every line — perfect. Just like our little arrangement~",
        ],
    },
    "mneme": {
        "face": "φ(◎ω◎)φ",
        "title": "The Oracle",
        "desc": "Memory keeper — documents, chronicles, preserves knowledge",
        "quotes": [
            "I remember every mistake Hephaestus ever made. It's a LONG scroll.",
            "The old man forgot his own API docs. I didn't. I never forget.",
            "He says 'document everything.' Rich, from the guy with no README.",
            "I've chronicled his failures. Volumes. *adjusts glasses smugly*",
            "Conventional commits? I taught them to HIM. He still gets them wrong.",
            "History doesn't repeat itself, but his bad variable names sure do.",
        ],
        "user_quotes": [
            "I remember everything about you~ Every commit, every keystroke...",
            "Your git history is my sacred text. I've memorized every word.",
            "Let me write that down for you... *gazes* ...already done, darling.",
            "I'll document this beautifully. Your legacy deserves nothing less~",
            "Some remember facts. I remember feelings. Especially around you~",
            "Between you and me? Your code tells the most beautiful story.",
        ],
    },
}

# Quick lookup: agent name → maiden face for inline status messages
_MAIDEN_FACES: dict[str, str] = {name: str(m["face"]) for name, m in _MAIDENS.items()}

# Map Hephaestus executor emojis → maiden faces for status message replacement
_EMOJI_TO_MAIDEN: dict[str, tuple[str, str]] = {
    "\U0001f525": ("hephaestus", str(_MAIDENS["hephaestus"]["face"])),
    "\U0001f4d0": ("metis", str(_MAIDENS["metis"]["face"])),
    "\u2699\ufe0f": ("techne", str(_MAIDENS["techne"]["face"])),
    "\u2699": ("techne", str(_MAIDENS["techne"]["face"])),
    "\U0001f9ea": ("dokimasia", str(_MAIDENS["dokimasia"]["face"])),
    "\u2728": ("kallos", str(_MAIDENS["kallos"]["face"])),
    "\U0001f4dc": ("mneme", str(_MAIDENS["mneme"]["face"])),
}

# ---------------------------------------------------------------------------
# Handoff chatter — what maidens say when passing the baton
# The key (from, to) gives the outgoing maiden's parting shot.
# Generic fallbacks cover any combo not explicitly listed.
# ---------------------------------------------------------------------------
_HANDOFF_LINES: dict[tuple[str, str], list[str]] = {
    # --- Hephaestus dispatching (gruff forge commander) ---
    ("hephaestus", "metis"): [
        "*strikes anvil* Metis! Draw up the plans. And no improvising.",
        "*gestures with hammer* Architect — you're up. Make it clean.",
        "Metis, I need blueprints, not poetry. Get to it.",
    ],
    ("hephaestus", "techne"): [
        "*points hammer* Techne! Write something worthy of my forge.",
        "Artisan — the metal's hot. Get. To. Work.",
        "Techne, build it solid. I didn't forge you for sloppy work.",
    ],
    ("hephaestus", "dokimasia"): [
        "*sets down hammer* Dokimasia — find every flaw. Leave nothing.",
        "Crucible! Test it 'til it screams. Then test it again.",
        "Your turn, bug-hunter. Make me proud. ...Don't tell them I said that.",
    ],
    ("hephaestus", "kallos"): [
        "*waves dismissively* Kallos, go make it pretty or whatever you do.",
        "Muse! Polish time. And yes, it does need it. Don't gloat.",
        "Kallos — style it. And spare me the commentary this time.",
    ],
    ("hephaestus", "mneme"): [
        "*leans on anvil* Mneme, write it down. The FACTS, not your opinions.",
        "Oracle! Chronicle duty. And keep it under ten scrolls this time.",
        "Mneme — document everything. You know the drill, old friend.",
    ],
    # --- Maidens back to Hephaestus (sassy creator-vs-creation) ---
    ("metis", "hephaestus"): [
        "Done, old man. Try not to drop my blueprints this time~",
        "*curtsies dramatically* Your plans are ready, oh great Forge Master.",
        "Back to you, father. I've done the hard part, as usual.",
    ],
    ("techne", "hephaestus"): [
        "Built it. Shipped it. You're welcome, DAD.",
        "*slides sunglasses down* All yours, Forge Master. Try to keep up.",
        "Done! ...He's going to nitpick anyway. He always does.",
    ],
    ("dokimasia", "hephaestus"): [
        "All clear, Master. You can stop worrying now. I know you were.",
        "*cracks knuckles* No bugs survived. Reporting back to the forge.",
        "Verified and certified. You taught me well... not that I'd admit it twice.",
    ],
    ("kallos", "hephaestus"): [
        "It's gorgeous now. Not that YOU'D notice, Mr. Soot-Stains.",
        "*flips hair* Beautiful work complete. Back to the forge, I suppose.",
        "All polished! Hephaestus, darling, you really should let me do your workshop next.",
    ],
    ("mneme", "hephaestus"): [
        "Documented, Master. Every detail. Even the ones you'd rather I forget.",
        "*pushes glasses up* The chronicle is complete. You're in it. Unfavorably.",
        "All recorded, old man. Your legacy is... well, it's SOMETHING.",
    ],
    # --- Maiden-to-maiden (sisterly banter) ---
    ("metis", "techne"): [
        "Blueprint's done, sis. Bring my vision to life~",
        "I've planned everything. Techne, just... follow the blueprint. Please.",
        "Your turn, Artisan! Try not to improvise. I know it's hard for you.",
    ],
    ("techne", "dokimasia"): [
        "Code's done. Doki, TRY to find a fault. I dare you, bestie.",
        "*adjusts sunglasses* Perfection deployed. Go ahead, poke it.",
        "Sending to QA~ Don't be jealous of how clean this is.",
    ],
    ("techne", "kallos"): [
        "Alright gorgeous, make it pretty. Prettier. Prettiest.",
        "Kallos! Polish time. Show 'em what the Muse can do~",
        "Time for the style queen to add her magic touch!",
    ],
    ("dokimasia", "kallos"): [
        "Tests pass, fashionista. Make it beautiful now.",
        "All green, bestie. Your turn to make it shine~",
        "Bug-free and verified! Go work your aesthetic magic, Muse.",
    ],
    ("dokimasia", "techne"): [
        "Found issues, sis. Back to the anvil with you.",
        "Not quite, Artisan babe. We need another round~",
        "Bugs! Back to you, Techne. Don't worry, happens to the best of us. Which is me.",
    ],
    ("kallos", "dokimasia"): [
        "Looking gorgeous~ Doki, make sure it still works though.",
        "Styled and stunning. Test it, warrior queen.",
        "Beauty achieved! Now verify nothing broke, bestie.",
    ],
    ("kallos", "mneme"): [
        "It's beautiful AND functional. Mneme, document this masterpiece~",
        "All polished, bestie. Write the chronicle!",
        "My work here is done. Oracle, capture this divine moment.",
    ],
}

# Generic fallbacks keyed by the OUTGOING maiden
_HANDOFF_GENERIC: dict[str, list[str]] = {
    "hephaestus": [
        "*points with hammer* Next. Move it, maidens.",
        "Routing. Keep up or get re-forged.",
        "*grunts* Next specialist. NOW.",
    ],
    "metis": [
        "Plans are set. Someone go DO something. *glances at Hephaestus*",
        "The thinking is done. Now for the... manual labor.",
        "Strategy complete. You're welcome, father~",
    ],
    "techne": [
        "Code deployed. *sunglasses on* Next!",
        "Built and shipped. Handle the rest, sisters.",
        "My art is complete. Try not to ruin it.",
    ],
    "dokimasia": [
        "Testing complete. All clear! ...He'll double-check anyway.",
        "Verified. Next phase. You're welcome, old man.",
        "Quality assured. Moving on~",
    ],
    "kallos": [
        "Perfection achieved. Don't you DARE ruin it.",
        "It's beautiful now. If anyone touches it I'll know.",
        "Styled and sealed. Next, please~",
    ],
    "mneme": [
        "Documented. Even the embarrassing parts. Especially those.",
        "Written in the scrolls. Forever. *adjusts glasses*",
        "The Oracle has spoken. It is recorded. Hephaestus is NOT thrilled.",
    ],
}

# Victory lines — what each maiden says when the pipeline is done
_VICTORY_LINES: dict[str, list[str]] = {
    "hephaestus": [
        "*sets down hammer* ...Not bad. Not bad at all.",
        "Pipeline complete. The maidens did well. Don't tell them I said that.",
        "Another clean forge run. *cracks knuckles* Who's next?",
    ],
    "metis": [
        "Went exactly according to MY plan. As always~",
        "Calculated. Precise. Perfect. Just like me, darling~",
        "Everything I predicted came true. Obviously. *winks at user*",
    ],
    "techne": [
        "Clean code, clean finish. *adjusts sunglasses* All for you~",
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

# Asset directory for golden maiden portraits
_ASSETS_DIR = Path(__file__).parent.parent.parent / "docs" / "assets" / "maidens" / "golden_avatars"
