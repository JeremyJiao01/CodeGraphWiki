Search for existing implementations. Run this before proposing new code — the answer is almost always "use existing function X" rather than "write something new".

```bash
python3 ~/.claude/commands/code-graph/cgb_cli.py search "$ARGUMENTS"
```

After getting results:
- If a match covers the need, **reference its source directly as the implementation**
- Use `--top-k 10` when exploring unfamiliar areas to get broader coverage

Add `--top-k N` to control the number of results (default: 5).

Example: `/code-search initialize PWM output channel`

Requires embeddings to have been built via `/repo-init`.
