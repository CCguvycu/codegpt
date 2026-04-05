# CodeGPT

**Your local AI assistant hub. One command. No cloud. No API keys.**

```
npm i -g codegpt-ai
```

Then type `code`.

```
  ╔══════════════════════════════════════════════════╗
  ║                                                  ║
  ║      C o d e   G P T   v2.0                      ║
  ║      local ai · powered by ollama                 ║
  ║                                                  ║
  ╚══════════════════════════════════════════════════╝
```

## What is it?

CodeGPT is a full-featured AI CLI that runs entirely on your machine using [Ollama](https://ollama.com). 123 commands, 8 AI agents, 26 tools, no cloud needed.

**Works on Windows, macOS, Linux, and Termux (Android).**

## Install

```bash
npm i -g codegpt-ai
code
```

No Python? No problem — a built-in Node.js chat client runs automatically. With Python installed, you get the full 123-command experience.

### Other install methods

```bash
# pip
pip install git+https://github.com/CCguvycu/codegpt.git
ai

# Termux (Android)
curl -sL https://raw.githubusercontent.com/CCguvycu/codegpt/main/install-termux.sh | bash
code

# Windows (PowerShell)
irm https://raw.githubusercontent.com/CCguvycu/codegpt/main/install.ps1 | iex
```

## Requirements

- **Node.js 16+** or **Python 3.10+**
- **Ollama** — [ollama.com](https://ollama.com) then `ollama pull llama3.2`
- Or connect to a remote Ollama with `/connect IP`

## Features

### 123 Commands

| Category | Commands |
|----------|----------|
| **Chat** | `/new` `/save` `/load` `/copy` `/regen` `/edit` `/history` `/export` |
| **Model** | `/model` `/temp` `/think` `/tokens` `/params` `/compact` |
| **AI Agents** | `/agent` `/all` `/vote` `/swarm` `/team` `/room` `/spectate` |
| **AI Lab** | `/lab bench` `/lab chain` `/lab prompt` `/race` `/compare` |
| **Tools** | `/tools` `/bg` `/split` `/grid` 26 AI CLI integrations |
| **Connect** | `/connect` `/server` `/qr` `/scan` `/disconnect` |
| **Files** | `/file` `/run` `/code` `/shell` `/browse` `/open` |
| **Memory** | `/mem` `/train` `/pin` `/search` `/fork` `/rate` |
| **Skills** | `/skill` `/skills` `/auto` `/cron` |
| **Comms** | `/broadcast` `/inbox` `/dm` `/monitor` `/hub` |
| **System** | `/github` `/weather` `/spotify` `/volume` `/sysinfo` |
| **Security** | `/pin-set` `/lock` `/audit` `/security` `/permissions` |
| **Profile** | `/profile` `/persona` `/usage` `/setname` `/setbio` |

### 8 AI Agents

Specialized agents with custom system prompts:

```
/agent coder build a REST API with auth
/agent debugger why does this crash
/agent reviewer check this code for bugs
/agent architect design a microservices system
/agent pentester find security vulnerabilities
/agent optimizer make this code faster
/agent explainer explain kubernetes simply
/agent researcher deep-dive into WebSockets
```

### Multi-AI System

```
/all what's the best database?       # All 8 agents answer in parallel
/vote Flask or FastAPI?              # Agents vote with consensus
/swarm build a CLI password manager  # 6-agent collaborative pipeline
/team claude codex                   # Group chat: you + 2 AIs
/room coder reviewer architect       # Chat room with 3+ AIs
/spectate claude gemini debate AI    # Watch AIs debate without you
```

### 26 AI Tool Integrations

Launch any AI CLI from CodeGPT. Auto-installs on first use. All sandboxed.

```
/claude    /codex     /gemini    /copilot   /cline
/aider     /shellgpt  /llm       /litellm   /opencommit
/gorilla   /chatgpt   /cursor    /ollama    /jq
/vercel    /netlify   /supabase  /railway   /wrangler
```

Split screen multiple tools:

```
/split claude codex                  # Side by side
/grid claude codex gemini cline      # 2x2 grid
```

### Custom Skills

Create your own commands — like OpenClaw's self-extending skills:

```
/skill poet Write all responses as poetry
/auto a brutal code reviewer that finds every bug
/cron 5m /weather                    # Scheduled tasks
```

### Security

- **Permission system** — asks before every action with risk level (CRITICAL/HIGH/MEDIUM/LOW)
- **PIN lock** — SHA-256 hashed, auto-locks after 10min idle
- **Sandbox** — non-coding tools run in isolated directories, API keys stripped
- **Rate limiting** — blocks rapid-fire command spam
- **Input sanitization** — strips null bytes and control characters
- **Shell blocklist** — blocks dangerous commands + injection patterns
- **Audit log** — every action logged
- **Pre-commit hook** — blocks secrets from being committed

### Remote Connect

```
/connect 192.168.1.100    # Connect to PC's Ollama from phone
/qr                       # Show QR code to scan
/server                   # Check connection status
```

### Token Counter

Tracks lifetime tokens and messages across all sessions. Visible on startup.

## CLI Args

```bash
code                           # Interactive chat
code --ask "explain recursion" # One-shot question
code --agent coder "flask app" # Run an agent
code --team claude codex "auth"# Two AIs respond
code --tools                   # List tools
code --models                  # List Ollama models
code --status                  # Show status
code doctor                    # System diagnostics
code update                    # Self-update
echo "question" | code         # Pipe input
```

## Aliases

30+ shortcuts for fast typing:

| Short | Full | Short | Full |
|-------|------|-------|------|
| `/q` | `/quit` | `/a` | `/all` |
| `/n` | `/new` | `/sw` | `/swarm` |
| `/s` | `/save` | `/t` | `/think` |
| `/m` | `/model` | `/h` | `/help` |
| `/f` | `/file` | `/con` | `/connect` |

## Personas

6 built-in AI personalities:

```
/persona hacker      # Cybersecurity expert, dark humor
/persona teacher     # Patient, step-by-step explanations
/persona roast       # Brutal code reviewer
/persona architect   # System design, ASCII diagrams
/persona minimal     # One-line answers, code only
/persona default     # Standard helpful assistant
```

## Architecture

```
codegpt/
  chat.py        6,500+ lines   Main CLI (Python)
  bin/chat.js     300 lines     Node.js fallback
  ai_cli/                       Package (updater, doctor)
  app.py                        TUI app (Textual)
  bot.py                        Telegram bot
  web.py                        Web app (Flask PWA)
```

## License

MIT — Built by [ArukuX](https://github.com/CCguvycu)
