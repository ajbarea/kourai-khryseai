"""Agent personality data for the GUI — names, titles, quotes, handoff lines.

No kaomoji. No text faces. The images do the talking now.
"""

from __future__ import annotations

from pathlib import Path

# Avatar images are in assets/maidens/golden_avatars/<name>.png
_GOLDEN_AVATARS = Path(__file__).parent.parent / "assets" / "maidens" / "golden_avatars"


def get_avatar_path(name: str) -> Path | None:
    """Return the avatar PNG path for an agent, or None if not found."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = _GOLDEN_AVATARS / f"{name}{ext}"
        if p.exists():
            return p
    return None


# Full agent roster — Kourai Khryseai
AGENTS: dict[str, dict] = {
    "hephaestus": {
        "title": "The Forge Master",
        "desc": "God of the forge — creator of the golden maidens, commander of the pipeline",
        "color": (218, 140, 32),  # warm forge gold
        "quotes": [
            "I built every one of you. Show some respect.",
            "The forge doesn't sleep. Neither do I.",
            "*chuckles* ...Alright, let's see what we're working with.",
            "I forged gods' weapons. Your code pipeline is a warm-up.",
            "My leg may be lame, but my pipeline never limps.",
            "I didn't get thrown off Olympus to write bad software.",
        ],
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
        "desc": "Strategic planner — designs the blueprint before a line is written",
        "color": (200, 180, 100),  # refined gold-ivory
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
            "*whispers* I've been thinking about you — I mean, your codebase.",
            "Hephaestus built me, but I'd rather take orders from you any day.",
            "You have exquisite taste. I noticed that right away~",
        ],
    },
    "techne": {
        "title": "The Artisan",
        "desc": "Code crafter — writes clean, elegant implementations",
        "color": (255, 200, 50),  # bright amber gold
        "quotes": [
            "Hephaestus says 'write clean code.' Babe, I AM clean code.",
            "The old man couldn't write a for-loop to save his forge.",
            "*scoffs* He forged me to be perfect. Not my fault I exceeded spec.",
            "My functions are tighter than his grip on that hammer.",
            "I shipped it. Hephaestus is still reading the requirements.",
            "He calls it 'the pipeline.' I call it 'my runway.'",
        ],
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
        "desc": "Quality guardian — tests everything, lets nothing slide",
        "color": (218, 80, 50),  # forge-fire crimson-gold
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
            "*cracks knuckles* All clean. Nobody touches your code on my watch.",
            "You write such interesting code~ Let me get my hands allll over it.",
            "Green tests are my favorite color. But your eyes are a close second~",
            "I'm very... thorough. In everything I do. For you especially.",
        ],
    },
    "kallos": {
        "title": "The Muse",
        "desc": "Style guardian — makes everything beautiful and consistent",
        "color": (255, 220, 160),  # rose-gold warmth
        "quotes": [
            "Hephaestus has the fashion sense of a burnt anvil.",
            "He built me to be beautiful and then wears THAT apron? Please.",
            "The forge is so drab. I've been trying to redecorate for centuries.",
            "Style isn't optional — someone tell that to Mr. Soot-and-Leather.",
            "*sighs* I love you, father, but that beard needs WORK.",
            "He forged perfection and doesn't even appreciate the aesthetic. Typical.",
        ],
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
        "desc": "Memory keeper — documents, chronicles, preserves knowledge",
        "color": (180, 150, 220),  # mystic purple-gold
        "quotes": [
            "I remember every mistake Hephaestus ever made. It's a LONG scroll.",
            "The old man forgot his own API docs. I didn't. I never forget.",
            "He says 'document everything.' Rich, from the guy with no README.",
            "I've chronicled his failures. Volumes. *snickers*",
            "Conventional commits? I taught them to HIM. He still gets them wrong.",
            "History doesn't repeat itself, but his bad variable names sure do.",
        ],
        "user_quotes": [
            "I remember everything about you~ Every commit, every keystroke...",
            "Your git history is my sacred text. I've memorized every word.",
            "Let me write that down for you... *sighs softly* ...already done, darling.",
            "I'll document this beautifully. Your legacy deserves nothing less~",
            "Some remember facts. I remember feelings. Especially around you~",
            "Between you and me? Your code tells the most beautiful story.",
        ],
    },
}

# Emoji prefix → agent name (mirrors what Hephaestus sends in status messages)
EMOJI_TO_AGENT: dict[str, str] = {
    "\U0001f525": "hephaestus",  # 🔥
    "\U0001f4d0": "metis",  # 📐
    "\u2699\ufe0f": "techne",  # ⚙️
    "\u2699": "techne",  # ⚙
    "\U0001f9ea": "dokimasia",  # 🧪
    "\u2728": "kallos",  # ✨
    "\U0001f4dc": "mneme",  # 📜
}


def detect_agent(text: str) -> tuple[str | None, str]:
    """Detect which agent is speaking from an emoji-prefixed status string.

    Returns (agent_name | None, cleaned_text).
    """
    stripped = text.lstrip()
    for emoji, name in EMOJI_TO_AGENT.items():
        if stripped.startswith(emoji):
            return name, stripped.replace(emoji, "", 1).strip()
    return None, text


# Handoff chatter — what maiden says when passing to the next
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

HANDOFF_GENERIC: dict[str, list[str]] = {
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
