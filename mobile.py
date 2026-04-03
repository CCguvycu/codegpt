"""CodeGPT Mobile — Flet app for Android + Desktop. Connects to Ollama."""

import json
import time
import threading
from pathlib import Path

import flet as ft
import requests

# --- Config ---

DEFAULT_SERVER = "http://192.168.1.237:5050"  # CodeGPT backend
DEFAULT_MODEL = ""  # Empty = use server default
CONFIG_DIR = Path.home() / ".codegpt"
MOBILE_CONFIG = CONFIG_DIR / "mobile_config.json"

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
        except Exception:
            pass
    return {"server": DEFAULT_SERVER, "model": DEFAULT_MODEL, "persona": "Default"}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MOBILE_CONFIG.write_text(json.dumps(config, indent=2))


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
    messages = []
    is_streaming = [False]

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
        status_text.value = f"{config['model']}  |  {len(messages)} msgs  |  {config.get('persona', 'Default')}"
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

        messages.append({"role": "user", "content": text})
        is_streaming[0] = True

        def do_request():
            server = config.get("server", DEFAULT_SERVER)
            model = config.get("model", DEFAULT_MODEL)
            persona = config.get("persona", "Default")
            system = PERSONAS.get(persona, SYSTEM_PROMPT)

            ollama_messages = [{"role": "system", "content": system}]
            ollama_messages.extend(messages)

            try:
                response = requests.post(
                    f"{server}/chat",
                    json={
                        "messages": messages,
                        "model": model,
                        "persona": persona,
                    },
                    stream=True,
                    timeout=120,
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
                messages.append({"role": "assistant", "content": final_text})

                # Final render
                remove_thinking()
                chat_list.controls[:] = [
                    c for c in chat_list.controls
                    if getattr(c, 'key', None) != "ai_latest"
                ]
                add_ai_bubble(final_text, stats)

            except requests.ConnectionError:
                remove_thinking()
                add_ai_bubble("Cannot connect to Ollama.\nCheck server IP in settings.", "error")
                if messages and messages[-1]["role"] == "user":
                    messages.pop()
            except requests.Timeout:
                remove_thinking()
                add_ai_bubble("Request timed out.", "error")
                if messages and messages[-1]["role"] == "user":
                    messages.pop()
            except Exception as ex:
                remove_thinking()
                add_ai_bubble(f"Error: {ex}", "error")
                if messages and messages[-1]["role"] == "user":
                    messages.pop()
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
        server_field = ft.TextField(
            value=config.get("server", DEFAULT_SERVER),
            label="Ollama Server URL",
            border_radius=12,
            text_size=14,
        )
        model_field = ft.TextField(
            value=config.get("model", DEFAULT_MODEL),
            label="Model",
            border_radius=12,
            text_size=14,
        )
        persona_dropdown = ft.Dropdown(
            value=config.get("persona", "Default"),
            label="Persona",
            options=[ft.dropdown.Option(p) for p in PERSONAS],
            border_radius=12,
            text_size=14,
        )

        def save_settings(e):
            config["server"] = server_field.value.strip().rstrip("/")
            config["model"] = model_field.value.strip()
            config["persona"] = persona_dropdown.value
            save_config(config)
            update_status()
            dlg.open = False
            page.update()
            page.open(ft.SnackBar(ft.Text("Settings saved"), duration=1500))

        def test_connection(e):
            server = server_field.value.strip().rstrip("/")
            try:
                resp = requests.get(f"{server}/health", timeout=5)
                data = resp.json()
                provider = data.get("provider", "?")
                model = data.get("model", "?")
                page.open(ft.SnackBar(
                    ft.Text(f"Connected. Provider: {provider}, Model: {model}"),
                    duration=3000,
                ))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(f"Failed: {ex}"), duration=3000))

        dlg = ft.AlertDialog(
            title=ft.Text("Settings"),
            content=ft.Container(
                content=ft.Column([
                    server_field,
                    ft.ElevatedButton("Test Connection", on_click=test_connection, icon=ft.Icons.WIFI),
                    model_field,
                    persona_dropdown,
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
        messages.clear()
        chat_list.controls.clear()

        # Welcome
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
        update_status()
        page.update()

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

    # Show welcome
    new_chat(None)


ft.app(target=main)
