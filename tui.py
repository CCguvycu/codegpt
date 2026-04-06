"""CodeGPT TUI — Terminal UI that looks like the desktop app. Works on Termux."""
import json
import os
import sys
import time
import subprocess
import threading
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
    "/temp": "Set temperature (0-2)",
    "/system": "Set system prompt",
    "/export": "Export chat as text",
    "/browse": "Fetch and summarize URL",
    "/open": "Open URL in browser",
    "/save": "Save conversation",
    "/copy": "Copy last response",
    "/regen": "Regenerate last response",
    "/compact": "Summarize old messages",
    "/search": "Search conversation",
    "/diff": "Compare last 2 responses",
    "/pin": "Pin a message",
    "/pins": "Show pinned messages",
    "/fork": "Fork conversation from #",
    "/rate": "Rate last response (good/bad)",
    "/all": "Ask ALL agents at once",
    "/vote": "Agents vote on a question",
    "/swarm": "6-agent pipeline",
    "/team": "Group chat with 2 AIs",
    "/room": "Chat room with 3+ AIs",
    "/spectate": "Watch AIs debate",
    "/dm": "Message a specific agent",
    "/race": "Race all models",
    "/compare": "Compare 2 models",
    "/chain": "Chain prompts (p1 | p2 | p3)",
    "/lab": "AI Lab experiments",
    "/train": "AI Training Lab",
    "/mem": "AI memory (save/recall)",
    "/skill": "Create custom command",
    "/skills": "List custom skills",
    "/auto": "AI creates a skill",
    "/cron": "Schedule recurring task",
    "/tools": "List AI tool integrations",
    "/github": "GitHub tools",
    "/spotify": "Spotify controls",
    "/volume": "System volume",
    "/sysinfo": "System info",
    "/usage": "Usage dashboard",
    "/profile": "View profile",
    "/setname": "Set display name",
    "/setbio": "Set bio",
    "/security": "Security dashboard",
    "/permissions": "View permissions",
    "/audit": "Security audit log",
    "/pin-set": "Set login PIN",
    "/lock": "Lock session",
    "/qr": "QR code to connect",
    "/broadcast": "Message all tools",
    "/inbox": "Check messages",
    "/feed": "Message feed",
    "/monitor": "Live dashboard",
    "/hub": "Command center",
    "/shortcuts": "Keyboard shortcuts",
    "/prompts": "Prompt templates",
    "/desktop": "Desktop app (PC only)",
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

    elif cmd == "/temp":
        if args:
            try:
                t = float(args)
                if 0 <= t <= 2:
                    console.print(Text(f"  Temperature: {t}", style="green"))
            except:
                console.print(Text("  Usage: /temp 0.7 (0.0-2.0)", style="dim"))
        else:
            console.print(Text("  Usage: /temp 0.7", style="dim"))
        console.print()

    elif cmd == "/system":
        if args:
            system = args
            console.print(Text("  System prompt updated.", style="green"))
        else:
            console.print(Text(f"  Current: {system[:80]}...", style="dim"))
        console.print()

    elif cmd == "/export":
        if messages:
            lines = []
            for m in messages:
                role = "You" if m["role"] == "user" else "AI"
                lines.append(f"{role}: {m['content']}\n")
            export_path = Path.home() / ".codegpt" / f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text("\n".join(lines), encoding="utf-8")
            console.print(Text(f"  Exported: {export_path}", style="green"))
        else:
            console.print(Text("  Nothing to export.", style="dim"))
        console.print()

    elif cmd == "/browse":
        if args:
            url = args if args.startswith("http") else "https://" + args
            console.print(Text(f"  Fetching {url}...", style="dim"))
            try:
                import re as _re
                r = requests.get(url, timeout=15, headers={"User-Agent": "CodeGPT/2.0"})
                text = _re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=_re.DOTALL)
                text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
                text = _re.sub(r'<[^>]+>', ' ', text)
                text = _re.sub(r'\s+', ' ', text).strip()[:3000]
                resp = requests.post(OLLAMA_URL, json={
                    "model": MODEL, "messages": [
                        {"role": "system", "content": "Summarize in 3-5 bullet points."},
                        {"role": "user", "content": text},
                    ], "stream": False,
                }, timeout=60)
                summary = resp.json().get("message", {}).get("content", text[:500])
                print_msg("ai", summary)
            except Exception as e:
                console.print(Text(f"  Error: {e}", style="red"))
        else:
            console.print(Text("  Usage: /browse github.com", style="dim"))
        console.print()

    elif cmd == "/open":
        if args:
            url = args if args.startswith("http") else "https://" + args
            if os.path.exists("/data/data/com.termux"):
                try:
                    subprocess.run(["termux-open-url", url], timeout=5)
                except:
                    subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", url], timeout=5)
            else:
                import webbrowser
                webbrowser.open(url)
            console.print(Text(f"  Opened: {url}", style="green"))
        else:
            console.print(Text("  Usage: /open google.com", style="dim"))
        console.print()

    elif cmd == "/all":
        if args:
            agents_list = {
                "coder": "You are an expert programmer.",
                "debugger": "You are a debugging expert.",
                "reviewer": "You are a code reviewer.",
                "architect": "You are a system architect.",
                "pentester": "You are an ethical pentester.",
                "explainer": "You are a patient teacher.",
                "optimizer": "You are a performance engineer.",
                "researcher": "You are a research analyst.",
            }
            import threading
            results = {}
            def _query(n, s):
                try:
                    r = requests.post(OLLAMA_URL, json={"model": MODEL, "messages": [
                        {"role": "system", "content": s}, {"role": "user", "content": args}
                    ], "stream": False}, timeout=90)
                    results[n] = r.json().get("message", {}).get("content", "")
                except:
                    results[n] = "(error)"
            threads = [threading.Thread(target=_query, args=(n, s), daemon=True) for n, s in agents_list.items()]
            for t in threads: t.start()
            console.print(Text("  Asking all 8 agents...", style="dim"))
            for t in threads: t.join(timeout=90)
            for name, resp in results.items():
                console.print(Text.from_markup(f"\n  [bright_blue]{name}[/]"))
                console.print(Text(f"  {resp[:200]}", style="white"))
            console.print()
        else:
            console.print(Text("  Usage: /all what database should I use?", style="dim"))
        console.print()

    elif cmd == "/save":
        if messages:
            save_path = Path.home() / ".codegpt" / "chats" / f"{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps({"messages": messages, "model": MODEL}))
            console.print(Text(f"  Saved: {save_path.name}", style="green"))
        else:
            console.print(Text("  Nothing to save.", style="dim"))
        console.print()

    elif cmd == "/copy":
        ai_msgs = [m for m in messages if m["role"] == "assistant"]
        if ai_msgs:
            last = ai_msgs[-1]["content"]
            try:
                import subprocess
                if os.path.exists("/data/data/com.termux"):
                    subprocess.run(["termux-clipboard-set"], input=last.encode(), timeout=5)
                else:
                    subprocess.run("clip" if os.name == "nt" else "pbcopy", input=last.encode(), shell=True, timeout=5)
                console.print(Text("  Copied to clipboard.", style="green"))
            except:
                console.print(Text("  Cannot copy — clipboard not available.", style="red"))
        else:
            console.print(Text("  No response to copy.", style="dim"))
        console.print()

    elif cmd == "/regen":
        if messages and messages[-1]["role"] == "assistant":
            messages.pop()
            if messages and messages[-1]["role"] == "user":
                last_q = messages[-1]["content"]
                messages.pop()
                print_msg("user", last_q)
                chat(last_q)
        else:
            console.print(Text("  Nothing to regenerate.", style="dim"))
            console.print()

    elif cmd == "/rate":
        rating = args.lower() if args else ""
        if rating in ("good", "bad", "+", "-"):
            ai_msgs = [m for m in messages if m["role"] == "assistant"]
            if ai_msgs:
                ratings_file = Path.home() / ".codegpt" / "ratings.json"
                ratings = []
                if ratings_file.exists():
                    try: ratings = json.loads(ratings_file.read_text())
                    except: pass
                ratings.append({"rating": "good" if rating in ("good", "+") else "bad",
                                "response": ai_msgs[-1]["content"][:200],
                                "timestamp": datetime.now().isoformat()})
                ratings_file.write_text(json.dumps(ratings))
                console.print(Text(f"  Rated: {rating}", style="green"))
        else:
            console.print(Text("  Usage: /rate good  or  /rate bad", style="dim"))
        console.print()

    elif cmd == "/usage":
        profile = {}
        if profile_file.exists():
            try: profile = json.loads(profile_file.read_text())
            except: pass
        console.print(Text.from_markup(
            f"  [bold]Session[/]\n"
            f"    Messages    [bright_blue]{len(messages)}[/]\n"
            f"    Tokens      [bright_blue]{total_tokens}[/]\n"
            f"    Model       [bright_blue]{MODEL}[/]\n"
            f"    Persona     [bright_blue]{persona}[/]\n\n"
            f"  [bold]Lifetime[/]\n"
            f"    Messages    [bright_blue]{profile.get('total_messages', 0)}[/]\n"
            f"    Sessions    [bright_blue]{profile.get('total_sessions', 0)}[/]"
        ))
        console.print()

    elif cmd == "/profile":
        profile = {}
        if profile_file.exists():
            try: profile = json.loads(profile_file.read_text())
            except: pass
        console.print(Text.from_markup(
            f"  [bold]{profile.get('name', 'User')}[/]\n"
            f"    Bio       {profile.get('bio', '')}\n"
            f"    Model     [bright_blue]{profile.get('model', MODEL)}[/]\n"
            f"    Persona   [green]{profile.get('persona', 'default')}[/]\n"
            f"    Sessions  {profile.get('total_sessions', 0)}"
        ))
        console.print()

    elif cmd == "/help" or cmd == "/h":
        groups = {
            "Chat": ["/new", "/save", "/copy", "/regen", "/history", "/clear", "/export", "/quit"],
            "Model": ["/model", "/models", "/persona", "/think", "/temp", "/tokens", "/system"],
            "AI": ["/agent", "/all", "/vote", "/swarm", "/team", "/room", "/spectate", "/race"],
            "Files": ["/browse", "/open"],
            "Memory": ["/mem", "/train", "/rate", "/search", "/fork", "/pin"],
            "Tools": ["/tools", "/skill", "/auto", "/cron"],
            "Connect": ["/connect", "/server", "/qr", "/weather", "/sysinfo", "/github"],
            "Profile": ["/profile", "/usage", "/setname", "/setbio", "/permissions"],
            "Security": ["/pin-set", "/lock", "/audit", "/security"],
        }
        for group, cmds_list in groups.items():
            console.print(Text(f"\n  {group}", style="bold bright_blue"))
            for c in cmds_list:
                desc = TUI_COMMANDS.get(c, "")
                if desc:
                    console.print(Text.from_markup(f"    [bright_blue]{c:<14}[/] [dim]{desc}[/]"))
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
