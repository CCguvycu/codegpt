"""System diagnostics — `ai doctor`."""
import shutil
import subprocess
import sys
from pathlib import Path


def run_doctor():
    """Check system dependencies and configuration."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="CodeGPT Doctor", border_style="bright_cyan",
                  title_style="bold cyan", show_header=True, header_style="bold")
    table.add_column("Check", style="white", width=24)
    table.add_column("Status", width=8)
    table.add_column("Details", style="dim")

    checks = []

    # Python
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python", True, py_ver))

    # Ollama
    ollama_ok = shutil.which("ollama") is not None
    if ollama_ok:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            model_count = len(r.stdout.strip().splitlines()) - 1
            checks.append(("Ollama", True, f"{model_count} models"))
        except Exception:
            checks.append(("Ollama", True, "installed, not running"))
    else:
        checks.append(("Ollama", False, "not installed — ollama.com"))

    # Ollama connectivity
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        models = [m["name"] for m in r.json().get("models", [])]
        checks.append(("Ollama API", True, f"{len(models)} models loaded"))
    except Exception:
        checks.append(("Ollama API", False, "not reachable — run: ollama serve"))

    # Data dir
    data_dir = Path.home() / ".codegpt"
    checks.append(("Data directory", data_dir.exists(), str(data_dir)))

    # Profile
    profile = data_dir / "profiles" / "cli_profile.json"
    checks.append(("Profile", profile.exists(), "configured" if profile.exists() else "run ai to setup"))

    # Memory
    mem = data_dir / "memory" / "memories.json"
    if mem.exists():
        import json
        try:
            count = len(json.loads(mem.read_text()))
            checks.append(("Memory", True, f"{count} entries"))
        except Exception:
            checks.append(("Memory", True, "exists"))
    else:
        checks.append(("Memory", True, "empty (normal)"))

    # Security
    pin = data_dir / "security" / "pin.hash"
    checks.append(("PIN lock", pin.exists(), "enabled" if pin.exists() else "disabled"))

    # External tools
    for name, bin_name in [("Claude Code", "claude"), ("GitHub CLI", "gh"),
                            ("Node.js", "node"), ("npm", "npm")]:
        ok = shutil.which(bin_name) is not None
        checks.append((name, ok, "found" if ok else "not found"))

    # Render
    for name, ok, detail in checks:
        status = "[green]OK[/]" if ok else "[red]FAIL[/]"
        table.add_row(name, status, detail)

    console.print(table)
    console.print()

    fails = sum(1 for _, ok, _ in checks if not ok)
    if fails == 0:
        console.print("[bold green]All checks passed.[/]")
    else:
        console.print(f"[yellow]{fails} issue(s) found.[/]")
