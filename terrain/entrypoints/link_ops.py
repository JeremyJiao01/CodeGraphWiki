"""JER-101 — ``terrain link`` schema v2 + N:1 (``linked_repos``).

Prior to v2, ``terrain link`` only wrote the *new* artifact's meta.json.
The authoritative (``source``) artifact never learned about its consumers,
so the data model couldn't express N repos sharing 1 database.

Schema v2 adds two fields:

* ``source_artifact`` — on every *linked-target* meta, the ``name`` of the
  authoritative artifact directory. Reverse pointer only.
* ``linked_repos``    — only on the *source* (authoritative) meta. List of
  ``{repo_path, repo_name, artifact_dir, linked_at}`` keyed by
  ``artifact_dir``. Idempotent under repeated ``terrain link`` calls.

``register_link`` writes both sides. ``migrate_meta_to_v2`` lazily upgrades
pre-v2 workspaces the first time CLI ``list``/``status`` or MCP
``list_repositories`` touches them.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from terrain.foundation.utils.paths import normalize_repo_path

SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _read_meta(meta_file: Path) -> dict[str, Any] | None:
    """Return parsed meta, or None if missing/corrupt."""
    if not meta_file.exists():
        return None
    try:
        return json.loads(meta_file.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def _atomic_write_meta(meta_file: Path, meta: dict[str, Any]) -> None:
    """Write meta.json atomically (tmp + rename)."""
    payload = json.dumps(meta, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".meta.", suffix=".tmp", dir=str(meta_file.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, meta_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _steps_for(artifact_dir: Path) -> dict[str, bool]:
    return {
        "graph": (artifact_dir / "graph.db").exists(),
        "api_docs": (artifact_dir / "api_docs" / "index.md").exists(),
        "embeddings": (artifact_dir / "vectors.pkl").exists(),
        "wiki": (artifact_dir / "wiki" / "index.md").exists(),
    }


# ---------------------------------------------------------------------------
# register_link — the single code path both CLI and MCP drive through
# ---------------------------------------------------------------------------

def register_link(
    ws: Path,
    *,
    source_dir: Path,
    target_dir: Path,
    repo_path: Any,
) -> None:
    """Link *target_dir* to *source_dir* for *repo_path*.

    * Writes ``target_dir/meta.json`` with ``source_artifact``,
      ``schema_version=2``, and never carries ``linked_repos`` over.
    * Upserts the corresponding entry in ``source_dir/meta.json``'s
      ``linked_repos`` list (keyed by ``artifact_dir``).

    The *ws* argument is accepted for future use (workspace-scoped logging
    or locks) and kept in the signature to match the PR-2 plan.
    """
    del ws  # reserved

    now = datetime.now().isoformat()
    canonical = normalize_repo_path(repo_path)
    repo_name = Path(str(repo_path)).name or "root"

    # ── Target side ───────────────────────────────────────────────────
    target_meta_file = target_dir / "meta.json"
    target_meta: dict[str, Any] = _read_meta(target_meta_file) or {}
    # Target meta must never claim authority over other links.
    target_meta.pop("linked_repos", None)

    target_meta.update({
        "schema_version": SCHEMA_VERSION,
        "source_artifact": source_dir.name,
        "linked_from": str(source_dir),  # kept for backward-compat readers
        "repo_path": canonical,
        "repo_name": repo_name,
        "linked_at": now,
        "steps": _steps_for(target_dir),
    })
    target_meta.setdefault("indexed_at", now)
    _atomic_write_meta(target_meta_file, target_meta)

    # ── Source side ───────────────────────────────────────────────────
    source_meta_file = source_dir / "meta.json"
    source_meta: dict[str, Any] = _read_meta(source_meta_file) or {}

    linked_repos = list(source_meta.get("linked_repos") or [])
    entry = {
        "repo_path": canonical,
        "repo_name": repo_name,
        "artifact_dir": target_dir.name,
        "linked_at": now,
    }
    replaced = False
    for i, existing in enumerate(linked_repos):
        if existing.get("artifact_dir") == target_dir.name:
            # Preserve original linked_at to keep the write idempotent.
            entry["linked_at"] = existing.get("linked_at", now)
            linked_repos[i] = entry
            replaced = True
            break
    if not replaced:
        linked_repos.append(entry)

    source_meta["schema_version"] = SCHEMA_VERSION
    source_meta["linked_repos"] = linked_repos
    _atomic_write_meta(source_meta_file, source_meta)


# ---------------------------------------------------------------------------
# migrate_meta_to_v2 — lazy upgrade for pre-v2 workspaces
# ---------------------------------------------------------------------------

def _source_artifact_for(meta: dict[str, Any]) -> str | None:
    """Extract the source artifact dir name from a v1 meta, if any."""
    if meta.get("source_artifact"):
        return str(meta["source_artifact"])
    for key in ("linked_from", "linked_to"):
        raw = meta.get(key)
        if raw:
            # legacy ``str(Path)`` — take the basename.
            return Path(str(raw)).name
    return None


def migrate_meta_to_v2(artifact_dir: Path, ws: Path) -> None:
    """Idempotently migrate ``artifact_dir/meta.json`` to schema v2.

    Cheap no-op when already v2. Writes atomically. Any failure to parse
    or write meta is swallowed — migration is best-effort; it must never
    break a read path.
    """
    meta_file = artifact_dir / "meta.json"
    meta = _read_meta(meta_file)
    if meta is None:
        return
    if meta.get("schema_version", 1) >= SCHEMA_VERSION:
        return

    # If this dir is itself a link target, just record source_artifact.
    pointer = _source_artifact_for(meta)
    if pointer:
        meta["source_artifact"] = pointer
        meta["schema_version"] = SCHEMA_VERSION
        try:
            _atomic_write_meta(meta_file, meta)
        except OSError:
            pass
        return

    # Otherwise it might be an authoritative source — reverse-scan siblings.
    linked_repos: list[dict[str, Any]] = []
    if ws.exists():
        self_name = artifact_dir.name
        for child in sorted(ws.iterdir()):
            if not child.is_dir() or child.name == self_name:
                continue
            child_meta = _read_meta(child / "meta.json")
            if child_meta is None:
                continue
            ptr = _source_artifact_for(child_meta)
            if ptr != self_name:
                continue
            linked_repos.append({
                "repo_path": normalize_repo_path(
                    child_meta.get("repo_path", child.name)
                ),
                "repo_name": child_meta.get("repo_name", child.name),
                "artifact_dir": child.name,
                "linked_at": child_meta.get(
                    "linked_at", child_meta.get("indexed_at", "")
                ),
            })

    meta["schema_version"] = SCHEMA_VERSION
    if linked_repos:
        meta["linked_repos"] = linked_repos
    try:
        _atomic_write_meta(meta_file, meta)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# unlink_artifact — symmetric teardown for register_link
# ---------------------------------------------------------------------------

class UnlinkError(Exception):
    """Raised when :func:`unlink_artifact` refuses or cannot complete."""


def _remove_child_tree(child_dir: Path) -> None:
    """Remove *child_dir* safely.

    Symlinks created by ``terrain link`` point at the authoritative source's
    data files — we must ``unlink()`` them, never ``rmtree()`` them, or
    we'd wipe the upstream data. On Windows (where ``terrain link`` falls
    back to ``copytree``), real copies are safe to ``rmtree``.
    """
    import shutil

    if not child_dir.exists() and not child_dir.is_symlink():
        return

    for entry in sorted(child_dir.iterdir()):
        # Symlink check must come before is_dir() — is_dir() on a symlink
        # follows the link and would report True for a dir symlink.
        if entry.is_symlink():
            entry.unlink()
        elif entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    child_dir.rmdir()


def unlink_artifact(ws: Path, target: str) -> dict[str, Any]:
    """Tear down a link created by :func:`register_link`.

    *target* is either:
      * an absolute/relative repo path (matched against ``repo_path`` in
        every meta, after normalization), or
      * a workspace artifact dir basename.

    Returns a dict describing the teardown::

        {
            "artifact_dir": "<child dir name>",
            "repo_path":    "<canonical repo path>",
            "source_artifact": "<source dir name>",
            "cleared_active": bool,
        }

    Raises :class:`UnlinkError` when:
      * the target cannot be found in *ws*,
      * the target resolves to the authoritative source (refuses to tear
        down the upstream DB — only children may be unlinked).
    """
    if not ws.exists():
        raise UnlinkError(f"Workspace does not exist: {ws}")

    # Build an in-memory index of every dir's meta so we can match both by
    # artifact name and by repo_path — and so we can find the source ptr
    # without a second read.
    metas: dict[str, dict[str, Any]] = {}
    for child in sorted(ws.iterdir()):
        if not child.is_dir():
            continue
        m = _read_meta(child / "meta.json")
        if m is not None:
            metas[child.name] = m

    child_name: str | None = None

    # Direct artifact_dir hit.
    if target in metas:
        child_name = target
    else:
        # Try matching by normalized repo_path.
        try:
            canonical = normalize_repo_path(target)
        except (TypeError, ValueError):
            canonical = None
        if canonical is not None:
            for name, meta in metas.items():
                meta_path = meta.get("repo_path")
                if not meta_path:
                    continue
                try:
                    meta_canonical = normalize_repo_path(meta_path)
                except (TypeError, ValueError):
                    meta_canonical = str(meta_path)
                if meta_canonical == canonical:
                    child_name = name
                    break

    if child_name is None:
        raise UnlinkError(
            f"Not found in workspace: {target}. "
            "Pass an artifact dir basename or a linked repo path."
        )

    child_meta = metas[child_name]
    source_name = child_meta.get("source_artifact")
    if not source_name:
        raise UnlinkError(
            f"{child_name} is not a linked child artifact "
            "(no source_artifact). Refusing to unlink the authoritative "
            "source. Use `terrain clean` to fully remove an artifact."
        )

    child_dir = ws / child_name
    source_dir = ws / str(source_name)

    # Remove the child entry from the source meta's linked_repos (idempotent).
    source_meta = metas.get(str(source_name)) or _read_meta(source_dir / "meta.json")
    if source_meta is not None:
        remaining = [
            e for e in (source_meta.get("linked_repos") or [])
            if e.get("artifact_dir") != child_name
        ]
        source_meta["schema_version"] = SCHEMA_VERSION
        source_meta["linked_repos"] = remaining
        try:
            _atomic_write_meta(source_dir / "meta.json", source_meta)
        except OSError:
            pass

    # Clear active.txt if we're tearing down the active artifact.
    cleared_active = False
    active_file = ws / "active.txt"
    if active_file.exists():
        try:
            active_name = active_file.read_text(
                encoding="utf-8", errors="replace"
            ).strip()
        except OSError:
            active_name = ""
        if active_name == child_name:
            try:
                active_file.write_text("", encoding="utf-8")
                cleared_active = True
            except OSError:
                pass

    # Finally remove the child artifact dir itself.
    _remove_child_tree(child_dir)

    return {
        "artifact_dir": child_name,
        "repo_path": child_meta.get("repo_path"),
        "source_artifact": str(source_name),
        "cleared_active": cleared_active,
    }


__all__ = [
    "SCHEMA_VERSION",
    "UnlinkError",
    "register_link",
    "migrate_meta_to_v2",
    "unlink_artifact",
]
