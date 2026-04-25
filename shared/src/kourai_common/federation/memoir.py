"""Forge Memoir reader/writer.

The Memoir is the canonical record of one ForgeSession — a JSONL file
where each line is a `MemoirEntry`. Every entry has two faces: a
narrative beat the visual novel can replay, and a training tuple the
federated-learning pipeline can consume.

Append-only by contract. One host owns one Memoir at a time; no
cross-process coordination is provided in this iteration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from kourai_common.federation.memoir_schema import MemoirEntry


MEMOIR_FILENAME = "memoir.jsonl"


class MemoirError(Exception):
    """Raised on Memoir read/write failures."""


class Memoir:
    """Reader/writer for one ForgeSession's memoir.jsonl file."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = Path(workdir)
        self.path = self.workdir / MEMOIR_FILENAME

    def append(self, entry: MemoirEntry) -> None:
        if not self.workdir.is_dir():
            raise MemoirError(f"workdir {self.workdir} is not a directory")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json())
            f.write("\n")

    def entries(self) -> Iterator[MemoirEntry]:
        """Yield each entry from the on-disk file in append order.

        Returns an empty iterator if the file does not exist yet.
        """
        from kourai_common.federation.memoir_schema import MemoirEntry

        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield MemoirEntry.model_validate_json(stripped)
                except (json.JSONDecodeError, ValueError) as e:
                    raise MemoirError(f"malformed entry on line {line_number}: {e}") from e
