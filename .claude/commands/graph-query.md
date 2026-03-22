Query the code knowledge graph for structural relationships. Particularly useful for understanding calling order, initialization sequences, and module dependencies.

```bash
python3 ~/.claude/commands/code-graph/cgb_cli.py query "$ARGUMENTS"
```

Typical use cases:
- **Calling order**: "what functions must be called before X?"
- **Init sequence**: "what is the startup sequence for module Y?"
- **Callers**: "which functions call Z?"
- **Dependencies**: "what does function W depend on?"
- **Module boundaries**: "what does module A export that module B uses?"

Requires an LLM API key configured (LLM_API_KEY, OPENAI_API_KEY, or MOONSHOT_API_KEY).

Example: `/graph-query what must be initialized before calling Inverter_Start?`
