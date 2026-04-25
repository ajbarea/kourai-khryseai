"""Memoir reader/writer scoped to one ForgeSession workdir."""

from __future__ import annotations

import pytest

from kourai_common.federation.memoir import Memoir, MemoirError
from kourai_common.federation.memoir_schema import (
    EntrySource,
    MemoirEntry,
)


class TestMemoirAppend:
    """Append-only writes produce one JSON-encoded line per entry."""

    def test_append_creates_file(self, tmp_path):
        memoir = Memoir(tmp_path)
        entry = MemoirEntry(
            scene_id="s1.t1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="x",
        )
        memoir.append(entry)
        assert (tmp_path / "memoir.jsonl").exists()

    def test_append_writes_one_line_per_entry(self, tmp_path):
        memoir = Memoir(tmp_path)
        for i in range(3):
            memoir.append(
                MemoirEntry(
                    scene_id=f"s1.t{i}",
                    agent="kallos",
                    source=EntrySource.SPECIALIST_PROPOSED,
                    agent_proposed=f"x{i}",
                )
            )
        contents = (tmp_path / "memoir.jsonl").read_text()
        lines = contents.strip().split("\n")
        assert len(lines) == 3

    def test_append_does_not_truncate(self, tmp_path):
        m1 = Memoir(tmp_path)
        m1.append(
            MemoirEntry(
                scene_id="s1.t1",
                agent="kallos",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed="first",
            )
        )

        m2 = Memoir(tmp_path)
        m2.append(
            MemoirEntry(
                scene_id="s1.t2",
                agent="kallos",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed="second",
            )
        )

        contents = (tmp_path / "memoir.jsonl").read_text()
        assert "first" in contents
        assert "second" in contents

    def test_append_to_missing_directory_raises(self, tmp_path):
        bogus = tmp_path / "does_not_exist"
        memoir = Memoir(bogus)
        with pytest.raises(MemoirError, match="not a directory"):
            memoir.append(
                MemoirEntry(
                    scene_id="s1.t1",
                    agent="kallos",
                    source=EntrySource.SPECIALIST_PROPOSED,
                    agent_proposed="x",
                )
            )


class TestMemoirRead:
    """`entries()` yields one MemoirEntry per JSONL line, preserving order."""

    def test_empty_memoir_yields_nothing(self, tmp_path):
        memoir = Memoir(tmp_path)
        assert list(memoir.entries()) == []

    def test_round_trip_preserves_order(self, tmp_path):
        memoir = Memoir(tmp_path)
        originals = [
            MemoirEntry(
                scene_id=f"s1.t{i}",
                agent="kallos",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed=f"x{i}",
            )
            for i in range(5)
        ]
        for entry in originals:
            memoir.append(entry)

        restored = list(memoir.entries())
        assert restored == originals

    def test_round_trip_preserves_split(self, tmp_path):
        memoir = Memoir(tmp_path)
        cupid_entry = MemoirEntry(
            scene_id="s1.cupid",
            agent="cupid",
            source=EntrySource.CUPID_SCENE,
            narrative_beat="cupid_check_in",
        )
        kallos_entry = MemoirEntry(
            scene_id="s1.kallos",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="lint fix",
        )
        memoir.append(cupid_entry)
        memoir.append(kallos_entry)

        restored = list(memoir.entries())
        assert restored[0].split.private_only is True
        assert restored[1].split.shared_eligible is True

    def test_malformed_line_raises(self, tmp_path):
        memoir = Memoir(tmp_path)
        memoir.path.write_text("not valid json\n")
        with pytest.raises(MemoirError, match="malformed"):
            list(memoir.entries())
