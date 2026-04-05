"""CodeGPT Launcher

Usage:
    python run.py              Start CLI chat (default)
    python run.py chat         Start CLI chat
    python run.py tui          Start TUI with sidebar
    python run.py bot          Start Telegram bot
    python run.py server       Start backend server
    python run.py mobile       Start mobile app (desktop preview)
    python run.py apk          Build Android APK
"""

import os
import sys
import json
import subprocess
from pathlib import Path

CONFIG_DIR = Path.home() / ".codegpt"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def run_script(name):
    script = Path(__file__).parent / name
    subprocess.run([sys.executable, str(script)])


def run_bot(token=None):
    config = load_config()
    bot_token = token or os.environ.get("CODEGPT_BOT_TOKEN") or config.get("bot_token")

    if not bot_token:
        print("  No token. Get one from @BotFather on Telegram.")
        try:
            bot_token = input("  Paste token > ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not bot_token:
            return
        try:
            if input("  Save for later? (y/n) > ").strip().lower() == "y":
                config["bot_token"] = bot_token
                save_config(config)
                print("  Saved.\n")
        except (KeyboardInterrupt, EOFError):
            pass

    os.environ["CODEGPT_BOT_TOKEN"] = bot_token
    run_script("bot.py")


def run_server():
    config = load_config()
    groq_key = os.environ.get("GROQ_API_KEY") or config.get("groq_api_key")

    if not groq_key:
        print("  No Groq API key found.")
        print("  Get a free one at: https://console.groq.com/keys\n")
        print("  Without it, the server will use local Ollama.\n")
        try:
            groq_key = input("  Paste Groq key (or Enter to skip) > ").strip()
        except (KeyboardInterrupt, EOFError):
            groq_key = ""

        if groq_key:
            try:
                if input("  Save for later? (y/n) > ").strip().lower() == "y":
                    config["groq_api_key"] = groq_key
                    save_config(config)
                    print("  Saved.\n")
            except (KeyboardInterrupt, EOFError):
                pass

    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    run_script("server.py")


def build_apk():
    project = Path(__file__).parent
    print("  Building APK with Flet...\n")
    result = subprocess.run(
        ["flet", "build", "apk", "--project", str(project), "--module-name", "mobile"],
        cwd=str(project),
    )
    if result.returncode == 0:
        # Copy APK to desktop
        apk_path = project / "build" / "apk" / "app-release.apk"
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "OneDrive" / "Desktop"
        if apk_path.exists():
            import shutil
            dest = desktop / "CodeGPT.apk"
            shutil.copy2(str(apk_path), str(dest))
            print(f"\n  APK copied to: {dest}")
        else:
            print(f"\n  APK built. Check: {project / 'build'}")
    else:
        print("\n  Build failed. Make sure Flet is installed: pip install flet")


def main():
    args = sys.argv[1:]

    if not args or args[0].lower() in ("chat", "cli"):
        run_script("chat.py")
    elif args[0].lower() in ("tui", "ui", "app"):
        run_script("app.py")
    elif args[0].lower() in ("bot", "telegram"):
        token = None
        if "--token" in args:
            idx = args.index("--token")
            if idx + 1 < len(args):
                token = args[idx + 1]
        if "--save-token" in args:
            idx = args.index("--save-token")
            if idx + 1 < len(args):
                token = args[idx + 1]
                config = load_config()
                config["bot_token"] = token
                save_config(config)
                print("  Token saved.")
        run_bot(token)
    elif args[0].lower() in ("server", "backend", "api"):
        run_server()
    elif args[0].lower() in ("mobile", "phone"):
        run_script("mobile.py")
    elif args[0].lower() in ("web",):
        run_script("web.py")
    elif args[0].lower() in ("apk", "build"):
        build_apk()
    elif args[0].lower() in ("help", "--help", "-h"):
        print(__doc__)
    else:
        print(f"  Unknown: {args[0]}")
        print("  Use: chat, tui, bot, server, mobile, or apk")


if __name__ == "__main__":
    main()
