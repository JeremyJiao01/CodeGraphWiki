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

## Block 2 — Verify Python 3.11.x

terrain-ai requires **exactly Python 3.11.x**. Versions 3.10, 3.12, and above are not supported. STOP if you cannot find Python 3.11.

**Check (Mac/Linux):**
```bash
python3.11 --version
```

**Check (Windows):**
```
py -3.11 --version
```

Expected output: `Python 3.11.x` where x is any patch version.

**If Python 3.11.x is found** → continue to Block 3.

**If Python 3.11 is not found or the version is wrong** → install it using the instructions below, then re-run the check. Do NOT continue with any other Python version.

| PLATFORM | Installation command |
|----------|---------------------|
| `mac`    | `brew install python@3.11` |
| `linux`  | `sudo apt install python3.11` or `sudo dnf install python3.11` |
| `windows`| Download the installer from `https://www.python.org/downloads/release/python-3119/` — check **"Add Python to PATH"** before installing. |

After installing, re-run the version check before continuing. If the version is still not 3.11.x, STOP and ask the user to resolve the Python installation manually.

---

## Block 3 — Install terrain-ai Python Package

Try the following commands in order. Stop at the first one that succeeds (exit code 0). If all four fail, STOP and report the full error output to the user, then suggest checking firewall or proxy settings.

**Mac/Linux — try in order:**
```bash
# Attempt 1: official PyPI
python3.11 -m pip install terrain-ai

# Attempt 2: Tsinghua mirror
python3.11 -m pip install terrain-ai -i https://pypi.tuna.tsinghua.edu.cn/simple

# Attempt 3: Aliyun mirror
python3.11 -m pip install terrain-ai -i https://mirrors.aliyun.com/pypi/simple

# Attempt 4: Douban mirror
python3.11 -m pip install terrain-ai -i https://pypi.douban.com/simple
```

**Windows — try in order:**
```
py -3.11 -m pip install terrain-ai
py -3.11 -m pip install terrain-ai -i https://pypi.tuna.tsinghua.edu.cn/simple
py -3.11 -m pip install terrain-ai -i https://mirrors.aliyun.com/pypi/simple
py -3.11 -m pip install terrain-ai -i https://pypi.douban.com/simple
```

After a successful install, verify:

**Mac/Linux:** `python3.11 -c "import terrain; print('ok')"`
**Windows:** `py -3.11 -c "import terrain; print('ok')"`

Expected output: `ok`. If this fails, try the next mirror source.

---

## Block 4 — Check for Existing API Keys

Check if `~/.terrain/.env` already contains keys.

**Mac/Linux:**
```bash
cat ~/.terrain/.env 2>/dev/null
```

**Windows:**
```
type "%USERPROFILE%\.terrain\.env" 2>nul
```

**If the file exists and contains `LLM_API_KEY`** → the keys are already configured. Skip to Block 5.

**If the file is missing or `LLM_API_KEY` is absent** → ask the user the following questions one at a time:

1. Which LLM provider are you using? (OpenAI / Anthropic / Gemini / other — for "other", ask for the base URL)
2. What is your LLM API key?
3. What model name should be used? (e.g. `gpt-4o`, `claude-opus-4-6`, `gemini-2.0-flash`)
4. Do you use a separate embedding provider? If yes: which one, what is the API key, and what model name?

Store the answers as variables. Do NOT write them to disk yet — proceed to Block 4.5 to validate them first.

---
