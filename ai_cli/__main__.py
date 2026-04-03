"""Entry point for `python -m ai_cli` and `ai` command."""
import sys
import os

# Fix Unicode on Windows
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    """Main entry point — wraps chat.py with auto-update check."""
    from ai_cli import __version__
    from ai_cli.updater import check_for_update

    # Handle meta-commands before loading the full CLI
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "--version" or cmd == "-v":
            print(f"CodeGPT v{__version__}")
            return
        elif cmd == "update":
            from ai_cli.updater import force_update
            force_update()
            return
        elif cmd == "doctor":
            from ai_cli.doctor import run_doctor
            run_doctor()
            return

    # Silent update check (non-blocking)
    check_for_update()

    # Add parent dir to path so chat.py imports work
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    # Launch the CLI
    from chat import main as chat_main
    chat_main()


if __name__ == "__main__":
    main()
