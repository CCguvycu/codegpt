"""Self-updating system — checks GitHub Releases for new versions."""
import os
import sys
import json
import shutil
import tempfile
import threading
from pathlib import Path

# Configure these for your repo
GITHUB_OWNER = "ArukuX"
GITHUB_REPO = "codegpt"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
UPDATE_CHECK_FILE = Path.home() / ".codegpt" / "last_update_check"


def _get_current_version():
    from ai_cli import __version__
    return __version__


def _parse_version(v):
    """Parse 'v1.2.3' or '1.2.3' into tuple."""
    v = v.lstrip("v").strip()
    parts = v.split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def _should_check():
    """Only check once per hour."""
    import time
    try:
        if UPDATE_CHECK_FILE.exists():
            last = float(UPDATE_CHECK_FILE.read_text().strip())
            if time.time() - last < 3600:  # 1 hour
                return False
    except Exception:
        pass
    return True


def _save_check_time():
    import time
    try:
        UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_CHECK_FILE.write_text(str(time.time()))
    except Exception:
        pass


def _fetch_latest():
    """Fetch latest release info from GitHub."""
    import requests
    try:
        resp = requests.get(RELEASES_URL, timeout=5, headers={"Accept": "application/vnd.github.v3+json"})
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _is_frozen():
    """Check if running as PyInstaller exe."""
    return getattr(sys, 'frozen', False)


def check_for_update():
    """Non-blocking update check on startup."""
    if not _should_check():
        return

    def _check():
        _save_check_time()
        release = _fetch_latest()
        if not release:
            return

        latest_tag = release.get("tag_name", "")
        current = _parse_version(_get_current_version())
        latest = _parse_version(latest_tag)

        if latest > current:
            # Store update info for next prompt
            update_file = Path.home() / ".codegpt" / "update_available.json"
            update_file.write_text(json.dumps({
                "version": latest_tag,
                "current": _get_current_version(),
                "url": release.get("html_url", ""),
                "assets": [
                    {"name": a["name"], "url": a["browser_download_url"]}
                    for a in release.get("assets", [])
                    if a["name"].endswith(".exe")
                ],
            }, indent=2))

    # Run in background thread — never block startup
    t = threading.Thread(target=_check, daemon=True)
    t.start()


def get_pending_update():
    """Check if there's a pending update notification."""
    update_file = Path.home() / ".codegpt" / "update_available.json"
    if update_file.exists():
        try:
            data = json.loads(update_file.read_text())
            latest = _parse_version(data["version"])
            current = _parse_version(_get_current_version())
            if latest > current:
                return data
        except Exception:
            pass
    return None


def force_update():
    """Force download and install the latest version."""
    import requests
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    console.print(Panel(
        Text("Checking for updates...", style="bold"),
        border_style="bright_cyan",
    ))

    release = _fetch_latest()
    if not release:
        console.print("[red]Cannot reach GitHub. Check your internet.[/]")
        return

    latest_tag = release.get("tag_name", "")
    current = _get_current_version()

    if _parse_version(latest_tag) <= _parse_version(current):
        console.print(f"[green]Already up to date (v{current})[/]")
        return

    # Find the exe asset
    exe_assets = [a for a in release.get("assets", []) if a["name"].endswith(".exe")]
    if not exe_assets:
        console.print("[yellow]No exe found in release. Update manually.[/]")
        console.print(f"  {release.get('html_url', '')}")
        return

    asset = exe_assets[0]

    # Find checksum file in release assets
    sha_assets = [a for a in release.get("assets", []) if a["name"].endswith(".sha256")]
    expected_hash = None
    if sha_assets:
        try:
            sha_resp = requests.get(sha_assets[0]["browser_download_url"], timeout=10)
            # Parse certutil output: second line is the hash
            lines = sha_resp.text.strip().splitlines()
            for line in lines:
                line = line.strip().replace(" ", "")
                if len(line) == 64 and all(c in "0123456789abcdef" for c in line.lower()):
                    expected_hash = line.lower()
                    break
        except Exception:
            pass

    console.print(f"  Downloading {asset['name']} ({latest_tag})...")
    if expected_hash:
        console.print(f"  Expected SHA256: {expected_hash[:16]}...")
    else:
        console.print("[yellow]  WARNING: No checksum file found. Cannot verify integrity.[/]")

    try:
        resp = requests.get(asset["browser_download_url"], stream=True, timeout=60)
        resp.raise_for_status()

        # Download to temp file and compute hash
        import hashlib as _hashlib
        sha256 = _hashlib.sha256()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
            sha256.update(chunk)
        tmp.close()

        actual_hash = sha256.hexdigest().lower()
        console.print(f"  Actual SHA256:   {actual_hash[:16]}...")

        # Verify checksum if available
        if expected_hash and actual_hash != expected_hash:
            console.print(Panel(
                Text(
                    "CHECKSUM MISMATCH — download may be tampered with.\n"
                    f"Expected: {expected_hash}\n"
                    f"Got:      {actual_hash}\n\n"
                    "Update aborted for your safety.",
                    style="bold red"
                ),
                title="[bold red]SECURITY ALERT[/]",
                border_style="red",
            ))
            os.unlink(tmp.name)
            return

        if expected_hash:
            console.print("[green]  Checksum verified.[/]")

        if _is_frozen():
            # Replace the running exe
            current_exe = sys.executable
            backup = current_exe + ".bak"

            # Rename current to .bak, move new to current
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(current_exe, backup)
            shutil.move(tmp.name, current_exe)

            console.print(Panel(
                Text(f"Updated: v{current} -> {latest_tag}\nChecksum: {actual_hash[:16]}...\nRestart to use the new version.", style="green"),
                border_style="green",
            ))
        else:
            # Running from source — just notify
            console.print(Panel(
                Text(f"New version available: {latest_tag}\nDownloaded to: {tmp.name}", style="yellow"),
                border_style="yellow",
            ))

        # Clear update notification
        update_file = Path.home() / ".codegpt" / "update_available.json"
        if update_file.exists():
            update_file.unlink()

    except Exception as e:
        console.print(f"[red]Update failed: {e}[/]")
