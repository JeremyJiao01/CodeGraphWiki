# terrain-ai Agent Installation Guide

> You are an AI agent. Read every block top-to-bottom and execute the commands.
> Do not skip blocks. Do not proceed past a block that ends in "STOP".

---

## Block 1 — Detect Operating System

Run the appropriate command and store the result as PLATFORM:

**Mac/Linux:**
```bash
uname -s
```
- Output contains `Darwin` → PLATFORM = `mac`
- Output contains `Linux` → PLATFORM = `linux`

**Windows** (run in PowerShell or cmd):
```
echo %OS%
```
- Output contains `Windows` → PLATFORM = `windows`

Use PLATFORM in every subsequent block to choose the correct commands.

---
