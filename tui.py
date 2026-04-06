"""CodeGPT TUI — Terminal UI that looks like the desktop app. Works on Termux."""
import json
import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.markdown import Markdown
from rich.rule import Rule
from rich.align import Align
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style as PtStyle

# Config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = "llama3.2"
SYSTEM = "You are a helpful AI assistant. Be concise and technical."

PERSONAS = {
    "default": "You are a helpful AI assistant. Be concise and technical.",
    "hacker": "You are a cybersecurity expert. Technical jargon, dark humor. Defensive only.",
    "teacher": "You are a patient teacher. Step by step, analogies, examples.",
    "roast": "You are a sarcastic code reviewer. Roast bad code but give the fix.",
    "architect": "You are a system architect. Scalability, ASCII diagrams, trade-offs.",
    "minimal": "Shortest answer possible. Code only. No commentary.",
}

def _try(url):
    try:
        r = requests.get(url.replace("/api/chat", "/api/tags"), timeout=2)
        return r.status_code == 200
    except:
        return False

# Auto-connect — try saved URL, localhost, common LAN IPs
_connected = False

# 1. Saved URL
saved_url = Path.home() / ".codegpt" / "ollama_url"
if saved_url.exists():
    url = saved_url.read_text().strip()
    if url:
        if "/api/chat" not in url:
            url = url.rstrip("/") + "/api/chat"
        if _try(url):
            OLLAMA_URL = url
            _connected = True

# 2. Localhost
if not _connected and _try(OLLAMA_URL):
    _connected = True

# 3. Common LAN IPs — scan for Ollama on the network
if not _connected:
    for ip in ["192.168.1.237", "192.168.1.1", "192.168.0.1", "10.0.2.2",
               "192.168.1.100", "192.168.1.50", "192.168.0.100", "192.168.0.50"]:
        test = f"http://{ip}:11434/api/chat"
        if _try(test):
            OLLAMA_URL = test
            # Save for next time
            Path.home().joinpath(".codegpt").mkdir(parents=True, exist_ok=True)
            Path.home().joinpath(".codegpt", "ollama_url").write_text(OLLAMA_URL)
            _connected = True
            break

# 4. Quick subnet scan (192.168.1.x)
if not _connected:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
        s.close()
        subnet = ".".join(my_ip.split(".")[:3])
        for last in range(1, 20):  # Scan .1 to .19
            test = f"http://{subnet}.{last}:11434/api/chat"
            if _try(test):
                OLLAMA_URL = test
                Path.home().joinpath(".codegpt").mkdir(parents=True, exist_ok=True)
                Path.home().joinpath(".codegpt", "ollama_url").write_text(OLLAMA_URL)
                _connected = True
                break
    except:
        pass

# Load profile
profile_file = Path.home() / ".codegpt" / "profiles" / "cli_profile.json"
USERNAME = "User"
if profile_file.exists():
    try:
        p = json.loads(profile_file.read_text())
        USERNAME = p.get("name", "User")
        MODEL = p.get("model", MODEL)
    except:
        pass

OLLAMA_BASE = OLLAMA_URL.replace("/api/chat", "")

console = Console()

TUI_COMMANDS = {
    "/help": "Show all commands",
    "/new": "New conversation",
    "/model": "Switch model",
    "/models": "List all models",
    "/persona": "Switch persona",
    "/think": "Toggle deep thinking",
    "/tokens": "Token count",
    "/clear": "Clear screen",
    "/sidebar": "Toggle sidebar",
    "/history": "Show history",
    "/connect": "Connect to remote Ollama",
    "/server": "Server info",
    "/weather": "Get weather",
    "/agent": "Run an AI agent",
    "/quit": "Exit",
}


class TuiCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith("/"):
            typed = text.lower()
            for cmd, desc in TUI_COMMANDS.items():
                if cmd.startswith(typed):
                    yield Completion(cmd, start_position=-len(text), display=cmd, display_meta=desc)

cmd_completer = TuiCompleter()
history = InMemoryHistory()
style = PtStyle.from_dict({
    "prompt": "ansicyan bold",
    "bottom-toolbar": "bg:#1a1a2e #888888",
})

messages = []
total_tokens = 0
persona = "default"
system = SYSTEM
show_sidebar = True


def try_connect():
    try:
        r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except:
        return []


def get_models():
    try:
        r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except:
        return []


def render_header():
    """Render the top bar."""
    w = min(console.width, 100)
    models = try_connect()
    status = "[green]online[/]" if models else "[red]offline[/]"

    console.print(Text.from_markup(
        f"  [bold red]Code[/][bold bright_blue]GPT[/] [dim]TUI v2.0[/]"
        f"    {status}"
        f"  [dim]·[/]  [bright_blue]{MODEL}[/]"
        f"  [dim]·[/]  [dim]{persona}[/]"
        f"  [dim]·[/]  [dim]{total_tokens} tok[/]"
    ))
    console.print(Rule(style="dim", characters="─"))


def render_sidebar():
    """Build sidebar content."""
    lines = []
    lines.append(f"[bold]{USERNAME}[/]")
    lines.append(f"[dim]{'─' * 20}[/]")
    lines.append("")
    lines.append(f"[dim]model[/]   [bright_blue]{MODEL}[/]")
    lines.append(f"[dim]persona[/] [green]{persona}[/]")
    lines.append(f"[dim]msgs[/]    {len(messages)}")
    lines.append(f"[dim]tokens[/]  {total_tokens}")
    lines.append("")
    lines.append("[bold]Commands[/]")
    lines.append("[dim]/model[/]   switch")
    lines.append("[dim]/persona[/] change")
    lines.append("[dim]/new[/]     clear")
    lines.append("[dim]/think[/]   reason")
    lines.append("[dim]/help[/]    all cmds")
    lines.append("[dim]/sidebar[/] toggle")
    lines.append("[dim]/quit[/]    exit")
    return "\n".join(lines)


def print_msg(role, content, stats=""):
    """Print a message."""
    if role == "user":
        console.print(Text(f"  {content}", style="bold white"))
    else:
        console.print(Rule(style="green", characters="─"))
        console.print(Markdown(content), width=min(console.width - 4, 90))
        if stats:
            console.print(Text(f"  {stats}", style="dim"))
    console.print()


def chat(text):
    """Send a message and get a response."""
    global total_tokens
    messages.append({"role": "user", "content": text})

    console.print(Text("  Thinking...", style="dim"))

    try:
        start = time.time()
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
        }, timeout=120)
        data = resp.json()
        content = data.get("message", {}).get("content", "No response.")
        elapsed = round(time.time() - start, 1)
        tokens = data.get("eval_count", 0)
        total_tokens += tokens
        messages.append({"role": "assistant", "content": content})

        # Clear "Thinking..."
        console.print("\033[A\033[K", end="")
        print_msg("ai", content, f"{tokens} tok · {elapsed}s")

    except Exception as e:
        console.print("\033[A\033[K", end="")
        print_msg("ai", f"Error: {e}")


def handle_command(text):
    """Handle slash commands. Returns True if handled."""
    global MODEL, persona, system, show_sidebar, messages, total_tokens

    cmd = text.split()[0].lower()
    args = text[len(cmd):].strip()

    if cmd == "/quit" or cmd == "/q":
        return "quit"

    elif cmd == "/new" or cmd == "/n":
        messages = []
        os.system("clear")
        render_header()
        console.print(Text("  New conversation.", style="dim"))
        console.print()

    elif cmd == "/model" or cmd == "/m":
        if args:
            MODEL = args
            console.print(Text(f"  Model: {MODEL}", style="green"))
        else:
            models = get_models()
            if models:
                for m in models:
                    mark = " *" if m == MODEL else ""
                    console.print(Text(f"  {m}{mark}", style="bright_blue" if mark else "dim"))
            else:
                console.print(Text("  Ollama offline.", style="red"))
        console.print()

    elif cmd == "/persona" or cmd == "/p":
        if args and args in PERSONAS:
            persona = args
            system = PERSONAS[args]
            console.print(Text(f"  Persona: {persona}", style="green"))
        else:
            for name in PERSONAS:
                mark = " *" if name == persona else ""
                console.print(Text(f"  {name}{mark}", style="green" if mark else "dim"))
        console.print()

    elif cmd == "/think" or cmd == "/t":
        if "step-by-step" in system:
            system = PERSONAS.get(persona, SYSTEM)
            console.print(Text("  Think mode: OFF", style="dim"))
        else:
            system += "\n\nThink step-by-step. Show your reasoning."
            console.print(Text("  Think mode: ON", style="green"))
        console.print()

    elif cmd == "/sidebar":
        show_sidebar = not show_sidebar
        console.print(Text(f"  Sidebar: {'on' if show_sidebar else 'off'}", style="dim"))
        console.print()

    elif cmd == "/tokens":
        console.print(Text(f"  Session: {total_tokens} tokens, {len(messages)} messages", style="dim"))
        console.print()

    elif cmd == "/clear":
        os.system("clear")
        render_header()

    elif cmd == "/history":
        if messages:
            for m in messages[-10:]:
                role = "You" if m["role"] == "user" else "AI"
                console.print(Text(f"  [{role}] {m['content'][:80]}", style="dim"))
        else:
            console.print(Text("  No messages.", style="dim"))
        console.print()

    elif cmd == "/connect":
        global OLLAMA_URL, OLLAMA_BASE
        if args:
            url = args if args.startswith("http") else "http://" + args
            if ":" not in url.split("//")[1]:
                url += ":11434"
            OLLAMA_URL = url.rstrip("/") + "/api/chat"
            OLLAMA_BASE = OLLAMA_URL.replace("/api/chat", "")
            models = try_connect()
            if models:
                console.print(Text(f"  Connected: {OLLAMA_BASE} ({len(models)} models)", style="green"))
                Path.home().joinpath(".codegpt", "ollama_url").write_text(OLLAMA_URL)
            else:
                console.print(Text(f"  Cannot reach {url}", style="red"))
        else:
            console.print(Text("  Usage: /connect 192.168.1.100", style="dim"))
        console.print()

    elif cmd == "/server":
        models = try_connect()
        status = "online" if models else "offline"
        console.print(Text(f"  Server: {OLLAMA_BASE} ({status})", style="green" if models else "red"))
        console.print()

    elif cmd == "/weather":
        city = args or "London"
        try:
            r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            d = r.json()["current_condition"][0]
            console.print(Text(f"  {city}: {d['weatherDesc'][0]['value']}, {d['temp_C']}C, {d['humidity']}% humidity", style="white"))
        except:
            console.print(Text(f"  Cannot get weather for {city}", style="red"))
        console.print()

    elif cmd == "/agent":
        parts = args.split(maxsplit=1)
        if len(parts) >= 2:
            agents = {
                "coder": "You are an expert programmer. Write clean, working code.",
                "debugger": "You are a debugging expert. Find and fix bugs.",
                "reviewer": "You are a code reviewer. Check for bugs, security, performance.",
                "architect": "You are a system architect. Design with ASCII diagrams.",
                "pentester": "You are an ethical pentester. Find vulnerabilities.",
                "explainer": "You are a teacher. Explain simply with analogies.",
                "optimizer": "You are a performance engineer. Optimize code.",
                "researcher": "You are a research analyst. Deep-dive into topics.",
            }
            name, task = parts
            if name in agents:
                console.print(Text(f"  Running {name} agent...", style="dim"))
                try:
                    resp = requests.post(OLLAMA_URL, json={
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": agents[name]},
                            {"role": "user", "content": task},
                        ], "stream": False,
                    }, timeout=90)
                    content = resp.json().get("message", {}).get("content", "")
                    print_msg("ai", f"**{name}:** {content}")
                except Exception as e:
                    console.print(Text(f"  Error: {e}", style="red"))
            else:
                console.print(Text(f"  Agents: {', '.join(agents.keys())}", style="dim"))
        else:
            console.print(Text("  Usage: /agent coder build a flask API", style="dim"))
        console.print()

    elif cmd == "/help" or cmd == "/h":
        cmds = {
            "/new": "New chat", "/model": "Switch model", "/persona": "Switch persona",
            "/think": "Toggle reasoning", "/tokens": "Token count", "/clear": "Clear screen",
            "/sidebar": "Toggle sidebar", "/history": "Show history", "/connect": "Remote Ollama",
            "/server": "Server info", "/weather": "Get weather", "/agent": "Run agent",
            "/help": "This list", "/quit": "Exit",
        }
        for c, d in cmds.items():
            console.print(Text.from_markup(f"    [bright_blue]{c:<12}[/] [dim]{d}[/]"))
        console.print()

    else:
        return None  # Not a command

    return True


def toolbar():
    return [("class:bottom-toolbar",
             f" {len(messages)} msgs · {total_tokens} tok · {MODEL} · {persona} · type / for commands ")]


def main():
    os.system("clear")

    # Welcome
    console.print()
    console.print(Text.from_markup(
        "[bold red]  ╔══════════════════════════════════╗[/]\n"
        "[bold red]  ║[/]  [bold red]Code[/][bold bright_blue]GPT[/] [dim]TUI v2.0[/]            [bold red]║[/]\n"
        "[bold red]  ║[/]  [dim]terminal ui · works everywhere[/]  [bold red]║[/]\n"
        "[bold red]  ╚══════════════════════════════════╝[/]"
    ))
    console.print()

    models = try_connect()
    if models:
        console.print(Text.from_markup(f"  [green]connected[/] · {len(models)} models · [bright_blue]{MODEL}[/]"))
    else:
        console.print(Text.from_markup("  [yellow]offline[/] · use [bright_blue]/connect IP[/] to link"))

    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    console.print(Text(f"\n  {greeting}, {USERNAME}.", style="bold"))
    console.print(Text("  Type a message to chat. Type / for commands.\n", style="dim"))

    while True:
        try:
            user_input = prompt(
                [("class:prompt", " ❯ ")],
                style=style,
                history=history,
                completer=cmd_completer,
                complete_while_typing=True,
                bottom_toolbar=toolbar,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            result = handle_command(user_input)
            if result == "quit":
                break
            elif result is None:
                # Unknown command — treat as chat
                print_msg("user", user_input)
                chat(user_input)
            continue

        print_msg("user", user_input)
        chat(user_input)

    console.print(Text(f"\n  {total_tokens} tokens · {len(messages)} messages\n", style="dim"))


if __name__ == "__main__":
    main()
