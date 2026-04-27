"""Unit tests for ``scripts/watch_protocols.py``.

The script's IO (httpx, gh CLI, file system) is wrapped in injectable
seams (``fetcher`` arg, ``dry_run`` flag, explicit state path) precisely
so the diff/digest/format logic can be tested without network or
issue-tracker calls. These tests cover the pure logic + a couple of
end-to-end shapes via subprocess for the entry point itself.
"""

from __future__ import annotations

import json

import pytest

# scripts/ is a real package (has __init__.py) — import via dotted path so
# `ty` static analysis can resolve it. Earlier draft used sys.path.insert
# + bare import which worked at runtime but tripped `ty unresolved-import`
# in CI.
from scripts import watch_protocols as wp


class TestDigesters:
    """Each ``kind`` has its own digester. The digest must be deterministic
    for unchanged content and the excerpt must give a human-readable hint."""

    def test_html_digest_is_stable_for_same_content(self):
        html = "<html><title>Hello</title><body>world</body></html>"
        d1, _ = wp._digest_html(html)
        d2, _ = wp._digest_html(html)
        assert d1 == d2

    def test_html_digest_changes_when_body_changes(self):
        d1, _ = wp._digest_html("<html><body>v1</body></html>")
        d2, _ = wp._digest_html("<html><body>v2</body></html>")
        assert d1 != d2

    def test_html_excerpt_includes_title_when_present(self):
        _, excerpt = wp._digest_html("<html><title>Spec</title><body>x</body></html>")
        assert "title: Spec" in excerpt
        assert "body[:400]" in excerpt

    def test_feed_digest_is_stable_for_same_entries(self):
        atom = (
            "<feed><title>Releases</title>"
            "<entry><title>v1.0</title></entry>"
            "<entry><title>v0.9</title></entry></feed>"
        )
        d1, _ = wp._digest_feed(atom)
        d2, _ = wp._digest_feed(atom)
        assert d1 == d2

    def test_feed_digest_changes_when_new_entry_appears(self):
        old = "<feed><title>Releases</title><entry><title>v0.9</title></entry></feed>"
        new = (
            "<feed><title>Releases</title>"
            "<entry><title>v1.0</title></entry>"
            "<entry><title>v0.9</title></entry></feed>"
        )
        assert wp._digest_feed(old)[0] != wp._digest_feed(new)[0]

    def test_feed_excerpt_lists_top_entries(self):
        atom = (
            "<feed><title>Releases</title>"
            "<entry><title>v1.0</title></entry>"
            "<entry><title>v0.9</title></entry></feed>"
        )
        _, excerpt = wp._digest_feed(atom)
        assert "v1.0" in excerpt
        assert "v0.9" in excerpt

    def test_pypi_digest_is_the_version_string(self):
        body = json.dumps(
            {
                "info": {"name": "a2a-sdk", "version": "0.3.26"},
                "releases": {"0.3.26": [{"upload_time": "2026-04-15T10:00:00"}]},
            }
        )
        digest, excerpt = wp._digest_pypi(body)
        assert digest == "0.3.26"
        assert "version: 0.3.26" in excerpt
        assert "uploaded: 2026-04-15" in excerpt

    def test_pypi_digest_changes_on_release(self):
        d1 = wp._digest_pypi(json.dumps({"info": {"version": "0.3.26"}, "releases": {}}))[0]
        d2 = wp._digest_pypi(json.dumps({"info": {"version": "0.3.27"}, "releases": {}}))[0]
        assert d1 != d2

    def test_pypi_handles_malformed_json(self):
        digest, excerpt = wp._digest_pypi("not json")
        assert digest == "<malformed>"
        assert "JSON decode failed" in excerpt

    def _docker_tags_response(
        self,
        tags: list[tuple[str, str, str]],
    ) -> str:
        """Build a Docker Hub tags JSON body.

        ``tags`` is a list of ``(name, last_updated, status)`` triples.
        """
        return json.dumps(
            {
                "count": len(tags),
                "next": None,
                "previous": None,
                "results": [
                    {"name": name, "last_updated": ts, "tag_status": status}
                    for name, ts, status in tags
                ],
            }
        )

    def test_docker_tag_digest_is_latest_stable_tag(self):
        body = self._docker_tags_response(
            [
                ("v10.5.0", "2026-04-26T21:13:00Z", "active"),
                ("v10.4.0", "2026-04-10T08:00:00Z", "active"),
                ("v10.3.0", "2026-03-22T11:30:00Z", "active"),
            ]
        )
        digest, excerpt = wp._digest_docker_tag(body)
        assert digest == "v10.5.0"
        assert "latest stable tag: v10.5.0" in excerpt
        assert "v10.4.0" in excerpt  # second candidate listed in the excerpt

    def test_docker_tag_skips_mutable_tag_names(self):
        """`latest`, `master`, `nightly` etc. should never be picked as the
        "latest release" — they always point at a moving stream and would
        either trigger drift on every cron tick or mask real version bumps.
        """
        body = self._docker_tags_response(
            [
                ("latest", "2026-04-27T00:00:00Z", "active"),
                ("master", "2026-04-27T00:00:00Z", "active"),
                ("nightly", "2026-04-27T00:00:00Z", "active"),
                ("v3.10.0-distroless", "2026-04-26T12:00:00Z", "active"),
            ]
        )
        digest, _ = wp._digest_docker_tag(body)
        assert digest == "v3.10.0-distroless"

    def test_docker_tag_skips_inactive_tags(self):
        """Deleted/withdrawn tags shouldn't be picked even if their
        ``last_updated`` is recent.
        """
        body = self._docker_tags_response(
            [
                ("v3.10.0", "2026-04-27T00:00:00Z", "deleted"),
                ("v3.9.5", "2026-04-15T00:00:00Z", "active"),
            ]
        )
        digest, _ = wp._digest_docker_tag(body)
        assert digest == "v3.9.5"

    def test_docker_tag_digest_changes_on_release(self):
        """The whole point of the watcher: when a new tag lands, the
        digest flips, and `diff_watches` opens an issue.
        """
        before = self._docker_tags_response([("v10.4.0", "2026-04-10T08:00:00Z", "active")])
        after = self._docker_tags_response(
            [
                ("v10.5.0", "2026-04-26T21:13:00Z", "active"),
                ("v10.4.0", "2026-04-10T08:00:00Z", "active"),
            ]
        )
        assert wp._digest_docker_tag(before)[0] != wp._digest_docker_tag(after)[0]

    def test_docker_tag_handles_malformed_json(self):
        digest, excerpt = wp._digest_docker_tag("not json")
        assert digest == "<malformed>"
        assert "JSON decode failed" in excerpt

    def test_docker_tag_handles_no_stable_tags(self):
        """If a registry response somehow contains only mutable tags (or
        is empty), don't crash — return a sentinel that's stable across
        runs so we don't spam the issue tracker on every tick.
        """
        body = self._docker_tags_response(
            [
                ("latest", "2026-04-27T00:00:00Z", "active"),
                ("master", "2026-04-27T00:00:00Z", "active"),
            ]
        )
        digest, excerpt = wp._digest_docker_tag(body)
        assert digest == "<no-stable-tag>"
        assert "no stable tag" in excerpt

    def test_docker_tag_skips_pr_build_artifacts(self):
        """Live smoke during M16 follow-on caught dozzle picking ``pr-4662``
        as the "latest tag" — a CI artifact, not a release. The semver-
        shaped filter rejects it; only ``v10.5.0`` survives as a real
        candidate.
        """
        body = self._docker_tags_response(
            [
                ("pr-4662", "2026-04-27T18:00:00Z", "active"),
                ("sha-abc123", "2026-04-27T17:00:00Z", "active"),
                ("v10.5.0", "2026-04-26T21:13:00Z", "active"),
            ]
        )
        digest, _ = wp._digest_docker_tag(body)
        assert digest == "v10.5.0"

    def test_docker_tag_skips_major_version_aliases(self):
        """Live smoke caught prometheus picking ``v3-distroless`` — the
        major-version alias that always points at the head of v3.x. The
        full-triplet semver filter rejects both major aliases (``v3``,
        ``v3-distroless``) and minor aliases (``v10.5``); only the full
        ``v3.10.0-distroless`` survives.
        """
        body = self._docker_tags_response(
            [
                ("v3-distroless", "2026-04-27T00:00:00Z", "active"),
                ("v3", "2026-04-27T00:00:00Z", "active"),
                ("v3.10.0-distroless", "2026-04-26T12:00:00Z", "active"),
            ]
        )
        digest, _ = wp._digest_docker_tag(body)
        assert digest == "v3.10.0-distroless"

    def test_docker_tag_skips_minor_stream_aliases(self):
        """Live smoke caught dozzle picking ``v10.5`` — the minor-stream
        alias re-pushed every time a 10.5.x patch lands. Its name stays
        the same across patches, so a name-only digest would never flip.
        Requiring a full ``MAJOR.MINOR.PATCH`` triplet keeps the digest
        responsive to every real release.
        """
        body = self._docker_tags_response(
            [
                ("v10.5", "2026-04-27T00:00:00Z", "active"),
                ("v10.5.0", "2026-04-26T21:13:00Z", "active"),
            ]
        )
        digest, _ = wp._digest_docker_tag(body)
        assert digest == "v10.5.0"


class TestDiffWatches:
    """``diff_watches`` is the pure core — the seam for testing the loop
    without HTTP, file system, or gh CLI."""

    def _watches(self):
        return (
            wp.Watch(key="alpha", url="https://example.com/alpha", kind="html", note="alpha note"),
            wp.Watch(key="beta", url="https://example.com/beta", kind="pypi", note="beta note"),
        )

    def test_initial_run_with_empty_state_emits_no_changes(self):
        # First time we see each URL — even though we record digests, no
        # diff exists to flag. The entire point: we don't open issues
        # for "we just started watching this."
        def fake_fetch(url):
            if "alpha" in url:
                return "<html><body>alpha v1</body></html>"
            return json.dumps({"info": {"version": "0.3.26"}, "releases": {}})

        changes, new_state = wp.diff_watches(self._watches(), {}, fake_fetch)
        assert changes == []
        assert "alpha" in new_state
        assert "beta" in new_state
        assert new_state["alpha"]["url"] == "https://example.com/alpha"
        assert new_state["beta"]["digest"] == "0.3.26"

    def test_unchanged_run_emits_no_changes(self):
        def fake_fetch(url):
            return "<html><body>same</body></html>"

        watches = (wp.Watch(key="alpha", url="https://x", kind="html", note=""),)
        # Seed state with the digest the same content produces.
        digest, _ = wp._digest_html("<html><body>same</body></html>")
        state = {"alpha": {"digest": digest, "url": "https://x", "checked_at": "old"}}

        changes, new_state = wp.diff_watches(watches, state, fake_fetch)
        assert changes == []
        # State is rewritten with a fresh checked_at but same digest.
        assert new_state["alpha"]["digest"] == digest

    def test_changed_run_emits_one_change_per_drifted_watch(self):
        def fake_fetch(url):
            if "alpha" in url:
                return "<html><body>NEW alpha</body></html>"
            return json.dumps({"info": {"version": "1.0.0"}, "releases": {}})

        # Seed state with OLD digests.
        old_alpha_digest, _ = wp._digest_html("<html><body>old alpha</body></html>")
        state = {
            "alpha": {
                "digest": old_alpha_digest,
                "url": "https://example.com/alpha",
                "checked_at": "old",
            },
            "beta": {"digest": "0.3.26", "url": "https://example.com/beta", "checked_at": "old"},
        }

        changes, _ = wp.diff_watches(self._watches(), state, fake_fetch)
        keys = {c.watch.key for c in changes}
        assert keys == {"alpha", "beta"}
        beta_change = next(c for c in changes if c.watch.key == "beta")
        assert beta_change.prior_digest == "0.3.26"
        assert beta_change.current_digest == "1.0.0"

    def test_fetch_failure_carries_prior_state_forward(self):
        # Transient HTTP error must NOT wipe the baseline — otherwise next
        # week's diff would be a noisy "first run."
        def fail_fetch(url):
            raise RuntimeError("network down")

        watches = (wp.Watch(key="alpha", url="https://x", kind="html", note=""),)
        state = {"alpha": {"digest": "abc123", "url": "https://x", "checked_at": "old"}}

        changes, new_state = wp.diff_watches(watches, state, fail_fetch)
        assert changes == []
        # Carried forward unchanged.
        assert new_state["alpha"] == state["alpha"]

    def test_fetch_failure_on_unseen_watch_skips_it(self):
        # No prior state for this key + fetch failed — don't add a
        # placeholder entry; next run will try fresh.
        def fail_fetch(url):
            raise RuntimeError("404")

        watches = (wp.Watch(key="alpha", url="https://x", kind="html", note=""),)
        changes, new_state = wp.diff_watches(watches, {}, fail_fetch)
        assert changes == []
        assert "alpha" not in new_state


class TestFormatIssueBody:
    """The body shape needs to be stable so future readers can grep for
    the canonical fields (prior_digest, current_digest, etc.)."""

    def test_body_contains_canonical_fields(self):
        change = wp.Change(
            watch=wp.Watch(key="alpha", url="https://x", kind="html", note="watch the alpha"),
            prior_digest="aaa",
            current_digest="bbb",
            excerpt="title: New release\nbody[:400]: details...",
            checked_at="2026-04-27T13:00:00+00:00",
        )
        body = wp.format_issue_body(change)
        assert "alpha" in body
        assert "https://x" in body
        assert "Prior digest" in body
        assert "aaa" in body
        assert "bbb" in body
        assert "watch the alpha" in body
        assert "Current excerpt" in body
        assert "M2" in body and "M7" in body  # triage path mentions ROADMAP items


class TestStateRoundtrip:
    """State load/save must be lossless and tolerant of missing/malformed files."""

    def test_load_missing_file_returns_empty_dict(self, tmp_path):
        assert wp.load_state(tmp_path / "nope.json") == {}

    def test_load_malformed_file_returns_empty_dict(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")
        assert wp.load_state(path) == {}

    def test_save_then_load_roundtrips(self, tmp_path):
        path = tmp_path / "state.json"
        state = {"alpha": {"digest": "abc", "url": "https://x", "checked_at": "now"}}
        wp.save_state(path, state)
        assert wp.load_state(path) == state

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "state.json"
        wp.save_state(path, {"k": {"digest": "v"}})
        assert path.exists()
        assert json.loads(path.read_text())["k"]["digest"] == "v"

    def test_save_is_atomic_via_tmp_then_rename(self, tmp_path):
        # Round-trip succeeds AND no .tmp file lingers afterward.
        path = tmp_path / "state.json"
        wp.save_state(path, {"a": {"digest": "1"}})
        wp.save_state(path, {"a": {"digest": "2"}})
        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == []
        assert json.loads(path.read_text())["a"]["digest"] == "2"


class TestOpenIssueDryRun:
    """Dry-run path prints to stdout and never invokes gh."""

    def test_dry_run_prints_body_and_does_not_subprocess(self, capsys, monkeypatch):
        called: list[list[str]] = []

        def spy_run(*args, **kwargs):
            called.append(args[0] if args else [])
            raise AssertionError("subprocess.run should not be called in dry-run mode")

        monkeypatch.setattr(wp.subprocess, "run", spy_run)

        change = wp.Change(
            watch=wp.Watch(key="alpha", url="https://x", kind="html", note="n"),
            prior_digest="old",
            current_digest="new",
            excerpt="excerpt content",
            checked_at="2026-04-27T13:00:00+00:00",
        )
        wp.open_issue(change, dry_run=True, repo="owner/repo")

        out = capsys.readouterr().out
        assert "DRY RUN ISSUE" in out
        assert "alpha" in out
        assert "old" in out and "new" in out
        assert called == []

    def test_no_repo_falls_back_to_dry_run_print(self, capsys, monkeypatch):
        # If GITHUB_REPOSITORY is unset (local invocation) we still
        # shouldn't try gh — fall through to the print path.
        def spy_run(*args, **kwargs):
            raise AssertionError("subprocess.run should not be called when repo is None")

        monkeypatch.setattr(wp.subprocess, "run", spy_run)

        change = wp.Change(
            watch=wp.Watch(key="alpha", url="https://x", kind="html", note="n"),
            prior_digest="old",
            current_digest="new",
            excerpt="excerpt",
            checked_at="2026-04-27T13:00:00+00:00",
        )
        wp.open_issue(change, dry_run=False, repo=None)
        out = capsys.readouterr().out
        assert "DRY RUN ISSUE" in out


class TestWatchesContract:
    """Defensive checks on the WATCHES list itself — shape mistakes here
    silently cause skipped watches at runtime."""

    def test_every_watch_key_is_unique(self):
        keys = [w.key for w in wp.WATCHES]
        assert len(keys) == len(set(keys)), "duplicate watch keys"

    def test_every_watch_kind_has_a_digester(self):
        for w in wp.WATCHES:
            assert w.kind in wp._DIGESTERS, f"{w.key} uses unregistered kind {w.kind!r}"

    def test_every_watch_url_starts_with_https(self):
        # No accidental http:// or relative URLs.
        for w in wp.WATCHES:
            assert w.url.startswith("https://"), f"{w.key} has non-https URL"

    def test_every_watch_has_non_empty_note(self):
        # Note lands in the issue body — empty note = unhelpful issue.
        for w in wp.WATCHES:
            assert w.note.strip(), f"{w.key} missing note"


@pytest.mark.parametrize("kind", ["html", "feed", "pypi", "docker-tag"])
def test_digester_returns_str_str(kind):
    """Defensive: every digester returns ``(str, str)`` so the loop's
    type assumptions hold even if a future digester author forgets."""
    digester = wp._DIGESTERS[kind]
    if kind == "pypi":
        digest, excerpt = digester(json.dumps({"info": {"version": "0.0.1"}, "releases": {}}))
    elif kind == "docker-tag":
        digest, excerpt = digester(
            json.dumps(
                {
                    "results": [
                        {
                            "name": "v1.0.0",
                            "last_updated": "2026-04-27T00:00:00Z",
                            "tag_status": "active",
                        }
                    ]
                }
            )
        )
    else:
        digest, excerpt = digester("<html><body>x</body></html>")
    assert isinstance(digest, str)
    assert isinstance(excerpt, str)
