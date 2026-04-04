# CodeGPT

**Your local AI assistant hub. One command. No cloud. No API keys.**

```
npm i -g codegpt-ai
```

Then type `ai`.

```
  ██████╗ ██████╗ ██████╗ ███████╗ ██████╗ ██████╗ ████████╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔════╝ ██╔══██╗╚══██╔══╝
 ██║     ██║   ██║██║  ██║█████╗  ██║  ███╗██████╔╝   ██║
 ██║     ██║   ██║██║  ██║██╔══╝  ██║   ██║██╔═══╝    ██║
 ╚██████╗╚██████╔╝██████╔╝███████╗╚██████╔╝██║        ██║
  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝        ╚═╝
```

## What is it?

A fully-featured AI chat CLI that runs locally on your machine using [Ollama](https://ollama.com). No API keys needed. No cloud. No subscription.

- **80+ slash commands** — chat, code, search, export, and more
- **8 AI agents** — coder, debugger, reviewer, architect, pentester, explainer, optimizer, researcher
- **29 AI tool integrations** — Claude, Codex, Gemini, Copilot, Cline, and more
- **Multi-AI system** — swarm, vote, race, team chat with multiple AIs
- **AI training** — train your own custom Ollama models from conversations
- **Security** — PIN lock, audit log, sandboxed tools, shell blocklist
- **Works anywhere** — Windows, macOS, Linux, Termux (Android)

## Install

### npm (recommended)
```bash
npm i -g codegpt-ai
ai
```

Works with just Node.js. If Python is installed, you get the full 80+ command experience. Without Python, you get a lightweight Node.js chat client.

### pip
```bash
pip install -e git+https://github.com/CCguvycu/codegpt.git#egg=codegpt
ai
```

### PowerShell (Windows)
```powershell
irm https://raw.githubusercontent.com/CCguvycu/codegpt/main/install.ps1 | iex
```

### Termux (Android)
```bash
curl -sL https://raw.githubusercontent.com/CCguvycu/codegpt/main/install-termux.sh | bash
```

## Requirements

- **Node.js 16+** (for npm install) OR **Python 3.10+** (for pip install)
- **Ollama** — install from [ollama.com](https://ollama.com), then `ollama pull llama3.2`
- Or connect to a remote Ollama server with `/connect IP`

## Quick Start

```bash
# Install
npm i -g codegpt-ai

# Pull a model
ollama pull llama3.2

# Start chatting
ai
```

Type `/help` inside for all commands.

## Features

### Chat
| Command | Description |
|---------|-------------|
| `/new` | New conversation |
| `/save` | Save conversation |
| `/load` | Load saved conversation |
| `/model` | Switch model |
| `/persona` | Switch personality (hacker, teacher, roast, architect, minimal) |
| `/think` | Toggle deep reasoning mode |
| `/file path` | Read a file into context |
| `/run` | Execute last code block |
| `/compact` | Summarize conversation to save context |

### AI Agents
```
/agent coder build a REST API
/agent debugger why does this crash
/agent reviewer check this code
/agent architect design a microservices system
```

8 specialized agents: `coder` `debugger` `researcher` `reviewer` `architect` `pentester` `explainer` `optimizer`

### Multi-AI
```
/all what's the best database?       # All 8 agents answer in parallel
/vote Flask or FastAPI?              # Agents vote with consensus
/swarm build a CLI password manager  # 6-agent pipeline
/team claude codex                   # Group chat with 2 AIs + you
/race explain recursion              # Race all models for speed
```

### AI Tools (29 integrations)
```
/tools                    # See all tools
/claude                   # Launch Claude Code
/codex                    # Launch Codex
/gemini                   # Launch Gemini CLI
/split claude codex       # Side-by-side split screen
/grid claude codex gemini cline  # 2x2 grid
```

All tools auto-install on first use. Sandboxed for security.

### AI Training
```
/rate good                # Rate a response
/train collect            # Save chat as training data
/train build mymodel      # Create custom Ollama model
/model mymodel            # Use your trained model
```

### Remote Connect
```
/connect 192.168.1.100    # Connect to PC's Ollama
/qr                       # Show QR code to connect from phone
/server                   # Check connection status
```

### Security
```
/pin-set                  # Set login PIN
/audit                    # View security log
/security                 # Security dashboard
```

### Integrations
```
/github repos             # Your GitHub repos
/spotify play             # Control Spotify
/weather London           # Get weather
/sysinfo                  # System info
```

## CLI Args (non-interactive)

```bash
ai --ask "explain kubernetes"
ai --agent coder "build a flask app"
ai --team claude codex "discuss auth"
ai --tools
ai --models
ai --status
ai doctor
ai update
echo "what is rust?" | ai
```

## Aliases

Type faster with 30+ shortcuts:

| Short | Full | Short | Full |
|-------|------|-------|------|
| `/q` | `/quit` | `/a` | `/all` |
| `/n` | `/new` | `/sw` | `/swarm` |
| `/s` | `/save` | `/t` | `/think` |
| `/m` | `/model` | `/h` | `/help` |
| `/f` | `/file` | `/con` | `/connect` |

## Architecture

```
codegpt/
  chat.py          6,200 lines   Main CLI (Python)
  bin/chat.js       300 lines    Node.js fallback
  bin/ai.js          50 lines    Entry point (routes to Python or Node)
  ai_cli/                        Package (updater, doctor)
  app.py                         TUI app (Textual)
  bot.py                         Telegram bot
  web.py                         Web app (Flask PWA)
  server.py                      Backend API
```

## Data

All data stored locally at `~/.codegpt/`:
- `profiles/` — user profile
- `memory/` — persistent AI memories
- `security/` — PIN hash, audit log
- `training/` — training data, custom models
- `chats/` — saved conversations

## License

MIT

## Author

Built by [ArukuX](https://github.com/CCguvycu)
