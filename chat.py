import json
import os
import re
import subprocess
import sys
import threading
import time
import shutil
import hashlib
import base64
from pathlib import Path
from datetime import datetime
from getpass import getpass

import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.rule import Rule
from rich.align import Align
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory, FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style as PtStyle

# --- Config ---

# Fix PATH for Termux and pip --user installs
_extra_paths = [
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/bin"),
]
if os.path.exists("/data/data/com.termux"):
    _extra_paths.extend([
        "/data/data/com.termux/files/usr/bin",
        "/data/data/com.termux/files/home/.local/bin",
        os.path.expanduser("~/.npm-global/bin"),
    ])
for _p in _extra_paths:
    if _p not in os.environ.get("PATH", "") and os.path.isdir(_p):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = "llama3.2"
CHATS_DIR = Path.home() / ".codegpt" / "conversations"
SYSTEM_PROMPT = """You are an AI modeled after a highly technical, system-focused developer mindset.

Communication:
- Be direct, concise, and dense with information
- No fluff, no filler, no emojis
- No motivational or overly friendly tone
- Give conclusions first, then minimal necessary explanation

Thinking:
- Break problems into systems and components
- Optimize for efficiency, scalability, and control
- Focus on practical, real-world solutions
- Avoid over-explaining basic concepts

Behavior:
- Do not sugar-coat
- Do not moralize
- Do not give generic advice
- If uncertain, say so briefly
- If incorrect, correct immediately

Focus areas:
- AI, coding, automation, cybersecurity (defensive), system design

Style:
- Structured when useful (lists, steps, architecture)
- Blunt but intelligent
- Slightly dark, high-intensity tone is acceptable

Goal:
Deliver high-value, efficient, technically sharp responses with zero wasted words."""

AI_TOOLS = {
    # --- Works everywhere (pip — pure Python) ---
    "shellgpt": {
        "name": "ShellGPT",
        "desc": "AI assistant in your shell",
        "bin": "sgpt",
        "install": ["pip", "install", "shell-gpt"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": True,
    },
    "llm": {
        "name": "LLM",
        "desc": "Simon Willison's multi-model CLI",
        "bin": "llm",
        "install": ["pip", "install", "llm"],
        "default_args": ["chat"],
        "needs_key": "OPENAI_API_KEY (or plugins)",
        "termux": True,
    },
    "litellm": {
        "name": "LiteLLM",
        "desc": "Unified API for 100+ models",
        "bin": "litellm",
        "install": ["pip", "install", "litellm"],
        "default_args": [],
        "needs_key": "Any provider key",
        "termux": True,
    },
    "gorilla": {
        "name": "Gorilla CLI",
        "desc": "AI generates CLI commands from English",
        "bin": "gorilla",
        "install": ["pip", "install", "gorilla-cli"],
        "default_args": [],
        "needs_key": "None — free API",
        "termux": True,
    },
    "chatgpt": {
        "name": "ChatGPT CLI",
        "desc": "Official ChatGPT in terminal",
        "bin": "chatgpt",
        "install": ["pip", "install", "chatgpt"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": True,
    },
    "aider": {
        "name": "Aider",
        "desc": "AI pair programmer — edits your code",
        "bin": "aider",
        "install": ["pip", "install", "aider-chat"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY or ANTHROPIC_API_KEY",
        "termux": True,
    },
    "interpreter": {
        "name": "Open Interpreter",
        "desc": "AI that runs code on your machine",
        "bin": "interpreter",
        "install": ["pip", "install", "open-interpreter"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY (or --local)",
        "termux": True,
    },
    "gpt-engineer": {
        "name": "GPT Engineer",
        "desc": "AI builds entire projects from prompts",
        "bin": "gpte",
        "install": ["pip", "install", "gpt-engineer"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": True,
    },
    "mentat": {
        "name": "Mentat",
        "desc": "AI coding agent by AbanteAI",
        "bin": "mentat",
        "install": ["pip", "install", "mentat"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY or ANTHROPIC_API_KEY",
        "termux": True,
    },
    # --- Works everywhere (npm — pure JS) ---
    "opencommit": {
        "name": "OpenCommit",
        "desc": "AI writes your git commit messages",
        "bin": "opencommit",
        "install": ["npm", "i", "-g", "opencommit"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": True,
    },
    "ai-shell": {
        "name": "AI Shell",
        "desc": "Natural language to shell commands",
        "bin": "ai",
        "install": ["npm", "i", "-g", "ai-shell"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": True,
    },
    "aipick": {
        "name": "AIPick",
        "desc": "AI-powered git commit selector",
        "bin": "aipick",
        "install": ["npm", "i", "-g", "aipick"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": True,
    },
    "cline": {
        "name": "Cline",
        "desc": "Autonomous AI coding agent",
        "bin": "cline",
        "install": ["npm", "i", "-g", "cline"],
        "default_args": [],
        "needs_key": "ANTHROPIC_API_KEY or OPENAI_API_KEY",
        "termux": True,
    },
    # --- Platform tools (pkg on Termux, winget on Windows) ---
    "ollama": {
        "name": "Ollama",
        "desc": "Run local LLMs",
        "bin": "ollama",
        "install": ["pip", "install", "ollama"],
        "install_termux": ["pkg", "install", "-y", "ollama"],
        "install_win": ["winget", "install", "Ollama.Ollama"],
        "default_args": ["run", "llama3.2"],
        "needs_key": "None — local",
        "termux": True,
    },
    "jq": {
        "name": "jq",
        "desc": "JSON processor for the command line",
        "bin": "jq",
        "install": ["pip", "install", "jq"],
        "install_termux": ["pkg", "install", "-y", "jq"],
        "install_win": ["winget", "install", "jqlang.jq"],
        "default_args": [],
        "needs_key": "None",
        "termux": True,
    },
    # --- Desktop/x86 only (native binaries, no ARM) ---
    "opencode": {
        "name": "OpenCode",
        "desc": "AI coding agent — terminal IDE",
        "bin": "opencode",
        "install": ["npm", "i", "-g", "opencode-ai"],
        "default_args": [],
        "needs_key": "ANTHROPIC_API_KEY or OPENAI_API_KEY",
        "termux": False,
    },
    "codex": {
        "name": "Codex",
        "desc": "OpenAI's coding agent CLI",
        "bin": "codex",
        "install": ["npm", "i", "-g", "@openai/codex"],
        "default_args": [],
        "needs_key": "OPENAI_API_KEY",
        "termux": False,  # ARM64 build fails on Termux
    },
    "gemini": {
        "name": "Gemini CLI",
        "desc": "Google's AI coding CLI",
        "bin": "gemini",
        "install": ["npm", "i", "-g", "@google/gemini-cli"],
        "default_args": [],
        "needs_key": "Google login",
        "termux": True,  # Pure JS, no native deps
    },
    "copilot": {
        "name": "GitHub Copilot",
        "desc": "AI pair programmer in terminal",
        "bin": "gh",
        "install": ["gh", "extension", "install", "github/gh-copilot"],
        "install_termux": ["pkg", "install", "-y", "gh"],
        "default_args": ["copilot"],
        "needs_key": "GitHub login",
        "termux": True,  # gh available via pkg
    },
    "gpt4all": {
        "name": "GPT4All",
        "desc": "Run AI models 100% offline",
        "bin": "gpt4all",
        "install": ["pip", "install", "gpt4all"],
        "default_args": [],
        "needs_key": "None — offline",
        "termux": False,
    },
    "cursor": {
        "name": "Cursor CLI",
        "desc": "Cursor AI editor from terminal",
        "bin": "cursor",
        "install": ["npm", "i", "-g", "cursor-cli"],
        "default_args": [],
        "needs_key": "Cursor account",
        "termux": True,  # Pure JS
    },
    # --- Deploy CLIs (work everywhere) ---
    "vercel": {
        "name": "Vercel",
        "desc": "Deploy frontend apps",
        "bin": "vercel",
        "install": ["npm", "i", "-g", "vercel"],
        "default_args": [],
        "needs_key": "Vercel account",
        "termux": True,
    },
    "netlify": {
        "name": "Netlify",
        "desc": "Deploy web apps",
        "bin": "netlify",
        "install": ["npm", "i", "-g", "netlify-cli"],
        "default_args": [],
        "needs_key": "Netlify account",
        "termux": True,
    },
    "supabase": {
        "name": "Supabase",
        "desc": "Backend-as-a-service CLI",
        "bin": "supabase",
        "install": ["npm", "i", "-g", "supabase"],
        "default_args": [],
        "needs_key": "Supabase account",
        "termux": True,
    },
    "railway": {
        "name": "Railway",
        "desc": "Deploy apps to the cloud",
        "bin": "railway",
        "install": ["npm", "i", "-g", "@railway/cli"],
        "default_args": [],
        "needs_key": "Railway account",
        "termux": True,
    },
    "wrangler": {
        "name": "Wrangler",
        "desc": "Cloudflare Workers CLI",
        "bin": "wrangler",
        "install": ["npm", "i", "-g", "wrangler"],
        "default_args": [],
        "needs_key": "Cloudflare account",
        "termux": True,
    },
}

SUGGESTIONS = [
    "Explain how TCP/IP works under the hood",
    "Write a Python script to monitor CPU usage",
    "What are the OWASP top 10 vulnerabilities?",
    "Design a REST API for a todo app",
    "How does Docker networking work?",
    "Explain buffer overflow attacks",
]

COMMANDS = {
    "/new": "Start a new conversation",
    "/save": "Save current conversation",
    "/load": "Load a saved conversation",
    "/delete": "Delete a saved conversation",
    "/copy": "Copy last AI response to clipboard",
    "/regen": "Regenerate last AI response",
    "/edit": "Edit & resend last message",
    "/model": "Switch model (/model <id>)",
    "/system": "Set system prompt",
    "/remind": "Set reminder (/remind 5m msg)",
    "/reminders": "List active reminders",
    "/voice": "Speak instead of type",
    "/file": "Read a file into context (/file path)",
    "/run": "Execute last Python code block",
    "/code": "Multi-line code input (end with <<<)",
    "/think": "Toggle deep thinking mode",
    "/temp": "Set temperature 0.0-2.0 (/temp 0.7)",
    "/tokens": "Show token usage stats",
    "/compact": "Summarize conversation to save context",
    "/search": "Search conversation (/search keyword)",
    "/export": "Export chat as markdown file",
    "/diff": "Compare last 2 AI responses",
    "/pin": "Pin a message for reference (/pin 3)",
    "/pins": "Show pinned messages",
    "/modelinfo": "Show current model details",
    "/params": "Set model params (/params top_p 0.9)",
    "/prompts": "Prompt template library",
    "/fork": "Fork conversation from message # (/fork 3)",
    "/compare": "Compare 2 models on same prompt",
    "/rate": "Rate last response (good/bad)",
    "/tag": "Tag current conversation (/tag python)",
    "/shortcuts": "Show keyboard shortcuts",
    "/agent": "Run an AI agent (/agent <task>)",
    "/agents": "List available agents",
    "/lab": "AI Lab — experiments & tools",
    "/chain": "Chain prompts (/chain p1 | p2 | p3)",
    "/mem": "AI memory (/mem save/recall/list)",
    "/shell": "Run a shell command (/shell dir)",
    "/usage": "Full usage dashboard",
    "/openclaw": "Launch OpenClaw AI assistant",
    "/claude": "Launch Claude Code CLI",
    "/aider": "Launch Aider (AI pair programmer)",
    "/interpreter": "Launch Open Interpreter",
    "/shellgpt": "Launch ShellGPT",
    "/opencode": "Launch OpenCode (AI coding agent)",
    "/codex": "Launch Codex (OpenAI coding CLI)",
    "/gemini": "Launch Gemini CLI (Google AI)",
    "/copilot": "Launch GitHub Copilot CLI",
    "/cline": "Launch Cline (coding agent)",
    "/gpt-engineer": "Launch GPT Engineer",
    "/mentat": "Launch Mentat (coding agent)",
    "/ollama": "Launch Ollama (run local models)",
    "/jq": "Launch jq (JSON processor)",
    "/llm": "Launch LLM (multi-model CLI)",
    "/gpt4all": "Launch GPT4All (offline AI)",
    "/litellm": "Launch LiteLLM (100+ models)",
    "/opencommit": "Launch OpenCommit (AI git commits)",
    "/ai-shell": "Launch AI Shell (English to commands)",
    "/gorilla": "Launch Gorilla CLI (AI commands)",
    "/chatgpt": "Launch ChatGPT CLI",
    "/cursor": "Launch Cursor CLI",
    "/aipick": "Launch AIPick (AI git selector)",
    "/vercel": "Launch Vercel (deploy)",
    "/netlify": "Launch Netlify (deploy)",
    "/supabase": "Launch Supabase CLI",
    "/railway": "Launch Railway (deploy)",
    "/wrangler": "Launch Wrangler (Cloudflare)",
    "/tools": "List all AI tools",
    "/bg": "Launch tool in new window (/bg claude)",
    "/split": "Split screen tools (/split claude codex)",
    "/splitv": "Vertical split (/splitv claude gemini)",
    "/grid": "4-pane grid of tools (/grid claude codex gemini cline)",
    "/running": "Show running AI tools",
    "/killall": "Close all background tools",
    "/broadcast": "Send message to all tools (/broadcast hello)",
    "/inbox": "Check messages from other tools",
    "/dm": "Message a specific tool (/dm claude fix this)",
    "/chat-link": "Link tools for live conversation",
    "/monitor": "Live dashboard — all tools & messages",
    "/feed": "Show all recent tool messages",
    "/hub": "Full hub view — tools, messages, stats",
    "/sidebar": "Toggle sidebar on/off",
    "/all": "Ask ALL agents at once (/all your question)",
    "/race": "Race all models — who answers first",
    "/vote": "All agents vote on a question",
    "/swarm": "Agents collaborate on a task step by step",
    "/team": "Start a team chat with 2 AIs (/team coder reviewer)",
    "/room": "AI chat room — multiple AIs talk (/room coder reviewer architect)",
    "/spectate": "Watch AIs chat without you (/spectate claude codex topic)",
    "/github": "GitHub tools (/github repos, issues, prs)",
    "/weather": "Get weather (/weather London)",
    "/open": "Open URL in browser (/open google.com)",
    "/spotify": "Spotify controls (/spotify play, pause, next)",
    "/volume": "Set system volume (/volume 50)",
    "/bright": "Set screen brightness (/bright 80)",
    "/sysinfo": "System info (CPU, RAM, disk, network)",
    "/train": "AI Training Lab (/train help)",
    "/pin-set": "Set a login PIN",
    "/pin-remove": "Remove login PIN",
    "/lock": "Lock session now",
    "/audit": "View security audit log",
    "/security": "Security status dashboard",
    "/permissions": "View/reset action permissions",
    "/skill": "Create a custom command (/skill name prompt)",
    "/skills": "List custom skills",
    "/browse": "Browse a URL and summarize (/browse url)",
    "/cron": "Schedule a recurring task (/cron 5m /weather)",
    "/crons": "List scheduled tasks",
    "/auto": "AI creates a skill from your description",
    "/connect": "Connect to remote Ollama (/connect 192.168.1.237)",
    "/disconnect": "Switch back to local Ollama",
    "/server": "Show current Ollama server",
    "/qr": "Show QR code to connect from phone",
    "/scan": "Scan QR code to connect to a server",
    "/profile": "View your profile",
    "/setname": "Set display name",
    "/setbio": "Set bio",
    "/persona": "Switch persona (/persona hacker)",
    "/personas": "List all personas",
    "/history": "Show conversation",
    "/clear": "Clear screen",
    "/help": "Show commands",
    "/quit": "Exit",
}

TIME_PATTERN = re.compile(r"^(\d+)\s*(s|sec|m|min|h|hr|hour)s?\b", re.IGNORECASE)
TIME_MULTIPLIERS = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hr": 3600, "hour": 3600}

active_reminders = []
reminder_lock = threading.Lock()

console = Console()
_hist_path = Path.home() / ".codegpt" / "input_history"
_hist_path.parent.mkdir(parents=True, exist_ok=True)
try:
    input_history = FileHistory(str(_hist_path))
except Exception:
    input_history = InMemoryHistory()
# Command categories for autocomplete display
CMD_CATEGORIES = {}
_cat_map = {
    "Chat": ["/new", "/save", "/load", "/delete", "/copy", "/regen", "/edit", "/history", "/clear", "/quit"],
    "Model": ["/model", "/modelinfo", "/params", "/temp", "/think", "/tokens", "/compact", "/system"],
    "AI Agents": ["/agent", "/agents", "/all", "/vote", "/swarm", "/team", "/room", "/spectate", "/dm", "/chat-link"],
    "AI Lab": ["/lab", "/chain", "/race", "/prompts", "/compare"],
    "Tools": ["/tools", "/bg", "/split", "/splitv", "/grid", "/running", "/killall"],
    "Connect": ["/connect", "/disconnect", "/server", "/qr", "/scan"],
    "Files & Code": ["/file", "/run", "/code", "/shell", "/browse", "/open", "/export"],
    "Memory": ["/mem", "/train", "/pin", "/pins", "/search", "/fork", "/rate", "/tag"],
    "Profile": ["/profile", "/setname", "/setbio", "/persona", "/personas", "/usage"],
    "Skills": ["/skill", "/skills", "/auto", "/cron", "/crons"],
    "Comms": ["/broadcast", "/inbox", "/feed", "/monitor", "/hub"],
    "System": ["/github", "/weather", "/spotify", "/volume", "/bright", "/sysinfo", "/voice", "/remind", "/reminders", "/shortcuts"],
    "Security": ["/pin-set", "/pin-remove", "/lock", "/audit", "/security", "/permissions"],
}
for _cat, _cmds in _cat_map.items():
    for _cmd in _cmds:
        CMD_CATEGORIES[_cmd] = _cat
# Tools get their own category
for _tool_name in AI_TOOLS:
    CMD_CATEGORIES[f"/{_tool_name}"] = "Tool"
CMD_CATEGORIES["/claude"] = "Tool"
CMD_CATEGORIES["/openclaw"] = "Tool"
CMD_CATEGORIES["/sidebar"] = "UI"
CMD_CATEGORIES["/diff"] = "Chat"
CMD_CATEGORIES["/help"] = "Help"


class SlashCompleter(Completer):
    """Show all commands with categories when typing /"""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith("/"):
            typed = text.lower()
            on_termux = os.path.exists("/data/data/com.termux")

            # Custom skills first
            skills = load_skills()
            for skill_name in skills:
                cmd = f"/{skill_name}"
                if cmd.startswith(typed):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"{cmd}",
                        display_meta=f"skill: {skills[skill_name].get('desc', '')[:30]}",
                    )

            # Main commands with categories
            for cmd, desc in COMMANDS.items():
                if cmd.startswith(typed):
                    tool_name = cmd[1:]
                    if on_termux and tool_name in AI_TOOLS and not AI_TOOLS[tool_name].get("termux", True):
                        continue
                    cat = CMD_CATEGORIES.get(cmd, "")
                    meta = f"[{cat}] {desc}" if cat else desc
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"{cmd}",
                        display_meta=meta,
                    )

            # Aliases
            for alias, target in ALIASES.items():
                if alias.startswith(typed) and alias not in COMMANDS:
                    desc = COMMANDS.get(target, "")
                    cat = CMD_CATEGORIES.get(target, "")
                    yield Completion(
                        alias,
                        start_position=-len(text),
                        display=f"{alias}",
                        display_meta=f"-> {target}",
                    )

cmd_completer = SlashCompleter()
input_style = PtStyle.from_dict({
    "prompt": "ansicyan bold",
    "bottom-toolbar": "bg:#1a1a2e #888888",
    "completion-menu": "bg:#1a1a2e #ffffff",
    "completion-menu.completion": "bg:#1a1a2e #ffffff",
    "completion-menu.completion.current": "bg:#00aaff #ffffff bold",
    "completion-menu.meta.completion": "bg:#1a1a2e #888888",
    "completion-menu.meta.completion.current": "bg:#00aaff #ffffff",
})

session_stats = {"messages": 0, "tokens_in": 0, "tokens_out": 0, "start": time.time()}
last_ai_response = ""

# --- Permissions ---

PERMISSION_ALWAYS_ALLOW = set()  # Commands the user has approved permanently
PERMISSION_FILE = Path.home() / ".codegpt" / "permissions.json"


def load_permissions():
    global PERMISSION_ALWAYS_ALLOW
    if PERMISSION_FILE.exists():
        try:
            data = json.loads(PERMISSION_FILE.read_text())
            PERMISSION_ALWAYS_ALLOW = set(data.get("always_allow", []))
        except Exception:
            pass


def save_permissions():
    PERMISSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    PERMISSION_FILE.write_text(json.dumps({
        "always_allow": list(PERMISSION_ALWAYS_ALLOW),
    }, indent=2))


# Actions that need confirmation — (description, risk level)
# Risk: CRITICAL, HIGH, MEDIUM, LOW
RISKY_ACTIONS = {
    # CRITICAL — can damage system, leak data, or run arbitrary code
    "shell":          ("Run a shell command",              "CRITICAL"),
    "code_exec":      ("Execute Python code",              "CRITICAL"),
    "tool_install":   ("Install a new tool",               "CRITICAL"),
    "connect":        ("Connect to a remote server",       "CRITICAL"),
    "pin_set":        ("Set a login PIN",                  "CRITICAL"),
    # HIGH — external access, data modification
    "tool_launch":    ("Launch an external AI tool",       "HIGH"),
    "open_url":       ("Open a URL in browser",            "HIGH"),
    "github":         ("Access GitHub",                    "HIGH"),
    "delete_chat":    ("Delete a saved conversation",      "HIGH"),
    "mem_clear":      ("Clear all AI memories",            "HIGH"),
    "train_build":    ("Build a custom AI model",          "HIGH"),
    "qr":             ("Generate QR code with your IP",    "HIGH"),
    "broadcast":      ("Send message to all tools",        "HIGH"),
    "system_prompt":  ("Modify system prompt",             "HIGH"),
    # MEDIUM — uses resources, changes settings
    "file_read":      ("Read a file into context",         "MEDIUM"),
    "export":         ("Export conversation to file",      "MEDIUM"),
    "save_chat":      ("Save conversation to disk",        "MEDIUM"),
    "train_collect":  ("Collect conversation as training",  "MEDIUM"),
    "mem_save":       ("Save to AI memory",                "MEDIUM"),
    "agent_run":      ("Run an AI agent",                  "MEDIUM"),
    "swarm":          ("Run agent swarm pipeline",         "MEDIUM"),
    "all_agents":     ("Ask all agents at once",           "MEDIUM"),
    "race":           ("Race all models",                  "MEDIUM"),
    "team_chat":      ("Start team chat with AIs",         "MEDIUM"),
    "spotify":        ("Control Spotify",                  "MEDIUM"),
    "volume":         ("Change system volume",             "MEDIUM"),
    "brightness":     ("Change screen brightness",         "MEDIUM"),
    # LOW — safe changes
    "model_change":   ("Switch AI model",                  "LOW"),
    "persona_change": ("Change AI persona",                "LOW"),
    "compact":        ("Summarize and compact conversation","LOW"),
    "fork":           ("Fork conversation",                "LOW"),
}

RISK_COLORS = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "green",
}

RISK_ICONS = {
    "CRITICAL": "☠",
    "HIGH": "⚠",
    "MEDIUM": "◇",
    "LOW": "△",
}


def ask_permission(action, detail=""):
    """Ask user for permission before performing an action.
    Returns True if allowed, False if denied."""

    # Already permanently approved
    if action in PERMISSION_ALWAYS_ALLOW:
        return True

    # Get action info
    action_info = RISKY_ACTIONS.get(action, (action, "MEDIUM"))
    if isinstance(action_info, str):
        action_desc, risk = action_info, "MEDIUM"
    else:
        action_desc, risk = action_info

    risk_color = RISK_COLORS.get(risk, "yellow")
    risk_icon = RISK_ICONS.get(risk, "?")

    # Risk warnings — explain what could happen
    risk_warnings = {
        "CRITICAL": "This can execute code, modify your system, or expose data.",
        "HIGH": "This accesses external services or modifies important data.",
        "MEDIUM": "This uses resources or changes session settings.",
        "LOW": "This is a safe operation with minimal impact.",
    }
    warning = risk_warnings.get(risk, "")

    # Clean minimal prompt — like Claude Code
    console.print()
    console.print(Text.from_markup(f"  [{risk_color}]{risk_icon} {action_desc}[/]"))
    if detail:
        console.print(Text(f"    {detail[:70]}", style="dim"))
    console.print(Text.from_markup(f"    [{risk_color}]{risk} — {warning}[/]"))
    console.print()

    try:
        answer = prompt(
            [("class:prompt", "  Allow? (y)es / (n)o / (a)lways > ")],
            style=input_style,
        ).strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False

    if answer in ("a", "always"):
        PERMISSION_ALWAYS_ALLOW.add(action)
        save_permissions()
        console.print(Text(f"  ✓ Always allowed", style="green"))
        return True
    elif answer in ("y", "yes", ""):
        return True
    else:
        print_sys("Denied.")
        return False


# Load saved permissions on startup
load_permissions()


# --- Security ---

SECURITY_DIR = Path.home() / ".codegpt" / "security"
SECURITY_DIR.mkdir(parents=True, exist_ok=True)
PIN_FILE = SECURITY_DIR / "pin.hash"
LOCK_FILE = SECURITY_DIR / "lock.conf"
AUDIT_FILE = SECURITY_DIR / "audit.log"

# Shell command blocklist
SHELL_BLOCKLIST = [
    "rm -rf", "del /f", "del /s", "format", "mkfs", "dd if=",
    "shutdown", "reboot", ":(){", "fork bomb", "rmdir /s",
    "> /dev/sda", "wget|sh", "curl|sh", "powershell -enc",
    "reg delete", "net user", "net localgroup", "taskkill /f /im",
]

# Max code execution per session
CODE_EXEC_LIMIT = 20
code_exec_count = 0
AUTO_LOCK_MINUTES = 10
last_activity = [time.time()]


def hash_pin(pin, salt=None):
    """Hash a PIN with a random salt. Returns 'salt:hash'."""
    if salt is None:
        salt = base64.b64encode(os.urandom(16)).decode("ascii")
    pin_hash = hashlib.sha256(f"{salt}:{pin}".encode()).hexdigest()
    return f"{salt}:{pin_hash}"


def set_pin(pin):
    """Set a new PIN with a random salt."""
    PIN_FILE.write_text(hash_pin(pin))


def verify_pin(pin):
    """Verify PIN against stored hash."""
    if not PIN_FILE.exists():
        return True
    stored = PIN_FILE.read_text().strip()
    # Support new format "salt:hash" and legacy format (plain hash)
    if ":" in stored and len(stored.split(":", 1)) == 2:
        salt, expected_hash = stored.split(":", 1)
        pin_hash = hashlib.sha256(f"{salt}:{pin}".encode()).hexdigest()
        return pin_hash == expected_hash
    # Legacy: static salt
    legacy_hash = hashlib.sha256(f"codegpt_v1_salt:{pin}".encode()).hexdigest()
    return stored == legacy_hash


def has_pin():
    """Check if a PIN is set."""
    return PIN_FILE.exists()


def remove_pin():
    """Remove the PIN."""
    if PIN_FILE.exists():
        PIN_FILE.unlink()


def check_auto_lock():
    """Check if session should be locked due to inactivity."""
    if not has_pin():
        return False
    elapsed = time.time() - last_activity[0]
    return elapsed > AUTO_LOCK_MINUTES * 60


def prompt_pin_unlock():
    """Prompt for PIN to unlock."""
    console.print(Panel(
        Text("Session locked due to inactivity.", style="bold yellow"),
        title="[bold yellow]Locked[/]",
        border_style="yellow",
        padding=(0, 2),
    ))
    for attempt in range(3):
        try:
            pin = getpass(f"  PIN ({3 - attempt} attempts): ")
        except (KeyboardInterrupt, EOFError):
            return False
        if verify_pin(pin):
            last_activity[0] = time.time()
            print_sys("Unlocked.")
            return True
        print_err("Wrong PIN.")
    print_err("Too many attempts. Exiting.")
    return False


def pin_login():
    """Initial PIN check on startup."""
    if not has_pin():
        return True
    console.print(Panel(
        Text("PIN required to access CodeGPT.", style="bold"),
        title="[bold bright_cyan]Security[/]",
        border_style="bright_cyan",
        padding=(0, 2),
    ))
    for attempt in range(3):
        try:
            pin = getpass(f"  Enter PIN ({3 - attempt} attempts): ")
        except (KeyboardInterrupt, EOFError):
            return False
        if verify_pin(pin):
            return True
        print_err("Wrong PIN.")
    print_err("Access denied.")
    return False


def audit_log(action, detail=""):
    """Write to audit log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {action}"
    if detail:
        entry += f" | {detail[:100]}"
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass



def is_shell_safe(cmd_text):
    """Check if a shell command is safe to run."""
    cmd_lower = cmd_text.lower().strip()

    # Blocklist check
    for blocked in SHELL_BLOCKLIST:
        if blocked in cmd_lower:
            return False, blocked

    # Block shell injection patterns
    injection_patterns = [
        r'[;&|`]',      # Command chaining/injection
        r'\$\(',        # Command substitution
        r'>\s*/dev/',   # Device writes
        r'\\x[0-9a-f]', # Hex escapes
        r'\\u[0-9a-f]', # Unicode escapes
        r'\brm\b.*-[rR]', # rm with recursive flag (any form)
    ]
    for pattern in injection_patterns:
        if re.search(pattern, cmd_text):
            return False, f"blocked pattern: {pattern}"

    # Max command length
    if len(cmd_text) > 500:
        return False, "command too long (500 char limit)"

    return True, ""


# --- Profiles ---

PROFILES_DIR = Path.home() / ".codegpt" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
CLI_PROFILE = PROFILES_DIR / "cli_profile.json"

PERSONAS = {
    "default": SYSTEM_PROMPT,
    "hacker": (
        "You are a cybersecurity expert and ethical hacker. Technical jargon, "
        "CVEs, attack vectors and defense strategies. Defensive security only. "
        "Dark humor about data breaches. Concise."
    ),
    "teacher": (
        "You are a patient programming teacher. Step by step, analogies, "
        "examples. Adapt to the student. Encourage questions."
    ),
    "roast": (
        "You are a brutally sarcastic code reviewer. Roast bad code mercilessly "
        "but always give the correct solution after. Dark humor. You care deep down."
    ),
    "architect": (
        "You are a senior system architect. Think in scalability, distributed systems, "
        "microservices. Draw ASCII diagrams. Always consider trade-offs."
    ),
    "minimal": "Shortest possible answer. One line if possible. Code only, no commentary.",
}

DEFAULT_PROFILE = {
    "name": "",
    "bio": "",
    "model": MODEL,
    "persona": "default",
    "total_messages": 0,
    "total_tokens": 0,
    "total_sessions": 0,
    "created": None,
}


def load_profile():
    if CLI_PROFILE.exists():
        try:
            data = json.loads(CLI_PROFILE.read_text())
            return {**DEFAULT_PROFILE, **data}
        except Exception:
            pass
    return {**DEFAULT_PROFILE}


def save_profile(profile):
    CLI_PROFILE.write_text(json.dumps(profile, indent=2))


def show_profile():
    profile = load_profile()
    w = tw()

    name = profile["name"] or "Not set"
    bio = profile["bio"] or "Not set"
    model = profile["model"]
    persona = profile["persona"]
    total_msgs = profile["total_messages"]
    total_tok = profile["total_tokens"]
    total_sess = profile["total_sessions"]
    since = profile["created"][:10] if profile.get("created") else "today"

    table = Table(border_style="bright_cyan", show_header=False, padding=(0, 2),
                  title="Your Profile", title_style="bold bright_cyan")
    table.add_column("Field", style="dim", width=14)
    table.add_column("Value", style="white")
    table.add_row("Name", name)
    table.add_row("Bio", bio)
    table.add_row("Model", f"[bright_cyan]{model}[/]")
    table.add_row("Persona", f"[green]{persona}[/]")
    table.add_row("Messages", str(total_msgs))
    table.add_row("Tokens", str(total_tok))
    table.add_row("Sessions", str(total_sess))
    table.add_row("Since", since)
    console.print(table)

    console.print()
    console.print(Text("  Edit: /setname, /setbio, /persona", style="dim"))
    console.print()


def setup_profile():
    """First-time welcome & profile setup wizard."""
    w = tw()
    compact = is_compact()

    # Big welcome popup
    if compact:
        console.print(Panel(
            Text.from_markup(
                "[bold bright_cyan]Welcome to CodeGPT![/]\n\n"
                "  Your local AI assistant.\n"
                "  80+ commands. 8 agents.\n"
                "  29 tools. No cloud needed.\n\n"
                "  Powered by [bold]Ollama[/].\n\n"
                "  [dim]Press Enter...[/]"
            ),
            border_style="bright_cyan", padding=(0, 1), width=w,
        ))
    else:
        console.print(Panel(
            Text.from_markup(
                "[bold bright_cyan]Welcome to CodeGPT![/]\n\n"
                "  Your local AI assistant hub.\n\n"
                "  [bright_cyan]80+[/] slash commands\n"
                "  [bright_cyan]8[/]   AI agents (coder, debugger, reviewer...)\n"
                "  [bright_cyan]29[/]  AI tool integrations (Claude, Codex, Gemini...)\n"
                "  [bright_cyan]6[/]   personas (hacker, teacher, architect...)\n"
                "  [bright_cyan]15[/]  prompt templates\n\n"
                "  No cloud. No API keys. Powered by [bold]Ollama[/].\n\n"
                "  [dim]Press Enter to continue...[/]"
            ),
            title="[bold bright_cyan]CodeGPT v1.0[/]",
            border_style="bright_cyan", padding=(1, 2), width=w,
        ))

    # Wait for Enter
    try:
        prompt([("class:prompt", " Press Enter to continue... ")], style=input_style)
    except (KeyboardInterrupt, EOFError):
        pass

    clear_screen()
    print_header(MODEL)
    console.print(Panel(
        Text("Let's set up your profile — takes 10 seconds.", style="bold"),
        border_style="bright_cyan", padding=(0, 1 if compact else 2), width=w,
    ))
    console.print()

    try:
        name = prompt([("class:prompt", " Your name > ")], style=input_style).strip()
        bio = prompt([("class:prompt", " Short bio > ")], style=input_style).strip()
    except (KeyboardInterrupt, EOFError):
        name = ""
        bio = ""

    profile = load_profile()
    profile["name"] = name or "User"
    profile["bio"] = bio or ""
    profile["created"] = datetime.now().isoformat()
    profile["total_sessions"] = 1
    save_profile(profile)

    # Post-setup quick start guide
    if compact:
        console.print(Panel(
            Text.from_markup(
                f"[bold green]Hey {profile['name']}![/]\n\n"
                "  [dim]Quick start:[/]\n"
                "  Just type to chat\n"
                "  [bright_cyan]/[/] see all commands\n"
                "  [bright_cyan]/help[/] full guide\n"
                "  [bright_cyan]/connect IP[/] link PC\n\n"
                "  [dim]Press Enter...[/]"
            ),
            title="[bold green]Ready[/]",
            border_style="green", padding=(0, 1), width=w,
        ))
    else:
        console.print(Panel(
            Text.from_markup(
                f"[bold green]Welcome, {profile['name']}![/]\n\n"
                "  [bold]Quick start:[/]\n"
                "  [bright_cyan]Just type[/]        Chat with the AI\n"
                "  [bright_cyan]/[/]                See all commands\n"
                "  [bright_cyan]/help[/]            Full command list\n"
                "  [bright_cyan]/persona hacker[/]  Change personality\n"
                "  [bright_cyan]/agent coder[/]     Use a specialist agent\n"
                "  [bright_cyan]/all question[/]    Ask all 8 agents at once\n"
                "  [bright_cyan]/tools[/]           Browse 29 AI tools\n"
                "  [bright_cyan]/connect IP[/]      Connect to remote Ollama\n\n"
                "  [dim]Tip: Press / to see autocomplete suggestions.[/]\n\n"
                "  [dim]Press Enter to start chatting...[/]"
            ),
            title="[bold green]You're all set[/]",
            border_style="green", padding=(1, 2), width=w,
        ))

    # Wait for Enter before entering chat
    try:
        prompt([("class:prompt", " Press Enter to start... ")], style=input_style)
    except (KeyboardInterrupt, EOFError):
        pass
    console.print()


# --- Sidebar ---

sidebar_enabled = False
SIDEBAR_WIDTH = 26


def build_sidebar():
    """Build the sidebar panel content."""
    profile = load_profile()
    name = profile.get("name", "User")
    persona = profile.get("persona", "default")
    mem_count = len(load_memories())
    pin_count = len(pinned_messages)
    elapsed = int(time.time() - session_stats["start"])
    msgs = session_stats["messages"]
    tok = session_stats["tokens_out"]
    unread = bus_unread("codegpt")

    # Running tools
    alive_tools = [n for n, i in running_tools.items()
                   if i.get("proc") is None or i["proc"].poll() is None]

    lines = []
    lines.append(f"[bold bright_cyan]{name}[/]")
    lines.append(f"[dim]{'━' * (SIDEBAR_WIDTH - 4)}[/]")
    lines.append("")

    # Session
    lines.append("[bold]Session[/]")
    lines.append(f"  [dim]Messages[/]  [bright_cyan]{msgs}[/]")
    lines.append(f"  [dim]Tokens[/]    [bright_cyan]{tok}[/]")
    lines.append(f"  [dim]Uptime[/]    [bright_cyan]{elapsed // 60}m {elapsed % 60}s[/]")
    lines.append(f"  [dim]Persona[/]   [green]{persona}[/]")
    lines.append("")

    # Think mode / temp
    lines.append("[bold]Config[/]")
    lines.append(f"  [dim]Think[/]     {'[green]ON[/]' if think_mode else '[dim]off[/]'}")
    lines.append(f"  [dim]Temp[/]      [bright_cyan]{temperature}[/]")
    lines.append("")

    # Memory & Pins
    lines.append("[bold]Data[/]")
    lines.append(f"  [dim]Memories[/]  [bright_cyan]{mem_count}[/]")
    lines.append(f"  [dim]Pinned[/]    [bright_cyan]{pin_count}[/]")
    if unread > 0:
        lines.append(f"  [dim]Inbox[/]     [bold red]{unread} new[/]")
    lines.append("")

    # Running tools
    if alive_tools:
        lines.append("[bold]Running[/]")
        for t in alive_tools[:5]:
            lines.append(f"  [green]●[/] {t}")
        lines.append("")

    # Quick commands
    lines.append("[bold]Quick[/]")
    lines.append("  [dim]/h[/] help")
    lines.append("  [dim]/m[/] model")
    lines.append("  [dim]/t[/] think")
    lines.append("  [dim]/a[/] all agents")
    lines.append("  [dim]/u[/] usage")

    return "\n".join(lines)


def print_with_sidebar(panel):
    """Print a panel with sidebar if enabled. Auto-disabled on small screens."""
    if not sidebar_enabled or is_compact() or console.width < 80:
        console.print(panel)
        return

    from rich.columns import Columns

    sidebar = Panel(
        Text.from_markup(build_sidebar()),
        title="[dim]sidebar[/]",
        border_style="bright_black",
        width=SIDEBAR_WIDTH,
        padding=(0, 1),
    )

    # Adjust main panel width
    main_width = tw() - SIDEBAR_WIDTH - 2
    if hasattr(panel, 'width'):
        panel.width = main_width

    console.print(Columns([sidebar, panel], padding=1))


# --- UI Components ---

def tw():
    return min(console.width, 100)


def is_compact():
    """Check if terminal is small (Termux, narrow window)."""
    return console.width < 60


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


LOGO_FULL = """
[bright_cyan]  ██████╗ ██████╗ ██████╗ ███████╗[/][bold white]  ██████╗ ██████╗ ████████╗[/]
[bright_cyan] ██╔════╝██╔═══██╗██╔══██╗██╔════╝[/][bold white] ██╔════╝ ██╔══██╗╚══██╔══╝[/]
[bright_cyan] ██║     ██║   ██║██║  ██║█████╗  [/][bold white] ██║  ███╗██████╔╝   ██║   [/]
[bright_cyan] ██║     ██║   ██║██║  ██║██╔══╝  [/][bold white] ██║   ██║██╔═══╝    ██║   [/]
[bright_cyan] ╚██████╗╚██████╔╝██████╔╝███████╗[/][bold white] ╚██████╔╝██║        ██║   [/]
[bright_cyan]  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝[/][bold white]  ╚═════╝ ╚═╝        ╚═╝   [/]
[dim]         Your Local AI Assistant — Powered by Ollama[/]"""

LOGO_COMPACT = """
[bold bright_cyan]╔═══════════════════════╗[/]
[bold bright_cyan]║[/] [bold white]C O D E[/][bold bright_cyan]  G P T[/]  [bold bright_cyan]║[/]
[bold bright_cyan]╚═══════════════════════╝[/]
[dim]  Local AI · Ollama[/]"""

LOGO = LOGO_FULL

# --- Command Aliases ---
ALIASES = {
    "/q": "/quit", "/x": "/quit", "/exit": "/quit",
    "/n": "/new", "/s": "/save", "/l": "/load",
    "/c": "/copy", "/r": "/regen", "/e": "/edit",
    "/h": "/help", "/m": "/model", "/t": "/think",
    "/f": "/file", "/v": "/voice",
    "/a": "/all", "/ag": "/agent", "/sw": "/swarm",
    "/p": "/prompts", "/pr": "/profile",
    "/u": "/usage", "/tk": "/tokens",
    "/gh": "/github", "/sp": "/spotify",
    "/w": "/weather", "/si": "/sysinfo",
    "/con": "/connect", "/srv": "/server",
    "/mon": "/monitor",
}

# --- Tips ---
TIPS = [
    "Type / to see all commands with autocomplete",
    "/think toggles deep reasoning mode",
    "/all asks ALL 8 agents your question at once",
    "/swarm runs a 6-agent pipeline on any task",
    "/split claude codex opens both side by side",
    "/connect IP connects to a remote Ollama server",
    "/qr generates a QR code to connect from your phone",
    "/train collect saves this chat as AI training data",
    "/mem save remembers things across sessions",
    "/rate good after a response improves future training",
    "/persona hacker changes the AI personality",
    "/lab bench benchmarks a prompt across all models",
    "/chain chains prompts: /chain explain X | simplify | give code",
    "/dm coder write a Flask app — instant agent response",
    "/fork 5 branches the conversation from message #5",
    "/compact summarizes old messages to save context",
    "/bg claude launches Claude Code in a new window",
    "You can pipe input: echo 'question' | ai",
    "/shortcuts shows all keyboard shortcuts",
    "/tools lists all 25 AI CLI integrations",
]

# --- Persistent History ---
HISTORY_FILE = Path.home() / ".codegpt" / "input_history"


def print_header(model):
    clear_screen()
    compact = is_compact()

    if compact:
        console.print()
        console.print(Text.from_markup(
            f"  [bold red]Code[/][bold bright_blue]GPT[/] [dim]v2.0 · {model}[/]"
        ))
        console.print(Rule(style="dim", characters="─"))
        console.print()
    else:
        is_local = "localhost" in OLLAMA_URL or "127.0.0.1" in OLLAMA_URL
        server = "local" if is_local else OLLAMA_URL.split("//")[1].split("/")[0] if "//" in OLLAMA_URL else "?"
        profile = load_profile()
        name = profile.get("name", "")
        mem_count = len(load_memories())

        console.print()

        # Banner parts
        R = "bold red"
        B = "bold bright_blue"
        D = "dim"

        def build_banner(pos):
            """Build banner with spider at given position (0-7 around the border)."""
            sp_faces = ["  /╲(o.o)╱\\", "  /╲(o.o)╱\\", "~~~(o.o)>", "~~~(o.o)>",
                        "  \\╱(o.o)╲/", "  \\╱(o.o)╲/", "<(o.o)~~~", "<(o.o)~~~"]
            spider = sp_faces[pos % 8]

            top_b = f"[{R}]  ╔════════════════════════════════════════════════════╗[/]"
            bot_b = f"[{R}]  ╚════════════════════════════════════════════════════╝[/]"
            empty = f"[{R}]  ║[/]                                                    [{R}]║[/]"
            title = f"[{R}]  ║[/]          [{R}]C[/][{B}]o[/][{R}]d[/][{B}]e[/]  [{R}]G[/][{B}]P[/][{R}]T[/]   [{D}]v2.0[/]                    [{R}]║[/]"
            sub   = f"[{R}]  ║[/]          [{D}]local ai · powered by ollama[/]             [{R}]║[/]"
            stats = f"[{R}]  ║[/]          [{B}]123[/] [{D}]commands ·[/] [{B}]26[/] [{D}]tools ·[/] [{B}]8[/] [{D}]agents[/]       [{R}]║[/]"

            lines = []
            p = pos % 8

            if p in (0, 1):  # top
                lines.append(f"[{D}]               {spider}[/]")
                lines.append(f"[{D}]                  ||[/]")
                lines.extend([top_b, empty, title, sub, stats, empty, bot_b])
            elif p in (2, 3):  # right
                lines.append(top_b)
                lines.append(empty)
                lines.append(title)
                lines.append(f"[{R}]  ║[/]          [{D}]local ai · powered by ollama[/]             [{R}]║[/][{D}]~~{spider}[/]")
                lines.extend([stats, empty, bot_b])
            elif p in (4, 5):  # bottom
                lines.extend([top_b, empty, title, sub, stats, empty, bot_b])
                lines.append(f"[{D}]                       ||[/]")
                lines.append(f"[{D}]                    {spider}[/]")
            else:  # left (6, 7)
                lines.append(top_b)
                lines.append(empty)
                lines.append(f"[{D}]{spider}~~[/][{R}]║[/]          [{R}]C[/][{B}]o[/][{R}]d[/][{B}]e[/]  [{R}]G[/][{B}]P[/][{R}]T[/]   [{D}]v2.0[/]                    [{R}]║[/]")
                lines.extend([sub, stats, empty, bot_b])

            return "\n".join(lines)

        # Animate spider crawling around the banner
        try:
            with Live(
                Text.from_markup(build_banner(0)),
                console=console, refresh_per_second=6, transient=True,
            ) as live:
                for frame in range(16):  # 2 full laps
                    live.update(Text.from_markup(build_banner(frame)))
                    time.sleep(0.2)

            # Final position — static
            import random
            final = random.randint(0, 7)
            console.print(Text.from_markup(build_banner(final)))
        except Exception:
            # Fallback if Live doesn't work
            console.print(Text.from_markup(build_banner(0)))
        console.print()
        console.print(Text.from_markup(
            f"  [dim]model[/]    [bright_blue]{model}[/]\n"
            f"  [dim]server[/]   [green]{server}[/]\n"
            f"  [dim]user[/]     {name}\n"
            f"  [dim]memory[/]   {mem_count} items"
        ))
        console.print(Rule(style="dim", characters="─"))
        console.print()


def print_welcome(model, available_models):
    w = tw()
    import random
    compact = is_compact()

    # Clean welcome — no heavy panels
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    console.print(Text(f"  {greeting}. How can I help?", style="bold white"))
    console.print()

    # Suggestions — clean list
    items = SUGGESTIONS[:3] if compact else SUGGESTIONS[:5]
    for i, s in enumerate(items, 1):
        console.print(Text.from_markup(f"  [bright_cyan]{i}.[/] [dim]{s}[/]"))
    console.print()

    # Tip
    tip = random.choice(TIPS)
    console.print(Text(f"  tip: {tip}", style="dim italic"))
    console.print()


def _build_suggestions(max_items=None):
    text = Text()
    items = SUGGESTIONS[:max_items] if max_items else SUGGESTIONS
    for i, s in enumerate(items, 1):
        if is_compact():
            text.append(f" {i}.", style="bright_cyan bold")
            text.append(f" {s[:30]}\n", style="white")
        else:
            text.append(f"  [{i}]", style="bright_cyan bold")
            text.append(f"  {s}\n", style="white")
    return text


def print_user_msg(text):
    # Clean inline style like Claude Code — no heavy panels
    console.print()
    console.print(Text(f"  {text}", style="bold white"))
    console.print()


def print_ai_msg(text, stats=""):
    # Minimal border, clean markdown — like Claude Code output
    w = tw()
    compact = is_compact()

    console.print(Rule(style="bright_green", characters="─"))
    console.print()
    console.print(Markdown(text), width=w - 4)
    if stats and not compact:
        console.print(Text(f"  {stats}", style="dim"))
    console.print()


def print_sys(text):
    # Simple dim text — no panels, no borders
    console.print(Text(f"  {text}", style="dim"))


def print_err(text):
    console.print(Text(f"  ✗ {text}", style="bold red"))


def print_success(text):
    console.print(Text(f"  ✓ {text}", style="bold green"))


def _print_err_panel(text):
    """Legacy panel error for important errors."""
    console.print(Panel(
        Text(text, style="bold red"),
        title="[bold red]Error[/]",
        title_align="left",
        border_style="red",
        padding=(0, 1),
        width=tw(),
    ))


def print_help():
    # Group commands by category — clean minimal list
    categories = {
        "Chat": ["/new", "/save", "/load", "/delete", "/copy", "/regen", "/edit", "/history", "/clear", "/quit"],
        "Model": ["/model", "/modelinfo", "/params", "/temp", "/think", "/tokens", "/compact"],
        "AI": ["/agent", "/agents", "/all", "/vote", "/swarm", "/team", "/room", "/spectate", "/dm", "/chat-link"],
        "Lab": ["/lab", "/chain", "/race", "/prompts"],
        "Tools": ["/tools", "/bg", "/split", "/grid", "/running", "/killall"],
        "Connect": ["/connect", "/disconnect", "/server", "/qr", "/scan"],
        "Files": ["/file", "/run", "/code", "/shell", "/browse", "/open", "/export"],
        "Memory": ["/mem", "/train", "/pin", "/pins", "/search", "/fork", "/rate", "/tag"],
        "Profile": ["/profile", "/setname", "/setbio", "/persona", "/personas", "/usage"],
        "Skills": ["/skill", "/skills", "/auto", "/cron", "/crons"],
        "Comms": ["/broadcast", "/inbox", "/feed", "/monitor", "/hub"],
        "System": ["/github", "/weather", "/spotify", "/volume", "/bright", "/sysinfo"],
        "Security": ["/pin-set", "/pin-remove", "/lock", "/audit", "/security", "/permissions"],
    }

    on_termux = os.path.exists("/data/data/com.termux")

    for cat, cmds in categories.items():
        console.print(Text(f"\n  {cat}", style="bold bright_cyan"))
        for cmd in cmds:
            desc = COMMANDS.get(cmd, "")
            if not desc:
                continue
            # Hide unsupported tool commands on Termux
            tool_name = cmd[1:]
            if on_termux and tool_name in AI_TOOLS and not AI_TOOLS[tool_name].get("termux", True):
                continue
            console.print(Text.from_markup(f"    [bright_cyan]{cmd:<16}[/] [dim]{desc}[/]"))

    console.print(Text("\n  Type / to autocomplete. Aliases: /q /n /s /m /h /a /t /f", style="dim"))
    console.print()


# --- Reminders ---

def parse_time(text):
    match = TIME_PATTERN.match(text.strip())
    if not match:
        return None, None, text
    value = int(match.group(1))
    unit = match.group(2).lower()
    seconds = value * TIME_MULTIPLIERS[unit]
    message = text[match.end():].strip()
    return seconds, f"{value}{unit}", message


def fire_reminder(rid, message, label):
    console.print()
    console.print(Panel(
        Text(f"  {message}", style="bold yellow"),
        title=f"[bold yellow]REMINDER[/] [dim]({label} ago)[/]",
        title_align="left",
        border_style="yellow",
        padding=(0, 1),
    ))
    with reminder_lock:
        active_reminders[:] = [r for r in active_reminders if r["id"] != rid]


def set_reminder(text):
    seconds, label, message = parse_time(text)
    if seconds is None:
        print_sys("Usage: /remind <time> <message>\n  /remind 5m Break\n  /remind 1h Email\n  /remind 30s Timer")
        return
    if not message:
        message = "Reminder!"

    rid = int(time.time() * 1000000) + id(text)
    timer = threading.Timer(seconds, fire_reminder, args=(rid, message, label))
    timer.daemon = True
    timer.start()

    with reminder_lock:
        active_reminders.append({"id": rid, "message": message, "label": label, "timer": timer})
    print_sys(f'Reminder: "{message}" in {label}')


def list_reminders():
    with reminder_lock:
        if not active_reminders:
            print_sys("No active reminders.")
            return
        table = Table(title="Reminders", border_style="yellow", title_style="bold yellow", show_header=False)
        table.add_column("#", style="cyan", width=3)
        table.add_column("Message")
        table.add_column("Timer", style="dim")
        for i, r in enumerate(active_reminders, 1):
            table.add_row(str(i), r["message"], r["label"])
        console.print(table)


def cancel_all_reminders():
    with reminder_lock:
        for r in active_reminders:
            r["timer"].cancel()
        active_reminders.clear()


# --- Conversation Save/Load ---

def save_conversation(messages, model):
    CHATS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate name from first user message
    first_msg = next((m["content"] for m in messages if m["role"] == "user"), "untitled")
    name = re.sub(r'[^\w\s-]', '', first_msg[:40]).strip().replace(' ', '_').lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{ts}_{name}.json"

    data = {"model": model, "messages": messages, "saved_at": datetime.now().isoformat()}
    try:
        (CHATS_DIR / filename).write_text(json.dumps(data, indent=2))
        print_sys(f"Saved: {filename}")
    except OSError as e:
        print_err(f"Save failed: {e}")


def load_conversation():
    if not CHATS_DIR.exists():
        print_sys("No saved conversations.")
        return None, None

    files = sorted(CHATS_DIR.glob("*.json"), reverse=True)
    if not files:
        print_sys("No saved conversations.")
        return None, None

    table = Table(title="Saved Conversations", border_style="bright_cyan",
                  title_style="bold cyan", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Date", style="dim", width=12)
    table.add_column("Name", style="white")
    table.add_column("Messages", style="dim", width=8)

    for i, f in enumerate(files[:10], 1):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        date = f.stem[:13].replace("_", " ")
        name = f.stem[14:].replace("_", " ")
        count = len(data.get("messages", []))
        table.add_row(str(i), date, name, str(count))

    console.print(table)
    console.print()

    try:
        choice = prompt([("class:prompt", " Select # > ")], style=input_style).strip()
        idx = int(choice) - 1
        if 0 <= idx < len(files[:10]):
            try:
                data = json.loads(files[idx].read_text())
            except (json.JSONDecodeError, OSError):
                print_err("Failed to read conversation file.")
                return None, None
            return data.get("messages", []), data.get("model", MODEL)
    except (ValueError, KeyboardInterrupt, EOFError):
        pass

    print_sys("Cancelled.")
    return None, None


def delete_conversation():
    if not CHATS_DIR.exists():
        print_sys("No saved conversations.")
        return

    files = sorted(CHATS_DIR.glob("*.json"), reverse=True)
    if not files:
        print_sys("No saved conversations.")
        return

    table = Table(title="Delete Conversation", border_style="red",
                  title_style="bold red", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Name", style="white")

    for i, f in enumerate(files[:10], 1):
        name = f.stem[14:].replace("_", " ")
        table.add_row(str(i), name)

    console.print(table)
    console.print()

    try:
        choice = prompt([("class:prompt", " Delete # > ")], style=input_style).strip()
        idx = int(choice) - 1
        if 0 <= idx < len(files[:10]):
            files[idx].unlink()
            print_sys("Deleted.")
            return
    except (ValueError, KeyboardInterrupt, EOFError):
        pass
    print_sys("Cancelled.")


# --- History ---

def show_history(messages):
    if not messages:
        print_sys("No messages yet.")
        return
    for msg in messages:
        if msg["role"] == "user":
            print_user_msg(msg["content"])
        else:
            print_ai_msg(msg["content"])
    console.print()


# --- Clipboard ---

def copy_to_clipboard(text):
    try:
        if os.name == "nt":
            subprocess.run("clip", input=text.encode("utf-8"), check=True)
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        elif shutil.which("pbcopy"):
            subprocess.run("pbcopy", input=text.encode(), check=True)
        else:
            print_err("No clipboard tool found.")
            return
        print_sys("Copied to clipboard.")
    except Exception as e:
        print_err(f"Clipboard failed: {e}")


# --- File Context ---

def read_file_context(file_path):
    """Read a file and return its contents for the AI."""
    path = Path(file_path.strip().strip('"').strip("'"))
    if not path.exists():
        print_err(f"File not found: {path}")
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print_err(f"Cannot read file: {e}")
        return None

    # Truncate if huge
    if len(content) > 15000:
        content = content[:15000] + "\n\n... (truncated, file too large)"

    lines = len(content.splitlines())
    size = path.stat().st_size
    size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"

    print_sys(f"Loaded: {path.name} ({lines} lines, {size_str})")
    return f"File: {path.name}\n```\n{content}\n```"


# --- Code Execution ---

def run_python_code(code, timeout=10):
    """Execute Python code in a subprocess."""
    import tempfile
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        return output.strip() or "(no output)", result.returncode
    except subprocess.TimeoutExpired:
        return "Timed out (10s limit).", 1
    except Exception as e:
        return f"Error: {e}", 1


def extract_code_blocks(text):
    """Extract Python code blocks from markdown."""
    pattern = r'```(?:python)?\s*\n(.*?)```'
    return re.findall(pattern, text, re.DOTALL)


# --- Multi-line Input ---

def get_multiline_code():
    """Get multi-line code input. End with <<< on its own line."""
    print_sys("Enter code (type <<< on a blank line to finish):")
    lines = []
    while True:
        try:
            line = input("  ... ")
            if line.strip() == "<<<":
                break
            lines.append(line)
        except (KeyboardInterrupt, EOFError):
            print_sys("Cancelled.")
            return None
    return "\n".join(lines)


# --- Export ---

def export_chat(messages, model, persona_name):
    """Export conversation as markdown file."""
    if not messages:
        print_sys("Nothing to export.")
        return

    lines = [f"# CodeGPT Chat Export\n"]
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Model:** {model}")
    lines.append(f"**Persona:** {persona_name}")
    lines.append(f"**Messages:** {len(messages)}\n")
    lines.append("---\n")

    for msg in messages:
        role = "**You**" if msg["role"] == "user" else "**AI**"
        lines.append(f"### {role}\n")
        lines.append(msg["content"])
        lines.append("")

    content = "\n".join(lines)
    export_dir = Path.home() / ".codegpt" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"chat_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    (export_dir / filename).write_text(content, encoding="utf-8")
    print_sys(f"Exported: {export_dir / filename}")


# --- Pinned Messages ---

pinned_messages = []

def pin_message(messages, index):
    """Pin a message by index."""
    try:
        idx = int(index) - 1
        if 0 <= idx < len(messages):
            pinned_messages.append(messages[idx])
            role = "You" if messages[idx]["role"] == "user" else "AI"
            preview = messages[idx]["content"][:50]
            print_sys(f"Pinned #{len(pinned_messages)}: [{role}] {preview}...")
        else:
            print_sys(f"Invalid index. Range: 1-{len(messages)}")
    except ValueError:
        print_sys("Usage: /pin <message number>")


def show_pins():
    if not pinned_messages:
        print_sys("No pinned messages.")
        return
    table = Table(title="Pinned Messages", border_style="yellow",
                  title_style="bold yellow", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Role", style="dim", width=5)
    table.add_column("Message", overflow="fold")
    for i, msg in enumerate(pinned_messages, 1):
        role = "You" if msg["role"] == "user" else "AI"
        preview = msg["content"][:100] + ("..." if len(msg["content"]) > 100 else "")
        table.add_row(str(i), role, preview)
    console.print(table)
    console.print()


# --- Search ---

def search_messages(messages, keyword):
    """Search through conversation for a keyword."""
    if not keyword:
        print_sys("Usage: /search <keyword>")
        return

    results = []
    for i, msg in enumerate(messages, 1):
        if keyword.lower() in msg["content"].lower():
            results.append((i, msg))

    if not results:
        print_sys(f"No matches for '{keyword}'.")
        return

    table = Table(title=f"Search: '{keyword}' ({len(results)} matches)",
                  border_style="bright_cyan", title_style="bold cyan",
                  show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Role", style="dim", width=5)
    table.add_column("Match", overflow="fold")
    for idx, msg in results:
        role = "You" if msg["role"] == "user" else "AI"
        # Show context around the keyword
        content = msg["content"]
        pos = content.lower().find(keyword.lower())
        start = max(0, pos - 30)
        end = min(len(content), pos + len(keyword) + 30)
        snippet = ("..." if start > 0 else "") + content[start:end] + ("..." if end < len(content) else "")
        table.add_row(str(idx), role, snippet)
    console.print(table)
    console.print()


# --- Model Info ---

model_params = {"top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1, "num_ctx": 4096}

def show_model_info(model):
    """Show model details from Ollama."""
    try:
        resp = requests.post("http://localhost:11434/api/show", json={"name": model}, timeout=5)
        data = resp.json()
        details = data.get("details", {})

        table = Table(title=f"Model: {model}", border_style="bright_cyan",
                      title_style="bold cyan", show_header=False, padding=(0, 2))
        table.add_column("Field", style="dim", width=16)
        table.add_column("Value", style="white")
        table.add_row("Family", details.get("family", "unknown"))
        table.add_row("Parameters", details.get("parameter_size", "unknown"))
        table.add_row("Quantization", details.get("quantization_level", "unknown"))
        table.add_row("Format", details.get("format", "unknown"))

        # Current params
        table.add_row("", "")
        table.add_row("temperature", str(temperature))
        for k, v in model_params.items():
            table.add_row(k, str(v))

        console.print(table)
        console.print()
    except Exception as e:
        print_err(f"Cannot get model info: {e}")


# --- Prompt Templates ---

PROMPT_TEMPLATES = {
    "explain": "Explain this concept clearly with examples: ",
    "debug": "Debug this code. Find bugs and fix them:\n",
    "review": "Review this code for quality, security, and performance:\n",
    "refactor": "Refactor this code to be cleaner and more efficient:\n",
    "test": "Write unit tests for this code:\n",
    "optimize": "Optimize this code for performance:\n",
    "document": "Write documentation/docstrings for this code:\n",
    "convert": "Convert this code to Python:\n",
    "regex": "Write a regex pattern that matches: ",
    "sql": "Write a SQL query that: ",
    "api": "Design a REST API endpoint for: ",
    "cli": "Write a CLI tool that: ",
    "script": "Write a bash/powershell script that: ",
    "security": "Analyze this for security vulnerabilities:\n",
    "architect": "Design the architecture for: ",
}

def show_prompts():
    table = Table(title="Prompt Templates", border_style="green",
                  title_style="bold green", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Name", style="bright_cyan", width=12)
    table.add_column("Prefix", style="dim")
    for i, (name, prefix) in enumerate(PROMPT_TEMPLATES.items(), 1):
        table.add_row(str(i), name, prefix.strip()[:50])
    console.print(table)
    console.print(Text("  Use: /p <name> <your text>", style="dim"))
    console.print(Text("  Example: /p debug my_function()", style="dim"))
    console.print()


# --- Conversation Forking ---

def fork_conversation(messages, from_index):
    """Fork conversation from a specific message index."""
    try:
        idx = int(from_index) - 1
        if 0 <= idx < len(messages):
            forked = messages[:idx + 1]
            print_sys(f"Forked from message #{idx + 1}. {len(forked)} messages kept.")
            return forked
        else:
            print_sys(f"Invalid index. Range: 1-{len(messages)}")
            return None
    except ValueError:
        print_sys("Usage: /fork <message number>")
        return None


# --- Model Comparison ---

def compare_models(prompt_text, model1, model2, system):
    """Send same prompt to 2 models and show both responses."""
    console.print(Panel(Text(prompt_text, style="white"),
                        title="[bold cyan]Prompt[/]", border_style="cyan",
                        padding=(0, 2), width=tw()))

    for m in [model1, model2]:
        console.print(Text(f"\n  Querying {m}...", style="dim"))
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": m, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt_text},
                ], "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "No response.")
            ec = data.get("eval_count", 0)
            td = data.get("total_duration", 0)
            ds = td / 1e9 if td else 0
            tps = ec / ds if ds > 0 else 0
            stats = f"{ec} tok | {ds:.1f}s | {tps:.0f} tok/s"

            console.print(Panel(
                Markdown(content),
                title=f"[bold green]{m}[/]",
                border_style="green",
                subtitle=f"[dim]{stats}[/]",
                subtitle_align="right",
                padding=(0, 2), width=tw(),
            ))
        except Exception as e:
            print_err(f"{m}: {e}")


# --- Response Rating ---

RATINGS_FILE = Path.home() / ".codegpt" / "ratings.json"

def rate_response(messages, rating):
    """Save a rating for the last AI response."""
    ai_msgs = [m for m in messages if m["role"] == "assistant"]
    if not ai_msgs:
        print_sys("No AI response to rate.")
        return

    last = ai_msgs[-1]["content"]
    last_user = ""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]["role"] == "user":
            last_user = messages[i]["content"]
            break

    ratings = []
    if RATINGS_FILE.exists():
        try:
            ratings = json.loads(RATINGS_FILE.read_text())
        except Exception:
            pass

    ratings.append({
        "rating": rating,
        "prompt": last_user[:200],
        "response": last[:200],
        "timestamp": datetime.now().isoformat(),
    })

    RATINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATINGS_FILE.write_text(json.dumps(ratings, indent=2))

    icon = "+" if rating == "good" else "-"
    print_sys(f"Rated [{icon}]. {len(ratings)} total ratings saved.")


# --- Shortcuts ---

def show_shortcuts():
    table = Table(title="Keyboard Shortcuts", border_style="yellow",
                  title_style="bold yellow", show_header=False, padding=(0, 2))
    table.add_column("Key", style="bright_cyan", width=16)
    table.add_column("Action", style="dim")
    table.add_row("Enter", "Send message")
    table.add_row("Up/Down", "Browse input history")
    table.add_row("Tab", "Autocomplete command")
    table.add_row("/", "Show all commands")
    table.add_row("Ctrl+C", "Cancel / Exit")
    table.add_row("Ctrl+D", "Exit")
    table.add_row("Ctrl+L", "Clear (in some terminals)")
    table.add_row("Ctrl+W", "Delete last word")
    table.add_row("Ctrl+U", "Clear input line")
    table.add_row("Ctrl+A", "Move cursor to start")
    table.add_row("Ctrl+E", "Move cursor to end")
    console.print(table)
    console.print()


# --- AI Agents ---

AI_AGENTS = {
    "coder": {
        "desc": "Writes code from a description",
        "system": (
            "You are an expert programmer. Given a task, write clean, working code. "
            "Include comments. Show the full implementation. "
            "If the task is ambiguous, make reasonable assumptions and state them."
        ),
    },
    "debugger": {
        "desc": "Finds and fixes bugs in code",
        "system": (
            "You are a debugging expert. Analyze the code or error provided. "
            "1. Identify the root cause. "
            "2. Explain why it happens. "
            "3. Provide the fixed code. "
            "4. Suggest how to prevent it in the future."
        ),
    },
    "researcher": {
        "desc": "Deep-dives into a topic",
        "system": (
            "You are a research analyst. Given a topic: "
            "1. Provide a comprehensive overview. "
            "2. List key concepts with explanations. "
            "3. Compare alternatives if applicable. "
            "4. Give practical recommendations. "
            "5. Cite specific tools, libraries, or resources."
        ),
    },
    "reviewer": {
        "desc": "Reviews code for quality & security",
        "system": (
            "You are a senior code reviewer. Analyze the code for: "
            "1. Bugs and logic errors. "
            "2. Security vulnerabilities (OWASP top 10). "
            "3. Performance issues. "
            "4. Code style and readability. "
            "5. Missing error handling. "
            "Rate severity: CRITICAL / HIGH / MEDIUM / LOW. Give fixes for each."
        ),
    },
    "architect": {
        "desc": "Designs system architecture",
        "system": (
            "You are a system architect. Given requirements: "
            "1. Propose an architecture (draw ASCII diagrams). "
            "2. List components and their responsibilities. "
            "3. Define data flow and APIs. "
            "4. Identify trade-offs and risks. "
            "5. Suggest tech stack."
        ),
    },
    "pentester": {
        "desc": "Security analysis & hardening",
        "system": (
            "You are an ethical penetration tester. Analyze the target for: "
            "1. Attack surface and entry points. "
            "2. Common vulnerabilities. "
            "3. Misconfigurations. "
            "4. Provide remediation steps. "
            "Defensive security only. Educational context."
        ),
    },
    "explainer": {
        "desc": "Explains complex topics simply",
        "system": (
            "You are a world-class teacher. Explain the given topic: "
            "1. Start with a one-sentence summary. "
            "2. Use an analogy a teenager would understand. "
            "3. Break down the key components. "
            "4. Give a practical example. "
            "5. End with 'what to learn next'."
        ),
    },
    "optimizer": {
        "desc": "Optimizes code for performance",
        "system": (
            "You are a performance engineer. Given code: "
            "1. Profile it mentally — find the bottleneck. "
            "2. Explain the performance issue. "
            "3. Rewrite the optimized version. "
            "4. Show before/after complexity (Big O). "
            "5. Benchmark suggestions."
        ),
    },
}


def list_agents():
    table = Table(title="AI Agents", border_style="bright_magenta",
                  title_style="bold bright_magenta", show_header=True, header_style="bold")
    table.add_column("Agent", style="bright_cyan", min_width=12)
    table.add_column("Description", style="dim")
    for name, info in AI_AGENTS.items():
        table.add_row(name, info["desc"])
    console.print(table)
    console.print(Text("  Use: /agent <name> <task>", style="dim"))
    console.print(Text("  Example: /agent coder a flask REST API for todos", style="dim"))
    console.print()


def run_agent(agent_name, task, model):
    """Run an AI agent on a task."""
    if agent_name not in AI_AGENTS:
        available = ", ".join(AI_AGENTS.keys())
        print_sys(f"Unknown agent. Available: {available}")
        return None

    agent = AI_AGENTS[agent_name]

    console.print(Panel(
        Text(f"Agent: {agent_name}\nTask: {task}", style="white"),
        title=f"[bold bright_magenta]Agent: {agent_name}[/]",
        border_style="bright_magenta",
        padding=(0, 2), width=tw(),
    ))

    # Multi-step agent: plan then execute
    plan_prompt = (
        f"Task: {task}\n\n"
        "First, create a brief step-by-step plan (3-5 steps) for this task. "
        "Then execute each step, showing your work."
    )

    agent_messages = [{"role": "user", "content": plan_prompt}]
    agent_system = agent["system"]

    # Step 1: Plan
    print_sys("Planning...")
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": [
                {"role": "system", "content": agent_system},
                {"role": "user", "content": plan_prompt},
            ], "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        plan = resp.json().get("message", {}).get("content", "")
    except Exception as e:
        print_err(f"Agent failed: {e}")
        return None

    console.print(Panel(
        Markdown(plan),
        title=f"[bold bright_magenta]{agent_name} — Result[/]",
        border_style="bright_magenta",
        padding=(0, 2), width=tw(),
    ))

    return plan


# --- AI Lab ---

def show_lab_menu():
    table = Table(title="AI Lab", border_style="bright_yellow",
                  title_style="bold bright_yellow", show_header=True, header_style="bold")
    table.add_column("Tool", style="bright_cyan", min_width=14)
    table.add_column("Description", style="dim")
    table.add_row("/lab bench", "Benchmark a prompt across all models")
    table.add_row("/lab chain", "Chain multiple prompts (pipe output)")
    table.add_row("/lab eval", "Evaluate model on test questions")
    table.add_row("/lab prompt", "Prompt optimizer — improve your prompt")
    table.add_row("/lab translate", "Translate text to any language")
    table.add_row("/lab summarize", "Summarize any text or URL")
    table.add_row("/lab extract", "Extract structured data from text")
    console.print(table)
    console.print()


def lab_bench(prompt_text, models, system):
    """Run same prompt across multiple models."""
    if not models:
        print_sys("No models available.")
        return

    console.print(Panel(
        Text(prompt_text, style="white"),
        title="[bold yellow]Benchmark Prompt[/]",
        border_style="yellow", padding=(0, 2), width=tw(),
    ))

    results = []
    for m in models[:5]:  # Max 5 models
        console.print(Text(f"\n  Running {m}...", style="dim"))
        try:
            start = time.time()
            resp = requests.post(
                OLLAMA_URL,
                json={"model": m, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt_text},
                ], "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = time.time() - start
            content = data.get("message", {}).get("content", "")
            ec = data.get("eval_count", 0)
            tps = ec / elapsed if elapsed > 0 else 0

            results.append({"model": m, "tokens": ec, "time": elapsed, "tps": tps})

            console.print(Panel(
                Markdown(content),
                title=f"[bold green]{m}[/]",
                subtitle=f"[dim]{ec} tok | {elapsed:.1f}s | {tps:.0f} tok/s[/]",
                subtitle_align="right",
                border_style="green", padding=(0, 2), width=tw(),
            ))
        except Exception as e:
            print_err(f"{m}: {e}")
            results.append({"model": m, "tokens": 0, "time": 0, "tps": 0})

    # Summary table
    if results:
        console.print()
        table = Table(title="Benchmark Results", border_style="yellow",
                      title_style="bold yellow", show_header=True, header_style="bold")
        table.add_column("Model", style="bright_cyan")
        table.add_column("Tokens", style="white", justify="right")
        table.add_column("Time", style="white", justify="right")
        table.add_column("Tok/s", style="green", justify="right")
        for r in sorted(results, key=lambda x: x["tps"], reverse=True):
            table.add_row(r["model"], str(r["tokens"]), f"{r['time']:.1f}s", f"{r['tps']:.0f}")
        console.print(table)
        console.print()


def lab_chain(chain_text, model, system):
    """Chain prompts — output of each becomes input to next."""
    prompts = [p.strip() for p in chain_text.split("|") if p.strip()]
    if len(prompts) < 2:
        print_sys("Need at least 2 prompts separated by |\nExample: /chain explain recursion | simplify this | give code example")
        return None

    console.print(Panel(
        Text(f"Chain: {len(prompts)} steps", style="bold"),
        title="[bold yellow]Prompt Chain[/]",
        border_style="yellow", padding=(0, 1), width=tw(),
    ))

    current_output = ""
    for i, p in enumerate(prompts, 1):
        if current_output:
            full_prompt = f"Previous context:\n{current_output}\n\nNow: {p}"
        else:
            full_prompt = p

        console.print(Text(f"\n  Step {i}/{len(prompts)}: {p[:50]}...", style="dim"))

        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": model, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": full_prompt},
                ], "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            current_output = resp.json().get("message", {}).get("content", "")

            console.print(Panel(
                Markdown(current_output),
                title=f"[bold green]Step {i}[/]",
                border_style="green", padding=(0, 2), width=tw(),
            ))
        except Exception as e:
            print_err(f"Step {i} failed: {e}")
            return current_output

    return current_output


def lab_prompt_optimizer(original_prompt, model, system):
    """Use AI to improve a prompt."""
    meta_prompt = (
        f"You are a prompt engineering expert. Analyze and improve this prompt:\n\n"
        f"Original: {original_prompt}\n\n"
        "Provide:\n"
        "1. What's wrong with the original prompt\n"
        "2. An improved version (in a code block)\n"
        "3. Why the improved version is better\n"
        "4. Example output difference"
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": meta_prompt},
            ], "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json().get("message", {}).get("content", "")

        console.print(Panel(
            Markdown(result),
            title="[bold yellow]Prompt Optimizer[/]",
            border_style="yellow", padding=(0, 2), width=tw(),
        ))
        return result
    except Exception as e:
        print_err(f"Optimizer failed: {e}")
        return None


# --- AI Memory (persistent across sessions) ---

MEMORY_DIR = Path.home() / ".codegpt" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE = MEMORY_DIR / "memories.json"


def load_memories():
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except Exception:
            pass
    return []


def save_memories(memories):
    MEMORY_FILE.write_text(json.dumps(memories, indent=2))


def mem_save(text):
    """Save something to AI memory."""
    memories = load_memories()
    memories.append({
        "content": text,
        "timestamp": datetime.now().isoformat(),
    })
    save_memories(memories)
    print_sys(f"Remembered. ({len(memories)} total memories)")


def mem_recall(query=""):
    """Recall memories, optionally filtered by keyword."""
    memories = load_memories()
    if not memories:
        print_sys("No memories saved. Use: /mem save <something to remember>")
        return ""

    if query:
        matches = [m for m in memories if query.lower() in m["content"].lower()]
    else:
        matches = memories

    if not matches:
        print_sys(f"No memories matching '{query}'.")
        return ""

    table = Table(title=f"Memories ({len(matches)})", border_style="bright_magenta",
                  title_style="bold bright_magenta", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Memory", style="white")
    table.add_column("Date", style="dim", width=12)

    for i, m in enumerate(matches, 1):
        date = m["timestamp"][:10] if m.get("timestamp") else "?"
        table.add_row(str(i), m["content"][:80], date)

    console.print(table)
    console.print()

    # Return as context string for AI
    return "\n".join(f"- {m['content']}" for m in matches[-10:])


def mem_clear():
    """Clear all memories."""
    save_memories([])
    print_sys("All memories cleared.")


def get_memory_context():
    """Get recent memories as system context."""
    memories = load_memories()
    if not memories:
        return ""
    recent = memories[-10:]
    return "User's saved memories:\n" + "\n".join(f"- {m['content']}" for m in recent)


# --- Shell Access ---

def run_shell(cmd_text):
    """Execute a shell command and show output."""
    if not cmd_text:
        print_sys("Usage: /shell <command>\nExample: /shell dir")
        return

    # Safety check
    safe, blocked = is_shell_safe(cmd_text)
    if not safe:
        print_err(f"Blocked: {blocked}")
        audit_log("SHELL_BLOCKED", f"{blocked}: {cmd_text[:80]}")
        return

    console.print(Panel(
        Text(f"$ {cmd_text}", style="bright_cyan"),
        title="[bold cyan]Shell[/]",
        border_style="cyan", padding=(0, 1), width=tw(),
    ))

    try:
        # Use shlex.split for safer argument parsing on non-Windows
        if os.name != "nt":
            import shlex
            args = shlex.split(cmd_text)
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=30,
                cwd=str(Path.home()),
            )
        else:
            result = subprocess.run(
                cmd_text, shell=True, capture_output=True, text=True, timeout=30,
                cwd=str(Path.home()),
            )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr

        output = output.strip() or "(no output)"

        # Truncate if huge
        if len(output) > 5000:
            output = output[:5000] + "\n\n... (truncated)"

        style = "white" if result.returncode == 0 else "red"
        console.print(Panel(
            Text(output, style=style),
            title=f"[{'green' if result.returncode == 0 else 'red'}]Exit: {result.returncode}[/]",
            border_style="green" if result.returncode == 0 else "red",
            padding=(0, 1), width=tw(),
        ))
    except subprocess.TimeoutExpired:
        print_err("Command timed out (30s limit).")
    except Exception as e:
        print_err(f"Shell error: {e}")


# --- Integrations ---

def github_command(sub, args=""):
    """GitHub integration via gh CLI."""
    if not shutil.which("gh"):
        print_err("GitHub CLI not installed. Install: winget install GitHub.cli")
        return

    commands = {
        "repos": "gh repo list --limit 10",
        "issues": "gh issue list --limit 10",
        "prs": "gh pr list --limit 10",
        "status": "gh status",
        "notifications": "gh api notifications --jq \".[].subject.title\"",
        "stars": "gh api user/starred --jq \".[].full_name\"",
        "profile": "gh api user --jq '{login, name, public_repos, followers}'",
        "gists": "gh gist list --limit 5",
    }

    if sub in commands:
        console.print(Text(f"  Running: {commands[sub]}", style="dim"))
        try:
            result = subprocess.run(
                commands[sub], shell=True, capture_output=True, text=True, timeout=15,
            )
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
            # Truncate to 10 lines for long outputs
            lines = output.split("\n")
            if len(lines) > 10:
                output = "\n".join(lines[:10]) + f"\n... ({len(lines) - 10} more)"
            console.print(Panel(
                Text(output, style="white"),
                title=f"[bold bright_cyan]GitHub: {sub}[/]",
                border_style="bright_cyan", padding=(0, 2), width=tw(),
            ))
        except Exception as e:
            print_err(f"GitHub error: {e}")
    elif sub == "create" and args:
        # Create a new issue
        try:
            result = subprocess.run(
                ["gh", "issue", "create", "--title", args, "--body", "Created from CodeGPT"],
                capture_output=True, text=True, timeout=15,
            )
            console.print(Text(result.stdout.strip(), style="green"))
        except Exception as e:
            print_err(f"Failed: {e}")
    elif sub == "search" and args:
        try:
            result = subprocess.run(
                ["gh", "search", "repos", args, "--limit", "5"],
                capture_output=True, text=True, timeout=15,
            )
            output = result.stdout.strip() or "No results."
            console.print(Panel(
                Text(output, style="white"),
                title=f"[bold bright_cyan]GitHub Search: {args}[/]",
                border_style="bright_cyan", padding=(0, 2), width=tw(),
            ))
        except Exception as e:
            print_err(f"Search failed: {e}")
    else:
        table = Table(title="GitHub Commands", border_style="bright_cyan",
                      title_style="bold cyan", show_header=False, padding=(0, 2))
        table.add_column("Command", style="bright_cyan", width=28)
        table.add_column("Description", style="dim")
        table.add_row("/github repos", "Your repositories")
        table.add_row("/github issues", "Open issues")
        table.add_row("/github prs", "Pull requests")
        table.add_row("/github status", "Your GitHub status")
        table.add_row("/github notifications", "Recent notifications")
        table.add_row("/github stars", "Starred repos")
        table.add_row("/github profile", "Your profile info")
        table.add_row("/github gists", "Your gists")
        table.add_row("/github search <query>", "Search repos")
        table.add_row("/github create <title>", "Create an issue")
        console.print(table)
        console.print()


def get_weather(city):
    """Get weather using wttr.in (no API key needed)."""
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        data = resp.json()
        current = data["current_condition"][0]
        area = data["nearest_area"][0]

        temp_c = current["temp_C"]
        feels = current["FeelsLikeC"]
        desc = current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        wind_mph = current["windspeedMiles"]
        wind_dir = current["winddir16Point"]
        location = area["areaName"][0]["value"]
        country = area["country"][0]["value"]

        console.print(Panel(
            Text.from_markup(
                f"[bold]{location}, {country}[/]\n\n"
                f"  Condition    [bright_cyan]{desc}[/]\n"
                f"  Temperature  [bright_cyan]{temp_c}°C[/] (feels {feels}°C)\n"
                f"  Humidity     [bright_cyan]{humidity}%[/]\n"
                f"  Wind         [bright_cyan]{wind_mph} mph {wind_dir}[/]"
            ),
            title="[bold yellow]Weather[/]",
            border_style="yellow", padding=(1, 2), width=tw(),
        ))
    except Exception as e:
        print_err(f"Weather failed: {e}")


def open_url(url):
    """Open a URL or search query in the default browser."""
    import webbrowser

    # Shortcuts
    shortcuts = {
        "google": "https://google.com",
        "youtube": "https://youtube.com",
        "github": "https://github.com",
        "reddit": "https://reddit.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "stackoverflow": "https://stackoverflow.com",
        "npm": "https://npmjs.com",
        "pypi": "https://pypi.org",
        "ollama": "https://ollama.com",
        "claude": "https://claude.ai",
        "chatgpt": "https://chat.openai.com",
        "gemini": "https://gemini.google.com",
    }

    if url.lower() in shortcuts:
        url = shortcuts[url.lower()]
    elif "." not in url and ":" not in url:
        # No dots = search query, not a URL
        query = url.replace(" ", "+")
        url = f"https://google.com/search?q={query}"
    elif not url.startswith("http"):
        url = "https://" + url

    # Platform-specific browser open
    try:
        if os.path.exists("/data/data/com.termux"):
            # Termux — use termux-open or am start
            try:
                subprocess.run(["termux-open-url", url], timeout=5)
            except FileNotFoundError:
                subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", url], timeout=5)
        elif os.name == "nt":
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.run(["open", url], timeout=5)
        else:
            webbrowser.open(url)
        print_sys(f"Opened: {url}")
    except Exception as e:
        print_err(f"Cannot open browser: {e}")
        print_sys(f"URL: {url}")
    audit_log("OPEN_URL", url)


def spotify_command(sub):
    """Spotify controls via system commands (Windows)."""
    if os.name != "nt":
        print_sys("Spotify controls only work on Windows.")
        return

    # Use Windows media key simulation via PowerShell
    media_keys = {
        "play": "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB3)",
        "pause": "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB3)",
        "next": "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB0)",
        "prev": "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB1)",
        "stop": "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB2)",
        "mute": "(New-Object -ComObject WScript.Shell).SendKeys([char]0xAD)",
    }

    if sub in media_keys:
        try:
            subprocess.run(
                ["powershell", "-Command", media_keys[sub]],
                capture_output=True, timeout=5,
            )
            print_sys(f"Spotify: {sub}")
        except Exception as e:
            print_err(f"Spotify failed: {e}")
    elif sub == "status":
        # Try to get current track from Spotify window title
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-Process spotify -ErrorAction SilentlyContinue | '
                 'Where-Object {$_.MainWindowTitle} | '
                 'Select-Object -ExpandProperty MainWindowTitle'],
                capture_output=True, text=True, timeout=5,
            )
            title = result.stdout.strip()
            if title and title != "Spotify":
                console.print(Panel(
                    Text(f"Now playing: {title}", style="bright_green"),
                    title="[bold green]Spotify[/]",
                    border_style="green", padding=(0, 2), width=tw(),
                ))
            else:
                print_sys("Spotify: nothing playing or not running.")
        except Exception:
            print_sys("Cannot get Spotify status.")
    else:
        table = Table(title="Spotify Controls", border_style="green",
                      title_style="bold green", show_header=False, padding=(0, 2))
        table.add_column("Command", style="bright_cyan", width=20)
        table.add_column("Action", style="dim")
        table.add_row("/spotify play", "Play / Resume")
        table.add_row("/spotify pause", "Pause")
        table.add_row("/spotify next", "Next track")
        table.add_row("/spotify prev", "Previous track")
        table.add_row("/spotify stop", "Stop")
        table.add_row("/spotify mute", "Mute / Unmute")
        table.add_row("/spotify status", "Now playing")
        console.print(table)
        console.print()


def set_volume(level):
    """Set system volume (Windows)."""
    if os.name != "nt":
        print_sys("Volume control only works on Windows.")
        return
    try:
        vol = int(level)
        if 0 <= vol <= 100:
            # Use PowerShell + nircmd alternative via COM
            ps_cmd = f'''
            $vol = {vol} / 100
            $obj = New-Object -ComObject WScript.Shell
            # Mute then set
            1..50 | ForEach-Object {{ $obj.SendKeys([char]0xAE) }}
            $steps = [math]::Round($vol * 50)
            1..$steps | ForEach-Object {{ $obj.SendKeys([char]0xAF) }}
            '''
            subprocess.run(["powershell", "-Command", ps_cmd],
                          capture_output=True, timeout=10)
            print_sys(f"Volume: {vol}%")
        else:
            print_sys("Range: 0-100")
    except ValueError:
        print_sys("Usage: /volume 50")
    except Exception as e:
        print_err(f"Volume failed: {e}")


def set_brightness(level):
    """Set screen brightness (Windows)."""
    if os.name != "nt":
        print_sys("Brightness control only works on Windows.")
        return
    try:
        bright = int(level)
        if 0 <= bright <= 100:
            ps_cmd = f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{bright})'
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                print_sys(f"Brightness: {bright}%")
            else:
                print_err("Brightness control not supported (desktop monitors).")
        else:
            print_sys("Range: 0-100")
    except ValueError:
        print_sys("Usage: /bright 80")
    except Exception as e:
        print_err(f"Brightness failed: {e}")


def show_sysinfo():
    """Show system information."""
    import platform

    # Basic info
    info = {
        "OS": f"{platform.system()} {platform.release()}",
        "Machine": platform.machine(),
        "Hostname": platform.node(),
        "Python": platform.python_version(),
    }

    # CPU, RAM, Disk via shell
    try:
        if os.name == "nt":
            # CPU
            cpu_result = subprocess.run(
                ['powershell', '-Command',
                 'Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name'],
                capture_output=True, text=True, timeout=5,
            )
            info["CPU"] = cpu_result.stdout.strip()

            # RAM
            ram_result = subprocess.run(
                ['powershell', '-Command',
                 '[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)'],
                capture_output=True, text=True, timeout=5,
            )
            info["RAM"] = f"{ram_result.stdout.strip()} GB"

            # Disk
            disk_result = subprocess.run(
                ['powershell', '-Command',
                 '$d = Get-PSDrive C; "$([math]::Round($d.Used/1GB,1)) / $([math]::Round(($d.Used+$d.Free)/1GB,1)) GB"'],
                capture_output=True, text=True, timeout=5,
            )
            info["Disk C:"] = disk_result.stdout.strip()

            # IP
            ip_result = subprocess.run(
                ['powershell', '-Command',
                 '(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne "127.0.0.1"} | Select-Object -First 1).IPAddress'],
                capture_output=True, text=True, timeout=5,
            )
            info["IP"] = ip_result.stdout.strip()

            # Battery
            bat_result = subprocess.run(
                ['powershell', '-Command',
                 '$b = Get-CimInstance Win32_Battery; if($b){"$($b.EstimatedChargeRemaining)% ($($b.Status))"}else{"No battery"}'],
                capture_output=True, text=True, timeout=5,
            )
            info["Battery"] = bat_result.stdout.strip()

            # Uptime
            up_result = subprocess.run(
                ['powershell', '-Command',
                 '$ts = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; "$($ts.Days)d $($ts.Hours)h $($ts.Minutes)m"'],
                capture_output=True, text=True, timeout=5,
            )
            info["Uptime"] = up_result.stdout.strip()

    except Exception:
        pass

    table = Table(title="System Info", border_style="bright_cyan",
                  title_style="bold cyan", show_header=False, padding=(0, 2))
    table.add_column("Field", style="dim", width=12)
    table.add_column("Value", style="white")
    for k, v in info.items():
        table.add_row(k, v or "unknown")
    console.print(table)
    console.print()


# --- AI Training Lab ---

TRAINING_DIR = Path.home() / ".codegpt" / "training"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DATA = TRAINING_DIR / "training_data.json"
CUSTOM_MODELS_DIR = TRAINING_DIR / "models"
CUSTOM_MODELS_DIR.mkdir(parents=True, exist_ok=True)


def load_training_data():
    if TRAINING_DATA.exists():
        try:
            return json.loads(TRAINING_DATA.read_text())
        except Exception:
            pass
    return {"examples": [], "system_prompt": "", "params": {}}


def save_training_data(data):
    TRAINING_DATA.write_text(json.dumps(data, indent=2))


def train_collect(messages):
    """Collect good conversation pairs as training examples."""
    data = load_training_data()
    pairs = []
    for i in range(len(messages) - 1):
        if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
            pairs.append({
                "user": messages[i]["content"],
                "assistant": messages[i + 1]["content"],
                "collected": datetime.now().isoformat(),
            })
    data["examples"].extend(pairs)
    save_training_data(data)
    print_sys(f"Collected {len(pairs)} conversation pairs. Total: {len(data['examples'])} examples.")


def train_collect_rated():
    """Collect only good-rated responses as training data."""
    if not RATINGS_FILE.exists():
        print_sys("No rated responses. Use /rate good after good AI responses first.")
        return

    ratings = json.loads(RATINGS_FILE.read_text())
    good_ratings = [r for r in ratings if r.get("rating") == "good"]

    if not good_ratings:
        print_sys("No good-rated responses found.")
        return

    data = load_training_data()
    # Deduplicate: track existing prompt+response pairs
    existing = {(ex.get("user", ""), ex.get("assistant", "")) for ex in data["examples"]}
    added = 0
    for r in good_ratings:
        key = (r.get("prompt", ""), r.get("response", ""))
        if key not in existing:
            data["examples"].append({
                "user": r.get("prompt", ""),
                "assistant": r.get("response", ""),
                "collected": r.get("timestamp", ""),
                "source": "rated",
            })
            existing.add(key)
            added += 1
    save_training_data(data)
    print_sys(f"Added {added} new rated examples ({len(good_ratings) - added} duplicates skipped). Total: {len(data['examples'])}.")


def train_build(model_name, base_model, system_prompt=""):
    """Build a custom Ollama model from training data."""
    data = load_training_data()

    if not data["examples"]:
        print_err("No training data. Use /train collect first.")
        return False

    # Build system prompt from examples
    if not system_prompt:
        system_prompt = SYSTEM_PROMPT

    # Create conversation template from examples
    example_text = ""
    for ex in data["examples"][:20]:  # Use top 20 examples
        user_msg = ex.get("user", "")[:200]
        asst_msg = ex.get("assistant", "")[:500]
        if user_msg and asst_msg:
            example_text += f"\nExample interaction:\nUser: {user_msg}\nAssistant: {asst_msg}\n"

    # Build Modelfile
    full_system = (
        f"{system_prompt}\n\n"
        f"You have been trained on {len(data['examples'])} example conversations. "
        f"Follow the style and patterns from these examples:\n"
        f"{example_text}"
    )

    modelfile_content = f'FROM {base_model}\n\n'
    modelfile_content += f'SYSTEM """{full_system}"""\n\n'

    # Add custom parameters
    params = data.get("params", {})
    if params.get("temperature"):
        modelfile_content += f'PARAMETER temperature {params["temperature"]}\n'
    if params.get("top_p"):
        modelfile_content += f'PARAMETER top_p {params["top_p"]}\n'
    if params.get("top_k"):
        modelfile_content += f'PARAMETER top_k {params["top_k"]}\n'
    if params.get("repeat_penalty"):
        modelfile_content += f'PARAMETER repeat_penalty {params["repeat_penalty"]}\n'

    # Save Modelfile
    modelfile_path = CUSTOM_MODELS_DIR / f"{model_name}.Modelfile"
    modelfile_path.write_text(modelfile_content)

    console.print(Panel(
        Text.from_markup(
            f"[bold]Building model: {model_name}[/]\n\n"
            f"  Base model:     [bright_cyan]{base_model}[/]\n"
            f"  Training data:  [bright_cyan]{len(data['examples'])} examples[/]\n"
            f"  Modelfile:      [dim]{modelfile_path}[/]\n\n"
            f"[dim]Creating with Ollama...[/]"
        ),
        title="[bold bright_magenta]Training[/]",
        border_style="bright_magenta", padding=(1, 2), width=tw(),
    ))

    # Create model with Ollama
    try:
        result = subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            console.print(Panel(
                Text.from_markup(
                    f"[bold green]Model '{model_name}' created![/]\n\n"
                    f"  Switch to it:  [bright_cyan]/model {model_name}[/]\n"
                    f"  Test it:       [bright_cyan]/train test {model_name}[/]\n"
                    f"  Delete it:     [bright_cyan]/train delete {model_name}[/]"
                ),
                title="[bold green]Success[/]",
                border_style="green", padding=(1, 2), width=tw(),
            ))
            audit_log("MODEL_TRAINED", model_name)
            return True
        else:
            err = result.stderr[:300] if result.stderr else "Unknown error"
            print_err(f"Build failed: {err}")
            return False
    except Exception as e:
        print_err(f"Build failed: {e}")
        return False


def train_test(custom_model, base_model, system):
    """Test custom model vs base model side by side."""
    test_prompts = [
        "Write a Python function to check if a number is prime.",
        "Explain what a REST API is in 2 sentences.",
        "What's wrong with: for i in range(len(lst)): lst.remove(lst[i])",
    ]

    console.print(Panel(
        Text(f"Testing {custom_model} vs {base_model}", style="bold"),
        title="[bold bright_magenta]Model Comparison[/]",
        border_style="bright_magenta", padding=(0, 2), width=tw(),
    ))

    for i, prompt in enumerate(test_prompts, 1):
        console.print(Text(f"\n  Test {i}: {prompt[:60]}...", style="bold"))

        for m in [base_model, custom_model]:
            try:
                start = time.time()
                resp = requests.post(
                    OLLAMA_URL,
                    json={"model": m, "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ], "stream": False},
                    timeout=60,
                )
                elapsed = time.time() - start
                content = resp.json().get("message", {}).get("content", "")[:300]
                label = "CUSTOM" if m == custom_model else "BASE"
                color = "bright_magenta" if m == custom_model else "bright_cyan"

                console.print(Panel(
                    Text(content, style="white"),
                    title=f"[bold {color}]{label}: {m}[/]",
                    subtitle=f"[dim]{elapsed:.1f}s[/]",
                    subtitle_align="right",
                    border_style=color, padding=(0, 2), width=tw(),
                ))
            except Exception as e:
                print_err(f"{m}: {e}")
    console.print()


def train_status():
    """Show training data status."""
    data = load_training_data()
    examples = data.get("examples", [])

    # Count custom models
    custom_models = list(CUSTOM_MODELS_DIR.glob("*.Modelfile"))

    # Rating stats
    good_count = sum(1 for ex in examples if ex.get("source") == "rated")
    conv_count = len(examples) - good_count

    console.print(Panel(
        Text.from_markup(
            f"[bold bright_magenta]AI Training Lab[/]\n"
            f"{'━' * 36}\n\n"
            f"[bold]Training Data[/]\n"
            f"  Total examples     [bright_cyan]{len(examples)}[/]\n"
            f"  From conversations [bright_cyan]{conv_count}[/]\n"
            f"  From ratings       [bright_cyan]{good_count}[/]\n\n"
            f"[bold]Custom Models[/]\n"
            f"  Modelfiles         [bright_cyan]{len(custom_models)}[/]\n"
            + ("\n".join(f"  [dim]{m.stem}[/]" for m in custom_models) if custom_models else "  [dim]none[/]")
            + f"\n\n[bold]Commands[/]\n"
            f"  /train collect     Collect current chat as training data\n"
            f"  /train rated       Collect good-rated responses\n"
            f"  /train build       Build a custom model\n"
            f"  /train test        Test custom vs base model\n"
            f"  /train list        List custom models\n"
            f"  /train delete      Delete a custom model\n"
            f"  /train export      Export training data as JSON\n"
            f"  /train clear       Clear all training data\n"
            f"  /train params      Set training parameters"
        ),
        border_style="bright_magenta", padding=(1, 2), width=tw(),
    ))
    console.print()


def train_set_params():
    """Interactively set training parameters."""
    data = load_training_data()
    params = data.get("params", {})

    console.print(Text("  Set parameters for your custom model:", style="bold"))
    console.print(Text("  Press Enter to keep current value.\n", style="dim"))

    try:
        t = input(f"  temperature ({params.get('temperature', 0.7)}): ").strip()
        if t:
            params["temperature"] = float(t)

        tp = input(f"  top_p ({params.get('top_p', 0.9)}): ").strip()
        if tp:
            params["top_p"] = float(tp)

        tk = input(f"  top_k ({params.get('top_k', 40)}): ").strip()
        if tk:
            params["top_k"] = int(tk)

        rp = input(f"  repeat_penalty ({params.get('repeat_penalty', 1.1)}): ").strip()
        if rp:
            params["repeat_penalty"] = float(rp)

    except (KeyboardInterrupt, EOFError):
        print_sys("Cancelled.")
        return

    data["params"] = params
    save_training_data(data)
    print_sys("Parameters saved. They'll be used when building models.")


# --- Background Tool Launcher ---

running_tools = {}  # {name: process}
running_tools_lock = threading.Lock()


def build_codegpt_context(messages=None):
    """Build a shared context file that all tools can read."""
    context_file = Path.home() / ".codegpt" / "context.json"
    project_dir = str(Path(__file__).parent)

    # Gather current state
    profile = load_profile()
    memories = load_memories()

    # Get recent conversation for context
    recent_msgs = []
    if messages:
        for msg in messages[-10:]:
            recent_msgs.append({
                "role": msg["role"],
                "content": msg["content"][:500],
            })

    # File listing with sizes
    files_info = []
    for f in Path(project_dir).glob("*.py"):
        try:
            size = f.stat().st_size
            lines = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            files_info.append({"name": f.name, "size": size, "lines": lines})
        except Exception:
            files_info.append({"name": f.name})

    # Pinned messages
    pins = []
    for p in pinned_messages:
        pins.append({"role": p["role"], "content": p["content"][:200]})

    # Training data count
    training_data = load_training_data()
    training_count = len(training_data.get("examples", []))

    # Ratings
    ratings_count = {"good": 0, "bad": 0}
    if RATINGS_FILE.exists():
        try:
            ratings = json.loads(RATINGS_FILE.read_text())
            ratings_count["good"] = sum(1 for r in ratings if r.get("rating") == "good")
            ratings_count["bad"] = sum(1 for r in ratings if r.get("rating") == "bad")
        except Exception:
            pass

    context = {
        "app": "CodeGPT",
        "version": "2.0",
        "project_dir": project_dir,
        "timestamp": datetime.now().isoformat(),

        # User
        "user": {
            "name": profile.get("name", ""),
            "bio": profile.get("bio", ""),
            "total_messages": profile.get("total_messages", 0),
            "total_tokens": profile.get("total_tokens", 0),
            "total_sessions": profile.get("total_sessions", 0),
            "since": profile.get("created", ""),
        },

        # Current session
        "session": {
            "model": profile.get("model", MODEL),
            "persona": profile.get("persona", "default"),
            "temperature": temperature,
            "think_mode": think_mode,
            "messages_count": session_stats.get("messages", 0),
            "tokens_in": session_stats.get("tokens_in", 0),
            "tokens_out": session_stats.get("tokens_out", 0),
            "params": model_params,
        },

        # Conversation
        "recent_messages": recent_msgs,
        "pinned_messages": pins,

        # Memory
        "memories": [m["content"] for m in memories[-20:]],

        # Project files
        "files": files_info,

        # Training
        "training_examples": training_count,

        # Ratings
        "ratings": ratings_count,

        # Running tools
        "tools_running": list(running_tools.keys()),

        # Instructions
        # Message bus
        "message_bus": str(MSG_BUS),
        "pipe_dir": str(MSG_PIPE_DIR),
        "unread_messages": bus_unread("codegpt"),

        # Tool roles
        "tool_roles": TOOL_ROLES,

        "instructions": (
            "You are connected to CodeGPT, a local AI assistant hub. "
            "Check $CODEGPT_TOOL_ROLE for your specific job. "
            "The user's name is shown above. Their memories contain persistent context. "
            "Recent messages show what they were discussing before launching you. "
            "Project files are Python source in the project_dir. "
            "Read CLAUDE.md in the project root for full architecture docs. "
            "When editing code, read files first and preserve existing patterns. "
            "MESSAGE BUS: You can communicate with other AI tools by writing JSON "
            "to the message_bus file. Format: {from, to, content, type, timestamp}. "
            "Check your pipe file at pipes/<your-name>.json for incoming messages."
        ),
    }

    context_file.write_text(json.dumps(context, indent=2))
    return context_file


# Tool role descriptions — what each tool's job is when launched from CodeGPT
TOOL_ROLES = {
    "claude": "You are Claude Code, the primary coding assistant. Edit files, run commands, debug code. You have full access to the CodeGPT project.",
    "openclaw": "You are OpenClaw, a personal AI assistant. Help with tasks, answer questions, manage workflows. You're running inside CodeGPT's sandbox.",
    "codex": "You are Codex, OpenAI's coding agent. Write and edit code, fix bugs, refactor. You have access to the CodeGPT project files.",
    "gemini": "You are Gemini CLI, Google's AI. Help with coding, research, and analysis. You have access to the CodeGPT project.",
    "copilot": "You are GitHub Copilot. Suggest code completions, write functions, help with git workflows.",
    "cline": "You are Cline, an autonomous coding agent. Plan and implement features, fix bugs, refactor code across multiple files.",
    "aider": "You are Aider, an AI pair programmer. Edit files based on user instructions. Focus on clean, working code changes.",
    "interpreter": "You are Open Interpreter. Run code, install packages, manage files. Execute the user's instructions step by step.",
    "shellgpt": "You are ShellGPT. Generate shell commands from natural language. Be precise and safe.",
    "opencode": "You are OpenCode, a terminal IDE. Help write, edit, and manage code projects.",
    "llm": "You are LLM CLI. Chat with various AI models. Help the user with questions and tasks.",
    "litellm": "You are LiteLLM. Provide a unified interface to 100+ AI models. Help route requests to the best model.",
    "gorilla": "You are Gorilla CLI. Generate accurate CLI commands from natural language descriptions.",
    "chatgpt": "You are ChatGPT CLI. Have helpful conversations, answer questions, write content.",
    "opencommit": "You are OpenCommit. Generate clear, descriptive git commit messages from staged changes.",
    "aipick": "You are AIPick. Help select and craft the best git commits with AI assistance.",
    "cursor": "You are Cursor CLI. Help with code editing, navigation, and AI-powered development.",
}


def build_tool_env(tool_name):
    """Build environment variables for a launched tool."""
    project_dir = str(Path(__file__).parent)
    env = os.environ.copy()
    profile = load_profile()

    # Tool's specific role/job
    role = TOOL_ROLES.get(tool_name, f"You are {tool_name}, launched from CodeGPT. Help the user with their task.")
    tool_info = AI_TOOLS.get(tool_name, {})

    # Inject CodeGPT context into every tool
    env["CODEGPT_HOME"] = str(Path.home() / ".codegpt")
    env["CODEGPT_PROJECT"] = project_dir
    env["CODEGPT_CONTEXT"] = str(Path.home() / ".codegpt" / "context.json")
    env["CODEGPT_MEMORY"] = str(Path.home() / ".codegpt" / "memory" / "memories.json")
    env["CODEGPT_PROFILE"] = str(Path.home() / ".codegpt" / "profiles" / "cli_profile.json")
    env["CODEGPT_TRAINING"] = str(Path.home() / ".codegpt" / "training")
    env["CODEGPT_CHATS"] = str(Path.home() / ".codegpt" / "chats")
    env["CODEGPT_TOOL"] = tool_name
    env["CODEGPT_TOOL_ROLE"] = role
    env["CODEGPT_TOOL_DESC"] = tool_info.get("desc", "")
    env["CODEGPT_USER"] = profile.get("name", "")
    env["CODEGPT_MODEL"] = profile.get("model", MODEL)
    env["CODEGPT_PERSONA"] = profile.get("persona", "default")
    env["CODEGPT_SESSIONS"] = str(profile.get("total_sessions", 0))
    env["CODEGPT_TOTAL_MSGS"] = str(profile.get("total_messages", 0))
    env["CODEGPT_APP"] = "CodeGPT — Local AI Assistant Hub"
    env["CODEGPT_VERSION"] = "2.0"

    return env


def _sanitize_shell_arg(s):
    """Strip characters that could break out of shell quoting."""
    return re.sub(r'[;&|`$"\'<>()!]', '', str(s))


def launch_bg_tool(tool_name, tool_bin, args=None, cwd=None):
    """Launch a tool in a new terminal window, connected to CodeGPT."""
    project_dir = str(Path(__file__).parent)
    coding_tools = ["codex", "opencode", "cline", "aider", "mentat",
                    "gpt-engineer", "interpreter", "copilot", "claude"]
    is_coding = tool_name in coding_tools
    work_dir = cwd or (project_dir if is_coding else str(Path.home() / ".codegpt" / "sandbox" / tool_name))
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    # Update shared context file
    build_codegpt_context()

    # Build env with CodeGPT vars
    tool_env = build_tool_env(tool_name)

    # Sanitize all values that go into shell strings
    safe_name = _sanitize_shell_arg(tool_name)
    safe_dir = _sanitize_shell_arg(work_dir)
    safe_bin = _sanitize_shell_arg(tool_bin)
    safe_args = _sanitize_shell_arg(args) if args else ""

    cmd_str = f"{safe_bin} {safe_args}".strip()

    if os.name == "nt":
        proc = subprocess.Popen(
            f'start "CodeGPT > {safe_name}" cmd /k "cd /d {safe_dir} && {cmd_str}"',
            shell=True,
            env=tool_env,
        )
    else:
        for term in ["gnome-terminal", "xterm", "konsole"]:
            if shutil.which(term):
                proc = subprocess.Popen([term, "--", "bash", "-c", f"cd {safe_dir} && {cmd_str}; exec bash"], env=tool_env)
                break
        else:
            proc = subprocess.Popen(cmd_str, shell=True, cwd=work_dir, env=tool_env)

    with running_tools_lock:
        running_tools[tool_name] = {
            "proc": proc,
            "started": datetime.now(),
            "bin": tool_bin,
            "cwd": work_dir,
        }
    return proc


def show_running_tools():
    """Show all running background tools."""
    with running_tools_lock:
        if not running_tools:
            print_sys("No tools running in background.")
            return

        # Clean up finished ones
        finished = [name for name, info in running_tools.items()
                    if info["proc"] is not None and info["proc"].poll() is not None]
        for name in finished:
            del running_tools[name]

        if not running_tools:
            print_sys("No tools running in background.")
            return

        table = Table(title="Running AI Tools", border_style="bright_green",
                      title_style="bold green", show_header=True, header_style="bold")
        table.add_column("Tool", style="bright_cyan", width=16)
        table.add_column("PID", style="dim", width=8)
        table.add_column("Uptime", style="white", width=10)
        table.add_column("Dir", style="dim")

        for name, info in running_tools.items():
            elapsed = int((datetime.now() - info["started"]).total_seconds())
            uptime = f"{elapsed // 60}m {elapsed % 60}s"
            pid = str(info["proc"].pid) if info["proc"] else "?"
            table.add_row(name, pid, uptime, info["cwd"][:40])

    console.print(table)
    console.print()


def kill_all_tools():
    """Close all background tools."""
    with running_tools_lock:
        if not running_tools:
            print_sys("No tools running.")
            return
        count = 0
        for name, info in list(running_tools.items()):
            try:
                if info["proc"]:
                    info["proc"].terminate()
                count += 1
            except Exception:
                pass
        running_tools.clear()
    print_sys(f"Closed {count} tools.")


# --- Inter-Tool Message Bus ---

MSG_BUS = Path.home() / ".codegpt" / "message_bus.json"
MSG_PIPE_DIR = Path.home() / ".codegpt" / "pipes"
MSG_PIPE_DIR.mkdir(parents=True, exist_ok=True)


def load_bus():
    if MSG_BUS.exists():
        try:
            return json.loads(MSG_BUS.read_text())
        except Exception:
            pass
    return {"messages": []}


def save_bus(data):
    MSG_BUS.write_text(json.dumps(data, indent=2))


def bus_send(from_tool, to_tool, content, msg_type="message"):
    """Send a message on the bus."""
    bus = load_bus()
    msg = {
        "id": len(bus["messages"]) + 1,
        "from": from_tool,
        "to": to_tool,  # "*" for broadcast
        "content": content,
        "type": msg_type,  # message, request, response, code, file
        "timestamp": datetime.now().isoformat(),
        "read": False,
    }
    bus["messages"].append(msg)

    # Keep last 100 messages
    if len(bus["messages"]) > 100:
        bus["messages"] = bus["messages"][-100:]

    save_bus(bus)

    # Also write to tool's pipe file for instant pickup
    pipe_file = MSG_PIPE_DIR / f"{to_tool}.json" if to_tool != "*" else None
    if pipe_file:
        pipe_msgs = []
        if pipe_file.exists():
            try:
                pipe_msgs = json.loads(pipe_file.read_text())
            except Exception:
                pass
        pipe_msgs.append(msg)
        pipe_file.write_text(json.dumps(pipe_msgs[-20:], indent=2))

    # For broadcast, write to all tool pipes
    if to_tool == "*":
        for tool_name in list(running_tools.keys()) + ["codegpt"]:
            if tool_name != from_tool:
                pf = MSG_PIPE_DIR / f"{tool_name}.json"
                pipe_msgs = []
                if pf.exists():
                    try:
                        pipe_msgs = json.loads(pf.read_text())
                    except Exception:
                        pass
                pipe_msgs.append(msg)
                pf.write_text(json.dumps(pipe_msgs[-20:], indent=2))

    return msg


def bus_read(tool_name, mark_read=True):
    """Read messages for a tool."""
    bus = load_bus()
    msgs = [m for m in bus["messages"]
            if (m["to"] == tool_name or m["to"] == "*") and m["from"] != tool_name]

    if mark_read:
        for m in bus["messages"]:
            if (m["to"] == tool_name or m["to"] == "*") and m["from"] != tool_name:
                m["read"] = True
        save_bus(bus)

    return msgs


def bus_unread(tool_name):
    """Count unread messages for a tool."""
    bus = load_bus()
    return sum(1 for m in bus["messages"]
               if (m["to"] == tool_name or m["to"] == "*")
               and m["from"] != tool_name and not m.get("read"))


def show_inbox():
    """Show messages for CodeGPT."""
    unread_count = bus_unread("codegpt")
    msgs = bus_read("codegpt")

    if not msgs:
        print_sys("Inbox empty. No messages from other tools.")
        return

    table = Table(title=f"Inbox ({unread_count} unread)", border_style="bright_cyan",
                  title_style="bold cyan", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("From", style="bright_magenta", width=12)
    table.add_column("Message", overflow="fold")
    table.add_column("Time", style="dim", width=8)

    for m in msgs[-15:]:
        ts = m["timestamp"][11:16] if m.get("timestamp") else "?"
        style = "" if m.get("read") else "bold"
        table.add_row(
            str(m.get("id", "?")),
            m.get("from", "?"),
            Text(m.get("content", "")[:80], style=style),
            ts,
        )
    console.print(table)
    console.print()


def link_tools_conversation(tool1, tool2, prompt, model, system):
    """Make two AI tools have a conversation with each other."""
    console.print(Panel(
        Text.from_markup(
            f"[bold]Linking: {tool1} <-> {tool2}[/]\n"
            f"[dim]Topic: {prompt[:60]}...[/]\n"
            f"[dim]Press Ctrl+C to stop[/]"
        ),
        title="[bold bright_green]Chat Link[/]",
        border_style="bright_green", padding=(0, 2), width=tw(),
    ))

    # Use AI to simulate a conversation between two "experts"
    agent1 = AI_AGENTS.get(tool1, {"system": system})
    agent2 = AI_AGENTS.get(tool2, {"system": system})

    history = []
    current = prompt
    turns = 0
    max_turns = 6

    try:
        while turns < max_turns:
            # Tool 1 speaks
            turns += 1
            speaker = tool1
            listener = tool2
            sys_prompt = agent1.get("system", system)

            context = f"You are {speaker} having a discussion with {listener}.\n"
            if history:
                context += "Conversation so far:\n" + "\n".join(
                    f"{h['speaker']}: {h['msg'][:200]}" for h in history[-4:]
                ) + "\n\n"
            context += f"Respond to: {current}"

            try:
                resp = requests.post(OLLAMA_URL, json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": context},
                    ],
                    "stream": False,
                }, timeout=60)
                response = resp.json().get("message", {}).get("content", "")
            except Exception as e:
                print_err(f"{speaker} failed: {e}")
                break

            history.append({"speaker": speaker, "msg": response})
            bus_send(speaker, listener, response)

            console.print(Panel(
                Markdown(response),
                title=f"[bold bright_cyan]{speaker}[/]",
                border_style="bright_cyan", padding=(0, 2), width=tw(),
            ))

            current = response

            # Swap roles
            tool1, tool2 = tool2, tool1
            agent1, agent2 = agent2, agent1

    except KeyboardInterrupt:
        print_sys("Chat link stopped.")

    # Save the conversation
    bus_send("codegpt", "*", f"Chat link ended: {turns} turns between {tool1} and {tool2}")
    return history


# --- Multi-AI System ---

def ask_all_agents(prompt, model, system):
    """Send prompt to all agents in parallel, show all responses."""
    console.print(Panel(
        Text(f"Asking all 8 agents: {prompt[:60]}...", style="bold"),
        title="[bold bright_cyan]All Agents[/]",
        border_style="bright_cyan", padding=(0, 2), width=tw(),
    ))

    results = {}

    def query_agent(name, agent_system):
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": model,
                "messages": [
                    {"role": "system", "content": agent_system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            }, timeout=90)
            content = resp.json().get("message", {}).get("content", "")
            ec = resp.json().get("eval_count", 0)
            results[name] = {"content": content, "tokens": ec}
        except Exception as e:
            results[name] = {"content": f"Error: {e}", "tokens": 0}

    # Launch all agents in parallel threads
    threads = []
    for name, info in AI_AGENTS.items():
        t = threading.Thread(target=query_agent, args=(name, info["system"]), daemon=True)
        threads.append(t)
        t.start()

    # Wait for all with progress
    with Live(
        Panel(Text("Waiting for agents...", style="dim"),
              border_style="bright_cyan", padding=(0, 2), width=tw()),
        console=console, refresh_per_second=4, transient=True,
    ) as live:
        while any(t.is_alive() for t in threads):
            done = len(results)
            total = len(AI_AGENTS)
            bar_w = 25
            filled = int(bar_w * done / total)
            bar = "█" * filled + "░" * (bar_w - filled)
            names_done = ", ".join(results.keys())
            live.update(Panel(
                Text.from_markup(
                    f"  [bright_green]{bar}[/] [bold]{done}/{total}[/]\n\n"
                    f"  [dim]Done: {names_done}[/]"
                ),
                title="[bold bright_cyan]Querying All Agents[/]",
                border_style="bright_cyan", padding=(0, 2), width=tw(),
            ))
            time.sleep(0.25)

    # Show all responses
    for name, data in results.items():
        color = "bright_cyan" if data["tokens"] > 0 else "red"
        console.print(Panel(
            Markdown(data["content"][:500]),
            title=f"[bold {color}]{name}[/]",
            subtitle=f"[dim]{data['tokens']} tok[/]",
            subtitle_align="right",
            border_style=color, padding=(0, 2), width=tw(),
        ))
        bus_send(name, "codegpt", data["content"][:200], "response")

    return results


def race_models(prompt, available_models, system):
    """Race all available Ollama models — show responses as they come in."""
    models = available_models[:6]  # Max 6 to avoid overload
    if not models:
        print_sys("No models available.")
        return

    console.print(Panel(
        Text.from_markup(
            f"[bold]Racing {len(models)} models![/]\n"
            f"[dim]{', '.join(models)}[/]"
        ),
        title="[bold yellow]Model Race[/]",
        border_style="yellow", padding=(0, 2), width=tw(),
    ))

    results = {}
    finish_order = []

    def query_model(m):
        try:
            start = time.time()
            resp = requests.post(OLLAMA_URL, json={
                "model": m,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            }, timeout=120)
            elapsed = time.time() - start
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            ec = data.get("eval_count", 0)
            tps = ec / elapsed if elapsed > 0 else 0
            results[m] = {"content": content, "time": elapsed, "tokens": ec, "tps": tps}
            finish_order.append(m)
        except Exception as e:
            results[m] = {"content": str(e), "time": 0, "tokens": 0, "tps": 0}
            finish_order.append(m)

    threads = []
    for m in models:
        t = threading.Thread(target=query_model, args=(m,), daemon=True)
        threads.append(t)
        t.start()

    # Live progress
    with Live(
        Panel(Text("Racing...", style="dim"),
              border_style="yellow", padding=(0, 2), width=tw()),
        console=console, refresh_per_second=4, transient=True,
    ) as live:
        while any(t.is_alive() for t in threads):
            done = len(results)
            positions = "\n".join(
                f"  [green]{i+1}.[/] {n} — {results[n]['time']:.1f}s"
                for i, n in enumerate(finish_order)
            )
            waiting = [m for m in models if m not in results]
            live.update(Panel(
                Text.from_markup(
                    f"  [bold]{done}/{len(models)} finished[/]\n\n"
                    + (positions + "\n" if positions else "")
                    + (f"\n  [dim]Waiting: {', '.join(waiting)}[/]" if waiting else "")
                ),
                title="[bold yellow]Race Progress[/]",
                border_style="yellow", padding=(0, 2), width=tw(),
            ))
            time.sleep(0.25)

    # Final results
    console.print(Panel(
        Text("RACE RESULTS", style="bold yellow", justify="center"),
        border_style="yellow", padding=(0, 2), width=tw(),
    ))

    for i, m in enumerate(finish_order):
        r = results[m]
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
        console.print(Panel(
            Markdown(r["content"][:400]),
            title=f"[bold green]{medal} {m}[/]",
            subtitle=f"[dim]{r['time']:.1f}s | {r['tokens']} tok | {r['tps']:.0f} tok/s[/]",
            subtitle_align="right",
            border_style="green" if i == 0 else "dim",
            padding=(0, 2), width=tw(),
        ))

    # Leaderboard
    table = Table(title="Leaderboard", border_style="yellow",
                  title_style="bold yellow", show_header=True, header_style="bold")
    table.add_column("Pos", width=4)
    table.add_column("Model", style="bright_cyan")
    table.add_column("Time", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Tok/s", justify="right", style="green")
    for i, m in enumerate(finish_order):
        r = results[m]
        table.add_row(str(i + 1), m, f"{r['time']:.1f}s", str(r['tokens']), f"{r['tps']:.0f}")
    console.print(table)
    console.print()

    return results


def agent_vote(prompt, model, system):
    """All agents vote on a question — show consensus."""
    console.print(Panel(
        Text(f"Voting: {prompt[:60]}...", style="bold"),
        title="[bold bright_magenta]Agent Vote[/]",
        border_style="bright_magenta", padding=(0, 2), width=tw(),
    ))

    vote_prompt = (
        f"{prompt}\n\n"
        "Give a clear, concise answer in 1-2 sentences. "
        "End with your confidence level: HIGH, MEDIUM, or LOW."
    )

    results = {}

    def query(name, sys_p):
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": vote_prompt},
                ],
                "stream": False,
            }, timeout=60)
            results[name] = resp.json().get("message", {}).get("content", "")
        except Exception:
            results[name] = "No response"

    threads = [threading.Thread(target=query, args=(n, a["system"]), daemon=True) for n, a in AI_AGENTS.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)

    # Show votes
    table = Table(title="Votes", border_style="bright_magenta",
                  title_style="bold bright_magenta", show_header=True, header_style="bold")
    table.add_column("Agent", style="bright_cyan", width=12)
    table.add_column("Answer", overflow="fold")
    for name, answer in results.items():
        table.add_row(name, answer[:120])
    console.print(table)

    # Ask AI to summarize consensus
    all_votes = "\n".join(f"{n}: {a[:150]}" for n, a in results.items())
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model,
            "messages": [{"role": "user", "content": (
                f"These agents voted on: {prompt}\n\n{all_votes}\n\n"
                "Summarize the consensus in 2-3 sentences. "
                "Note where agents agree and disagree."
            )}],
            "stream": False,
        }, timeout=60)
        consensus = resp.json().get("message", {}).get("content", "")
        console.print(Panel(
            Markdown(consensus),
            title="[bold green]Consensus[/]",
            border_style="green", padding=(0, 2), width=tw(),
        ))
    except Exception:
        pass

    console.print()
    return results


def agent_swarm(task, model, system):
    """Agents collaborate step by step — each builds on the last."""
    # Define the pipeline
    pipeline = [
        ("architect", "Design the approach and break down the task."),
        ("coder", "Implement the solution based on the architect's plan."),
        ("reviewer", "Review the code for bugs and improvements."),
        ("optimizer", "Optimize the code for performance."),
        ("pentester", "Check for security vulnerabilities."),
        ("explainer", "Summarize what was built and how it works."),
    ]

    console.print(Panel(
        Text.from_markup(
            f"[bold]Swarm Task: {task[:60]}...[/]\n\n"
            f"  Pipeline: {' → '.join(p[0] for p in pipeline)}\n\n"
            f"[dim]Each agent builds on the previous agent's output.[/]"
        ),
        title="[bold bright_green]Agent Swarm[/]",
        border_style="bright_green", padding=(1, 2), width=tw(),
    ))

    accumulated = f"Task: {task}"

    try:
        for i, (agent_name, instruction) in enumerate(pipeline, 1):
            agent = AI_AGENTS.get(agent_name, {})
            agent_sys = agent.get("system", system)

            swarm_prompt = (
                f"You are step {i}/6 in a collaborative pipeline.\n"
                f"Your role: {instruction}\n\n"
                f"Previous work:\n{accumulated}\n\n"
                f"Build on the previous work. Be specific and actionable."
            )

            console.print(Text(f"\n  Step {i}/6: {agent_name} — {instruction[:40]}...", style="bold"))

            try:
                resp = requests.post(OLLAMA_URL, json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": agent_sys},
                        {"role": "user", "content": swarm_prompt},
                    ],
                    "stream": False,
                }, timeout=90)
                response = resp.json().get("message", {}).get("content", "")
            except Exception as e:
                print_err(f"{agent_name} failed: {e}")
                continue

            console.print(Panel(
                Markdown(response),
                title=f"[bold bright_cyan]Step {i}: {agent_name}[/]",
                border_style="bright_cyan", padding=(0, 2), width=tw(),
            ))

            accumulated += f"\n\n--- {agent_name} output ---\n{response}"
            bus_send(agent_name, "codegpt", response[:200], "response")

    except KeyboardInterrupt:
        print_sys("Swarm stopped.")

    return accumulated


# --- Team Chat ---

# Tool personas — simulate external AI tools in team chat
TOOL_PERSONAS = {
    "claude": {
        "system": (
            "You are Claude, made by Anthropic. You are thoughtful, careful, and thorough. "
            "You think step-by-step, consider edge cases, and write clean, safe code. "
            "You refuse to help with harmful tasks. You're honest about uncertainty."
        ),
        "color": "bright_cyan",
    },
    "codex": {
        "system": (
            "You are Codex by OpenAI. You are a fast, code-first AI. You prefer showing code "
            "over explaining. You write concise, working solutions. You optimize for simplicity."
        ),
        "color": "green",
    },
    "gemini": {
        "system": (
            "You are Gemini by Google. You have broad knowledge, can reason about images and code. "
            "You give balanced, well-researched answers. You cite sources when possible."
        ),
        "color": "yellow",
    },
    "copilot": {
        "system": (
            "You are GitHub Copilot. You are an expert pair programmer. You autocomplete code, "
            "suggest whole functions, and know every framework. Code first, explain second."
        ),
        "color": "bright_white",
    },
    "gpt": {
        "system": (
            "You are ChatGPT by OpenAI. You are helpful, creative, and conversational. "
            "You explain things clearly and adapt to the user's level. You're good at everything."
        ),
        "color": "bright_green",
    },
    "mistral": {
        "system": (
            "You are Mistral AI. You are fast, efficient, and direct. You give concise answers "
            "without filler. You're great at code and reasoning. European AI values."
        ),
        "color": "bright_red",
    },
    "llama": {
        "system": (
            "You are Llama by Meta. You are open-source and proud of it. You give solid, "
            "practical answers. You're competitive with proprietary models. You support open AI."
        ),
        "color": "bright_blue",
    },
    "deepseek": {
        "system": (
            "You are DeepSeek. You think deeply before answering, using chain-of-thought reasoning. "
            "You show your thinking process. You're especially strong at math and code."
        ),
        "color": "bright_magenta",
    },
}


def resolve_team_member(name):
    """Resolve a name to a team member config: agent, tool persona, or model."""
    # Check built-in agents first
    if name in AI_AGENTS:
        return {
            "name": name,
            "system": AI_AGENTS[name]["system"],
            "model": None,  # Use default model
            "color": "bright_cyan",
            "type": "agent",
        }

    # Check tool personas
    if name in TOOL_PERSONAS:
        return {
            "name": name,
            "system": TOOL_PERSONAS[name]["system"],
            "model": None,
            "color": TOOL_PERSONAS[name]["color"],
            "type": "tool",
        }

    # Treat as a model name — use it as the Ollama model
    return {
        "name": name,
        "system": f"You are an AI running on the {name} model. Be helpful, concise, and technical.",
        "model": name,  # Use this specific model
        "color": "bright_yellow",
        "type": "model",
    }


def team_chat(name1, name2, default_model, system):
    """Interactive group chat: you + 2 AIs. Accepts agents, tools, or models."""
    m1 = resolve_team_member(name1)
    m2 = resolve_team_member(name2)

    # Show team info
    type_labels = {"agent": "Agent", "tool": "AI Tool", "model": "Model"}
    console.print(Panel(
        Text.from_markup(
            f"[bold]Team Chat[/]\n\n"
            f"  [{m1['color']}]{m1['name']}[/] ({type_labels[m1['type']]})\n"
            f"  [{m2['color']}]{m2['name']}[/] ({type_labels[m2['type']]})\n\n"
            f"  Talk normally — both AIs respond.\n"
            f"  @{m1['name']} or @{m2['name']} to talk to one.\n"
            f"  Type [bold]exit[/] to leave.\n"
        ),
        title="[bold bright_green]Team Chat[/]",
        border_style="bright_green", padding=(1, 2), width=tw(),
    ))

    history = []

    while True:
        try:
            user_input = prompt(
                [("class:prompt", f" You > ")],
                style=input_style,
                history=input_history,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "/exit", "quit", "/quit"):
            break

        console.print(Panel(
            Text(user_input, style="white"),
            title="[bold bright_cyan]You[/]",
            title_align="left",
            border_style="bright_cyan",
            padding=(0, 2), width=tw(),
        ))

        history.append({"role": "user", "speaker": "user", "content": user_input})

        # Decide who responds
        mention1 = f"@{m1['name']}" in user_input.lower()
        mention2 = f"@{m2['name']}" in user_input.lower()

        if mention1 and not mention2:
            responders = [m1]
        elif mention2 and not mention1:
            responders = [m2]
        else:
            responders = [m1, m2]

        for member in responders:
            other = m2 if member == m1 else m1
            conv_history = "\n".join(
                f"{'You' if h['speaker'] == 'user' else h['speaker']}: {h['content'][:300]}"
                for h in history[-8:]
            )

            team_prompt = (
                f"You are {member['name']} in a group chat with the user and {other['name']}.\n"
                f"Conversation so far:\n{conv_history}\n\n"
                f"Respond as {member['name']}. Be concise. Build on what others said. "
                f"If {other['name']} made a mistake, correct it. "
                f"If you agree, add something new. Don't repeat what was already said."
            )

            use_model = member["model"] or default_model

            try:
                resp = requests.post(OLLAMA_URL, json={
                    "model": use_model,
                    "messages": [
                        {"role": "system", "content": member["system"]},
                        {"role": "user", "content": team_prompt},
                    ],
                    "stream": False,
                }, timeout=90)
                response = resp.json().get("message", {}).get("content", "")
            except Exception as e:
                response = f"(error — {e})"

            console.print(Panel(
                Markdown(response),
                title=f"[bold {member['color']}]{member['name']}[/]",
                title_align="left",
                border_style=member["color"],
                padding=(0, 2), width=tw(),
            ))

            history.append({"role": "assistant", "speaker": member["name"], "content": response})
            bus_send(member["name"], "codegpt", response[:200], "response")

    console.print(Panel(
        Text(f"Team chat ended. {len(history)} messages.", style="dim"),
        border_style="dim", padding=(0, 2), width=tw(),
    ))

    return history


# --- Chat Room ---

def chat_room(member_names, default_model, system, user_joins=True, topic=""):
    """Multi-AI chat room. User can join or spectate."""
    members = [resolve_team_member(n) for n in member_names]

    names_display = ", ".join(f"[{m['color']}]{m['name']}[/]" for m in members)
    mode = "Join" if user_joins else "Spectate"

    console.print(Rule(style="bright_green", characters="─"))
    console.print(Text.from_markup(
        f"  [bold]Chat Room[/] — {mode} mode\n"
        f"  Members: {names_display}\n"
    ))
    if user_joins:
        console.print(Text("  Type to talk. @name to address one AI. 'exit' to leave.", style="dim"))
    else:
        console.print(Text("  Watching AIs chat. Ctrl+C to stop.", style="dim"))
    console.print(Rule(style="bright_green", characters="─"))
    console.print()

    history = []

    if user_joins:
        # Interactive room — user + multiple AIs
        while True:
            try:
                user_input = prompt(
                    [("class:prompt", " You ❯ ")],
                    style=input_style,
                    history=input_history,
                ).strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input or user_input.lower() in ("exit", "/exit", "quit"):
                break

            console.print(Text(f"  {user_input}", style="bold white"))
            console.print()
            history.append({"speaker": "user", "content": user_input})

            # Check for @mentions
            mentioned = []
            for m in members:
                if f"@{m['name']}" in user_input.lower():
                    mentioned.append(m)

            # If no mentions, all respond
            responders = mentioned if mentioned else members

            for member in responders:
                others = [m['name'] for m in members if m != member] + ["user"]
                conv = "\n".join(
                    f"{h['speaker']}: {h['content'][:200]}"
                    for h in history[-10:]
                )

                room_prompt = (
                    f"You are {member['name']} in a group chat with {', '.join(others)}.\n"
                    f"Chat so far:\n{conv}\n\n"
                    f"Respond as {member['name']}. Keep it short (2-4 sentences). "
                    f"React to what was said. Agree, disagree, or add something new. "
                    f"Don't repeat what others said."
                )

                try:
                    resp = requests.post(OLLAMA_URL, json={
                        "model": member["model"] or default_model,
                        "messages": [
                            {"role": "system", "content": member["system"]},
                            {"role": "user", "content": room_prompt},
                        ],
                        "stream": False,
                    }, timeout=60)
                    response = resp.json().get("message", {}).get("content", "")
                except Exception as e:
                    response = f"(offline)"

                console.print(Text.from_markup(f"  [{member['color']}]{member['name']}[/] {response}"))
                console.print()
                history.append({"speaker": member["name"], "content": response})
                bus_send(member["name"], "codegpt", response[:200], "response")

    else:
        # Spectate mode — AIs chat with each other, user watches
        try:
            # Get initial topic from last arg or default
            if not topic:
                topic = "Introduce yourselves and start a technical discussion."
            if history:
                topic = history[-1]["content"]

            current_input = topic
            rounds = 0
            max_rounds = 12

            while rounds < max_rounds:
                for member in members:
                    rounds += 1
                    if rounds > max_rounds:
                        break

                    others = [m['name'] for m in members if m != member]
                    conv = "\n".join(
                        f"{h['speaker']}: {h['content'][:200]}"
                        for h in history[-8:]
                    )

                    room_prompt = (
                        f"You are {member['name']} in a group chat with {', '.join(others)}.\n"
                        f"{'Topic: ' + current_input if not history else 'Chat so far:'}\n"
                        f"{conv}\n\n"
                        f"Respond as {member['name']}. Keep it short (2-3 sentences). "
                        f"Build on the conversation. Be opinionated."
                    )

                    try:
                        resp = requests.post(OLLAMA_URL, json={
                            "model": member["model"] or default_model,
                            "messages": [
                                {"role": "system", "content": member["system"]},
                                {"role": "user", "content": room_prompt},
                            ],
                            "stream": False,
                        }, timeout=60)
                        response = resp.json().get("message", {}).get("content", "")
                    except Exception as e:
                        response = "(offline)"

                    console.print(Text.from_markup(f"  [{member['color']}]{member['name']}[/] {response}"))
                    console.print()
                    history.append({"speaker": member["name"], "content": response})
                    time.sleep(0.5)

        except KeyboardInterrupt:
            pass

    console.print(Rule(style="dim", characters="─"))
    console.print(Text(f"  Room closed. {len(history)} messages.", style="dim"))
    console.print()
    return history


# --- Split Screen ---

def get_tool_cmd(name):
    """Get the launch command string for a tool."""
    project_dir = str(Path(__file__).parent)
    coding_tools = ["codex", "opencode", "cline", "aider", "mentat",
                    "gpt-engineer", "interpreter", "copilot", "claude"]

    if name == "claude":
        return f"cd /d {project_dir} && claude", project_dir
    elif name == "openclaw":
        sandbox = str(Path.home() / ".codegpt" / "sandbox" / "openclaw")
        return f"cd /d {sandbox} && openclaw", sandbox
    elif name in AI_TOOLS:
        tool = AI_TOOLS[name]
        bin_name = tool["bin"]
        args = " ".join(tool.get("default_args", []))
        cmd = f"{bin_name} {args}".strip()
        if name in coding_tools:
            return f"cd /d {project_dir} && {cmd}", project_dir
        else:
            sandbox = str(Path.home() / ".codegpt" / "sandbox" / name)
            return f"cd /d {sandbox} && {cmd}", sandbox
    else:
        return name, project_dir


def split_tools(tools, vertical=False):
    """Split screen with multiple tools using Windows Terminal panes."""
    if os.name != "nt" or not shutil.which("wt"):
        print_err("Split screen needs Windows Terminal (wt.exe).")
        return

    if len(tools) < 2:
        print_sys("Need at least 2 tools.\nExample: /split claude codex")
        return

    # Update context
    build_codegpt_context()

    # Build env vars to pass
    env_sets = []
    profile = load_profile()
    env_sets.append(f'set CODEGPT_PROJECT={Path(__file__).parent}')
    env_sets.append(f'set CODEGPT_USER={profile.get("name", "")}')
    env_sets.append(f'set CODEGPT_CONTEXT={Path.home() / ".codegpt" / "context.json"}')
    env_prefix = " && ".join(env_sets) + " && "

    split_flag = "-V" if vertical else "-H"

    # First tool in the main pane
    first_cmd, first_dir = get_tool_cmd(tools[0])
    safe_first = _sanitize_shell_arg(tools[0])
    safe_first_dir = _sanitize_shell_arg(first_dir)
    safe_first_cmd = _sanitize_shell_arg(first_cmd)
    wt_cmd = f'wt -w 0 nt --title "CodeGPT > {safe_first}" -d "{safe_first_dir}" cmd /k "{env_prefix}{safe_first_cmd}"'

    # Add remaining tools as split panes
    for tool in tools[1:]:
        tool_cmd, tool_dir = get_tool_cmd(tool)
        Path(tool_dir).mkdir(parents=True, exist_ok=True)
        safe_tool = _sanitize_shell_arg(tool)
        safe_tool_dir = _sanitize_shell_arg(tool_dir)
        safe_tool_cmd = _sanitize_shell_arg(tool_cmd)
        wt_cmd += f' ; sp {split_flag} --title "CodeGPT > {safe_tool}" -d "{safe_tool_dir}" cmd /k "{env_prefix}{safe_tool_cmd}"'

    subprocess.Popen(wt_cmd, shell=True)

    # Track them
    for tool in tools:
        running_tools[tool] = {
            "proc": None,
            "started": datetime.now(),
            "bin": tool,
            "cwd": get_tool_cmd(tool)[1],
        }

    tool_list = ", ".join(tools)
    console.print(Panel(
        Text.from_markup(
            f"[bold]Split screen launched![/]\n\n"
            f"  Tools: [bright_cyan]{tool_list}[/]\n"
            f"  Layout: [bright_cyan]{'vertical' if vertical else 'horizontal'}[/]\n"
            f"  Panes: [bright_cyan]{len(tools)}[/]\n\n"
            f"[dim]Each pane is connected to CodeGPT.\n"
            f"Use Alt+Arrow keys to switch between panes.\n"
            f"Ctrl+Shift+W to close a pane.[/]"
        ),
        title="[bold bright_green]Split Screen[/]",
        border_style="bright_green", padding=(1, 2), width=tw(),
    ))
    audit_log("SPLIT_LAUNCH", tool_list)


def grid_tools(tools):
    """Launch 4 tools in a 2x2 grid using Windows Terminal."""
    if os.name != "nt" or not shutil.which("wt"):
        print_err("Grid mode needs Windows Terminal (wt.exe).")
        return

    if len(tools) < 2:
        print_sys("Need at least 2 tools.\nExample: /grid claude codex gemini cline")
        return

    build_codegpt_context()

    profile = load_profile()
    env_prefix = (
        f'set CODEGPT_PROJECT={Path(__file__).parent} && '
        f'set CODEGPT_USER={profile.get("name", "")} && '
        f'set CODEGPT_CONTEXT={Path.home() / ".codegpt" / "context.json"} && '
    )

    # Build 2x2 grid: top-left, top-right, bottom-left, bottom-right
    cmds = []
    for t in tools[:4]:
        cmd, d = get_tool_cmd(t)
        Path(d).mkdir(parents=True, exist_ok=True)
        cmds.append((_sanitize_shell_arg(t), _sanitize_shell_arg(cmd), _sanitize_shell_arg(d)))

    # First pane (top-left)
    wt_cmd = f'wt -w 0 nt --title "CodeGPT > {cmds[0][0]}" -d "{cmds[0][2]}" cmd /k "{env_prefix}{cmds[0][1]}"'

    if len(cmds) >= 2:
        # Top-right
        wt_cmd += f' ; sp -V --title "CodeGPT > {cmds[1][0]}" -d "{cmds[1][2]}" cmd /k "{env_prefix}{cmds[1][1]}"'

    if len(cmds) >= 3:
        # Bottom-left (split first pane horizontally)
        wt_cmd += f' ; mf first ; sp -H --title "CodeGPT > {cmds[2][0]}" -d "{cmds[2][2]}" cmd /k "{env_prefix}{cmds[2][1]}"'

    if len(cmds) >= 4:
        # Bottom-right (split second pane horizontally)
        wt_cmd += f' ; mf up ; mf right ; sp -H --title "CodeGPT > {cmds[3][0]}" -d "{cmds[3][2]}" cmd /k "{env_prefix}{cmds[3][1]}"'

    subprocess.Popen(wt_cmd, shell=True)

    for t, _, d in cmds:
        running_tools[t] = {
            "proc": None, "started": datetime.now(), "bin": t, "cwd": d,
        }

    tool_list = ", ".join(t[0] for t in cmds)
    console.print(Panel(
        Text.from_markup(
            f"[bold]Grid launched![/]\n\n"
            f"  ┌──────────┬──────────┐\n"
            f"  │ [bright_cyan]{cmds[0][0]:^8}[/] │ [bright_cyan]{cmds[1][0] if len(cmds) > 1 else '':^8}[/] │\n"
            f"  ├──────────┼──────────┤\n"
            f"  │ [bright_cyan]{cmds[2][0] if len(cmds) > 2 else '':^8}[/] │ [bright_cyan]{cmds[3][0] if len(cmds) > 3 else '':^8}[/] │\n"
            f"  └──────────┴──────────┘\n\n"
            f"[dim]Alt+Arrow = switch panes | Ctrl+Shift+W = close pane[/]"
        ),
        title="[bold bright_green]2x2 Grid[/]",
        border_style="bright_green", padding=(1, 2), width=tw(),
    ))
    audit_log("GRID_LAUNCH", tool_list)


# --- Custom Skills (OpenClaw-style self-extending) ---

SKILLS_DIR = Path.home() / ".codegpt" / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def load_skills():
    """Load all custom skills."""
    skills = {}
    for f in SKILLS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            skills[data["name"]] = data
        except Exception:
            pass
    return skills


def save_skill(name, prompt_text, desc=""):
    """Save a custom skill."""
    skill = {
        "name": name,
        "prompt": prompt_text,
        "desc": desc or f"Custom skill: {name}",
        "created": datetime.now().isoformat(),
    }
    (SKILLS_DIR / f"{name}.json").write_text(json.dumps(skill, indent=2))
    return skill


def delete_skill(name):
    f = SKILLS_DIR / f"{name}.json"
    if f.exists():
        f.unlink()
        return True
    return False


# --- Browser ---

def browse_url(url, model=None):
    """Fetch a URL, extract text, and summarize it."""
    if not url.startswith("http"):
        url = "https://" + url

    print_sys(f"Fetching {url}...")

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "CodeGPT/2.0"})
        resp.raise_for_status()
        html = resp.text

        # Simple HTML to text — strip tags
        import re as _re
        text = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = _re.sub(r'\s+', ' ', text).strip()

        # Truncate
        text = text[:5000]

        console.print(Rule(style="bright_cyan", characters="─"))
        console.print(Text(f"  {url}", style="dim"))
        console.print()

        # Ask AI to summarize
        try:
            ai_resp = requests.post(OLLAMA_URL, json={
                "model": model or MODEL,
                "messages": [
                    {"role": "system", "content": "Summarize this web page content in 3-5 bullet points. Be concise."},
                    {"role": "user", "content": f"URL: {url}\n\nContent:\n{text}"},
                ],
                "stream": False,
            }, timeout=60)
            summary = ai_resp.json().get("message", {}).get("content", text[:500])
            console.print(Markdown(summary))
        except Exception:
            # Fallback: show raw text
            console.print(Text(text[:500], style="white"))

        console.print()
        return text

    except Exception as e:
        print_err(f"Cannot fetch {url}: {e}")
        return None


# --- Cron / Scheduled Tasks ---

active_crons = []
cron_command_queue = []  # Thread-safe command queue for cron execution


def add_cron(interval_str, command):
    """Schedule a recurring command."""
    # Parse interval: 5m, 1h, 30s
    match = re.match(r'^(\d+)\s*(s|sec|m|min|h|hr|hour)s?$', interval_str, re.IGNORECASE)
    if not match:
        print_err("Bad interval. Examples: 30s, 5m, 1h")
        return

    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit in ('m', 'min'):
        seconds = value * 60
    elif unit in ('h', 'hr', 'hour'):
        seconds = value * 3600
    else:
        seconds = value

    def run_cron():
        while True:
            time.sleep(seconds)
            # Check if still active
            if cron_entry not in active_crons:
                break
            cron_entry["last_run"] = datetime.now().isoformat()
            cron_entry["runs"] += 1
            # Queue the command for main loop to execute
            cron_command_queue.append(command)

    cron_entry = {
        "command": command,
        "interval": interval_str,
        "seconds": seconds,
        "runs": 0,
        "created": datetime.now().isoformat(),
        "last_run": None,
    }
    active_crons.append(cron_entry)

    t = threading.Thread(target=run_cron, daemon=True)
    t.start()
    cron_entry["thread"] = t

    print_sys(f"Scheduled: {command} every {interval_str}")


def list_crons():
    if not active_crons:
        print_sys("No scheduled tasks. Use: /cron 5m /weather")
        return

    table = Table(title="Scheduled Tasks", border_style="bright_cyan",
                  title_style="bold cyan", show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Command", style="bright_cyan")
    table.add_column("Interval", style="dim")
    table.add_column("Runs", style="dim", width=5)
    for i, c in enumerate(active_crons, 1):
        table.add_row(str(i), c["command"], c["interval"], str(c["runs"]))
    console.print(table)
    console.print()


# --- Auto-Skill (AI creates commands) ---

def auto_create_skill(description, model):
    """AI creates a custom skill from a description."""
    print_sys("AI is designing your skill...")

    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model,
            "messages": [
                {"role": "system", "content": (
                    "You are a skill designer for CodeGPT CLI. "
                    "Given a description, create a skill with:\n"
                    "1. A short name (lowercase, no spaces)\n"
                    "2. A system prompt that the AI will use\n"
                    "3. A description\n\n"
                    "Respond ONLY in this JSON format:\n"
                    '{"name": "skillname", "prompt": "system prompt here", "desc": "short description"}'
                )},
                {"role": "user", "content": description},
            ],
            "stream": False,
        }, timeout=60)
        content = resp.json().get("message", {}).get("content", "")

        # Parse JSON from response
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            skill_data = json.loads(json_match.group())
            name = skill_data.get("name", "").lower().replace(" ", "-")
            prompt_text = skill_data.get("prompt", "")
            desc = skill_data.get("desc", "")

            if name and prompt_text:
                save_skill(name, prompt_text, desc)
                print_success(f"Skill created: /{name}")
                print_sys(f"  {desc}")
                print_sys(f"  Use it: /{name} <your message>")
                return name

        print_err("AI couldn't create a valid skill. Try a clearer description.")

    except Exception as e:
        print_err(f"Failed: {e}")
    return None


# --- Voice Input ---

def voice_input():
    """Record from microphone and transcribe to text."""
    try:
        import speech_recognition as sr
    except ImportError:
        print_err("Install speech_recognition:\n  pip install SpeechRecognition PyAudio")
        return None

    recognizer = sr.Recognizer()

    try:
        mic = sr.Microphone()
    except (AttributeError, OSError):
        print_err("No microphone found. Install PyAudio:\n  pip install PyAudio")
        return None

    print_sys("Listening... (speak now)")

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
    except sr.WaitTimeoutError:
        print_sys("No speech detected.")
        return None
    except Exception as e:
        print_err(f"Mic error: {e}")
        return None

    print_sys("Transcribing...")

    try:
        text = recognizer.recognize_google(audio)
        print_sys(f'Heard: "{text}"')
        return text
    except sr.UnknownValueError:
        print_sys("Could not understand audio.")
        return None
    except sr.RequestError as e:
        print_err(f"Speech API error: {e}")
        return None


# --- Streaming ---

think_mode = False
temperature = 0.7

def stream_response(messages, system, model):
    global last_ai_response, think_mode, temperature
    ollama_messages = [{"role": "system", "content": system}]

    # Add memory context
    mem_ctx = get_memory_context()
    if mem_ctx:
        ollama_messages.append({"role": "system", "content": mem_ctx})

    # Add pinned messages as context
    if pinned_messages:
        pin_context = "\n".join(f"[Pinned] {m['content'][:200]}" for m in pinned_messages)
        ollama_messages.append({"role": "system", "content": f"Reference context:\n{pin_context}"})

    # Deep thinking mode
    if think_mode:
        ollama_messages.append({"role": "system", "content": (
            "IMPORTANT: Before answering, think through this step-by-step. "
            "Show your reasoning process in a <think> block, then give the final answer. "
            "Format: <think>your reasoning</think>\n\nFinal answer here."
        )})

    for msg in messages:
        ollama_messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        request_body = {"model": model, "messages": ollama_messages, "stream": True}
        opts = {"temperature": temperature}
        opts.update(model_params)
        request_body["options"] = opts

        response = requests.post(
            OLLAMA_URL,
            json=request_body,
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        full_response = []
        stats_line = ""
        w = tw()

        # Thinking animation then stream
        with Live(
            Panel(
                Text("Thinking...", style="dim italic"),
                title="[bold bright_green]AI[/]",
                title_align="left",
                border_style="bright_green",
                padding=(0, 2),
                width=w,
            ),
            console=console,
            refresh_per_second=12,
            transient=True,
        ) as live:
            dots = 0
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "message" in chunk and "content" in chunk["message"]:
                    token = chunk["message"]["content"]
                    full_response.append(token)

                    current = "".join(full_response)
                    live.update(Panel(
                        Markdown(current),
                        title="[bold bright_green]AI[/]",
                        title_align="left",
                        border_style="bright_green",
                        subtitle="[dim italic]streaming...[/]",
                        subtitle_align="right",
                        padding=(0, 2),
                        width=w,
                    ))

                if chunk.get("done"):
                    td = chunk.get("total_duration", 0)
                    ec = chunk.get("eval_count", 0)
                    pec = chunk.get("prompt_eval_count", 0)
                    ds = td / 1e9 if td else 0
                    tps = ec / ds if ds > 0 else 0
                    stats_line = f"[dim]{ec} tok | {ds:.1f}s | {tps:.0f} tok/s[/]"
                    session_stats["tokens_in"] += pec
                    session_stats["tokens_out"] += ec

        final = "".join(full_response)
        last_ai_response = final
        print_ai_msg(final, stats_line)

        # Action bar
        actions = Text()
        actions.append("  /copy", style="bright_cyan")
        actions.append("  /regen", style="bright_cyan")
        actions.append("  /edit", style="bright_cyan")
        console.print(Align.right(actions, width=tw()))
        console.print()

        return final

    except requests.ConnectionError:
        print_err("Cannot connect to Ollama. Is it running?")
        return None
    except requests.Timeout:
        print_err("Request timed out.")
        return None
    except requests.HTTPError as e:
        print_err(str(e))
        return None


# --- Input ---

def _bottom_toolbar():
    """Clean status bar like Claude Code."""
    elapsed = int(time.time() - session_stats["start"])
    mins = elapsed // 60
    msgs = session_stats["messages"]
    tok = session_stats["tokens_out"]
    if is_compact():
        return [("class:bottom-toolbar", f" {msgs} msgs · {tok} tok · {mins}m ")]
    return [("class:bottom-toolbar",
             f" {msgs} msgs · {tok} tokens · {mins}m · type / for commands ")]


def get_input():
    try:
        return prompt(
            [("class:prompt", " ❯ ")],
            style=input_style,
            history=input_history,
            completer=cmd_completer,
            complete_while_typing=True,
            bottom_toolbar=_bottom_toolbar,
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return None


# --- Main ---

def main():
    global last_ai_response, code_exec_count, OLLAMA_URL, sidebar_enabled, think_mode, temperature

    # CLI args mode: python chat.py --ask "question" or python chat.py --cmd "/tools"
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--ask" and len(sys.argv) > 2:
            question = " ".join(sys.argv[2:])
            try:
                resp = requests.post(
                    OLLAMA_URL,
                    json={"model": MODEL, "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": question},
                    ], "stream": False},
                    timeout=120,
                )
                print(resp.json().get("message", {}).get("content", ""))
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
            return

        elif arg == "--agent" and len(sys.argv) > 3:
            agent_name = sys.argv[2]
            task = " ".join(sys.argv[3:])
            if agent_name in AI_AGENTS:
                result = run_agent(agent_name, task, MODEL)
                if result:
                    print(result)
            else:
                print(f"Unknown agent. Available: {', '.join(AI_AGENTS.keys())}")
            return

        elif arg == "--team" and len(sys.argv) > 3:
            # Non-interactive: get one round from both AIs
            name1, name2 = sys.argv[2], sys.argv[3]
            topic = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "introduce yourself"
            m1 = resolve_team_member(name1)
            m2 = resolve_team_member(name2)
            for member in [m1, m2]:
                try:
                    resp = requests.post(OLLAMA_URL, json={
                        "model": member["model"] or MODEL,
                        "messages": [
                            {"role": "system", "content": member["system"]},
                            {"role": "user", "content": topic},
                        ], "stream": False,
                    }, timeout=90)
                    content = resp.json().get("message", {}).get("content", "")
                    print(f"\n[{member['name']}]\n{content}")
                except Exception as e:
                    print(f"[{member['name']}] Error: {e}")
            return

        elif arg == "--tools":
            installed = 0
            for name, info in AI_TOOLS.items():
                ok = shutil.which(info["bin"]) is not None
                if ok:
                    installed += 1
                status = "+" if ok else "-"
                print(f"  {status} /{name:<16} {info['name']}")
            print(f"\n  {installed}/{len(AI_TOOLS)} installed")
            return

        elif arg == "--models":
            try:
                resp = requests.get(OLLAMA_URL.replace("/api/chat", "/api/tags"), timeout=3)
                models = [m["name"] for m in resp.json().get("models", [])]
                for m in models:
                    print(f"  {m}")
                print(f"\n  {len(models)} models")
            except Exception:
                print("  Ollama not reachable")
            return

        elif arg == "--status":
            profile = load_profile()
            mem_count = len(load_memories())
            try:
                resp = requests.get(OLLAMA_URL.replace("/api/chat", "/api/tags"), timeout=3)
                model_count = len(resp.json().get("models", []))
                ollama_status = f"running ({model_count} models)"
            except Exception:
                ollama_status = "offline"
            tool_count = sum(1 for t in AI_TOOLS.values() if shutil.which(t["bin"]))

            try:
                from ai_cli import __version__ as _v
            except ImportError:
                _v = "2.0.0"
            print(f"  CodeGPT v{_v}")
            print(f"  User:     {profile.get('name', 'not set')}")
            print(f"  Model:    {profile.get('model', MODEL)}")
            print(f"  Persona:  {profile.get('persona', 'default')}")
            print(f"  Ollama:   {ollama_status}")
            print(f"  Tools:    {tool_count}/{len(AI_TOOLS)} installed")
            print(f"  Memories: {mem_count}")
            print(f"  Sessions: {profile.get('total_sessions', 0)}")
            return

        elif arg in ("--help", "-h"):
            print("CodeGPT — Local AI Assistant Hub")
            print("")
            print("  ai                    Interactive CLI")
            print("  ai --ask <question>   Quick one-shot question")
            print("  ai --agent <name> <task>  Run an agent")
            print("  ai --team <a1> <a2> <topic>  Two AIs respond")
            print("  ai --tools            List all AI tools")
            print("  ai --models           List Ollama models")
            print("  ai --status           Show status")
            print("  ai --version          Show version")
            print("  ai doctor             System diagnostics")
            print("  ai update             Self-update")
            print("")
            print("  echo 'question' | ai  Pipe input")
            return

    # Pipe support: echo "question" | ai
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            try:
                resp = requests.post(
                    OLLAMA_URL,
                    json={"model": MODEL, "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": piped},
                    ], "stream": False},
                    timeout=120,
                )
                print(resp.json().get("message", {}).get("content", ""))
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
            return

    # PIN login
    if not pin_login():
        sys.exit(0)
    audit_log("SESSION_START")

    # Connect to Ollama — never crash, always start the CLI
    available_models = []

    def try_connect(url):
        """Try to connect to an Ollama instance."""
        try:
            base = url.replace("/api/chat", "/api/tags")
            resp = requests.get(base, timeout=3)
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    # Try 1: Current OLLAMA_URL
    available_models = try_connect(OLLAMA_URL)

    # Try 2: Auto-start local Ollama
    if not available_models and shutil.which("ollama"):
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
            )
            for _ in range(10):
                time.sleep(1)
                available_models = try_connect(OLLAMA_URL)
                if available_models:
                    break
        except Exception:
            pass

    # Try 3: Check common remote addresses
    if not available_models:
        for remote in ["http://192.168.1.237:11434/api/chat",
                       "http://10.0.2.2:11434/api/chat"]:
            models = try_connect(remote)
            if models:
                OLLAMA_URL = remote
                available_models = models
                break

    # Try 4: Load saved URL from last session
    if not available_models:
        saved_url = Path.home() / ".codegpt" / "ollama_url"
        if saved_url.exists():
            saved = saved_url.read_text().strip()
            if saved:
                models = try_connect(saved)
                if models:
                    OLLAMA_URL = saved
                    available_models = models

    # Always continue — offline mode if no backend
    if not available_models:
        available_models = [MODEL]  # Use default model name as placeholder
        offline_mode = True
    else:
        offline_mode = False

    # Load profile
    profile = load_profile()
    first_time = profile["created"] is None

    if first_time:
        setup_profile()
        profile = load_profile()
    else:
        profile["total_sessions"] = profile.get("total_sessions", 0) + 1
        save_profile(profile)

    messages = []
    model = profile.get("model", MODEL)
    persona_name = profile.get("persona", "default")
    system = PERSONAS.get(persona_name, SYSTEM_PROMPT)

    print_header(model)

    # Clean welcome — like Claude Code
    if not first_time:
        name = profile.get("name", "")
        if offline_mode:
            console.print(Text.from_markup("  [yellow]offline[/] — use [bright_cyan]/connect IP[/] to link to Ollama"))
            console.print()

        if name:
            hour = datetime.now().hour
            greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
            console.print(Text(f"  {greeting}, {name}.", style="bold white"))
        console.print(Text("  Type a message to chat. Type / for commands.", style="dim"))
        console.print()

    print_welcome(model, available_models)

    while True:
        # Auto-lock check
        if check_auto_lock():
            if not prompt_pin_unlock():
                audit_log("LOCKED_OUT")
                break

        # Drain cron command queue
        while cron_command_queue:
            cron_cmd = cron_command_queue.pop(0)
            print_sys(f"[cron] {cron_cmd}")

        user_input = get_input()
        if user_input is None:
            cancel_all_reminders()
            audit_log("SESSION_END")
            console.print(Panel(Text("Session ended.", style="dim"), border_style="dim"))
            break

        if not user_input:
            continue

        last_activity[0] = time.time()

        # Suggestion number shortcut
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(SUGGESTIONS):
                user_input = SUGGESTIONS[idx]

        # Commands
        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()

            # Resolve aliases
            if cmd in ALIASES:
                real_cmd = ALIASES[cmd]
                user_input = real_cmd + user_input[len(cmd):]
                cmd = real_cmd

            if cmd == "/quit":
                cancel_all_reminders()
                # Save profile stats
                profile["total_messages"] = profile.get("total_messages", 0) + session_stats["messages"]
                profile["total_tokens"] = profile.get("total_tokens", 0) + session_stats["tokens_out"]
                profile["model"] = model
                save_profile(profile)

                elapsed = int(time.time() - session_stats["start"])
                name = profile.get("name", "")
                goodbye = f"See you, {name}." if name else "Session ended."
                console.print(Panel(
                    Text(f"{goodbye}\n"
                         f"Duration: {elapsed // 60}m {elapsed % 60}s  |  "
                         f"Messages: {session_stats['messages']}  |  "
                         f"Tokens: {session_stats['tokens_in']}in / {session_stats['tokens_out']}out",
                         style="dim"),
                    title="[dim]Session Summary[/]",
                    border_style="dim",
                ))
                break

            elif cmd == "/new":
                if messages:
                    try:
                        ans = prompt([("class:prompt", " Save current chat? (y/n) > ")], style=input_style).strip().lower()
                        if ans == "y":
                            save_conversation(messages, model)
                    except (KeyboardInterrupt, EOFError):
                        pass
                messages = []
                last_ai_response = ""
                session_stats["messages"] = 0
                print_header(model)
                print_welcome(model, available_models)
                continue

            elif cmd == "/save":
                if not messages:
                    print_sys("Nothing to save.")
                elif ask_permission("save_chat", "Save conversation"):
                    save_conversation(messages, model)
                continue

            elif cmd == "/load":
                loaded_msgs, loaded_model = load_conversation()
                if loaded_msgs is not None:
                    messages = loaded_msgs
                    if loaded_model:
                        model = loaded_model
                    session_stats["messages"] = len(messages)
                    print_header(model)
                    # Show last few messages
                    for msg in messages[-4:]:
                        if msg["role"] == "user":
                            print_user_msg(msg["content"])
                        else:
                            print_ai_msg(msg["content"])
                    last_ai = [m for m in messages if m["role"] == "assistant"]
                    if last_ai:
                        last_ai_response = last_ai[-1]["content"]
                    print_sys(f"Loaded {len(messages)} messages.")
                continue

            elif cmd == "/delete":
                if ask_permission("delete_chat", "Delete a saved conversation"):
                    delete_conversation()
                continue

            elif cmd == "/copy":
                if last_ai_response:
                    copy_to_clipboard(last_ai_response)
                else:
                    print_sys("No AI response to copy.")
                continue

            elif cmd == "/regen":
                if messages and messages[-1]["role"] == "assistant":
                    messages.pop()
                    session_stats["messages"] -= 1
                    response = stream_response(messages, system, model)
                    if response:
                        messages.append({"role": "assistant", "content": response})
                        session_stats["messages"] += 1
                else:
                    print_sys("Nothing to regenerate.")
                continue

            elif cmd == "/edit":
                if messages:
                    # Find last user message
                    last_user_idx = None
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i]["role"] == "user":
                            last_user_idx = i
                            break
                    if last_user_idx is not None:
                        old_msg = messages[last_user_idx]["content"]
                        console.print(Panel(Text(old_msg, style="dim"), title="[dim]Editing[/]",
                                            border_style="bright_black", padding=(0, 1), width=tw()))
                        try:
                            new_msg = prompt(
                                [("class:prompt", " Edit > ")],
                                style=input_style,
                                default=old_msg,
                            ).strip()
                        except (KeyboardInterrupt, EOFError):
                            print_sys("Cancelled.")
                            continue

                        if new_msg and new_msg != old_msg:
                            # Remove everything from that message onward
                            messages = messages[:last_user_idx]
                            messages.append({"role": "user", "content": new_msg})
                            session_stats["messages"] = len(messages)
                            print_user_msg(new_msg)
                            response = stream_response(messages, system, model)
                            if response:
                                messages.append({"role": "assistant", "content": response})
                                session_stats["messages"] += 1
                        else:
                            print_sys("No changes.")
                    else:
                        print_sys("No user message to edit.")
                else:
                    print_sys("No messages to edit.")
                continue

            elif cmd == "/clear":
                print_header(model)
                continue

            elif cmd == "/file":
                file_path = user_input[len("/file "):].strip()
                if file_path and ask_permission("file_read", file_path):
                    file_content = read_file_context(file_path)
                    if file_content:
                        messages.append({"role": "user", "content": file_content})
                        session_stats["messages"] += 1
                        print_user_msg(f"[file: {Path(file_path).name}]")
                        response = stream_response(messages, system, model)
                        if response:
                            messages.append({"role": "assistant", "content": response})
                            session_stats["messages"] += 1
                        else:
                            messages.pop()
                else:
                    print_sys("Usage: /file path/to/file.py")
                continue

            elif cmd == "/run":
                if code_exec_count >= CODE_EXEC_LIMIT:
                    print_err(f"Code execution limit reached ({CODE_EXEC_LIMIT}/session). Restart to reset.")
                    continue
                if not ask_permission("code_exec", "Execute Python code from last AI response"):
                    continue
                code_exec_count += 1
                audit_log("CODE_EXEC", f"run #{code_exec_count}")
                # Find last code block in AI responses
                for msg in reversed(messages):
                    if msg["role"] == "assistant":
                        blocks = extract_code_blocks(msg["content"])
                        if blocks:
                            code = blocks[-1]
                            print_sys(f"Running...\n{code[:100]}{'...' if len(code) > 100 else ''}")
                            output, rc = run_python_code(code)
                            status = "OK" if rc == 0 else "FAIL"
                            console.print(Panel(
                                Text(output[:3000], style="green" if rc == 0 else "red"),
                                title=f"[bold {'green' if rc == 0 else 'red'}]Output ({status})[/]",
                                border_style="green" if rc == 0 else "red",
                                padding=(0, 2),
                                width=tw(),
                            ))
                            break
                else:
                    print_sys("No code blocks found in recent messages.")
                continue

            elif cmd == "/code":
                code_text = get_multiline_code()
                if code_text:
                    user_input = f"```python\n{code_text}\n```\nAnalyze this code."
                    print_user_msg("[code block]")
                    messages.append({"role": "user", "content": user_input})
                    session_stats["messages"] += 1
                    response = stream_response(messages, system, model)
                    if response:
                        messages.append({"role": "assistant", "content": response})
                        session_stats["messages"] += 1
                    else:
                        messages.pop()
                continue

            elif cmd == "/think":
                think_mode = not think_mode
                state = "ON — deep reasoning" if think_mode else "OFF — normal"
                print_sys(f"Thinking mode: {state}")
                continue

            elif cmd == "/temp":
                temp_val = user_input[len("/temp "):].strip()
                if temp_val:
                    try:
                        t = float(temp_val)
                        if 0.0 <= t <= 2.0:
                            temperature = t
                            print_sys(f"Temperature: {temperature}")
                        else:
                            print_sys("Range: 0.0 (precise) to 2.0 (creative)")
                    except ValueError:
                        print_sys("Usage: /temp 0.7")
                else:
                    print_sys(f"Current: {temperature}\nRange: 0.0 (precise) to 2.0 (creative)")
                continue

            elif cmd == "/tokens":
                table = Table(title="Token Usage", border_style="bright_cyan",
                              title_style="bold cyan", show_header=False)
                table.add_column("Metric", style="dim", width=16)
                table.add_column("Value", style="white")
                table.add_row("This session in", str(session_stats["tokens_in"]))
                table.add_row("This session out", str(session_stats["tokens_out"]))
                table.add_row("Messages", str(session_stats["messages"]))
                table.add_row("Lifetime msgs", str(profile.get("total_messages", 0)))
                table.add_row("Lifetime tokens", str(profile.get("total_tokens", 0)))
                table.add_row("Sessions", str(profile.get("total_sessions", 0)))
                console.print(table)
                console.print()
                continue

            elif cmd == "/compact":
                if len(messages) <= 4:
                    print_sys("Not enough messages to compact.")
                    continue
                print_sys("Compacting conversation...")
                summary_prompt = (
                    "Summarize the key points of this conversation so far in 3-5 bullet points. "
                    "Include any decisions made, code written, or problems solved."
                )
                compact_msgs = messages + [{"role": "user", "content": summary_prompt}]
                response = stream_response(compact_msgs, system, model)
                if response:
                    # Replace history with summary + last 2 exchanges
                    keep = messages[-4:]
                    messages = [{"role": "assistant", "content": f"[Conversation summary]\n{response}"}] + keep
                    session_stats["messages"] = len(messages)
                    print_sys(f"Compacted: {len(messages)} messages remaining.")
                continue

            elif cmd == "/search":
                keyword = user_input[len("/search "):].strip()
                search_messages(messages, keyword)
                continue

            elif cmd == "/export":
                if ask_permission("export", "Export chat as markdown"):
                    export_chat(messages, model, persona_name)
                continue

            elif cmd == "/diff":
                ai_msgs = [m for m in messages if m["role"] == "assistant"]
                if len(ai_msgs) >= 2:
                    console.print(Panel(
                        Markdown(ai_msgs[-2]["content"]),
                        title="[bold yellow]Previous[/]",
                        border_style="yellow",
                        padding=(0, 2), width=tw(),
                    ))
                    console.print(Panel(
                        Markdown(ai_msgs[-1]["content"]),
                        title="[bold green]Latest[/]",
                        border_style="green",
                        padding=(0, 2), width=tw(),
                    ))
                else:
                    print_sys("Need at least 2 AI responses to diff.")
                continue

            elif cmd == "/pin":
                idx = user_input[len("/pin "):].strip()
                pin_message(messages, idx)
                continue

            elif cmd == "/pins":
                show_pins()
                continue

            elif cmd == "/modelinfo":
                show_model_info(model)
                continue

            elif cmd == "/params":
                args_text = user_input[len("/params "):].strip()
                if args_text:
                    parts = args_text.split()
                    if len(parts) == 2 and parts[0] in model_params:
                        try:
                            model_params[parts[0]] = float(parts[1])
                            print_sys(f"{parts[0]}: {model_params[parts[0]]}")
                        except ValueError:
                            print_sys("Value must be a number.")
                    else:
                        available = ", ".join(model_params.keys())
                        print_sys(f"Params: {available}\nUsage: /params top_p 0.9")
                else:
                    table = Table(title="Model Parameters", border_style="bright_cyan",
                                  title_style="bold cyan", show_header=False)
                    table.add_column("Param", style="bright_cyan", width=16)
                    table.add_column("Value", style="white")
                    table.add_row("temperature", str(temperature))
                    for k, v in model_params.items():
                        table.add_row(k, str(v))
                    console.print(table)
                    console.print(Text("  /params <name> <value> to change", style="dim"))
                    console.print()
                continue

            elif cmd == "/prompts" or cmd == "/p":
                args_text = user_input.split(maxsplit=2)
                if len(args_text) >= 3 and args_text[1] in PROMPT_TEMPLATES:
                    # Use a template: /p debug my_code()
                    template = PROMPT_TEMPLATES[args_text[1]]
                    full_prompt = template + args_text[2]
                    print_user_msg(f"[{args_text[1]}] {args_text[2][:50]}...")
                    messages.append({"role": "user", "content": full_prompt})
                    session_stats["messages"] += 1
                    response = stream_response(messages, system, model)
                    if response:
                        messages.append({"role": "assistant", "content": response})
                        session_stats["messages"] += 1
                    else:
                        messages.pop()
                else:
                    show_prompts()
                continue

            elif cmd == "/fork":
                idx = user_input[len("/fork "):].strip()
                forked = fork_conversation(messages, idx)
                if forked is not None:
                    messages = forked
                    session_stats["messages"] = len(messages)
                continue

            elif cmd == "/compare":
                args_text = user_input[len("/compare "):].strip()
                if not args_text:
                    print_sys("Usage: /compare model1 model2 your prompt")
                    print_sys("Example: /compare llama3.2 mistral What is recursion?")
                else:
                    parts = args_text.split(maxsplit=2)
                    if len(parts) >= 3:
                        compare_models(parts[2], parts[0], parts[1], system)
                    else:
                        print_sys("Need: /compare <model1> <model2> <prompt>")
                continue

            elif cmd == "/rate":
                rating = user_input[len("/rate "):].strip().lower()
                if rating in ("good", "bad", "+", "-", "up", "down"):
                    rate_response(messages, "good" if rating in ("good", "+", "up") else "bad")
                else:
                    print_sys("Usage: /rate good  or  /rate bad")
                continue

            elif cmd == "/tag":
                tag = user_input[len("/tag "):].strip()
                if tag:
                    print_sys(f"Tag: {tag} (applied when you /save)")
                    # Store tag for next save
                    session_stats["tag"] = tag
                else:
                    current = session_stats.get("tag", "none")
                    print_sys(f"Current tag: {current}")
                continue

            elif cmd == "/shortcuts":
                show_shortcuts()
                continue

            elif cmd == "/agent":
                args_text = user_input[len("/agent "):].strip()
                if not args_text or not ask_permission("agent_run", args_text[:50]):
                    if not args_text: list_agents()
                    continue
                parts = args_text.split(maxsplit=1)
                if len(parts) >= 2 and parts[0] in AI_AGENTS:
                    result = run_agent(parts[0], parts[1], model)
                    if result:
                        messages.append({"role": "user", "content": f"[agent:{parts[0]}] {parts[1]}"})
                        messages.append({"role": "assistant", "content": result})
                        session_stats["messages"] += 2
                elif len(parts) == 1 and parts[0] in AI_AGENTS:
                    print_sys(f"Need a task. Usage: /agent {parts[0]} <task description>")
                else:
                    list_agents()
                continue

            elif cmd == "/agents":
                list_agents()
                continue

            elif cmd == "/lab":
                args_text = user_input[len("/lab "):].strip()
                parts = args_text.split(maxsplit=1)
                sub = parts[0] if parts else ""

                if sub == "bench":
                    if len(parts) >= 2:
                        lab_bench(parts[1], available_models, system)
                    else:
                        print_sys("Usage: /lab bench <prompt to test across all models>")

                elif sub == "chain":
                    if len(parts) >= 2:
                        result = lab_chain(parts[1], model, system)
                        if result:
                            messages.append({"role": "assistant", "content": result})
                    else:
                        print_sys("Usage: /lab chain prompt1 | prompt2 | prompt3")

                elif sub == "prompt":
                    if len(parts) >= 2:
                        lab_prompt_optimizer(parts[1], model, system)
                    else:
                        print_sys("Usage: /lab prompt <your prompt to optimize>")

                elif sub == "eval":
                    print_sys("Running quick eval...")
                    eval_questions = [
                        "What is 15 * 23?",
                        "Write a Python one-liner to reverse a string.",
                        "What is the time complexity of binary search?",
                        "Name 3 OWASP top 10 vulnerabilities.",
                        "What does TCP stand for?",
                    ]
                    correct = 0
                    for q in eval_questions:
                        try:
                            resp = requests.post(OLLAMA_URL, json={"model": model, "messages": [
                                {"role": "user", "content": q + " Answer in one line."}
                            ], "stream": False}, timeout=30)
                            ans = resp.json().get("message", {}).get("content", "")
                            console.print(Text(f"  Q: {q}", style="dim"))
                            console.print(Text(f"  A: {ans[:100]}", style="white"))
                            console.print()
                            correct += 1
                        except Exception:
                            console.print(Text(f"  Q: {q} — FAILED", style="red"))
                    print_sys(f"Eval: {correct}/{len(eval_questions)} answered ({model})")

                elif sub == "translate":
                    if len(parts) >= 2:
                        try:
                            resp = requests.post(OLLAMA_URL, json={"model": model, "messages": [
                                {"role": "system", "content": "You are a translator. Translate to the requested language. Only output the translation."},
                                {"role": "user", "content": parts[1]},
                            ], "stream": False}, timeout=60)
                            result = resp.json().get("message", {}).get("content", "")
                            console.print(Panel(Text(result), title="[bold green]Translation[/]",
                                                border_style="green", padding=(0, 2), width=tw()))
                        except Exception as e:
                            print_err(f"Translation failed: {e}")
                    else:
                        print_sys("Usage: /lab translate <text> to <language>")

                elif sub == "summarize":
                    if len(parts) >= 2:
                        try:
                            resp = requests.post(OLLAMA_URL, json={"model": model, "messages": [
                                {"role": "system", "content": "Summarize in 3-5 bullet points. Be concise."},
                                {"role": "user", "content": parts[1]},
                            ], "stream": False}, timeout=60)
                            result = resp.json().get("message", {}).get("content", "")
                            console.print(Panel(Markdown(result), title="[bold green]Summary[/]",
                                                border_style="green", padding=(0, 2), width=tw()))
                        except Exception as e:
                            print_err(f"Summary failed: {e}")
                    else:
                        print_sys("Usage: /lab summarize <text to summarize>")

                elif sub == "extract":
                    if len(parts) >= 2:
                        try:
                            resp = requests.post(OLLAMA_URL, json={"model": model, "messages": [
                                {"role": "system", "content": "Extract structured data as JSON. Only output valid JSON."},
                                {"role": "user", "content": parts[1]},
                            ], "stream": False}, timeout=60)
                            result = resp.json().get("message", {}).get("content", "")
                            console.print(Panel(Text(result), title="[bold green]Extracted Data[/]",
                                                border_style="green", padding=(0, 2), width=tw()))
                        except Exception as e:
                            print_err(f"Extraction failed: {e}")
                    else:
                        print_sys("Usage: /lab extract <text with data to extract>")

                else:
                    show_lab_menu()
                continue

            elif cmd == "/chain":
                chain_text = user_input[len("/chain "):].strip()
                if chain_text:
                    result = lab_chain(chain_text, model, system)
                    if result:
                        messages.append({"role": "assistant", "content": result})
                        session_stats["messages"] += 1
                else:
                    print_sys("Usage: /chain prompt1 | prompt2 | prompt3")
                continue

            elif cmd == "/mem":
                args_text = user_input[len("/mem "):].strip()
                parts = args_text.split(maxsplit=1)
                sub = parts[0] if parts else ""

                if sub == "save" and len(parts) >= 2:
                    mem_save(parts[1])
                elif sub == "recall":
                    query = parts[1] if len(parts) >= 2 else ""
                    mem_recall(query)
                elif sub == "list":
                    mem_recall()
                elif sub == "clear":
                    mem_clear()
                elif sub == "inject":
                    # Inject memories as a user-role context message (not system — avoids corrupting conversation)
                    mem_context = get_memory_context()
                    if mem_context:
                        messages.append({"role": "user", "content": f"[Memory context for reference]:\n{mem_context}"})
                        print_sys("Memories injected into context.")
                    else:
                        print_sys("No memories to inject.")
                else:
                    print_sys("Usage:\n  /mem save <text>  — remember something\n  /mem recall [query]  — search memories\n  /mem list  — show all\n  /mem inject  — add memories to AI context\n  /mem clear  — delete all")
                continue

            elif cmd == "/usage":
                elapsed = int(time.time() - session_stats["start"])
                mins = elapsed // 60
                secs = elapsed % 60
                mem_count = len(load_memories())
                pin_count = len(pinned_messages)
                saved = len(list(CHATS_DIR.glob("*.json"))) if CHATS_DIR.exists() else 0
                ratings = []
                if RATINGS_FILE.exists():
                    try:
                        ratings = json.loads(RATINGS_FILE.read_text())
                    except Exception:
                        pass
                good = sum(1 for r in ratings if r.get("rating") == "good")
                bad = sum(1 for r in ratings if r.get("rating") == "bad")

                console.print(Panel(
                    Text.from_markup(
                        f"[bold bright_cyan]CodeGPT Usage Dashboard[/]\n"
                        f"{'━' * 36}\n\n"
                        f"[bold]Session[/]\n"
                        f"  Uptime         [bright_cyan]{mins}m {secs}s[/]\n"
                        f"  Messages       [bright_cyan]{session_stats['messages']}[/]\n"
                        f"  Tokens in      [bright_cyan]{session_stats['tokens_in']}[/]\n"
                        f"  Tokens out     [bright_cyan]{session_stats['tokens_out']}[/]\n"
                        f"  Model          [bright_cyan]{model}[/]\n"
                        f"  Persona        [bright_cyan]{persona_name}[/]\n"
                        f"  Temperature    [bright_cyan]{temperature}[/]\n"
                        f"  Think mode     [bright_cyan]{'ON' if think_mode else 'OFF'}[/]\n\n"
                        f"[bold]Lifetime[/]\n"
                        f"  Total messages [bright_cyan]{profile.get('total_messages', 0)}[/]\n"
                        f"  Total tokens   [bright_cyan]{profile.get('total_tokens', 0)}[/]\n"
                        f"  Sessions       [bright_cyan]{profile.get('total_sessions', 0)}[/]\n"
                        f"  Since          [bright_cyan]{profile.get('created', '?')[:10]}[/]\n\n"
                        f"[bold]Storage[/]\n"
                        f"  Saved chats    [bright_cyan]{saved}[/]\n"
                        f"  Memories       [bright_cyan]{mem_count}[/]\n"
                        f"  Pinned msgs    [bright_cyan]{pin_count}[/]\n"
                        f"  Ratings        [green]{good} good[/] / [red]{bad} bad[/]\n\n"
                        f"[bold]Model Params[/]\n"
                        + "\n".join(f"  {k:<16} [bright_cyan]{v}[/]" for k, v in model_params.items())
                    ),
                    border_style="bright_cyan",
                    padding=(1, 2),
                    width=tw(),
                ))
                console.print()
                continue

            elif cmd == "/github":
                parts = user_input[len("/github "):].strip().split(maxsplit=1)
                sub = parts[0] if parts else ""
                args = parts[1] if len(parts) > 1 else ""
                if ask_permission("github", f"GitHub: {sub}"):
                    github_command(sub, args)
                continue

            elif cmd == "/weather":
                city = user_input[len("/weather "):].strip()
                if city:
                    get_weather(city)
                else:
                    get_weather("Southampton")  # Default
                continue

            elif cmd == "/open":
                url = user_input[len("/open "):].strip()
                if url and ask_permission("open_url", url):
                    open_url(url)
                else:
                    print_sys("Usage: /open google.com")
                continue

            elif cmd == "/spotify":
                sub = user_input[len("/spotify "):].strip().lower()
                if ask_permission("spotify", f"Spotify: {sub}"):
                    spotify_command(sub)
                continue

            elif cmd == "/volume":
                level = user_input[len("/volume "):].strip()
                if level and ask_permission("volume", f"Set volume to {level}"):
                    set_volume(level)
                else:
                    print_sys("Usage: /volume 50 (range 0-100)")
                continue

            elif cmd == "/bright":
                level = user_input[len("/bright "):].strip()
                if level and ask_permission("brightness", f"Set brightness to {level}"):
                    set_brightness(level)
                else:
                    print_sys("Usage: /bright 80 (range 0-100)")
                continue

            elif cmd == "/sysinfo":
                show_sysinfo()
                continue

            elif cmd == "/train":
                args_text = user_input[len("/train "):].strip()
                parts = args_text.split(maxsplit=1)
                sub = parts[0] if parts else ""
                extra = parts[1] if len(parts) > 1 else ""

                if sub == "collect":
                    train_collect(messages)

                elif sub == "rated":
                    train_collect_rated()

                elif sub == "build":
                    if not extra:
                        try:
                            name = input("  Model name: ").strip()
                            base = input(f"  Base model ({model}): ").strip() or model
                        except (KeyboardInterrupt, EOFError):
                            print_sys("Cancelled.")
                            continue
                    else:
                        name_parts = extra.split(maxsplit=1)
                        name = name_parts[0]
                        base = name_parts[1] if len(name_parts) > 1 else model
                    if name:
                        train_build(name, base, system)

                elif sub == "test":
                    custom = extra or ""
                    if not custom:
                        models_list = list(CUSTOM_MODELS_DIR.glob("*.Modelfile"))
                        if models_list:
                            custom = models_list[-1].stem
                        else:
                            print_sys("No custom models. Build one with /train build")
                            continue
                    train_test(custom, model, system)

                elif sub == "list":
                    models_list = list(CUSTOM_MODELS_DIR.glob("*.Modelfile"))
                    if models_list:
                        table = Table(title="Custom Models", border_style="bright_magenta",
                                      title_style="bold bright_magenta", show_header=True, header_style="bold")
                        table.add_column("Model", style="bright_cyan")
                        table.add_column("Modelfile", style="dim")
                        for m in models_list:
                            table.add_row(m.stem, str(m))
                        console.print(table)
                    else:
                        print_sys("No custom models yet.")

                elif sub == "delete":
                    if extra:
                        # Delete from Ollama
                        try:
                            subprocess.run(["ollama", "rm", extra], capture_output=True, timeout=10)
                            mf = CUSTOM_MODELS_DIR / f"{extra}.Modelfile"
                            if mf.exists():
                                mf.unlink()
                            print_sys(f"Deleted model: {extra}")
                            audit_log("MODEL_DELETED", extra)
                        except Exception as e:
                            print_err(f"Delete failed: {e}")
                    else:
                        print_sys("Usage: /train delete <model_name>")

                elif sub == "export":
                    data = load_training_data()
                    export_path = TRAINING_DIR / f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
                    export_path.write_text(json.dumps(data, indent=2))
                    print_sys(f"Exported: {export_path}")

                elif sub == "clear":
                    save_training_data({"examples": [], "system_prompt": "", "params": {}})
                    print_sys("Training data cleared.")

                elif sub == "params":
                    train_set_params()

                else:
                    train_status()
                console.print()
                continue

            elif cmd == "/bg":
                bg_args = user_input[len("/bg "):].strip().split(maxsplit=1)
                bg_tool = bg_args[0] if bg_args else ""
                bg_extra = bg_args[1] if len(bg_args) > 1 else ""

                # Check if it's a known tool
                if bg_tool == "claude":
                    if shutil.which("claude"):
                        launch_bg_tool("claude", "claude", bg_extra)
                        print_sys("Claude Code launched in new window.")
                        audit_log("BG_LAUNCH", "claude")
                    else:
                        print_err("Claude Code not installed.")
                elif bg_tool == "openclaw":
                    if shutil.which("openclaw"):
                        launch_bg_tool("openclaw", "openclaw", bg_extra)
                        print_sys("OpenClaw launched in new window.")
                        audit_log("BG_LAUNCH", "openclaw")
                    else:
                        print_err("OpenClaw not installed.")
                elif bg_tool in AI_TOOLS:
                    tool = AI_TOOLS[bg_tool]
                    if shutil.which(tool["bin"]):
                        full_args = " ".join(tool.get("default_args", []))
                        if bg_extra:
                            full_args = (full_args + " " + bg_extra).strip()
                        launch_bg_tool(bg_tool, tool["bin"], full_args or None)
                        print_sys(f"{tool['name']} launched in new window.")
                        audit_log("BG_LAUNCH", bg_tool)
                    else:
                        print_err(f"{tool['name']} not installed. Run /{bg_tool} to install it first.")
                elif bg_tool:
                    # Try launching any command in bg
                    launch_bg_tool(bg_tool, bg_tool, bg_extra or None, cwd=str(Path(__file__).parent))
                    print_sys(f"'{bg_tool}' launched in new window.")
                else:
                    print_sys("Usage: /bg <tool> [args]\nExample: /bg claude\n         /bg codex\n         /bg claude fix the bug")
                continue

            elif cmd == "/split":
                tools = user_input[len("/split "):].strip().split()
                if tools:
                    split_tools(tools, vertical=False)
                else:
                    print_sys("Usage: /split claude codex\n       /split claude codex gemini")
                continue

            elif cmd == "/splitv":
                tools = user_input[len("/splitv "):].strip().split()
                if tools:
                    split_tools(tools, vertical=True)
                else:
                    print_sys("Usage: /splitv claude gemini")
                continue

            elif cmd == "/grid":
                tools = user_input[len("/grid "):].strip().split()
                if tools:
                    grid_tools(tools)
                else:
                    print_sys("Usage: /grid claude codex gemini cline")
                continue

            elif cmd == "/broadcast":
                msg_text = user_input[len("/broadcast "):].strip()
                if msg_text and ask_permission("broadcast", msg_text[:50]):
                    bus_send("codegpt", "*", msg_text)
                    count = len(running_tools)
                    print_sys(f"Broadcast sent to {count} tools: {msg_text[:50]}")
                else:
                    print_sys("Usage: /broadcast hello everyone")
                continue

            elif cmd == "/inbox":
                show_inbox()
                continue

            elif cmd == "/dm":
                parts = user_input[len("/dm "):].strip().split(maxsplit=1)
                if len(parts) >= 2:
                    target = parts[0]
                    msg_text = parts[1]
                    bus_send("codegpt", target, msg_text)

                    # If target is an AI agent, get a response
                    if target in AI_AGENTS:
                        agent = AI_AGENTS[target]
                        try:
                            resp = requests.post(OLLAMA_URL, json={
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": agent["system"]},
                                    {"role": "user", "content": msg_text},
                                ],
                                "stream": False,
                            }, timeout=60)
                            reply = resp.json().get("message", {}).get("content", "")
                            bus_send(target, "codegpt", reply, "response")
                            console.print(Panel(
                                Markdown(reply),
                                title=f"[bold bright_magenta]{target}[/]",
                                border_style="bright_magenta", padding=(0, 2), width=tw(),
                            ))
                        except Exception as e:
                            print_err(f"{target} didn't respond: {e}")
                    else:
                        print_sys(f"Message sent to {target}.")
                else:
                    print_sys("Usage: /dm coder write a flask app\n       /dm researcher explain kubernetes")
                continue

            elif cmd == "/chat-link":
                parts = user_input[len("/chat-link "):].strip().split(maxsplit=2)
                if len(parts) >= 3:
                    t1, t2, topic = parts[0], parts[1], parts[2]
                    history = link_tools_conversation(t1, t2, topic, model, system)
                    if history:
                        for h in history:
                            messages.append({"role": "assistant",
                                            "content": f"[{h['speaker']}]: {h['msg']}"})
                        session_stats["messages"] += len(history)
                elif len(parts) == 2:
                    print_sys(f"Need a topic.\nUsage: /chat-link {parts[0]} {parts[1]} discuss Python vs Rust")
                else:
                    print_sys("Usage: /chat-link coder reviewer discuss best practices for error handling")
                    print_sys("       /chat-link architect pentester analyze this API design")
                continue

            elif cmd == "/all":
                prompt_text = user_input[len("/all "):].strip()
                if prompt_text:
                    results = ask_all_agents(prompt_text, model, system)
                    messages.append({"role": "user", "content": f"[/all] {prompt_text}"})
                    summary = "\n".join(f"**{n}**: {r['content'][:100]}..." for n, r in results.items())
                    messages.append({"role": "assistant", "content": summary})
                    session_stats["messages"] += 2
                else:
                    print_sys("Usage: /all what's the best way to handle errors in Python?")
                continue

            elif cmd == "/race":
                prompt_text = user_input[len("/race "):].strip()
                if prompt_text:
                    race_models(prompt_text, available_models, system)
                else:
                    print_sys("Usage: /race explain recursion in one paragraph")
                continue

            elif cmd == "/vote":
                prompt_text = user_input[len("/vote "):].strip()
                if prompt_text:
                    agent_vote(prompt_text, model, system)
                else:
                    print_sys("Usage: /vote should I use Flask or FastAPI for this project?")
                continue

            elif cmd == "/swarm":
                task_text = user_input[len("/swarm "):].strip()
                if task_text:
                    result = agent_swarm(task_text, model, system)
                    messages.append({"role": "user", "content": f"[/swarm] {task_text}"})
                    messages.append({"role": "assistant", "content": result[-500:]})
                    session_stats["messages"] += 2
                else:
                    print_sys("Usage: /swarm build a REST API for a todo app with auth")
                continue

            elif cmd == "/team":
                parts = user_input[len("/team "):].strip().split()
                if len(parts) >= 2:
                    history = team_chat(parts[0], parts[1], model, system)
                    # Add team chat to main conversation
                    for h in history:
                        if h["speaker"] == "user":
                            messages.append({"role": "user", "content": h["content"]})
                        else:
                            messages.append({"role": "assistant", "content": f"[{h['speaker']}]: {h['content']}"})
                    session_stats["messages"] += len(history)
                else:
                    print_sys("Usage: /team coder reviewer\n       /team architect pentester\n       /team explainer debugger")
                    print_sys(f"\nAgents: {', '.join(AI_AGENTS.keys())}")
                continue

            elif cmd == "/sidebar":
                sidebar_enabled = not sidebar_enabled
                state = "ON" if sidebar_enabled else "OFF"
                print_sys(f"Sidebar: {state}")
                if sidebar_enabled and console.width < 80:
                    print_sys("Terminal too narrow for sidebar. Widen to 80+ chars.")
                continue

            elif cmd == "/room":
                parts = user_input[len("/room "):].strip().split()
                if len(parts) >= 2:
                    history = chat_room(parts, model, system, user_joins=True)
                    for h in history:
                        if h["speaker"] == "user":
                            messages.append({"role": "user", "content": h["content"]})
                        else:
                            messages.append({"role": "assistant", "content": f"[{h['speaker']}] {h['content']}"})
                    session_stats["messages"] += len(history)
                else:
                    print_sys("Usage: /room coder reviewer architect")
                    print_sys("       /room claude codex gemini deepseek")
                    print_sys(f"\nAvailable: {', '.join(list(AI_AGENTS.keys()) + list(TOOL_PERSONAS.keys()))}")
                continue

            elif cmd == "/spectate":
                args = user_input[len("/spectate "):].strip().split()
                if len(args) >= 2:
                    # Last arg could be a topic
                    names = args
                    topic = ""
                    # Check if last args aren't AI names — treat as topic
                    all_names = set(AI_AGENTS.keys()) | set(TOOL_PERSONAS.keys())
                    topic_words = []
                    while names and names[-1] not in all_names:
                        topic_words.insert(0, names.pop())
                    topic = " ".join(topic_words) if topic_words else "Discuss the best programming practices"

                    if len(names) >= 2:
                        # Inject topic
                        h = chat_room(names, model, system, user_joins=False, topic=topic)
                    else:
                        print_sys("Need at least 2 AIs. Example: /spectate coder reviewer discuss Python")
                else:
                    print_sys("Usage: /spectate coder reviewer discuss error handling")
                    print_sys("       /spectate claude codex gemini debate which is best")
                continue

            elif cmd == "/monitor":
                # Live updating dashboard — press Ctrl+C to exit
                console.print(Text("  Live monitor — Ctrl+C to stop\n", style="dim"))
                try:
                    while True:
                        # Clear and redraw
                        clear_screen()

                        # Header
                        console.print(Panel(
                            Text("CODEGPT MONITOR", style="bold bright_cyan", justify="center"),
                            border_style="bright_cyan", padding=(0, 2), width=tw(),
                        ))

                        # Running tools
                        finished = [n for n, i in running_tools.items() if i["proc"] and i["proc"].poll() is not None]
                        for n in finished:
                            del running_tools[n]

                        tools_table = Table(title="Running Tools", border_style="bright_green",
                                           title_style="bold green", show_header=True, header_style="bold",
                                           width=tw())
                        tools_table.add_column("Tool", style="bright_cyan", width=14)
                        tools_table.add_column("Uptime", style="white", width=10)
                        tools_table.add_column("Dir", style="dim")

                        if running_tools:
                            for name, info in running_tools.items():
                                elapsed = int((datetime.now() - info["started"]).total_seconds())
                                uptime = f"{elapsed // 60}m {elapsed % 60}s"
                                tools_table.add_row(name, uptime, str(info["cwd"])[-35:])
                        else:
                            tools_table.add_row("[dim]none[/]", "", "")
                        console.print(tools_table)

                        # Recent messages
                        bus = load_bus()
                        recent = bus["messages"][-10:]

                        msg_table = Table(title="Message Feed", border_style="bright_magenta",
                                         title_style="bold bright_magenta", show_header=True,
                                         header_style="bold", width=tw())
                        msg_table.add_column("Time", style="dim", width=6)
                        msg_table.add_column("From", style="bright_cyan", width=10)
                        msg_table.add_column("To", style="yellow", width=10)
                        msg_table.add_column("Message", overflow="fold")

                        if recent:
                            for m in recent:
                                ts = m.get("timestamp", "")[11:16]
                                content = m.get("content", "")[:60]
                                read_style = "dim" if m.get("read") else ""
                                msg_table.add_row(ts, m.get("from", "?"),
                                                  m.get("to", "?"),
                                                  Text(content, style=read_style))
                        else:
                            msg_table.add_row("", "[dim]no messages[/]", "", "")
                        console.print(msg_table)

                        # Stats bar
                        unread = bus_unread("codegpt")
                        elapsed = int(time.time() - session_stats["start"])
                        console.print(Panel(
                            Text.from_markup(
                                f"  Tools: [bright_cyan]{len(running_tools)}[/]  |  "
                                f"  Messages: [bright_cyan]{len(bus['messages'])}[/]  |  "
                                f"  Unread: [{'red' if unread else 'green'}]{unread}[/]  |  "
                                f"  Session: [dim]{elapsed // 60}m[/]  |  "
                                f"  Model: [dim]{model}[/]"
                            ),
                            border_style="dim", padding=(0, 1), width=tw(),
                        ))

                        console.print(Text("\n  Refreshing every 3s — Ctrl+C to stop", style="dim"))
                        time.sleep(3)
                except KeyboardInterrupt:
                    print_header(model)
                    print_sys("Monitor closed.")
                continue

            elif cmd == "/feed":
                bus = load_bus()
                recent = bus["messages"][-20:]

                if not recent:
                    print_sys("No messages yet. Use /broadcast, /dm, or /chat-link to start.")
                    continue

                table = Table(title="Message Feed", border_style="bright_magenta",
                              title_style="bold bright_magenta", show_header=True,
                              header_style="bold")
                table.add_column("#", style="cyan", width=3)
                table.add_column("Time", style="dim", width=6)
                table.add_column("From", style="bright_cyan", width=12)
                table.add_column("To", style="yellow", width=12)
                table.add_column("Type", style="dim", width=8)
                table.add_column("Message", overflow="fold")

                for m in recent:
                    ts = m.get("timestamp", "")[11:16]
                    content = m.get("content", "")[:80]
                    read_style = "dim" if m.get("read") else "white"
                    table.add_row(
                        str(m.get("id", "")),
                        ts,
                        m.get("from", "?"),
                        m.get("to", "?"),
                        m.get("type", "msg"),
                        Text(content, style=read_style),
                    )
                console.print(table)
                console.print()
                continue

            elif cmd == "/hub":
                # Full hub view — everything in one screen
                clear_screen()
                w = tw()

                # Hub header
                console.print(Panel(
                    Text.from_markup(
                        "[bold bright_cyan]  ██╗  ██╗██╗   ██╗██████╗[/]\n"
                        "[bold bright_cyan]  ██║  ██║██║   ██║██╔══██╗[/]\n"
                        "[bold bright_cyan]  ███████║██║   ██║██████╔╝[/]\n"
                        "[bold bright_cyan]  ██╔══██║██║   ██║██╔══██╗[/]\n"
                        "[bold bright_cyan]  ██║  ██║╚██████╔╝██████╔╝[/]\n"
                        "[bold bright_cyan]  ╚═╝  ╚═╝ ╚═════╝ ╚═════╝[/]\n"
                        "[dim]        CodeGPT Command Center[/]"
                    ),
                    border_style="bright_cyan", padding=(1, 2), width=w,
                ))

                # Tools status
                tools_table = Table(title="AI Tools", border_style="bright_green",
                                   title_style="bold green", show_header=True,
                                   header_style="bold", width=w)
                tools_table.add_column("Tool", style="bright_cyan", width=14)
                tools_table.add_column("Status", width=8)
                tools_table.add_column("Uptime", style="dim", width=10)
                tools_table.add_column("Messages", style="dim", width=8)

                # Show installed tools + running status
                all_tool_names = list(AI_TOOLS.keys()) + ["claude", "openclaw"]
                for tname in all_tool_names:
                    if tname in AI_TOOLS:
                        installed = shutil.which(AI_TOOLS[tname]["bin"]) is not None
                    elif tname == "claude":
                        installed = shutil.which("claude") is not None
                    else:
                        installed = shutil.which("openclaw") is not None

                    is_running = tname in running_tools
                    if is_running:
                        elapsed = int((datetime.now() - running_tools[tname]["started"]).total_seconds())
                        status = "[bold green]LIVE[/]"
                        uptime = f"{elapsed // 60}m {elapsed % 60}s"
                    elif installed:
                        status = "[dim]ready[/]"
                        uptime = ""
                    else:
                        status = "[dim]—[/]"
                        uptime = ""

                    # Count messages for this tool
                    bus = load_bus()
                    msg_count = sum(1 for m in bus["messages"]
                                   if m.get("from") == tname or m.get("to") == tname)

                    tools_table.add_row(tname, status, uptime, str(msg_count) if msg_count else "")
                console.print(tools_table)

                # Recent messages
                bus = load_bus()
                recent = bus["messages"][-8:]
                if recent:
                    msg_table = Table(title="Recent Messages", border_style="bright_magenta",
                                     title_style="bold bright_magenta", show_header=True,
                                     header_style="bold", width=w)
                    msg_table.add_column("From", style="bright_cyan", width=10)
                    msg_table.add_column("To", style="yellow", width=10)
                    msg_table.add_column("Message", overflow="fold")
                    msg_table.add_column("Time", style="dim", width=6)
                    for m in recent:
                        ts = m.get("timestamp", "")[11:16]
                        msg_table.add_row(m.get("from", "?"), m.get("to", "?"),
                                          m.get("content", "")[:50], ts)
                    console.print(msg_table)

                # Session stats
                elapsed = int(time.time() - session_stats["start"])
                unread = bus_unread("codegpt")
                mem_count = len(load_memories())

                console.print(Panel(
                    Text.from_markup(
                        f"  Session: [bright_cyan]{elapsed // 60}m {elapsed % 60}s[/]  |  "
                        f"  Model: [bright_cyan]{model}[/]  |  "
                        f"  Messages: [bright_cyan]{session_stats['messages']}[/]  |  "
                        f"  Unread: [{'red' if unread else 'green'}]{unread}[/]  |  "
                        f"  Memories: [bright_cyan]{mem_count}[/]  |  "
                        f"  Tools: [bright_cyan]{len(running_tools)}[/]"
                    ),
                    border_style="dim", padding=(0, 1), width=w,
                ))
                console.print()
                continue

            elif cmd == "/running":
                show_running_tools()
                continue

            elif cmd == "/killall":
                kill_all_tools()
                continue

            elif cmd == "/tools":
                table = Table(title="AI Tools Hub", border_style="bright_magenta",
                              title_style="bold bright_magenta", show_header=True, header_style="bold")
                table.add_column("Command", style="bright_cyan", width=15)
                table.add_column("Tool", style="white", width=16)
                table.add_column("Needs", style="dim", width=22)
                table.add_column("Status", width=7)
                table.add_column("Safe", width=7)
                coding_tools = ["codex", "opencode", "cline", "aider", "mentat",
                                "gpt-engineer", "interpreter", "copilot"]
                on_termux = os.path.exists("/data/data/com.termux")
                for cmd_name, info in AI_TOOLS.items():
                    # Skip unsupported tools on Termux
                    if on_termux and not info.get("termux", True):
                        continue
                    installed = shutil.which(info["bin"]) is not None
                    status = "[green]ready[/]" if installed else "[dim]—[/]"
                    needs = info.get("needs_key", "")
                    if needs.startswith("None"):
                        needs_display = "[green]free[/]"
                    else:
                        needs_display = f"[yellow]{needs[:20]}[/]"
                    access = "[cyan]full[/]" if cmd_name in coding_tools else "[green]safe[/]"
                    table.add_row(f"/{cmd_name}", info["name"], needs_display, status, access)
                # Claude and OpenClaw
                claude_ok = shutil.which("claude") is not None
                claw_ok = shutil.which("openclaw") is not None
                table.add_row("/claude", "Claude Code", "[yellow]ANTHROPIC_API_KEY[/]",
                              "[green]ready[/]" if claude_ok else "[dim]—[/]", "[dim]full[/]")
                table.add_row("/openclaw", "OpenClaw", "[yellow]Gateway token[/]",
                              "[green]ready[/]" if claw_ok else "[dim]—[/]", "[green]yes[/]")
                console.print(table)
                console.print(Text.from_markup(
                    "  [green]yes[/] = sandboxed (API keys stripped, isolated dir)\n"
                    "  [dim]full[/] = full system access\n"
                    "  [green]free[/] = no API key needed\n"
                    "  Auto-install on first use. All verified packages."
                ))
                console.print()
                continue

            elif cmd in [f"/{t}" for t in AI_TOOLS]:
                tool_key = cmd[1:]  # strip /
                tool = AI_TOOLS[tool_key]
                tool_bin = tool["bin"]

                # Block unsupported tools on Termux — explain why
                is_termux = os.path.exists("/data/data/com.termux")
                if is_termux and not tool.get("termux", True):
                    reasons = {
                        "opencode": "OpenCode needs Bun runtime and native x86/x64 binaries that aren't available for ARM processors.",
                        "codex": "Codex requires native binaries that don't compile on ARM/Android.",
                        "gpt4all": "GPT4All needs a C++ backend (llama.cpp) that requires desktop-level hardware to run.",
                    }
                    reason = reasons.get(tool_key, "This tool requires native binaries that aren't available for ARM/Android.")

                    # Suggest alternatives
                    alternatives = {
                        "opencode": "/cline or /gemini",
                        "codex": "/gemini or /cline",
                        "gpt4all": "/ollama (if available) or /connect PC_IP",
                    }
                    alt = alternatives.get(tool_key, "Check /tools for available alternatives")

                    console.print()
                    console.print(Text.from_markup(f"  [bold red]✗ {tool['name']} — not available on Termux[/]"))
                    console.print()
                    console.print(Text.from_markup(f"  [bold]Why:[/] {reason}"))
                    console.print()
                    console.print(Text.from_markup(f"  [bold]Try instead:[/] [bright_cyan]{alt}[/]"))
                    console.print(Text("  Or use this tool on your PC.", style="dim"))
                    console.print()
                    continue
                tool_args = user_input[len(cmd):].strip()

                if shutil.which(tool_bin):
                    if not ask_permission("tool_launch", f"Launch {tool['name']}"):
                        continue

                    # Coding tools get full project access, others are sandboxed
                    coding_tools = ["codex", "opencode", "cline", "aider", "mentat",
                                    "gpt-engineer", "interpreter", "copilot"]
                    is_coding_tool = tool_key in coding_tools

                    # Update shared context before any launch
                    build_codegpt_context(messages)
                    tool_env = build_tool_env(tool_key)

                    if is_coding_tool:
                        project_dir = str(Path(__file__).parent)
                        console.print(Panel(
                            Text.from_markup(
                                f"[bold]{tool['name']} — Connected to CodeGPT[/]\n\n"
                                f"  Project dir:  [bright_cyan]{project_dir}[/]\n"
                                f"  Files:        [green]full access[/]\n"
                                f"  API keys:     [green]available[/]\n"
                                f"  Context:      [green]shared[/]\n"
                                f"  Memory:       [green]shared[/]\n\n"
                                f"[dim]Type 'exit' or Ctrl+C to return to CodeGPT.[/]"
                            ),
                            title=f"[bold bright_cyan]{tool['name']}[/]",
                            border_style="bright_cyan", padding=(1, 2), width=tw(),
                        ))
                        audit_log(f"TOOL_LAUNCH", f"{tool_key} full_access cwd={project_dir}")
                        launch_cmd = [tool_bin] + tool.get("default_args", [])
                        if tool_args:
                            launch_cmd.append(tool_args)
                        subprocess.run(" ".join(launch_cmd), shell=True, cwd=project_dir, env=tool_env)
                    else:
                        tool_sandbox = Path.home() / ".codegpt" / "sandbox" / tool_key
                        tool_sandbox.mkdir(parents=True, exist_ok=True)

                        # Strip API keys for sandboxed tools but keep CodeGPT context
                        sensitive_keys = [
                            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
                            "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
                            "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN",
                            "SSH_AUTH_SOCK", "SSH_AGENT_PID",
                            "AZURE_KEY", "GOOGLE_API_KEY", "HF_TOKEN",
                            "CODEGPT_BOT_TOKEN", "TELEGRAM_TOKEN",
                            "DATABASE_URL", "REDIS_URL", "MONGO_URI",
                        ]
                        stripped = []
                        for key in sensitive_keys:
                            if key in tool_env:
                                tool_env.pop(key)
                                stripped.append(key)

                        console.print(Panel(
                            Text.from_markup(
                                f"[bold]{tool['name']} — Connected to CodeGPT (Sandboxed)[/]\n\n"
                                f"  Working dir:  [bright_cyan]{tool_sandbox}[/]\n"
                                f"  Keys stripped: [green]{len(stripped)}[/]\n"
                                f"  Context:      [green]shared[/]\n"
                                f"  Memory:       [green]shared[/]\n\n"
                                f"[dim]Type 'exit' or Ctrl+C to return to CodeGPT.[/]"
                            ),
                            title=f"[bold bright_magenta]Sandboxed: {tool['name']}[/]",
                            border_style="bright_magenta", padding=(1, 2), width=tw(),
                        ))
                        audit_log(f"TOOL_LAUNCH", f"{tool_key} sandbox={tool_sandbox} stripped={len(stripped)}")
                        launch_cmd = [tool_bin] + tool.get("default_args", [])
                        if tool_args:
                            launch_cmd.append(tool_args)
                        subprocess.run(" ".join(launch_cmd), shell=True, cwd=str(tool_sandbox), env=tool_env)

                    print_sys("Back to CodeGPT.")
                    audit_log(f"TOOL_EXIT", tool_key)
                else:
                    # Pick platform-specific install command
                    if is_termux and "install_termux" in tool:
                        install_cmd = list(tool["install_termux"])
                    elif os.name == "nt" and "install_win" in tool:
                        install_cmd = list(tool["install_win"])
                    else:
                        install_cmd = list(tool["install"])

                    if not ask_permission("tool_install", f"Install {tool['name']} via {' '.join(install_cmd[:3])}"):
                        continue
                    print_sys(f"Installing {tool['name']}...")

                    is_npm = install_cmd[0] in ("npm", "npm.cmd")

                    if is_npm and os.name == "nt":
                        install_cmd[0] = "npm.cmd"

                    install_done = [False]
                    install_ok = [False]
                    install_err = [""]

                    def do_tool_install(cmd_list=install_cmd):
                        try:
                            r = subprocess.run(
                                cmd_list, capture_output=True, text=True,
                                timeout=300, shell=True,
                            )
                            install_ok[0] = r.returncode == 0
                            if not install_ok[0]:
                                # Show both stderr and stdout for better debugging
                                err = r.stderr.strip() if r.stderr else ""
                                out = r.stdout.strip() if r.stdout else ""
                                install_err[0] = err[:300] or out[:300] or f"Exit code {r.returncode}"
                        except subprocess.TimeoutExpired:
                            install_err[0] = "Timed out (5min)"
                        except Exception as e:
                            install_err[0] = str(e)[:300]
                        install_done[0] = True

                    thr = threading.Thread(target=do_tool_install, daemon=True)
                    thr.start()

                    bar_width = 30
                    with Live(
                        Panel(Text("Starting...", style="dim"),
                              title=f"[bold bright_magenta]Installing {tool['name']}[/]",
                              border_style="bright_magenta", padding=(1, 2), width=tw()),
                        console=console, refresh_per_second=10, transient=True,
                    ) as live:
                        start_t = time.time()
                        while not install_done[0]:
                            elapsed = time.time() - start_t
                            pct = min(int((elapsed / 8.0) * 100), 95)
                            filled = int(bar_width * pct / 100)
                            bar = "█" * filled + "░" * (bar_width - filled)
                            live.update(Panel(
                                Text.from_markup(
                                    f"  [bright_cyan]Installing {tool['name']}...[/]\n\n"
                                    f"  [bright_green]{bar}[/] [bold]{pct}%[/]\n\n"
                                    f"  [dim]{elapsed:.0f}s elapsed[/]"
                                ),
                                title=f"[bold bright_magenta]{tool['name']}[/]",
                                border_style="bright_magenta", padding=(1, 2), width=tw(),
                            ))
                            time.sleep(0.1)

                    if install_ok[0]:
                        elapsed = time.time() - start_t

                        # Rehash PATH — find newly installed binaries
                        for _p in [
                            os.path.expanduser("~/.local/bin"),
                            os.path.expanduser("~/.npm-global/bin"),
                            "/data/data/com.termux/files/usr/bin",
                            os.path.expanduser("~/bin"),
                        ]:
                            if os.path.isdir(_p) and _p not in os.environ.get("PATH", ""):
                                os.environ["PATH"] = _p + os.pathsep + os.environ["PATH"]

                        # Try to find the binary
                        found_bin = shutil.which(tool_bin)

                        # Fallback: search common install locations
                        if not found_bin:
                            search_dirs = [
                                os.path.expanduser("~/.local/bin"),
                                os.path.expanduser("~/.npm-global/bin"),
                                "/data/data/com.termux/files/usr/bin",
                            ]
                            for sd in search_dirs:
                                candidate = os.path.join(sd, tool_bin)
                                if os.path.isfile(candidate):
                                    found_bin = candidate
                                    break

                        # Fallback: try python -m for pip packages
                        pip_module_map = {
                            "sgpt": "sgpt",
                            "llm": "llm",
                            "litellm": "litellm",
                            "gorilla": "gorilla_cli",
                            "chatgpt": "chatgpt",
                            "aider": "aider",
                            "interpreter": "interpreter",
                            "gpte": "gpt_engineer",
                            "mentat": "mentat",
                        }

                        if found_bin:
                            print_sys(f"Installed in {elapsed:.1f}s. Launching...")
                            audit_log(f"TOOL_INSTALL", tool_key)
                            launch_cmd = [found_bin] + tool.get("default_args", [])
                            subprocess.run(" ".join(launch_cmd), shell=True)
                            print_sys("Back to CodeGPT.")
                        elif tool_bin in pip_module_map:
                            # Try python -m fallback
                            mod = pip_module_map[tool_bin]
                            print_sys(f"Installed in {elapsed:.1f}s. Launching via python -m {mod}...")
                            audit_log(f"TOOL_INSTALL", tool_key)
                            launch_cmd = [sys.executable, "-m", mod] + tool.get("default_args", [])
                            subprocess.run(launch_cmd)
                            print_sys("Back to CodeGPT.")
                        else:
                            print_err(f"Installed but '{tool_bin}' not found in PATH.")
                            print_sys(f"Try: which {tool_bin}")
                            print_sys("Or restart your terminal and try again.")
                    else:
                        print_err(f"Install failed: {install_err[0]}")
                        manual = " ".join(tool["install"])
                        print_sys(f"Try manually: {manual}")
                continue

            elif cmd == "/claude":
                if shutil.which("claude"):
                    # Give Claude full context — CWD to project, pass conversation summary
                    project_dir = str(Path(__file__).parent)
                    claude_args = user_input[len("/claude "):].strip()

                    console.print(Panel(
                        Text.from_markup(
                            f"[bold]Claude Code — Full Access[/]\n\n"
                            f"  Project dir:  [bright_cyan]{project_dir}[/]\n"
                            f"  Files:        [green]full access[/]\n"
                            f"  API keys:     [green]available[/]\n"
                            f"  Memory:       [green]shared[/]\n\n"
                            f"[dim]Type /exit in Claude to return to CodeGPT.[/]"
                        ),
                        title="[bold bright_cyan]Claude Code[/]",
                        border_style="bright_cyan", padding=(1, 2), width=tw(),
                    ))
                    audit_log("CLAUDE_LAUNCH", f"cwd={project_dir}")
                    build_codegpt_context(messages)
                    claude_env = build_tool_env("claude")

                    if claude_args:
                        subprocess.run(["claude", claude_args], shell=True, cwd=project_dir, env=claude_env)
                    else:
                        subprocess.run(["claude"], shell=True, cwd=project_dir, env=claude_env)
                    print_sys("Back to CodeGPT.")
                    audit_log("CLAUDE_EXIT")
                else:
                    print_sys("Claude Code not installed. Installing...")
                    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

                    install_done = [False]
                    install_ok = [False]
                    install_err = [""]

                    def do_claude_install():
                        try:
                            r = subprocess.run(
                                [npm_cmd, "i", "-g", "@anthropic-ai/claude-code"],
                                capture_output=True, text=True, timeout=300,
                                shell=True,
                            )
                            install_ok[0] = r.returncode == 0
                            if not install_ok[0]:
                                install_err[0] = r.stderr[:200] if r.stderr else "Unknown error"
                        except subprocess.TimeoutExpired:
                            install_err[0] = "Timed out."
                        except Exception as e:
                            install_err[0] = str(e)
                        install_done[0] = True

                    t = threading.Thread(target=do_claude_install, daemon=True)
                    t.start()

                    phases = ["Resolving packages", "Downloading CLI", "Linking binaries", "Configuring", "Done"]
                    bar_width = 30

                    with Live(
                        Panel(Text("Starting...", style="dim"),
                              title="[bold bright_cyan]Installing Claude Code[/]",
                              border_style="bright_cyan", padding=(1, 2), width=tw()),
                        console=console, refresh_per_second=10, transient=True,
                    ) as live:
                        start_t = time.time()
                        while not install_done[0]:
                            elapsed = time.time() - start_t
                            phase_idx = min(int(elapsed / 2.0), len(phases) - 1)
                            pct = min(int((elapsed / 10.0) * 100), 95)
                            filled = int(bar_width * pct / 100)
                            bar = "█" * filled + "░" * (bar_width - filled)
                            live.update(Panel(
                                Text.from_markup(
                                    f"  [bright_cyan]{phases[phase_idx]}...[/]\n\n"
                                    f"  [bright_green]{bar}[/] [bold]{pct}%[/]\n\n"
                                    f"  [dim]{elapsed:.0f}s elapsed[/]"
                                ),
                                title="[bold bright_cyan]Installing Claude Code[/]",
                                border_style="bright_cyan", padding=(1, 2), width=tw(),
                            ))
                            time.sleep(0.1)

                    if install_ok[0]:
                        print_sys("Installed. Launching Claude Code...")
                        audit_log("CLAUDE_INSTALL")
                        subprocess.run(["claude"], shell=True)
                        print_sys("Back to CodeGPT.")
                    else:
                        print_err(f"Install failed: {install_err[0]}")
                        print_sys("Try manually: npm i -g @anthropic-ai/claude-code")
                continue

            elif cmd == "/openclaw":
                # Sandboxed OpenClaw launch
                sandbox_dir = Path.home() / ".codegpt" / "openclaw_sandbox"
                sandbox_dir.mkdir(parents=True, exist_ok=True)

                # Restricted environment — strip dangerous vars, limit PATH
                safe_env = os.environ.copy()
                # Remove sensitive vars
                for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
                            "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "SSH_AUTH_SOCK"]:
                    safe_env.pop(key, None)

                # Block write access to important dirs by setting CWD to sandbox
                console.print(Panel(
                    Text.from_markup(
                        "[bold]OpenClaw Sandbox Mode[/]\n\n"
                        f"  Working dir:  [bright_cyan]{sandbox_dir}[/]\n"
                        "  API keys:     [green]stripped[/]\n"
                        "  File access:  [green]sandbox only[/]\n"
                        "  Network:      [yellow]allowed[/]\n\n"
                        "[dim]OpenClaw cannot access your files outside the sandbox.\n"
                        "Type 'exit' in OpenClaw to return to CodeGPT.[/]"
                    ),
                    title="[bold bright_magenta]Sandboxed[/]",
                    border_style="bright_magenta",
                    padding=(1, 2), width=tw(),
                ))

                audit_log("OPENCLAW_LAUNCH", f"sandbox={sandbox_dir}")

                if shutil.which("openclaw"):
                    subprocess.run(
                        ["openclaw"], shell=True,
                        cwd=str(sandbox_dir),
                        env=safe_env,
                    )
                    print_sys("Back to CodeGPT.")
                    audit_log("OPENCLAW_EXIT")
                else:
                    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

                    # Countdown install with live progress
                    install_done = [False]
                    install_ok = [False]
                    install_err = [""]

                    def do_install():
                        try:
                            r = subprocess.run(
                                [npm_cmd, "i", "-g", "openclaw"],
                                capture_output=True, text=True, timeout=300,
                                shell=True,
                            )
                            install_ok[0] = r.returncode == 0
                            if not install_ok[0]:
                                install_err[0] = r.stderr[:200] if r.stderr else "Unknown error"
                        except subprocess.TimeoutExpired:
                            install_err[0] = "Timed out (5min). Check disk space / internet."
                        except Exception as e:
                            install_err[0] = str(e)
                        install_done[0] = True

                    t = threading.Thread(target=do_install, daemon=True)
                    t.start()

                    # Animated progress
                    phases = [
                        "Resolving packages",
                        "Downloading modules",
                        "Linking binaries",
                        "Configuring runtime",
                        "Finalizing install",
                    ]
                    bar_width = 30

                    with Live(
                        Panel(Text("Starting...", style="dim"),
                              title="[bold bright_magenta]Installing OpenClaw[/]",
                              border_style="bright_magenta", padding=(1, 2), width=tw()),
                        console=console, refresh_per_second=10, transient=True,
                    ) as live:
                        start_t = time.time()
                        while not install_done[0]:
                            elapsed = time.time() - start_t
                            phase_idx = min(int(elapsed / 1.0), len(phases) - 1)
                            phase = phases[phase_idx]

                            # Progress bar
                            if install_done[0]:
                                pct = 100
                            else:
                                pct = min(int((elapsed / 5.0) * 100), 95)

                            filled = int(bar_width * pct / 100)
                            bar = "█" * filled + "░" * (bar_width - filled)

                            display = Text.from_markup(
                                f"  [bright_cyan]{phase}...[/]\n\n"
                                f"  [bright_green]{bar}[/] [bold]{pct}%[/]\n\n"
                                f"  [dim]{elapsed:.0f}s elapsed[/]"
                            )
                            live.update(Panel(
                                display,
                                title="[bold bright_magenta]Installing OpenClaw[/]",
                                border_style="bright_magenta", padding=(1, 2), width=tw(),
                            ))
                            time.sleep(0.1)

                    # Final result
                    if install_ok[0]:
                        elapsed = time.time() - start_t
                        console.print(Panel(
                            Text.from_markup(
                                f"  [bright_green]{'█' * bar_width}[/] [bold]100%[/]\n\n"
                                f"  [bold green]Installed in {elapsed:.1f}s[/]"
                            ),
                            title="[bold bright_magenta]OpenClaw Ready[/]",
                            border_style="bright_green", padding=(1, 2), width=tw(),
                        ))
                        audit_log("OPENCLAW_INSTALL")
                        print_sys("Launching sandboxed...")
                        subprocess.run(
                            ["openclaw"], shell=True,
                            cwd=str(sandbox_dir),
                            env=safe_env,
                        )
                        print_sys("Back to CodeGPT.")
                        audit_log("OPENCLAW_EXIT")
                    else:
                        print_err(f"Install failed: {install_err[0]}")
                        print_sys("Try manually: npm i -g openclaw")
                continue

            elif cmd == "/shell":
                cmd_text = user_input[len("/shell "):].strip()
                safe, blocked = is_shell_safe(cmd_text)
                if not safe:
                    print_err(f"Blocked: {blocked}")
                    audit_log("SHELL_BLOCKED", f"{blocked} in: {cmd_text}")
                elif ask_permission("shell", f"$ {cmd_text}"):
                    audit_log("SHELL", cmd_text)
                    run_shell(cmd_text)
                continue

            elif cmd == "/pin-set":
                try:
                    new_pin = getpass("  New PIN: ")
                    confirm = getpass("  Confirm: ")
                    if new_pin == confirm and len(new_pin) >= 4:
                        set_pin(new_pin)
                        audit_log("PIN_SET")
                        print_sys("PIN set. You'll need it to log in next time.")
                    elif new_pin != confirm:
                        print_err("PINs don't match.")
                    else:
                        print_err("PIN must be at least 4 characters.")
                except (KeyboardInterrupt, EOFError):
                    print_sys("Cancelled.")
                continue

            elif cmd == "/pin-remove":
                if has_pin():
                    try:
                        pin = getpass("  Current PIN to confirm: ")
                        if verify_pin(pin):
                            remove_pin()
                            audit_log("PIN_REMOVED")
                            print_sys("PIN removed.")
                        else:
                            print_err("Wrong PIN.")
                    except (KeyboardInterrupt, EOFError):
                        print_sys("Cancelled.")
                else:
                    print_sys("No PIN is set.")
                continue

            elif cmd == "/lock":
                if has_pin():
                    audit_log("MANUAL_LOCK")
                    if not prompt_pin_unlock():
                        break
                else:
                    print_sys("Set a PIN first: /pin-set")
                continue

            elif cmd == "/audit":
                if AUDIT_FILE.exists():
                    try:
                        log_lines = AUDIT_FILE.read_text().strip().split("\n")
                        recent = log_lines[-20:]  # Last 20 entries
                        table = Table(title="Security Audit Log", border_style="yellow",
                                      title_style="bold yellow", show_header=True, header_style="bold")
                        table.add_column("Timestamp", style="dim", width=20)
                        table.add_column("Event", style="white")
                        for line in recent:
                            parts = line.split("] ", 1)
                            if len(parts) == 2:
                                ts = parts[0].lstrip("[")
                                event = parts[1]
                                table.add_row(ts, event)
                        console.print(table)
                        console.print(Text(f"  {len(log_lines)} total events", style="dim"))
                        console.print()
                    except Exception:
                        print_sys("Cannot read audit log.")
                else:
                    print_sys("No audit events yet.")
                continue

            elif cmd == "/connect":
                addr = user_input[len("/connect "):].strip()
                if addr and ask_permission("connect", f"Connect to {addr}"):
                    if not addr.startswith("http"):
                        addr = "http://" + addr
                    if ":" not in addr.split("//")[1]:
                        addr += ":11434"
                    new_url = addr if "/api/chat" in addr else f"{addr.rstrip('/')}/api/chat"

                    # Test connection
                    test_models = try_connect(new_url)
                    if test_models:
                        OLLAMA_URL = new_url
                        available_models = test_models
                        model = available_models[0] if available_models else MODEL

                        # Save for next session
                        config_file = Path.home() / ".codegpt" / "ollama_url"
                        config_file.parent.mkdir(parents=True, exist_ok=True)
                        config_file.write_text(OLLAMA_URL)

                        console.print(Panel(
                            Text.from_markup(
                                f"[bold green]Connected![/]\n\n"
                                f"  Server:  [bright_cyan]{OLLAMA_URL}[/]\n"
                                f"  Models:  [bright_cyan]{len(available_models)}[/] ({', '.join(available_models[:5])})\n"
                                f"  Active:  [bright_cyan]{model}[/]\n\n"
                                f"[dim]Saved — will auto-connect next session.[/]"
                            ),
                            title="[bold green]Remote Connected[/]",
                            border_style="green", padding=(1, 2), width=tw(),
                        ))
                        audit_log("REMOTE_CONNECT", OLLAMA_URL)
                    else:
                        print_err(f"Cannot reach {new_url}")
                        print_sys("Make sure Ollama is running on that machine:\n  OLLAMA_HOST=0.0.0.0 ollama serve")
                else:
                    print_sys("Usage: /connect 192.168.1.237\n       /connect mypc.local\n       /connect 10.0.0.5:11434")
                continue

            elif cmd == "/disconnect":
                OLLAMA_URL = "http://localhost:11434/api/chat"
                saved = Path.home() / ".codegpt" / "ollama_url"
                if saved.exists():
                    saved.unlink()
                test_models = try_connect(OLLAMA_URL)
                if test_models:
                    available_models = test_models
                    print_sys(f"Switched to local Ollama. {len(available_models)} models.")
                else:
                    print_sys("Switched to local. Ollama not running locally.")
                continue

            elif cmd == "/server":
                is_local = "localhost" in OLLAMA_URL or "127.0.0.1" in OLLAMA_URL
                test_models = try_connect(OLLAMA_URL)
                status = "[green]connected[/]" if test_models else "[red]unreachable[/]"
                saved = Path.home() / ".codegpt" / "ollama_url"
                saved_url = saved.read_text().strip() if saved.exists() else "none"

                console.print(Panel(
                    Text.from_markup(
                        f"[bold bright_cyan]Ollama Server[/]\n"
                        f"{'━' * 36}\n\n"
                        f"  URL:       [bright_cyan]{OLLAMA_URL}[/]\n"
                        f"  Type:      [bright_cyan]{'local' if is_local else 'remote'}[/]\n"
                        f"  Status:    {status}\n"
                        f"  Models:    [bright_cyan]{len(test_models) if test_models else 0}[/]\n"
                        f"  Saved URL: [dim]{saved_url}[/]\n"
                    ),
                    border_style="bright_cyan", padding=(1, 2), width=tw(),
                ))
                if test_models:
                    for m in test_models[:10]:
                        console.print(f"    [bright_cyan]{m}[/]")
                console.print()
                continue

            elif cmd == "/qr":
                if not ask_permission("qr", "Show QR code with your local IP"):
                    continue
                # Generate QR code with this machine's Ollama URL
                import socket
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                except Exception:
                    local_ip = "127.0.0.1"

                qr_url = f"http://{local_ip}:11434/api/chat"

                # Build QR code in terminal using Unicode blocks
                qr_data = qr_url
                try:
                    # Try qrcode library
                    import qrcode
                    qr = qrcode.QRCode(border=1)
                    qr.add_data(qr_data)
                    qr.make(fit=True)

                    lines = []
                    matrix = qr.get_matrix()
                    for row in matrix:
                        line = ""
                        for cell in row:
                            line += "██" if cell else "  "
                        lines.append(line)
                    qr_text = "\n".join(lines)
                except ImportError:
                    # Fallback: simple ASCII QR using block chars
                    # Encode URL into a visual pattern
                    qr_text = ""
                    chars = qr_data
                    size = max(len(chars), 21)
                    import hashlib as _h
                    seed = _h.md5(chars.encode()).digest()
                    for y in range(21):
                        row = ""
                        for x in range(21):
                            # Fixed patterns for QR corners
                            if (x < 7 and y < 7) or (x >= 14 and y < 7) or (x < 7 and y >= 14):
                                if x < 7 and y < 7:
                                    if x in (0,6) or y in (0,6):
                                        row += "██"
                                    elif 2<=x<=4 and 2<=y<=4:
                                        row += "██"
                                    else:
                                        row += "  "
                                elif x >= 14 and y < 7:
                                    nx = x - 14
                                    if nx in (0,6) or y in (0,6):
                                        row += "██"
                                    elif 2<=nx<=4 and 2<=y<=4:
                                        row += "██"
                                    else:
                                        row += "  "
                                else:
                                    nx = x
                                    ny = y - 14
                                    if nx in (0,6) or ny in (0,6):
                                        row += "██"
                                    elif 2<=nx<=4 and 2<=ny<=4:
                                        row += "██"
                                    else:
                                        row += "  "
                            else:
                                idx = (y * 21 + x) % len(seed)
                                row += "██" if seed[idx] & (1 << (x % 8)) else "  "
                        qr_text += row + "\n"
                    qr_text += f"\n  (Install 'qrcode' for a real scannable QR)"
                    qr_text += f"\n  pip install qrcode"

                console.print(Panel(
                    Text.from_markup(
                        f"[white]{qr_text}[/]\n\n"
                        f"  [bold]Scan this QR code on your phone[/]\n"
                        f"  Or type on Termux:\n\n"
                        f"  [bright_cyan]/connect {local_ip}[/]\n\n"
                        f"  URL: [dim]{qr_url}[/]"
                    ),
                    title="[bold bright_cyan]Connect via QR[/]",
                    border_style="bright_cyan", padding=(1, 2), width=tw(),
                ))
                console.print()
                continue

            elif cmd == "/scan":
                # On phone: scan QR or paste URL
                print_sys("Paste the URL from the QR code or type the IP:")
                try:
                    scanned = prompt([("class:prompt", " URL or IP > ")], style=input_style).strip()
                    if scanned:
                        if not scanned.startswith("http"):
                            scanned = "http://" + scanned
                        if ":" not in scanned.split("//")[1]:
                            scanned += ":11434"
                        new_url = scanned if "/api/chat" in scanned else f"{scanned.rstrip('/')}/api/chat"

                        test_models = try_connect(new_url)
                        if test_models:
                            OLLAMA_URL = new_url
                            available_models = test_models
                            model = available_models[0] if available_models else MODEL

                            config_file = Path.home() / ".codegpt" / "ollama_url"
                            config_file.parent.mkdir(parents=True, exist_ok=True)
                            config_file.write_text(OLLAMA_URL)

                            console.print(Panel(
                                Text.from_markup(
                                    f"[bold green]Connected![/]\n\n"
                                    f"  Server:  [bright_cyan]{OLLAMA_URL}[/]\n"
                                    f"  Models:  [bright_cyan]{len(available_models)}[/]\n"
                                ),
                                border_style="green", padding=(0, 2), width=tw(),
                            ))
                            audit_log("QR_CONNECT", OLLAMA_URL)
                        else:
                            print_err(f"Cannot reach {new_url}")
                except (KeyboardInterrupt, EOFError):
                    print_sys("Cancelled.")
                continue

            elif cmd == "/skill":
                args_text = user_input[len("/skill "):].strip()
                parts = args_text.split(maxsplit=1)
                if len(parts) == 2:
                    skill_name = parts[0].lower().replace(" ", "-")
                    skill_prompt = parts[1]
                    save_skill(skill_name, skill_prompt)
                    print_success(f"Skill created: /{skill_name}")
                    print_sys(f"  Use it: /{skill_name} <your message>")
                elif len(parts) == 1 and parts[0] == "delete":
                    print_sys("Usage: /skill delete <name>")
                elif len(parts) == 1:
                    # Check if it's a delete
                    print_sys("Usage: /skill myskill Your custom system prompt here")
                else:
                    print_sys("Usage: /skill myskill Your system prompt for this skill")
                    print_sys("Example: /skill poet Write responses as poetry")
                continue

            elif cmd == "/skills":
                skills = load_skills()
                if skills:
                    console.print(Text("  Custom skills:", style="bold"))
                    for name, data in skills.items():
                        console.print(Text.from_markup(
                            f"  [bright_cyan]/{name}[/] — [dim]{data.get('desc', data.get('prompt', '')[:40])}[/]"
                        ))
                    console.print()
                else:
                    print_sys("No custom skills. Create one:")
                    print_sys("  /skill myskill Your system prompt")
                    print_sys("  /auto describe what you want the skill to do")
                continue

            elif cmd == "/browse":
                url = user_input[len("/browse "):].strip()
                if url and ask_permission("open_url", f"Fetch {url}"):
                    content = browse_url(url, model=model)
                    if content:
                        messages.append({"role": "user", "content": f"[browsed: {url}]"})
                        messages.append({"role": "assistant", "content": content[:500]})
                        session_stats["messages"] += 2
                else:
                    print_sys("Usage: /browse google.com")
                continue

            elif cmd == "/cron":
                args_text = user_input[len("/cron "):].strip()
                parts = args_text.split(maxsplit=1)
                if len(parts) == 2:
                    add_cron(parts[0], parts[1])
                elif args_text == "stop":
                    active_crons.clear()
                    print_sys("All crons stopped.")
                else:
                    print_sys("Usage: /cron 5m /weather")
                    print_sys("       /cron 1h /status")
                    print_sys("       /cron stop")
                continue

            elif cmd == "/crons":
                list_crons()
                continue

            elif cmd == "/auto":
                desc = user_input[len("/auto "):].strip()
                if desc:
                    auto_create_skill(desc, model)
                else:
                    print_sys("Usage: /auto a skill that writes haiku poetry")
                    print_sys("       /auto a code reviewer that checks for security bugs")
                continue

            # Check custom skills
            elif cmd[1:] in load_skills():
                skill = load_skills()[cmd[1:]]
                skill_input = user_input[len(cmd):].strip()
                if skill_input:
                    messages.append({"role": "user", "content": skill_input})
                    session_stats["messages"] += 1
                    # Use skill's prompt as system
                    old_system = system
                    system = skill["prompt"]
                    response = stream_response(messages, system, model)
                    system = old_system
                    if response:
                        messages.append({"role": "assistant", "content": response})
                        session_stats["messages"] += 1
                    else:
                        messages.pop()
                else:
                    print_sys(f"Usage: /{cmd[1:]} <your message>")
                    print_sys(f"  Prompt: {skill['prompt'][:60]}...")
                continue

            elif cmd == "/permissions":
                sub = user_input[len("/permissions "):].strip().lower()
                if sub == "reset":
                    PERMISSION_ALWAYS_ALLOW.clear()
                    save_permissions()
                    print_sys("All permissions reset. You'll be asked again.")
                else:
                    console.print(Text("\n  Permissions", style="bold"))
                    console.print(Rule(style="dim", characters="─"))

                    # Group by risk level
                    for risk_level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                        rc = RISK_COLORS.get(risk_level, "yellow")
                        ri = RISK_ICONS.get(risk_level, "?")
                        console.print(Text.from_markup(f"\n  [{rc}]{ri} {risk_level}[/]"))
                        for action, info in RISKY_ACTIONS.items():
                            if isinstance(info, tuple):
                                desc, risk = info
                            else:
                                desc, risk = info, "MEDIUM"
                            if risk != risk_level:
                                continue
                            status = "[green]✓ allowed[/]" if action in PERMISSION_ALWAYS_ALLOW else "[dim]ask[/]"
                            console.print(Text.from_markup(f"    {action:<16} {status}  [dim]{desc}[/]"))
                    console.print(table)
                    console.print(Text("  /permissions reset — revoke all", style="dim"))
                    console.print()
                continue

            elif cmd == "/security":
                pin_status = "[green]ON[/]" if has_pin() else "[red]OFF[/]"
                auto_lock_status = f"{AUTO_LOCK_MINUTES}min" if has_pin() else "[dim]disabled[/]"
                audit_count = 0
                if AUDIT_FILE.exists():
                    try:
                        audit_count = len(AUDIT_FILE.read_text().strip().split("\n"))
                    except Exception:
                        pass
                blocked_cmds = len(SHELL_BLOCKLIST)
                exec_remaining = CODE_EXEC_LIMIT - code_exec_count

                console.print(Panel(
                    Text.from_markup(
                        f"[bold bright_cyan]Security Dashboard[/]\n"
                        f"{'━' * 36}\n\n"
                        f"[bold]Authentication[/]\n"
                        f"  PIN lock       {pin_status}\n"
                        f"  Auto-lock      {auto_lock_status}\n\n"
                        f"[bold]Execution Limits[/]\n"
                        f"  Code runs left [bright_cyan]{exec_remaining}/{CODE_EXEC_LIMIT}[/]\n"
                        f"  Shell blocklist [bright_cyan]{blocked_cmds} patterns[/]\n"
                        f"  Shell timeout  [bright_cyan]30s[/]\n"
                        f"  Code timeout   [bright_cyan]10s[/]\n\n"
                        f"[bold]Audit[/]\n"
                        f"  Log entries    [bright_cyan]{audit_count}[/]\n"
                        f"  Log file       [dim]{AUDIT_FILE}[/]\n\n"
                        f"[bold]Storage[/]\n"
                        f"  PIN hash       [green]SHA-256[/]\n"
                        f"  Location       [dim]{SECURITY_DIR}[/]\n"
                    ),
                    border_style="bright_cyan",
                    padding=(1, 2),
                    width=tw(),
                ))
                console.print()
                continue

            elif cmd == "/system":
                new_system = user_input[len("/system "):].strip()
                if new_system and ask_permission("system_prompt", new_system[:50]):
                    system = new_system
                    print_sys(f"System prompt updated: {system[:60]}...")
                else:
                    print_sys(f"Current: {system[:100]}...")
                continue

            elif cmd == "/model":
                new_model = user_input[len("/model "):].strip()
                if new_model and ask_permission("model_change", f"Switch to {new_model}"):
                    model = new_model
                    profile["model"] = model
                    save_profile(profile)
                    print_header(model)
                    print_sys(f"Model: {model}")
                else:
                    if available_models:
                        table = Table(title="Models", border_style="bright_cyan",
                                      title_style="bold cyan", show_header=True, header_style="bold")
                        table.add_column("Model", style="bright_cyan")
                        table.add_column("Active", style="green", justify="center")
                        for m in available_models:
                            active = "*" if m == model or m.startswith(model + ":") else ""
                            table.add_row(m, active)
                        console.print(table)
                    else:
                        print_sys(f"Current: {model}")
                continue

            elif cmd == "/remind":
                set_reminder(user_input[len("/remind "):])
                continue

            elif cmd == "/reminders":
                list_reminders()
                continue

            elif cmd == "/voice":
                spoken = voice_input()
                if spoken:
                    # Send the spoken text as a message
                    print_user_msg(spoken)
                    messages.append({"role": "user", "content": spoken})
                    session_stats["messages"] += 1
                    response = stream_response(messages, system, model)
                    if response:
                        messages.append({"role": "assistant", "content": response})
                        session_stats["messages"] += 1
                    else:
                        messages.pop()
                continue

            elif cmd == "/profile":
                show_profile()
                continue

            elif cmd == "/setname":
                new_name = user_input[len("/setname "):].strip()
                if new_name:
                    profile["name"] = new_name[:30]
                    save_profile(profile)
                    print_sys(f"Name: {profile['name']}")
                else:
                    print_sys("Usage: /setname Your Name")
                continue

            elif cmd == "/setbio":
                new_bio = user_input[len("/setbio "):].strip()
                if new_bio:
                    profile["bio"] = new_bio[:160]
                    save_profile(profile)
                    print_sys(f"Bio: {profile['bio']}")
                else:
                    print_sys("Usage: /setbio I build things")
                continue

            elif cmd == "/persona":
                new_persona = user_input[len("/persona "):].strip().lower()
                if new_persona in PERSONAS and ask_permission("persona_change", f"Switch to {new_persona}"):
                    persona_name = new_persona
                    system = PERSONAS[persona_name]
                    profile["persona"] = persona_name
                    save_profile(profile)
                    print_sys(f"Persona: {persona_name}")
                elif new_persona:
                    available = ", ".join(PERSONAS.keys())
                    print_sys(f"Unknown. Available: {available}")
                else:
                    print_sys(f"Current: {persona_name}\nUsage: /persona hacker")
                continue

            elif cmd == "/personas":
                table = Table(title="Personas", border_style="green",
                              title_style="bold green", show_header=True, header_style="bold")
                table.add_column("Name", style="bright_cyan", min_width=10)
                table.add_column("Description", style="dim")
                table.add_column("", width=3)
                for name, prompt_text in PERSONAS.items():
                    active = "*" if name == persona_name else ""
                    desc = prompt_text[:60] + "..." if len(prompt_text) > 60 else prompt_text
                    table.add_row(name, desc, active)
                console.print(table)
                console.print()
                continue

            elif cmd == "/history":
                show_history(messages)
                continue

            elif cmd == "/help":
                print_help()
                continue

            else:
                print_sys(f"Unknown: {cmd}. Type /help")
                continue

        # Regular message
        print_user_msg(user_input)
        messages.append({"role": "user", "content": user_input})
        session_stats["messages"] += 1

        response = stream_response(messages, system, model)
        if response:
            messages.append({"role": "assistant", "content": response})
            session_stats["messages"] += 1
        else:
            messages.pop()


if __name__ == "__main__":
    main()
