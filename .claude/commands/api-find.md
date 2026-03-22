**Use this FIRST before writing any implementation code.** Find existing interfaces in this codebase that match the requirement.

```bash
python3 ~/.claude/commands/code-graph/cgb_cli.py api-find "$ARGUMENTS"
```

After getting results:
1. Check if any returned function already solves the problem — if yes, use it directly, don't rewrite it
2. Note the call graph to understand calling order and dependencies
3. If nothing matches exactly, use the found implementations as your coding template — not general language conventions

Add `--top-k N` to get more results (default: 5).

Example: `/api-find PWM duty cycle update`

Requires embeddings to have been built via `/repo-init`.
