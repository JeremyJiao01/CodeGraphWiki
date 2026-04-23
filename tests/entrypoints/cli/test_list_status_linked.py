"""JER-102 — ``terrain list`` / ``terrain status`` rendering for linked repos.

Schema v2 (from JER-101) introduces two new meta.json fields:

* ``source_artifact`` on every *child* (linked-target) meta — reverse pointer
  to the authoritative artifact dir.
* ``linked_repos`` on the *source* (authoritative) meta — list of all repo
  mounts sharing this database.

Consumers (``_load_repos``, ``_get_repo_status_entries``) must now surface:

* a ``linked_source`` field on entries whose artifact is a child — so CLI
  ``list`` can render ``linked → <source_repo_name>`` and MCP
  ``list_repositories`` / ``get_repository_info`` can expose the pointer.
* a ``shared_count`` field on entries whose artifact is authoritative and
  has ``>=1`` linked_repos — so CLI ``status`` / ``list`` can display
  ``(shared by N repos)`` when ``N >= 2``.

Each linked child carries its own ``repo_path``, so the existing per-dir
loop already gives one status row per mount with its own
``GitChangeDetector`` result — no artificial expansion is needed.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from terrain.entrypoints.cli import cli as cli_mod
from terrain.foundation.utils.paths import normalize_repo_path


def _make_source_dir(ws: Path, artifact_name: str, repo: Path) -> Path:
    d = ws / artifact_name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "repo_path": normalize_repo_path(repo),
                "repo_name": repo.name,
                "indexed_at": "2026-04-23T00:00:00",
                "steps": {"graph": False, "api_docs": False,
                          "embeddings": False, "wiki": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return d


def _make_child_dir(ws: Path, artifact_name: str, repo: Path, source_dir: Path) -> Path:
    d = ws / artifact_name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source_artifact": source_dir.name,
                "linked_from": str(source_dir),
                "repo_path": normalize_repo_path(repo),
                "repo_name": repo.name,
                "linked_at": "2026-04-23T00:00:00",
                "indexed_at": "2026-04-23T00:00:00",
                "steps": {"graph": False, "api_docs": False,
                          "embeddings": False, "wiki": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return d


def _upsert_linked_repos(source_dir: Path, entries: list[dict]) -> None:
    meta = json.loads((source_dir / "meta.json").read_text(encoding="utf-8"))
    meta["linked_repos"] = entries
    (source_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class TestLoadReposExposesLinkage:
    def test_child_entry_carries_linked_source(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()

        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo_a = tmp_path / "origin_clone_a"
        child_repo_a.mkdir()

        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child_a = _make_child_dir(ws, "origin_bbbb2222", child_repo_a, source_dir)
        _upsert_linked_repos(source_dir, [
            {"repo_path": normalize_repo_path(child_repo_a),
             "repo_name": child_repo_a.name,
             "artifact_dir": child_a.name,
             "linked_at": "2026-04-23T00:00:00"},
        ])

        repos = cli_mod._load_repos(ws)
        by_name = {r["name"]: r for r in repos}

        # Child row exposes linked_source (source artifact's repo_name).
        child_entry = by_name[child_repo_a.name]
        assert child_entry.get("linked_source") == src_repo.name

        # Source row itself does not set linked_source (it's the authority).
        source_entry = by_name[src_repo.name]
        assert source_entry.get("linked_source") in (None, "")

    def test_source_entry_has_shared_count(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        repo_a = tmp_path / "clone_a"
        repo_a.mkdir()
        repo_b = tmp_path / "clone_b"
        repo_b.mkdir()

        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child_a = _make_child_dir(ws, "origin_bbbb2222", repo_a, source_dir)
        child_b = _make_child_dir(ws, "origin_cccc3333", repo_b, source_dir)
        _upsert_linked_repos(source_dir, [
            {"repo_path": normalize_repo_path(repo_a),
             "repo_name": repo_a.name, "artifact_dir": child_a.name,
             "linked_at": "2026-04-23T00:00:00"},
            {"repo_path": normalize_repo_path(repo_b),
             "repo_name": repo_b.name, "artifact_dir": child_b.name,
             "linked_at": "2026-04-23T00:00:00"},
        ])

        repos = cli_mod._load_repos(ws)
        by_name = {r["name"]: r for r in repos}
        assert by_name[src_repo.name]["shared_count"] == 2
        # Children carry a link pointer, not a shared_count.
        assert by_name[repo_a.name].get("shared_count") in (None, 0)


class TestGetRepoStatusEntriesLinkage:
    def test_each_linked_mount_yields_its_own_entry(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        repo_a = tmp_path / "clone_a"
        repo_a.mkdir()
        repo_b = tmp_path / "clone_b"
        repo_b.mkdir()

        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child_a = _make_child_dir(ws, "origin_bbbb2222", repo_a, source_dir)
        child_b = _make_child_dir(ws, "origin_cccc3333", repo_b, source_dir)
        _upsert_linked_repos(source_dir, [
            {"repo_path": normalize_repo_path(repo_a),
             "repo_name": repo_a.name, "artifact_dir": child_a.name,
             "linked_at": "2026-04-23T00:00:00"},
            {"repo_path": normalize_repo_path(repo_b),
             "repo_name": repo_b.name, "artifact_dir": child_b.name,
             "linked_at": "2026-04-23T00:00:00"},
        ])

        entries = cli_mod._get_repo_status_entries(ws)
        # One entry per artifact dir — three total.
        names = {e["artifact_dir"] for e in entries}
        assert names == {source_dir.name, child_a.name, child_b.name}

        # Each child entry reports its own repo_path (independent git probe).
        child_a_entry = next(e for e in entries if e["artifact_dir"] == child_a.name)
        child_b_entry = next(e for e in entries if e["artifact_dir"] == child_b.name)
        assert child_a_entry["path"] == normalize_repo_path(repo_a)
        assert child_b_entry["path"] == normalize_repo_path(repo_b)

        # Children surface a linked_source pointer for downstream display.
        assert child_a_entry.get("linked_source") == src_repo.name
        assert child_b_entry.get("linked_source") == src_repo.name

        # Source surfaces shared_count so CLI can annotate ``(shared by N)``.
        source_entry = next(e for e in entries if e["artifact_dir"] == source_dir.name)
        assert source_entry.get("shared_count") == 2

    def test_standalone_repo_has_no_linkage_fields(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        repo = tmp_path / "solo"
        repo.mkdir()
        _make_source_dir(ws, "solo_aaaa1111", repo)

        entries = cli_mod._get_repo_status_entries(ws)
        assert len(entries) == 1
        e = entries[0]
        assert e.get("linked_source") in (None, "")
        assert e.get("shared_count") in (None, 0)


class TestCmdListRendersLinkedArrow:
    def test_list_marks_child_with_linked_arrow(self, tmp_path: Path, monkeypatch):
        ws = tmp_path / "ws"
        ws.mkdir()

        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo = tmp_path / "origin_clone_a"
        child_repo.mkdir()

        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child = _make_child_dir(ws, "origin_bbbb2222", child_repo, source_dir)
        _upsert_linked_repos(source_dir, [
            {"repo_path": normalize_repo_path(child_repo),
             "repo_name": child_repo.name, "artifact_dir": child.name,
             "linked_at": "2026-04-23T00:00:00"},
        ])

        monkeypatch.setenv("TERRAIN_WORKSPACE", str(ws))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_mod.cmd_list(SimpleNamespace())
        assert rc == 0
        out = buf.getvalue()
        # The child row shows "linked → <source_repo_name>".
        assert f"linked → {src_repo.name}" in out

    def test_list_marks_authoritative_with_shared_count(self, tmp_path: Path, monkeypatch):
        ws = tmp_path / "ws"
        ws.mkdir()

        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        repo_a = tmp_path / "clone_a"
        repo_a.mkdir()
        repo_b = tmp_path / "clone_b"
        repo_b.mkdir()

        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child_a = _make_child_dir(ws, "origin_bbbb2222", repo_a, source_dir)
        child_b = _make_child_dir(ws, "origin_cccc3333", repo_b, source_dir)
        _upsert_linked_repos(source_dir, [
            {"repo_path": normalize_repo_path(repo_a),
             "repo_name": repo_a.name, "artifact_dir": child_a.name,
             "linked_at": "2026-04-23T00:00:00"},
            {"repo_path": normalize_repo_path(repo_b),
             "repo_name": repo_b.name, "artifact_dir": child_b.name,
             "linked_at": "2026-04-23T00:00:00"},
        ])

        monkeypatch.setenv("TERRAIN_WORKSPACE", str(ws))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_mod.cmd_list(SimpleNamespace())
        assert rc == 0
        out = buf.getvalue()
        assert "shared by 2" in out


class TestCmdStatusJsonExposesLinkage:
    def test_status_json_reports_linked_source_and_shared_count(
        self, tmp_path: Path, monkeypatch
    ):
        ws = tmp_path / "ws"
        ws.mkdir()

        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        repo_a = tmp_path / "clone_a"
        repo_a.mkdir()
        repo_b = tmp_path / "clone_b"
        repo_b.mkdir()

        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child_a = _make_child_dir(ws, "origin_bbbb2222", repo_a, source_dir)
        child_b = _make_child_dir(ws, "origin_cccc3333", repo_b, source_dir)
        _upsert_linked_repos(source_dir, [
            {"repo_path": normalize_repo_path(repo_a),
             "repo_name": repo_a.name, "artifact_dir": child_a.name,
             "linked_at": "2026-04-23T00:00:00"},
            {"repo_path": normalize_repo_path(repo_b),
             "repo_name": repo_b.name, "artifact_dir": child_b.name,
             "linked_at": "2026-04-23T00:00:00"},
        ])

        monkeypatch.setenv("TERRAIN_WORKSPACE", str(ws))
        buf = io.StringIO()
        ns = SimpleNamespace(json=True, debug=None)
        with redirect_stdout(buf):
            rc = cli_mod.cmd_status(ns)
        assert rc == 0
        payload = json.loads(buf.getvalue())
        by_dir = {e["artifact_dir"]: e for e in payload}

        assert by_dir[child_a.name]["linked_source"] == src_repo.name
        assert by_dir[child_b.name]["linked_source"] == src_repo.name
        assert by_dir[source_dir.name]["shared_count"] == 2
