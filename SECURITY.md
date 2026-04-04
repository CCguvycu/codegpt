# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** open a public GitHub issue
2. Email: cameroncull5@gmail.com
3. Include: description, steps to reproduce, impact assessment
4. Expected response time: 48 hours

## Security Model

### What CodeGPT protects against:
- **Sandboxed tools** — non-coding AI tools run in isolated directories with API keys stripped
- **Shell blocklist** — dangerous commands and injection patterns are blocked
- **Code execution limits** — max 20 code runs per session
- **PIN authentication** — optional PIN lock with SHA-256 hashing
- **Audit logging** — all security events logged to `~/.codegpt/security/audit.log`
- **Auto-update verification** — SHA256 checksums verified before replacing binaries
- **Dependency bounds** — version ranges prevent installing major breaking versions

### What CodeGPT does NOT protect against:
- **Local machine compromise** — if an attacker has local access, they can modify config files
- **Ollama model attacks** — malicious models could generate harmful outputs
- **Network MITM** — Ollama communication is HTTP (not HTTPS) on localhost
- **Full sandbox escape** — coding tools have file system access by design

### Supply Chain Measures
- GitHub Actions pinned to commit SHAs
- Release artifacts include SHA256 checksums
- Dependencies use version upper bounds
- npm published with 2FA required
- Install scripts verify checksums when available

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |
| < 1.0   | No        |

## Dependencies

Core dependencies (audited):
- `requests` — HTTP client
- `rich` — Terminal UI
- `prompt-toolkit` — Input handling

Optional:
- `textual` — TUI app
- `flask` — Web app
- `python-telegram-bot` — Telegram bot

## Architecture

```
User Input
    |
    v
[Input Validation] --> Shell Blocklist + Injection Pattern Check
    |
    v
[Command Router] --> Slash commands, AI agents, tool launchers
    |
    v
[Ollama API] --> HTTP to localhost:11434 (or remote server)
    |
    v
[Tool Sandbox] --> Isolated dirs, stripped env vars, audit logged
```
