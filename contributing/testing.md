# Testing

## Test Structure

Tests mirror the source layout under `tests/`:

```
tests/
  foundation/              # L0 + L1 tests
    parsers/               # Parser-specific tests (func ptr, etc.)
    test_env_config.py     # reload_env, EMBED_* vars (fix 34a7ffc)
    test_kuzu_regression.py    # flush retry, get_statistics (fix eaf2abf, 157da26)
    test_c_ingestion_resilience.py  # per-function error isolation (fix 7be31d6)
  domains/
    core/                  # L2 tests (graph, embedding, search)
    upper/                 # L3 tests (apidoc, rag, guidance)
      calltrace/           # Call trace tests
      test_llm_response_parsing.py  # API response guards (fix 063594b)
  entrypoints/             # L4 tests (mcp, cli)
    test_windows_paths.py  # artifact_dir_for + _parse_repo_path (fix 0960c46, 75c3d7c)
    test_pickle_compat.py  # _CompatUnpickler old paths (fix c677270)
    test_mcp_server_guards.py  # _SKIP_SYNC_TOOLS, IO safety (fix bdc3d54, 2aa931b, d9362b2)
  test_dep_check.py        # Layer dependency checker
  test_regression_e2e.py   # Cross-layer regression tests
```

## Naming Conventions

- File: `test_<module>.py`
- Class: `Test<Feature>`
- Method: `test_<behavior>`

Example: `test_graph_build.py` / `TestGraphBuild` / `test_resolves_cross_file_calls`

## Run Commands

```bash
# Full suite
python -m pytest tests/ -v

# Single file
python -m pytest tests/domains/core/test_graph_build.py -v

# Single test
python -m pytest tests/domains/core/test_graph_build.py::TestGraphBuild::test_build -v

# By keyword
python -m pytest tests/ -k "embedding" -v
```

## Test Types

| Type | Scope | Example |
|------|-------|---------|
| Unit | Single function/class, no I/O | `foundation/test_types.py` |
| Regression | Targeted fix verification | `entrypoints/test_windows_paths.py`, `foundation/test_kuzu_regression.py` |
| Integration | Multiple modules, real DB | `domains/core/test_graph_build.py`, `domains/core/test_integration_semantic.py` |
| End-to-end | Full pipeline or MCP protocol | `entrypoints/test_mcp_protocol.py`, `entrypoints/test_mcp_e2e.py`, `test_regression_e2e.py` |

## GBK/GB2312 Encoding

Some test fixtures use GBK or GB2312 encoded files. If tests fail with encoding errors on your system:

- Ensure your locale supports these encodings.
- The `foundation/utils/encoding.py` module handles detection and conversion.
- Related tests verify that non-UTF-8 files are parsed correctly.

## Regression Guarantee

Every test added for a new feature automatically becomes part of the regression baseline.
`pytest` discovers all `test_*.py` files under `tests/` recursively, and CI runs the
full suite on every push and pull request. This means:

1. Your new tests **will** run on every future change — no extra registration needed.
2. If a later change breaks your feature, CI will catch it before merge.
3. Never delete or weaken an existing test to make a new feature pass. Fix the code instead.

## Impact-Based Testing

When your change touches files covered by specific test suites, you **must** run those tests locally before pushing. This is not optional — CI catches failures, but local testing catches them faster and avoids broken pushes.

All paths below are relative to `terrain/`.

| Changed Files | Required Tests | Command |
|---------------|---------------|---------|
| `foundation/parsers/call_processor.py` | func ptr detection | `pytest tests/foundation/parsers/test_func_ptr_detection.py -v` |
| `foundation/parsers/call_resolver.py` | func ptr detection | `pytest tests/foundation/parsers/test_func_ptr_detection.py -v` |
| `foundation/parsers/language_spec.py` | func ptr detection | `pytest tests/foundation/parsers/test_func_ptr_detection.py -v` |
| `foundation/parsers/parser_loader.py` | func ptr detection | `pytest tests/foundation/parsers/test_func_ptr_detection.py -v` |
| `foundation/types/constants.py` | func ptr + calltrace | `pytest tests/foundation/parsers/test_func_ptr_detection.py tests/domains/upper/calltrace/ -v` |
| `foundation/services/kuzu_service.py` | graph build | `pytest tests/domains/core/test_graph_build.py -v` |
| `foundation/services/graph_service.py` | graph build | `pytest tests/domains/core/test_graph_build.py -v` |
| `domains/core/graph/builder.py` | graph build | `pytest tests/domains/core/test_graph_build.py -v` |
| `domains/core/graph/graph_updater.py` | func ptr + graph build | `pytest tests/foundation/parsers/test_func_ptr_detection.py tests/domains/core/test_graph_build.py -v` |
| `domains/core/graph/incremental_updater.py` | incremental update | `pytest tests/domains/core/test_incremental_updater.py -v` |
| `domains/core/embedding/` | embedding | `pytest tests/domains/core/test_embedder.py tests/domains/core/test_step3_embedding.py -v` |
| `domains/core/search/graph_query.py` | calltrace | `pytest tests/domains/upper/calltrace/ -v` |
| `domains/core/search/semantic_search.py` | semantic search | `pytest tests/domains/core/test_integration_semantic.py -v` |
| `domains/upper/calltrace/` | calltrace | `pytest tests/domains/upper/calltrace/ -v` |
| `domains/upper/apidoc/` | api docs | `pytest tests/domains/upper/test_api_docs.py tests/domains/upper/test_api_find.py -v` |
| `domains/upper/rag/` | rag | `pytest tests/domains/upper/test_rag.py tests/domains/upper/test_client.py -v` |
| `entrypoints/mcp/tools.py` | MCP protocol + pickle compat | `pytest tests/entrypoints/ -v` |
| `entrypoints/mcp/pipeline.py` | MCP + CLI + Windows paths | `pytest tests/entrypoints/ -v` |
| `entrypoints/mcp/server.py` | MCP protocol + server guards | `pytest tests/entrypoints/ -v` |
| `entrypoints/cli/` | CLI + Windows path parsing | `pytest tests/entrypoints/ -v` |
| `foundation/services/kuzu_service.py` | Kuzu regression (flush retry, stats) | `pytest tests/foundation/test_kuzu_regression.py tests/domains/core/test_graph_build.py -v` |
| `foundation/parsers/definition_processor.py` | C ingestion resilience | `pytest tests/foundation/test_c_ingestion_resilience.py -v` |
| `foundation/utils/settings.py` | env config reload | `pytest tests/foundation/test_env_config.py -v` |
| `domains/upper/rag/client.py` | LLM response parsing | `pytest tests/domains/upper/test_llm_response_parsing.py -v` |

**Rule:** When adding new test files, add a row to this table mapping source files to the new tests. This keeps the impact map current.

## Pipeline Entry Point Consistency

`entrypoints/mcp/pipeline.py` is shared by both the MCP server and the CLI (`terrain index`, `terrain rebuild`). When modifying pipeline behavior, **both entry points must be validated**:

1. **MCP path** — run `python -m pytest tests/entrypoints/ -v`
2. **CLI path** — manually verify `terrain index <path>` and `terrain rebuild` complete without error

A change that only passes MCP tests may silently break the CLI, and vice versa. Both must be checked before merge.

## Before Submitting Checklist

1. `python tools/dep_check.py` -- zero violations.
2. `python -m pytest tests/ -v` -- all tests pass.
3. No new imports that violate layer rules (see `contributing/architecture.md`).
4. If your change touches files in the Impact-Based Testing table above, verify those specific tests pass locally before pushing.
