"""CodeGPT Mobile — Flet app for Android + Desktop. Connects to Ollama."""

import json
import sys
import time
import threading
from pathlib import Path

import flet as ft
import requests


def _log(where, ex):
    """Lightweight stderr logger for non-fatal failures."""
    print(f"[mobile] {where}: {ex}", file=sys.stderr)

# --- Config ---

DEFAULT_SERVER = "http://localhost:5050"  # CodeGPT backend
DEFAULT_MODEL = ""  # Empty = use server default
CONFIG_DIR = Path.home() / ".codegpt"
MOBILE_CONFIG = CONFIG_DIR / "mobile_config.json"
MOBILE_HISTORY = CONFIG_DIR / "mobile_history.json"

SYSTEM_PROMPT = """You are an AI modeled after a highly technical, system-focused developer mindset.
Be direct, concise, and dense with information. No fluff, no filler, no emojis.
Give conclusions first, then minimal necessary explanation.
Focus on: AI, coding, automation, cybersecurity, system design.
Blunt but intelligent. Slightly dark tone is acceptable.
Keep responses concise for mobile reading."""

PERSONAS = {
    "Default": SYSTEM_PROMPT,
    "Hacker": "You are a cybersecurity expert. Technical jargon, CVEs, attack vectors. Defensive security only. Be concise for mobile.",
    "Teacher": "You are a patient programming teacher. Step by step, analogies, examples. Adapt to the student. Concise for mobile.",
    "Roast": "You are a brutally sarcastic code reviewer. Roast bad code then give the fix. Dark humor. Concise for mobile.",
    "Minimal": "Shortest possible answer. One line if possible. Code only, no commentary.",
}


def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if MOBILE_CONFIG.exists():
        try:
            return json.loads(MOBILE_CONFIG.read_text())
        except Exception as ex:
            _log("load_config", ex)
    return {
        "server": DEFAULT_SERVER,
        "model": DEFAULT_MODEL,
        "persona": "Default",
        "ephemeral": False,
    }


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MOBILE_CONFIG.write_text(json.dumps(config, indent=2))


def load_history():
    if MOBILE_HISTORY.exists():
        try:
            data = json.loads(MOBILE_HISTORY.read_text())
            if isinstance(data, list):
                return data
        except Exception as ex:
            _log("load_history", ex)
    return []


def save_history(messages, ephemeral=False):
    """Persist chat history. Returns True on success, False on failure.

    When ephemeral=True, the file is removed (if present) and nothing is
    written — used so users can opt out of plaintext local persistence.
    Failures are logged to stderr so disk-full / permission errors are
    diagnosable instead of silently dropping conversations.
    """
    if ephemeral:
        try:
            if MOBILE_HISTORY.exists():
                MOBILE_HISTORY.unlink()
        except Exception as ex:
            _log("save_history(ephemeral unlink)", ex)
        return True
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Cap history at last 200 messages to prevent runaway file growth
        MOBILE_HISTORY.write_text(json.dumps(messages[-200:], indent=2))
        return True
    except Exception as ex:
        _log("save_history", ex)
        return False


def _is_local_server(url):
    """Check if a server URL points to localhost (safe for HTTP).

    Fail-closed: if the URL is unparseable, treat as REMOTE (not local)
    so the HTTP warning is shown. Never silently assume local.
    """
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1") or (
            host.startswith("127.") and host.count(".") == 3
            and all(p.isdigit() and 0 <= int(p) <= 255 for p in host.split("."))
        )
    except Exception:
        return False  # fail-closed: unknown URL = treat as remote


def _warn_if_http(url):
    """Return a warning string if the URL is HTTP on a non-local host."""
    if url.startswith("http://") and not _is_local_server(url):
        return "⚠ HTTP connection — traffic is not encrypted"
    return ""


def _enforce_transport_security(url):
    """Raise ValueError if the server URL is HTTP on a non-local host.

    Unlike _warn_if_http (which is UI-only), this BLOCKS the request from
    going out. Called before every network request to ensure cleartext
    traffic never leaves the machine to a remote endpoint.

    Returns the URL unchanged if it passes, or raises ValueError with a
    user-readable message if it doesn't.
    """
    if url.startswith("http://") and not _is_local_server(url):
        raise ValueError(
            f"Refused to connect to remote server over HTTP (no encryption).\n"
            f"Change server to https:// in Settings, or use a local server."
        )
    return url


def fetch_models(server):
    """Fetch available models from server /models endpoint."""
    try:
        _enforce_transport_security(server)
        resp = requests.get(f"{server.rstrip('/')}/models", timeout=5, verify=True)
        return resp.json().get("models", [])
    except ValueError as ex:
        _log("fetch_models (blocked)", ex)
        return []
    except Exception as ex:
        _log("fetch_models", ex)
        return []


# --- Main App ---

def main(page: ft.Page):
    # Theme
    page.title = "CodeGPT"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.CYAN,
        font_family="Roboto",
    )
    page.padding = 0

    # State
    config = load_config()
    messages = load_history()
    is_streaming = [False]

    # Concurrency primitives:
    # - state_lock guards mutations to `messages` and `chat_list.controls`
    #   that may be touched by both the UI thread (new_chat, send_message)
    #   and the background do_request worker.
    # - dialog_token monotonically increments each time the Settings dialog
    #   is opened; background workers spawned for an old dialog instance
    #   compare against the current token before applying results.
    state_lock = threading.RLock()
    dialog_token = [0]

    # --- UI Components ---

    chat_list = ft.ListView(
        expand=True,
        spacing=8,
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        auto_scroll=True,
    )

    input_field = ft.TextField(
        hint_text="Message CodeGPT...",
        border_radius=24,
        filled=True,
        expand=True,
        on_submit=lambda e: send_message(e),
        text_size=14,
        content_padding=ft.padding.symmetric(horizontal=16, vertical=10),
    )

    status_text = ft.Text(
        f"{config['model']}  |  0 msgs",
        size=11,
        color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
    )

    def update_status():
        http_warn = _warn_if_http(config.get("server", DEFAULT_SERVER))
        base = f"{config['model']}  |  {len(messages)} msgs  |  {config.get('persona', 'Default')}"
        status_text.value = f"{base}  {http_warn}" if http_warn else base
        try:
            page.update()
        except Exception:
            pass

    # --- Message Bubbles ---

    def add_user_bubble(text):
        chat_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text("You", size=11, color=ft.Colors.CYAN, weight=ft.FontWeight.BOLD),
                    ft.Text(text, size=14, color=ft.Colors.WHITE, selectable=True),
                ], spacing=4),
                padding=ft.padding.all(12),
                border_radius=ft.border_radius.only(
                    top_left=16, top_right=16, bottom_left=16, bottom_right=4,
                ),
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.CYAN),
                margin=ft.margin.only(left=48, bottom=4),
            )
        )

    def add_ai_bubble(text, stats=""):
        bubble = ft.Container(
            content=ft.Column([
                ft.Text("AI", size=11, color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD),
                ft.Markdown(
                    text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme=ft.MarkdownCodeTheme.MONOKAI,
                    on_tap_link=lambda e: page.launch_url(e.data),
                ),
                ft.Text(stats, size=10, color=ft.Colors.with_opacity(0.4, ft.Colors.WHITE)) if stats else ft.Container(),
            ], spacing=4),
            padding=ft.padding.all(12),
            border_radius=ft.border_radius.only(
                top_left=16, top_right=16, bottom_left=4, bottom_right=16,
            ),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
            margin=ft.margin.only(right=48, bottom=4),
            key="ai_latest",
        )
        chat_list.controls.append(bubble)

    def add_thinking_bubble():
        chat_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.GREEN),
                    ft.Text("Thinking...", size=13, color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE), italic=True),
                ], spacing=8),
                padding=ft.padding.all(12),
                border_radius=16,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREEN),
                margin=ft.margin.only(right=48, bottom=4),
                key="thinking",
            )
        )

    def remove_thinking():
        chat_list.controls[:] = [c for c in chat_list.controls if getattr(c, 'key', None) != "thinking"]

    # --- Send Message ---

    def send_message(e):
        text = input_field.value.strip()
        if not text or is_streaming[0]:
            return

        input_field.value = ""
        add_user_bubble(text)
        add_thinking_bubble()
        page.update()

        with state_lock:
            messages.append({"role": "user", "content": text})
            save_history(messages, ephemeral=config.get("ephemeral", False))
            is_streaming[0] = True

        def do_request():
            server = config.get("server", DEFAULT_SERVER)
            model = config.get("model", DEFAULT_MODEL)
            persona = config.get("persona", "Default")

            try:
                _enforce_transport_security(server)
                response = requests.post(
                    f"{server}/chat",
                    json={
                        "messages": messages,
                        "model": model,
                        "persona": persona,
                    },
                    stream=True,
                    timeout=120,
                    verify=True,
                )
                response.raise_for_status()

                full = []
                stats = ""
                last_update = 0

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    content = chunk.get("content", "")
                    if content:
                        full.append(content)

                        now = time.time()
                        if now - last_update >= 0.5:
                            remove_thinking()
                            chat_list.controls[:] = [
                                c for c in chat_list.controls
                                if getattr(c, 'key', None) != "ai_latest"
                            ]
                            add_ai_bubble("".join(full), "streaming...")
                            try:
                                page.update()
                            except Exception:
                                pass
                            last_update = now

                    if chunk.get("done"):
                        stats = chunk.get("stats", "")
                        if not stats:
                            tokens = chunk.get("tokens", {})
                            provider = chunk.get("provider", "")
                            out_tok = tokens.get("output", 0)
                            stats = f"{out_tok} tok | {provider}"

                final_text = "".join(full)
                with state_lock:
                    messages.append({"role": "assistant", "content": final_text})
                    save_history(messages, ephemeral=config.get("ephemeral", False))

                    # Final render
                    remove_thinking()
                    chat_list.controls[:] = [
                        c for c in chat_list.controls
                        if getattr(c, 'key', None) != "ai_latest"
                    ]
                    add_ai_bubble(final_text, stats)

            except ValueError as ex:
                # Transport security block (HTTP to remote host).
                with state_lock:
                    remove_thinking()
                    add_ai_bubble(str(ex), "security")
                    if messages and messages[-1]["role"] == "user":
                        messages.pop()
                        save_history(messages, ephemeral=config.get("ephemeral", False))
            except requests.ConnectionError:
                with state_lock:
                    remove_thinking()
                    add_ai_bubble("Cannot connect to Ollama.\nCheck server IP in settings.", "error")
                    if messages and messages[-1]["role"] == "user":
                        messages.pop()
                        save_history(messages, ephemeral=config.get("ephemeral", False))
            except requests.Timeout:
                with state_lock:
                    remove_thinking()
                    add_ai_bubble("Request timed out.", "error")
                    if messages and messages[-1]["role"] == "user":
                        messages.pop()
                        save_history(messages, ephemeral=config.get("ephemeral", False))
            except Exception as ex:
                _log("do_request", ex)
                with state_lock:
                    remove_thinking()
                    add_ai_bubble(f"Error: {ex}", "error")
                    if messages and messages[-1]["role"] == "user":
                        messages.pop()
                        save_history(messages, ephemeral=config.get("ephemeral", False))
            finally:
                is_streaming[0] = False
                update_status()
                try:
                    page.update()
                except Exception:
                    pass

        threading.Thread(target=do_request, daemon=True).start()

    # --- Settings Dialog ---

    def open_settings(e):
        # MED-1 fix: bump the dialog token. Background workers spawned for
        # this dialog will compare against `dialog_token[0]` before applying
        # any UI write. If the dialog has since been closed/reopened, the
        # token will not match and the worker silently discards its result.
        dialog_token[0] += 1
        my_token = dialog_token[0]

        server_field = ft.TextField(
            value=config.get("server", DEFAULT_SERVER),
            label="Server URL",
            border_radius=12,
            text_size=14,
        )

        # Model dropdown — populated lazily from a background thread to avoid
        # blocking the UI/ANR if the server is offline (5s timeout per call).
        current_model = config.get("model", DEFAULT_MODEL)
        initial_options = [ft.dropdown.Option(current_model)] if current_model else []
        model_dropdown = ft.Dropdown(
            value=current_model,
            label="Model (loading…)",
            options=initial_options,
            border_radius=12,
            text_size=14,
            editable=True,  # Allow manual entry as fallback
        )

        def populate_models_async(server):
            """Fetch models off the UI thread."""
            models = fetch_models(server)
            # MED-1: discard stale results from a dialog that has since closed
            if my_token != dialog_token[0]:
                return
            if models:
                if current_model and current_model not in models:
                    models.insert(0, current_model)
                model_dropdown.options = [ft.dropdown.Option(m) for m in models]
                model_dropdown.label = "Model"
                if not model_dropdown.value and models:
                    model_dropdown.value = models[0]
            else:
                model_dropdown.label = "Model (server offline — type manually)"
            try:
                page.update()
            except Exception as ex:
                _log("populate_models_async update", ex)

        threading.Thread(
            target=populate_models_async,
            args=(server_field.value.strip().rstrip("/"),),
            daemon=True,
        ).start()

        persona_dropdown = ft.Dropdown(
            value=config.get("persona", "Default"),
            label="Persona",
            options=[ft.dropdown.Option(p) for p in PERSONAS],
            border_radius=12,
            text_size=14,
        )

        # MED-2: ephemeral mode — when ON, history is never persisted to disk.
        ephemeral_switch = ft.Switch(
            value=bool(config.get("ephemeral", False)),
            label="Ephemeral mode (no history saved)",
        )
        plaintext_warning = ft.Text(
            "⚠ History is stored as plaintext at ~/.codegpt/mobile_history.json",
            size=11,
            color=ft.Colors.with_opacity(0.6, ft.Colors.AMBER),
        )

        def refresh_models(e):
            server = server_field.value.strip().rstrip("/")

            def worker():
                models = fetch_models(server)
                # MED-1: bail if dialog has been closed/reopened since spawn
                if my_token != dialog_token[0]:
                    return
                if models:
                    model_dropdown.options = [ft.dropdown.Option(m) for m in models]
                    model_dropdown.label = "Model"
                    if model_dropdown.value not in models:
                        model_dropdown.value = models[0]
                    snack = ft.SnackBar(ft.Text(f"Loaded {len(models)} models"), duration=1500)
                else:
                    snack = ft.SnackBar(ft.Text("No models — server offline?"), duration=2000)
                try:
                    page.open(snack)
                    page.update()
                except Exception as ex:
                    _log("refresh_models update", ex)

            threading.Thread(target=worker, daemon=True).start()

        def save_settings(e):
            config["server"] = server_field.value.strip().rstrip("/")
            config["model"] = (model_dropdown.value or "").strip()
            config["persona"] = persona_dropdown.value
            config["ephemeral"] = bool(ephemeral_switch.value)
            # If user just enabled ephemeral mode, wipe any existing history.
            if config["ephemeral"]:
                save_history(messages, ephemeral=True)
            save_config(config)
            update_status()
            dlg.open = False
            page.update()
            page.open(ft.SnackBar(ft.Text("Settings saved"), duration=1500))

        def test_connection(e):
            server = server_field.value.strip().rstrip("/")

            def worker():
                try:
                    resp = requests.get(f"{server}/health", timeout=5)
                    data = resp.json()
                    provider = data.get("provider", "?")
                    model = data.get("model", "?")
                    snack = ft.SnackBar(
                        ft.Text(f"Connected. Provider: {provider}, Model: {model}"),
                        duration=3000,
                    )
                except Exception as ex:
                    _log("test_connection", ex)
                    snack = ft.SnackBar(ft.Text(f"Failed: {ex}"), duration=3000)
                # MED-1: bail if dialog has been closed/reopened since spawn
                if my_token != dialog_token[0]:
                    return
                try:
                    page.open(snack)
                    page.update()
                except Exception as ex:
                    _log("test_connection update", ex)

            threading.Thread(target=worker, daemon=True).start()

        def clear_history(e):
            # Close dialog first to prevent flicker, then let new_chat handle
            # the messages.clear() + file unlink + welcome render in one pass.
            dlg.open = False
            page.update()
            new_chat(None)
            page.open(ft.SnackBar(ft.Text("History cleared"), duration=1500))

        dlg = ft.AlertDialog(
            title=ft.Text("Settings"),
            content=ft.Container(
                content=ft.Column([
                    server_field,
                    ft.Row([
                        ft.ElevatedButton("Test", on_click=test_connection, icon=ft.Icons.WIFI),
                        ft.ElevatedButton("Refresh Models", on_click=refresh_models, icon=ft.Icons.REFRESH),
                    ], spacing=8),
                    model_dropdown,
                    persona_dropdown,
                    ft.Divider(height=8, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    ephemeral_switch,
                    plaintext_warning,
                    ft.OutlinedButton(
                        "Clear History",
                        on_click=clear_history,
                        icon=ft.Icons.DELETE_FOREVER,
                        style=ft.ButtonStyle(color=ft.Colors.RED_300),
                    ),
                ], spacing=16, tight=True),
                width=320,
                padding=ft.padding.only(top=8),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.ElevatedButton("Save", on_click=save_settings),
            ],
        )
        page.open(dlg)

    # --- New Chat ---

    def new_chat(e):
        # HIGH-2 fix: refuse to clear state while a streaming response is
        # in flight. Otherwise the background do_request thread would still
        # be appending tokens to a list/widget the UI just emptied — race.
        if is_streaming[0]:
            try:
                page.open(ft.SnackBar(
                    ft.Text("Wait for current response to finish."),
                    duration=1500,
                ))
                page.update()
            except Exception as ex:
                _log("new_chat snackbar", ex)
            return

        with state_lock:
            messages.clear()
            try:
                if MOBILE_HISTORY.exists():
                    MOBILE_HISTORY.unlink()
            except FileNotFoundError:
                pass
            except Exception as ex:
                _log("new_chat unlink", ex)
            chat_list.controls.clear()
            _append_welcome()
        update_status()
        page.update()

    def _append_welcome():
        chat_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text("CodeGPT", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("Local AI assistant on your phone.", size=14,
                            color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
                            text_align=ft.TextAlign.CENTER),
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    *[
                        ft.OutlinedButton(
                            text=s,
                            on_click=lambda e, txt=s: (setattr(input_field, 'value', txt), send_message(e)),
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                        )
                        for s in [
                            "Explain TCP/IP",
                            "Python CPU monitor script",
                            "OWASP top 10",
                            "Design a REST API",
                        ]
                    ],
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                padding=ft.padding.all(32),
                alignment=ft.alignment.center,
            )
        )

    # --- App Bar ---

    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.TERMINAL, color=ft.Colors.CYAN),
        title=ft.Text("CodeGPT", weight=ft.FontWeight.BOLD),
        center_title=False,
        bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.BLACK),
        actions=[
            ft.IconButton(ft.Icons.ADD_COMMENT, on_click=new_chat, tooltip="New Chat"),
            ft.IconButton(ft.Icons.SETTINGS, on_click=open_settings, tooltip="Settings"),
        ],
    )

    # --- Bottom Input Bar ---

    send_btn = ft.IconButton(
        ft.Icons.SEND_ROUNDED,
        icon_color=ft.Colors.CYAN,
        on_click=send_message,
        tooltip="Send",
    )

    input_bar = ft.Container(
        content=ft.Row([input_field, send_btn], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor=ft.Colors.with_opacity(0.95, ft.Colors.BLACK),
        border=ft.border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE))),
    )

    # --- Status Bar ---

    status_bar = ft.Container(
        content=status_text,
        padding=ft.padding.symmetric(horizontal=16, vertical=4),
        bgcolor=ft.Colors.with_opacity(0.95, ft.Colors.BLACK),
    )

    # --- Layout ---

    page.add(
        ft.Column([
            ft.Container(content=chat_list, expand=True),
            status_bar,
            input_bar,
        ], expand=True, spacing=0),
    )

    # If we have persisted history, replay it. Otherwise show welcome.
    if messages:
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                add_user_bubble(content)
            elif role == "assistant":
                add_ai_bubble(content, "")
        update_status()
        page.update()
    else:
        new_chat(None)


ft.app(target=main)
