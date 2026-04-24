#!/usr/bin/env python3
"""Standalone CI indexing script — no Node.js required.

Builds a code knowledge graph, API docs, LLM descriptions, and semantic
embeddings for a repository, storing artifacts in ``{repo}/.terrain/``
so they can be committed and shipped with the repo.

Usage:
    python scripts/ci_index.py /path/to/repo
    python scripts/ci_index.py /path/to/repo --name "My Project"
    python scripts/ci_index.py /path/to/repo --no-embed --no-llm
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# =========================================================================
# CI 配置 — 在这里填写你的 API 凭据
# =========================================================================

# Embedding API（用于语义搜索向量化）
EMBEDDING_API_KEY = ""          # 填写你的 embedding API key
EMBEDDING_BASE_URL = ""         # 填写 embedding API base URL
EMBEDDING_MODEL = ""            # 填写 embedding 模型名称

# LLM API（用于自动生成函数描述）
LLM_API_KEY = ""                # 填写你的 LLM API key
LLM_BASE_URL = ""               # 填写 LLM API base URL
LLM_MODEL = ""                  # 填写 LLM 模型名称

# =========================================================================


def _inject_env() -> None:
    """将上方硬编码的配置注入环境变量，供 terrain 内部模块读取。"""
    env_map = {
        "DASHSCOPE_API_KEY": EMBEDDING_API_KEY,
        "DASHSCOPE_BASE_URL": EMBEDDING_BASE_URL,
        "EMBEDDING_MODEL": EMBEDDING_MODEL,
        "LLM_API_KEY": LLM_API_KEY,
        "LLM_BASE_URL": LLM_BASE_URL,
        "LLM_MODEL": LLM_MODEL,
    }
    for key, value in env_map.items():
        if value:
            os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build code index for CI pipelines (no Node.js needed)",
    )
    parser.add_argument("repo_path", help="Path to the repository to index")
    parser.add_argument("--name", default=None, help="Display name (default: directory name)")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM description generation")
    parser.add_argument("--backend", default="kuzu", choices=["kuzu", "memgraph", "memory"])
    args = parser.parse_args()

    # Inject hardcoded config into env before importing terrain modules
    _inject_env()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"ERROR: Path does not exist: {repo_path}")
        return 1

    custom_name = args.name or repo_path.name

    # Artifacts go into {repo}/.terrain/ for shipping with git
    artifact_dir = repo_path / ".terrain"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "graph.db"
    vectors_path = artifact_dir / "vectors.pkl"

    skip_embed = args.no_embed
    skip_llm = args.no_llm

    # Validate keys
    if not skip_embed and not EMBEDDING_API_KEY:
        print("WARNING: EMBEDDING_API_KEY is empty, embeddings will use DummyEmbedder (zero vectors)")
    if not skip_llm and not LLM_API_KEY:
        print("WARNING: LLM_API_KEY is empty, LLM descriptions will be skipped")
        skip_llm = True

    print(f"{'=' * 60}")
    print(f"  Terrain CI Index")
    print(f"  Repo:     {repo_path}")
    print(f"  Name:     {custom_name}")
    print(f"  Output:   {artifact_dir}")
    print(f"  Embed:    {'skip' if skip_embed else EMBEDDING_MODEL or 'auto-detect'}")
    print(f"  LLM:      {'skip' if skip_llm else LLM_MODEL or 'auto-detect'}")
    print(f"{'=' * 60}")
    print()

    t0 = time.monotonic()

    try:
        from terrain.entrypoints.mcp.pipeline import (
            build_graph,
            build_vector_index,
            generate_api_docs_step,
            generate_descriptions_step,
            save_meta,
        )

        # ----------------------------------------------------------
        # Step 1: Build graph
        # ----------------------------------------------------------
        print("[1/3] Building code graph...")
        builder = build_graph(
            repo_path,
            db_path,
            rebuild=True,
            progress_cb=lambda msg, pct: print(f"       {msg}"),
            backend=args.backend,
        )
        elapsed = time.monotonic() - t0
        print(f"  ✓ Graph built ({elapsed:.1f}s)")
        print()

        # ----------------------------------------------------------
        # Step 2: Generate API docs + LLM descriptions
        # ----------------------------------------------------------
        print("[2/3] Generating API docs...")
        generate_api_docs_step(
            builder,
            artifact_dir,
            rebuild=True,
            progress_cb=lambda msg, pct: print(f"       {msg}"),
            repo_path=repo_path,
        )
        elapsed = time.monotonic() - t0
        print(f"  ✓ API docs generated ({elapsed:.1f}s)")

        if not skip_llm:
            print("       LLM description generation...")
            desc_result = generate_descriptions_step(
                artifact_dir=artifact_dir,
                repo_path=repo_path,
                progress_cb=lambda msg, pct: print(f"       {msg}"),
            )
            count = desc_result.get("generated_count", 0)
            print(f"  ✓ LLM descriptions: {count} functions")
        print()

        # Save meta early so repo is discoverable even if embedding fails
        from terrain.foundation.services.git_service import GitChangeDetector
        head = GitChangeDetector().get_current_head(repo_path)
        save_meta(artifact_dir, repo_path, 0, last_indexed_commit=head, repo_name=custom_name)

        # ----------------------------------------------------------
        # Step 3: Build embeddings
        # ----------------------------------------------------------
        if not skip_embed:
            print("[3/3] Building embeddings...")
            build_vector_index(
                builder,
                repo_path,
                vectors_path,
                rebuild=True,
                progress_cb=lambda msg, pct: print(f"       {msg}"),
            )
            elapsed = time.monotonic() - t0
            print(f"  ✓ Embeddings built ({elapsed:.1f}s)")
            print()
        else:
            print("[3/3] Embeddings skipped (--no-embed)")
            print()

        # Final meta update
        save_meta(artifact_dir, repo_path, 0, last_indexed_commit=head, repo_name=custom_name)

        total = time.monotonic() - t0
        print(f"{'=' * 60}")
        print(f"  ✓ Index complete in {total:.1f}s")
        print(f"  Output: {artifact_dir}")
        print()
        print(f"  To ship with git:")
        print(f"    git add .terrain/")
        print(f"    git commit -m 'chore: update code index'")
        print(f"{'=' * 60}")
        return 0

    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return 130
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
