Generate a structured implementation plan for a feature described in the design document below, by researching the indexed codebase through MCP tools.

**Input:** $ARGUMENTS (path to design document, or inline design text)

---

## Pre-flight

Call `get_repository_info` to verify the active repository has all services available:
- graph: true
- api_docs: true
- embeddings: true

If any service is missing, stop and say:
> "Repository index is incomplete. Please run `/repo-init <repo-path>` first."

If the input is a file path, read the file. Otherwise treat $ARGUMENTS as the design text.

---

## Phase 1: Concept Extraction (no tool calls)

Read the design document and extract:

- **Functional concepts** — capability keywords (e.g. "serial init", "fault registration", "timer callback")
- **Entity names** — specific module/function/type names mentioned
- **Action verbs** — init, register, callback, poll, etc. — these hint at which interface patterns to search

Produce 2-8 concepts. Each concept is a search keyword for Phase 2.

---

## Phase 2: Broad Search

For each concept from Phase 1, call:

```
find_api(query="<concept keyword>", top_k=5)
```

From the results:
- Keep semantically relevant matches (high score + your judgment)
- Deduplicate (same qualified_name from multiple searches)
- Note which design-doc concept each candidate relates to

If a concept yields no results, rephrase the keyword and retry once. If still nothing, mark it as "no existing implementation found".

---

## Phase 3: Deep Research

For each candidate interface from Phase 2:

| Action | MCP Tool | When |
|--------|----------|------|
| Get full signature, call tree, source code | `get_api_doc(qualified_name="...")` | **Every candidate — mandatory** |
| Find who calls this interface | `find_callers(function_name="...")` | When you need to understand usage patterns |
| Trace full call chain to entry points | `trace_call_chain(target_function="...")` | When you need to confirm scope of impact |
| Browse module hierarchy | `list_api_docs()` or `list_api_docs(module="...")` | **At least once** — to determine where new functions should be placed |

Extract from the results:

1. **Reusable interfaces** — confirmed signatures, parameter semantics, preconditions
2. **Usage patterns** — from `find_callers` results, observe how other code calls each interface (parameter passing, error handling)
3. **Code style** — from `get_api_doc` source code, note naming conventions, comment language, error handling patterns
4. **Dependency direction** — from call trees, confirm that new code calling existing interfaces respects the dependency direction (no reverse dependencies)

---

## Phase 3.5: Gap Check

Review Phase 3 results and check:

- Are there qualified_names in call trees (callees) that the design document references but Phase 2 did not search?
- Are there callers that suggest a dependency the design document missed?

**Gap criteria** — an interface counts as a gap if:
1. It is mentioned (directly or indirectly) in the design document but was not found in Phase 2, OR
2. It is a direct callee of a candidate interface that the new code will likely need to call directly

If gaps found → run Phase 2 + Phase 3 for the new interfaces (**one round only**)
If no gaps → proceed to Phase 4

---

## Phase 4: Output

Synthesize all research into this exact format:

```
# Implementation Plan

## Goal
[One paragraph summary from the design document]

## Existing Interfaces to Reuse
| Interface | Signature | Location | Usage Notes |
|-----------|-----------|----------|-------------|
| `qualified_name` | `return_type func(params)` | `file:line` | How to call, preconditions, caveats |

## New Functions to Create
| Function | Module/File | Responsibility | Dependencies |
|----------|-------------|----------------|--------------|
| `new_func` | `path` | What it does | Which existing interfaces it calls |

## Files to Modify
| File | Change | Reason |
|------|--------|--------|
| `path` | What to change | Why |

## Dependency Order
file_a → file_b → file_c

## Code Style Conventions
- Naming: ...
- Error handling: ...
- Comment language: ...

## Architecture Constraints
- Dependency direction: ...
- Layer placement: ...
```

**⚠️ STOP HERE.** Present this plan to the user and wait for explicit confirmation before taking any further action. Do not write code until the user approves.

---

## Edge Cases

- **`find_api` returns no results**: Rephrase keyword and retry once. If still nothing, mark the concept as "no existing implementation" and note it in the plan as requiring new code without architecture alignment guarantees.
- **Design document involves a language not indexed**: Stop and inform the user. Suggest running `/repo-init` on the target repository first.
- **Too many candidate interfaces (>15)**: Prioritize by relevance score. Deep-research the top 10, note the rest as "identified but not fully researched" in the plan.
- **Design document is too large**: Suggest splitting into multiple `/code-gen` invocations, each targeting a sub-feature.
