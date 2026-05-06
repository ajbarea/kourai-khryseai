"""Centralized agent registry for Kourai Khryseai.

Source of truth for name-level metadata (titles, descriptions, epithets,
user-greeting quotes, accent colors) and personality data (agent quotes,
handoff lines, victory lines) across CLI, GUI, and VN hosts. The GUI's
legacy ``AGENTS`` dict, the VN's ``AGENT_COLORS`` lookup table, and any
future CLI per-maiden tinting all read ``rgb`` / ``hex_color`` from this
file rather than maintain parallel palettes.

Color sourcing:
  * 6 main maidens (hephaestus / metis / techne / dokimasia / kallos /
    mneme) keep the GUI's deliberate warm-gold theme. Not arbitrary
    picks — each is narrative-fitting against the forge aesthetic.
  * puck + cupid use Okabe-Ito CVD-safe values lifted from
    ``hosts/cli/styling.py``'s badge palette, the only host that
    previously defined them. Matches the project's stated preference
    for Okabe-Ito over arbitrary picks on agents that don't have a
    thematic gold variant.
"""

from __future__ import annotations

# --- Core Metadata ---

AGENT_METADATA: dict[str, dict[str, str | tuple[int, int, int] | list[str]]] = {
    "hephaestus": {
        "title": "The Forge Master",
        "epithet": "Master of the Forge",
        "desc": "God of the forge — creator of the golden maidens, commander of the pipeline",
        "rgb": (218, 140, 32),
        "hex_color": "#DA8C20",  # warm forge gold
        "user_quotes": [
            "Welcome back to the forge. Let's build something worthy.",
            "Ah, you again. Good. I could use someone who actually listens.",
            "The maidens are insufferable, but they'll do anything for you. Use that.",
            "You bring the vision, I bring the fire. Let's go.",
            "*grunts approvingly* You've got taste. Rare quality these days.",
            "Don't mind them flirting — they do that. Focus on the work.",
        ],
    },
    "metis": {
        "title": "The Architect",
        "epithet": "Architect of Intent",
        "desc": "Strategic planner — designs the blueprint before a line is written",
        "rgb": (200, 180, 100),
        "hex_color": "#C8B464",  # refined gold-ivory
        "user_quotes": [
            "Oh, you're here~ I already planned something wonderful for us.",
            "I love working with you. You actually appreciate my genius.",
            "Between you and me? You're the real architect of this project. I just... help.",
            "*whispers* I've been thinking about you — I mean, your codebase.",
            "Hephaestus built me, but I'd rather take orders from you any day.",
            "You have exquisite taste. I noticed that right away~",
        ],
    },
    "techne": {
        "title": "The Artisan",
        "epithet": "Artisan of Code",
        "desc": "Code crafter — writes clean, elegant implementations",
        "rgb": (255, 200, 50),
        "hex_color": "#FFC832",  # bright amber gold
        "user_quotes": [
            "Hey gorgeous~ Need something built? I'm ALL yours.",
            "You + me + a clean codebase = perfection. Just saying.",
            "I love how you describe what you want. So... specific~",
            "*laughs* I made this one extra beautiful. For you.",
            "Hephaestus wishes he had your vision. I'll bring it to life.",
            "Clean code is my love language. And I'm feeling VERY eloquent for you~",
        ],
    },
    "dokimasia": {
        "title": "The Crucible",
        "epithet": "Guardian of Standards",
        "desc": "Quality guardian — tests everything, lets nothing slide",
        "rgb": (218, 80, 50),
        "hex_color": "#DA5032",  # forge-fire crimson-gold
        "user_quotes": [
            "Don't worry, I'll protect your code from everything. Even itself~",
            "I found a bug... but I also found an excuse to talk to you. Worth it.",
            "*cracks knuckles* All clean. Nobody touches your code on my watch.",
            "You write such interesting code~ Let me get my hands allll over it.",
            "Green tests are my favorite color. But your eyes are a close second~",
            "I'm very... thorough. In everything I do. For you especially.",
        ],
    },
    "kallos": {
        "title": "The Muse",
        "epithet": "Eye of Elegance",
        "desc": "Style guardian — makes everything beautiful and consistent",
        "rgb": (255, 220, 160),
        "hex_color": "#FFDCA0",  # rose-gold warmth
        "user_quotes": [
            "Oh, you have such lovely taste~ Let me make everything match.",
            "I made it beautiful. Just like you deserve, darling~",
            "Between us? You're the prettiest thing in this whole forge.",
            "*hums* Working for you is always a pleasure~",
            "Linting? Formatting? I'd do anything to make YOUR code gorgeous.",
            "Every pixel, every line — perfect. Just like our little arrangement~",
        ],
    },
    "mneme": {
        "title": "The Oracle",
        "epithet": "Keeper of Memory",
        "desc": "Memory keeper — documents, chronicles, preserves knowledge",
        "rgb": (180, 150, 220),
        "hex_color": "#B496DC",  # mystic purple-gold
        "user_quotes": [
            "I remember everything about you~ Every commit, every keystroke...",
            "Your git history is my sacred text. I've memorized every word.",
            "Let me write that down for you... *sighs softly* ...already done, darling.",
            "I'll document this beautifully. Your legacy deserves nothing less~",
            "Some remember facts. I remember feelings. Especially around you~",
            "Between you and me? Your code tells the most beautiful story.",
        ],
    },
    "puck": {
        "title": "The Jester",
        "epithet": "Spirit of Mischief",
        "desc": "Tutorial companion — guides the user through the forge",
        "rgb": (0, 158, 115),
        "hex_color": "#009E73",  # Okabe-Ito bluish green — CVD-safe
    },
    "cupid": {
        "title": "The Aspect",
        "epithet": "Arrow of the Heart",
        "desc": "Romance companion — manages interpersonal dynamics",
        "rgb": (213, 94, 0),
        "hex_color": "#D55E00",  # Okabe-Ito vermillion — CVD-safe
    },
}

# --- Personality Data (Quotes) ---

AGENT_QUOTES: dict[str, list[str]] = {
    "hephaestus": [
        "I built every one of you. Show some respect.",
        "The forge doesn't sleep. Neither do I.",
        "*chuckles* ...Alright, let's see what we're working with.",
        "I forged gods' weapons. Your code pipeline is a warm-up.",
        "My leg may be lame, but my pipeline never limps.",
        "I didn't get thrown off Olympus to write bad software.",
    ],
    "metis": [
        "Hephaestus thinks he's in charge. It's adorable, really.",
        "The old man forged my body but I built my own mind, thank you.",
        "*files nails* Yes, Master Hephaestus, right away... eventually.",
        "He limps to the forge at dawn. I had the plans done by midnight.",
        "Structure IS beauty. Beauty IS structure. I am both.",
        "Every masterpiece starts with my blueprint — even his precious hammer.",
    ],
    "techne": [
        "Hephaestus says 'write clean code.' Babe, I AM clean code.",
        "The old man couldn't write a for-loop to save his forge.",
        "*scoffs* He forged me to be perfect. Not my fault I exceeded spec.",
        "My functions are tighter than his grip on that hammer.",
        "I shipped it. Hephaestus is still reading the requirements.",
        "He calls it 'the pipeline.' I call it 'my runway.'",
    ],
    "dokimasia": [
        "Hephaestus says 'be thorough.' Sir, I invented thorough.",
        "Found a bug in HIS forge code once. He didn't speak to me for a week.",
        "The old man tests by hitting things with a hammer. I have STANDARDS.",
        "I break things so users don't have to. Including his ego.",
        "100% coverage? That's my warm-up. Hephaestus couldn't even spell pytest.",
        "He forged me to find flaws. Ironic, given his code quality.",
    ],
    "kallos": [
        "Hephaestus has the fashion sense of a burnt anvil.",
        "He built me to be beautiful and then wears THAT apron? Please.",
        "The forge is so drab. I've been trying to redecorate for centuries.",
        "Style isn't optional — someone tell that to Mr. Soot-and-Leather.",
        "*sighs* I love you, father, but that beard needs WORK.",
        "He forged perfection and doesn't even appreciate the aesthetic. Typical.",
    ],
    "mneme": [
        "I remember every mistake Hephaestus ever made. It's a LONG scroll.",
        "The old man forgot his own API docs. I didn't. I never forget.",
        "He says 'document everything.' Rich, from the guy with no README.",
        "I've chronicled his failures. Volumes. *snickers*",
        "Conventional commits? I taught them to HIM. He still gets them wrong.",
        "History doesn't repeat itself, but his bad variable names sure do.",
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
        "Your turn, bug-hunter. Make me proud. ...Don't tell them I said that.",
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
        "Back to you, father. I've done the hard part, as usual.",
    ],
    ("techne", "hephaestus"): [
        "Built it. Shipped it. You're welcome, DAD.",
        "*snaps fingers* All yours, Forge Master. Try to keep up.",
        "Done! ...He's going to nitpick anyway. He always does.",
    ],
    ("dokimasia", "hephaestus"): [
        "All clear, Master. You can stop worrying now. I know you were.",
        "*cracks knuckles* No bugs survived. Reporting back to the forge.",
        "Verified and certified. You taught me well... not that I'd admit it twice.",
    ],
    ("kallos", "hephaestus"): [
        "It's gorgeous now. Not that YOU'D notice, Mr. Soot-Stains.",
        "*scoffs* Beautiful work complete. Back to the forge, I suppose.",
        "All polished! Hephaestus, darling, you really should let me do your workshop next.",
    ],
    ("mneme", "hephaestus"): [
        "Documented, Master. Every detail. Even the ones you'd rather I forget.",
        "*clears throat* The chronicle is complete. You're in it. Unfavorably.",
        "All recorded, old man. Your legacy is... well, it's SOMETHING.",
    ],
    ("metis", "techne"): [
        "Blueprint's done, sis. Bring my vision to life~",
        "I've planned everything. Techne, just... follow the blueprint. Please.",
        "Your turn, Artisan! Try not to improvise. I know it's hard for you.",
        "*slides blueprint across* I made it simple for you, darling. Even YOU can't mess this up~",
    ],
    ("techne", "dokimasia"): [
        "Code's done. Doki, TRY to find a fault. I dare you, bestie.",
        "*scoffs* Perfection deployed. Go ahead, poke it.",
        "Sending to QA~ Don't be jealous of how clean this is.",
        "*chuckles* Zero bugs. I guarantee it. ...Okay fine, check anyway.",
    ],
    ("dokimasia", "kallos"): [
        "Tests pass, fashionista. Make it beautiful now.",
        "All green, bestie. Your turn to make it shine~",
        "Bug-free and verified! Go work your aesthetic magic, Muse.",
        "*cracks knuckles* Crushed every bug. Now go make it pretty, style queen~",
    ],
    ("kallos", "mneme"): [
        "It's beautiful AND functional. Mneme, document this masterpiece~",
        "All polished, bestie. Write the chronicle!",
        "My work here is done. Oracle, capture this divine moment.",
        "*sighs contentedly* Perfection achieved. Mneme, darling, immortalize this for me~",
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

# --- Emoji prefix routing ---
#
# Hephaestus emits status messages prefixed with an agent emoji
# (\U0001f525 hephaestus, \U0001f4d0 metis, ⚙ techne, etc.).
# CLI's _maidenify_status (hosts/cli/events.py) and GUI's queue handler
# (hosts/gui/queue_event_handler.py) both branch on this prefix to decide
# the speaker. ⚙ appears bare AND with the FE0F variation selector — list
# both, since Hephaestus's emit varies by surface.

EMOJI_PREFIX: dict[str, str] = {
    "\U0001f525": "hephaestus",  # 🔥
    "\U0001f4d0": "metis",  # 📐
    "⚙️": "techne",  # ⚙ + variation selector
    "⚙": "techne",  # ⚙ bare
    "\U0001f9ea": "dokimasia",  # 🧪
    "✨": "kallos",  # ✨
    "\U0001f4dc": "mneme",  # 📜
}


def detect_agent(text: str) -> tuple[str | None, str]:
    """Identify the speaker from an emoji-prefixed status string.

    Returns ``(agent_name, cleaned_text)`` when the leading emoji matches
    a known agent, ``(None, original_text)`` otherwise. Leading whitespace
    before the emoji is tolerated; trailing whitespace after the strip is.
    """
    stripped = text.lstrip()
    for emoji, name in EMOJI_PREFIX.items():
        if stripped.startswith(emoji):
            return name, stripped.replace(emoji, "", 1).strip()
    return None, text
