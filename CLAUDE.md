# CodeGPT — Project Context

## What This Is
CodeGPT is a full-featured local AI assistant hub. CLI chat, TUI, Telegram bot, web app, and 15+ AI tool integrations — all powered by Ollama running locally.

## Stack
- **Language**: Python 3.13
- **AI Backend**: Ollama (localhost:11434), default model: llama3.2
- **CLI**: Rich + prompt_toolkit (chat.py)
- **TUI**: Textual (app.py)
- **Web**: Flask + HTTPS (web.py)
- **Bot**: python-telegram-bot (bot.py)
- **Server**: Flask API, Groq/Ollama (server.py)
- **Launcher**: run.py (all modes)

## Files
- `chat.py` — Main CLI with 60+ slash commands, AI agents, AI lab, training, security, tool integrations
- `app.py` — TUI sidebar app (Textual)
- `bot.py` — Telegram bot (live streaming, profiles, 10 features)
- `web.py` — PWA web app (Flask + HTTPS)
- `server.py` — Backend API (Groq cloud + Ollama local)
- `run.py` — Launcher (cli/tui/web/bot/server/mobile)
- `mobile.py` — Flet mobile app (incomplete, disk space issue)

## Key Architecture (chat.py)
- `COMMANDS` dict — all slash commands
- `AI_TOOLS` dict — all external tool configs (bin, install, default_args)
- `AI_AGENTS` dict — 8 specialized agents (coder, debugger, researcher, etc.)
- `PERSONAS` dict — 6 personalities (default, hacker, teacher, roast, architect, minimal)
- `PROMPT_TEMPLATES` dict — 15 reusable prompt prefixes
- `stream_response()` — streaming Ollama chat with live rendering
- `SlashCompleter` — autocomplete for / commands
- Profile system — persistent user data at ~/.codegpt/profiles/
- Memory system — persistent AI memory at ~/.codegpt/memory/
- Security — PIN lock, audit log, shell blocklist, code exec limits
- Training — collect conversations, build custom Ollama models

## Data Locations
- `~/.codegpt/profiles/cli_profile.json` — user profile
- `~/.codegpt/memory/memories.json` — AI memories
- `~/.codegpt/security/` — PIN hash, audit log
- `~/.codegpt/training/` — training data, custom modelfiles
- `~/.codegpt/sandbox/` — sandboxed tool working dirs
- `~/.codegpt/context.json` — shared context (updated every tool launch)
- `~/.codegpt/chats/` — saved conversations
- `~/.codegpt/exports/` — exported chats
- `~/.codegpt/ratings.json` — response ratings

## Owner
ArukuX (Ark), student dev, Southampton UK. Prefers direct/technical tone.

## Rules
- All external AI tools are sandboxed (except coding tools that need file access)
- API keys are stripped from sandboxed tool environments
- All tool launches are audit logged
- Security PIN uses SHA-256 hashing
- Code execution limited to 20/session
- Shell commands checked against blocklist
