"""Backwards-compatibility shim — imports from focused submodules.

Original monolith split into:
- gossip_models.py     — pure data containers (enums, dataclasses)
- gossip_chemistry.py  — pair metadata and chemistry lookup
- gossip_core.py       — main gossip API (sessions, rounds, responses)
- gossip_jealousy.py   — jealousy confrontation subsystem
"""

from kourai_common.gossip_chemistry import *  # noqa: F403
from kourai_common.gossip_chemistry import _normalize_pair  # noqa: F401
from kourai_common.gossip_core import *  # noqa: F403
from kourai_common.gossip_core import (  # noqa: F401
    _build_gossip_messages,
    _build_gossip_system_prompt,
)
from kourai_common.gossip_jealousy import *  # noqa: F403
from kourai_common.gossip_jealousy import (  # noqa: F401
    _generate_confrontation_text,
    _generate_jealousy_responses,
)
from kourai_common.gossip_models import *  # noqa: F403
