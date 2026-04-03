# Codex Instructions

You are working on **CodeGPT** — a local AI assistant hub built in Python. See CLAUDE.md for full project context.

Main file is `chat.py` (~3500 lines). Be careful with edits — it has 60+ commands wired together.

When making changes:
- Read the existing code first
- Don't break the command routing (elif chain in main loop)
- Keep Rich formatting consistent
- Test with: `python chat.py`
