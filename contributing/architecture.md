# Architecture

## Layer Model

```
L0  foundation/types/                          Pure data: constants, types, config, models
L1  foundation/{parsers,services,utils}/       Shared infra: AST parsing, DB drivers, utilities
L2  domains/core/{graph,embedding,search}/     Core domains: graph build, embeddings, search
L3  domains/upper/{apidoc,calltrace,rag,guidance}/  Upper domains: API docs, call trace, RAG, guidance
L4  entrypoints/{mcp,cli}/                     Entry points: MCP server, CLI commands
```

### Mapping to Source Tree

All paths below are relative to `code_graph_builder/`.

| Layer | Source path(s) |
|-------|---------------|
| L0 | `foundation/types/constants.py`, `foundation/types/types.py`, `foundation/types/config.py`, `foundation/types/models.py` |
| L1 | `foundation/parsers/` (language_spec, parser_loader, factory, call_processor, call_resolver, definition_processor, import_processor, structure_processor, type_inference, utils), `foundation/services/` (kuzu_service, graph_service, git_service, memory_service), `foundation/utils/` (encoding, path_utils, settings) |
| L2 | `domains/core/graph/` (builder, graph_updater, incremental_updater), `domains/core/embedding/` (qwen3_embedder, vector_store), `domains/core/search/` (graph_query, semantic_search) |
| L3 | `domains/upper/apidoc/api_doc_generator.py`, `domains/upper/calltrace/` (tracer, formatter, wiki_writer), `domains/upper/rag/` (rag_engine, client, cypher_generator, llm_backend, markdown_generator, prompt_templates, camel_agent, config), `domains/upper/guidance/` (agent, prompts, toolset) |
| L4 | `entrypoints/mcp/` (server, tools, pipeline, file_editor), `entrypoints/cli/` (cli, cgb_cli, commands_cli) |

## Dependency Rules

| Layer | May import | Must NOT import |
|-------|-----------|-----------------|
| L0 | stdlib, third-party | Any project module |
| L1 | L0 | L2, L3, L4 |
| L2 | L0, L1 | L3, L4, other L2 domains |
| L3 | L0, L1, L2 | L4, other L3 domains |
| L4 | L0, L1, L2, L3 | Other L4 entrypoints |

**One-line rule:** Upper layers import lower layers. Never reverse. Never cross-domain at same layer.

## Enforcement

```bash
python tools/dep_check.py
```

Run before every commit. CI will reject violations.
