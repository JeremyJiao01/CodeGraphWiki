# Add a Feature

File checklists per scenario. Follow the layer rules in `contributing/architecture.md`.

All paths below are relative to `code_graph_builder/`.

---

## Adding a New Parser (L1)

1. `foundation/types/constants.py` -- add language to `SupportedLanguage` enum.
2. `foundation/parsers/language_spec.py` -- add `_<lang>_get_name`, `_<lang>_file_to_module`, and a `LanguageSpec` entry.
3. `foundation/parsers/factory.py` -- register the new language in `ProcessorFactory`.
4. `foundation/parsers/parser_loader.py` -- add grammar loading logic.
5. `pyproject.toml` -- add `tree-sitter-<lang>` dependency (core or `treesitter-full`).
6. `tests/foundation/test_<lang>.py` -- unit + integration tests.

**Layer rule:** Parsers (L1) may only import from L0. Do not import builder, embeddings, or MCP modules.

---

## Adding a New Database Backend (L1 + L2)

1. `foundation/services/<backend>_service.py` -- implement service matching `IngestorProtocol` (L1).
2. `foundation/services/__init__.py` -- export the new service.
3. `domains/core/graph/builder.py` -- wire the new backend as an option (L2).
4. `foundation/types/config.py` -- add config keys if needed (L0).
5. `tests/foundation/test_<backend>_service.py` -- tests.

**Layer rule:** Service module (L1) imports L0 only. Builder (L2) imports L0 + L1.

---

## Adding a New Embedding Model (L2)

1. `domains/core/embedding/<model>_embedder.py` -- implement embedder.
2. `domains/core/embedding/__init__.py` -- export.
3. `foundation/types/config.py` -- add model selection config (L0).
4. `tests/domains/core/test_embedder.py` -- add test cases.

**Layer rule:** Embeddings (L2) may import L0 and L1. Do not import rag, guidance, or MCP.

---

## Adding a New MCP Tool (L4)

1. `entrypoints/mcp/tools.py` -- add tool function.
2. `entrypoints/mcp/server.py` -- register the tool.
3. `tests/entrypoints/test_mcp_protocol.py` -- protocol-level test.
4. `tests/entrypoints/test_mcp_user_flow.py` -- user-flow test.

**Layer rule:** MCP (L4) may import any lower layer. Do not import CLI modules.

---

## Adding a New CLI Command (L4)

1. `entrypoints/cli/commands_cli.py` -- add command function.
2. `entrypoints/cli/cli.py` or `entrypoints/cli/cgb_cli.py` -- register the command.
3. `tests/entrypoints/test_cli_<command>.py` -- tests.

**Layer rule:** CLI (L4) may import any lower layer. Do not import MCP modules.

---

## Adding a Call Trace Feature (L3)

1. `domains/upper/calltrace/tracer.py` -- BFS tracing algorithm, data models.
2. `domains/upper/calltrace/formatter.py` -- tree text formatting.
3. `domains/upper/calltrace/wiki_writer.py` -- Wiki investigation worksheet generation.
4. `domains/core/search/graph_query.py` -- extend `GraphQueryService` if new query methods needed.
5. `entrypoints/mcp/tools.py` -- register MCP tool + handler.
6. `tests/domains/upper/calltrace/` -- unit tests for tracer, formatter, wiki_writer.

**Layer rule:** Calltrace (L3) imports L2 (`GraphQueryService`) only. Do not import MCP, CLI, or other L3 domains.

---

## Enhancing Function Pointer / Indirect Call Detection (L1)

1. `foundation/types/constants.py` -- add query/capture constants.
2. `foundation/types/models.py` -- add query field to `LanguageSpec` if new pattern.
3. `foundation/parsers/language_spec.py` -- add Tree-sitter query to target language spec.
4. `foundation/parsers/parser_loader.py` -- compile and register the new query.
5. `foundation/parsers/call_processor.py` -- add detection method.
6. `foundation/parsers/call_resolver.py` -- add resolution mapping if needed.
7. `domains/core/graph/graph_updater.py` -- wire into build pipeline.
8. `tests/foundation/parsers/test_func_ptr_detection.py` -- add test cases.

**Layer rule:** Parsers (L1) import L0 only. GraphUpdater (L2) calls L1 methods.

---

## Adding a RAG Feature (L3)

1. `domains/upper/rag/<feature>.py` -- implement feature.
2. `domains/upper/rag/__init__.py` -- export.
3. `domains/upper/rag/config.py` -- add config if needed.
4. `tests/domains/upper/test_rag.py` -- add test cases.

**Layer rule:** RAG (L3) may import L0, L1, L2. Do not import guidance, MCP, or CLI.

---

## Adding a Guidance Feature (L3)

1. `domains/upper/guidance/agent.py` -- implement or extend agent logic.
2. `domains/upper/guidance/toolset.py` -- add tool definitions.
3. `domains/upper/guidance/prompts.py` -- add prompt templates.
4. `tests/domains/upper/test_guidance.py` -- add test cases.

**Layer rule:** Guidance (L3) may import L0, L1, L2. Do not import rag, calltrace, MCP, or CLI.
