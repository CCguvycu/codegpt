"""CodeGPT — Terminal UI with sidebar, powered by Ollama."""

import json
import os
import re
import subprocess
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime

import requests
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll, Center, Grid
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label, ListItem, ListView,
    Markdown, Static, RichLog,
)
from rich.text import Text

# --- Config ---

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3.2"
CHATS_DIR = Path.home() / ".codegpt" / "conversations"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

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

SUGGESTIONS = [
    "Explain how TCP/IP works under the hood",
    "Write a Python script to monitor CPU usage",
    "What are the OWASP top 10 vulnerabilities?",
    "Design a REST API for a todo app",
]

TIME_PATTERN = re.compile(r"^(\d+)\s*(s|sec|m|min|h|hr|hour)s?\b", re.IGNORECASE)
TIME_MULTIPLIERS = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hr": 3600, "hour": 3600}


# --- Helpers ---

def get_saved_chats():
    """Return list of saved chat files, newest first."""
    if not CHATS_DIR.exists():
        return []
    return sorted(CHATS_DIR.glob("*.json"), reverse=True)


def chat_display_name(path):
    """Extract display name from chat filename."""
    stem = path.stem
    if len(stem) > 14:
        return stem[14:].replace("_", " ").title()
    return stem.replace("_", " ")


def chat_date(path):
    """Extract date string from chat filename."""
    stem = path.stem
    if len(stem) >= 13:
        return stem[:8]
    return ""


def save_chat(messages, model):
    """Save conversation to disk."""
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    first_msg = next((m["content"] for m in messages if m["role"] == "user"), "untitled")
    name = re.sub(r'[^\w\s-]', '', first_msg[:40]).strip().replace(' ', '_').lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{ts}_{name}.json"
    data = {"model": model, "messages": messages, "saved_at": datetime.now().isoformat()}
    (CHATS_DIR / filename).write_text(json.dumps(data, indent=2))
    return filename


def load_chat(path):
    """Load conversation from disk."""
    data = json.loads(path.read_text())
    return data.get("messages", []), data.get("model", DEFAULT_MODEL)


def ensure_ollama():
    """Start Ollama if not running. Returns list of available models."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return [m["name"] for m in resp.json().get("models", [])]
    except (requests.ConnectionError, requests.Timeout):
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
        )
        for _ in range(15):
            time.sleep(1)
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=2)
                return [m["name"] for m in resp.json().get("models", [])]
            except (requests.ConnectionError, requests.Timeout):
                continue
        return []


# --- Welcome Popup ---

WELCOME_FLAG = Path.home() / ".codegpt" / ".welcomed"

class WelcomeModal(ModalScreen):
    """First-launch welcome popup."""

    CSS = """
    WelcomeModal {
        align: center middle;
    }

    #welcome-dialog {
        width: 60;
        height: auto;
        max-height: 30;
        background: #161b22;
        border: thick #58a6ff;
        padding: 2 3;
    }

    #welcome-title {
        text-align: center;
        text-style: bold;
        color: #58a6ff;
        width: 100%;
        margin: 0 0 1 0;
    }

    #welcome-ascii {
        text-align: center;
        color: #238636;
        width: 100%;
        margin: 0 0 1 0;
    }

    #welcome-body {
        color: #c9d1d9;
        margin: 1 0;
    }

    #welcome-version {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin: 1 0;
    }

    #welcome-features {
        color: #8b949e;
        margin: 1 2;
    }

    #welcome-keys {
        color: #58a6ff;
        margin: 1 2;
    }

    #welcome-footer {
        text-align: center;
        color: #484f58;
        width: 100%;
        margin: 1 0 0 0;
    }

    #welcome-go-btn {
        width: 100%;
        margin: 1 0 0 0;
        background: #238636;
        color: white;
        text-style: bold;
        border: none;
        height: 3;
    }

    #welcome-go-btn:hover {
        background: #2ea043;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-dialog"):
            yield Static(
                "C O D E  G P T",
                id="welcome-title",
            )
            yield Static(
                "  ██████╗ ██████╗ ████████╗\n"
                " ██╔════╝ ██╔══██╗╚══██╔══╝\n"
                " ██║  ███╗██████╔╝   ██║   \n"
                " ██║   ██║██╔═══╝    ██║   \n"
                " ╚██████╔╝██║        ██║   \n"
                "  ╚═════╝ ╚═╝        ╚═╝   ",
                id="welcome-ascii",
            )
            yield Static(
                "Your local AI coding assistant.\n"
                "Powered by Ollama. Runs 100% on your machine.",
                id="welcome-body",
            )
            yield Static("v1.0.0", id="welcome-version")
            yield Static(
                "Features:\n"
                "  * Multi-turn conversations\n"
                "  * Streaming responses\n"
                "  * Save & load chat history\n"
                "  * Switch models on the fly\n"
                "  * Copy, regenerate, edit messages\n"
                "  * Reminders & suggestions\n"
                "  * Sidebar with saved chats",
                id="welcome-features",
            )
            yield Static(
                "Shortcuts:\n"
                "  Ctrl+N  New chat     Ctrl+S  Save\n"
                "  Ctrl+B  Sidebar      Ctrl+R  Regen\n"
                "  Ctrl+Q  Quit         Ctrl+C  Copy",
                id="welcome-keys",
            )
            yield Button("Let's go", id="welcome-go-btn")
            yield Static("By Ark  |  Built with Textual", id="welcome-footer")

    @on(Button.Pressed, "#welcome-go-btn")
    def on_go(self) -> None:
        # Mark as welcomed so it doesn't show again
        WELCOME_FLAG.parent.mkdir(parents=True, exist_ok=True)
        WELCOME_FLAG.touch()
        self.dismiss()

    def on_key(self, event) -> None:
        # Any key dismisses
        if event.key in ("enter", "escape", "space"):
            WELCOME_FLAG.parent.mkdir(parents=True, exist_ok=True)
            WELCOME_FLAG.touch()
            self.dismiss()


# --- Widgets ---

class ChatMessage(Static):
    """A single chat message bubble."""

    def __init__(self, role: str, content: str, stats: str = "") -> None:
        super().__init__()
        self.role = role
        self.content = content
        self.stats = stats

    def compose(self) -> ComposeResult:
        if self.role == "user":
            yield Static(self.content, classes="user-bubble")
        else:
            yield Markdown(self.content, classes="ai-bubble")
            if self.stats:
                yield Static(self.stats, classes="msg-stats")


class WelcomeView(Static):
    """Welcome screen with suggestions."""

    def compose(self) -> ComposeResult:
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning."
        elif hour < 18:
            greeting = "Good afternoon."
        else:
            greeting = "Good evening."

        yield Static(f"\n\n{greeting}", classes="welcome-greeting")
        yield Static("How can I help you today?\n", classes="welcome-sub")
        for i, s in enumerate(SUGGESTIONS, 1):
            yield Button(f"  {s}", id=f"suggest-{i}", classes="suggestion-btn")


class SidebarItem(ListItem):
    """A conversation item in the sidebar."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.chat_path = path

    def compose(self) -> ComposeResult:
        name = chat_display_name(self.chat_path)
        date = chat_date(self.chat_path)
        yield Static(f"[bright_cyan]{name}[/]\n[dim]{date}[/]")


# --- Main App ---

class CodeGPT(App):
    """CodeGPT Terminal UI."""

    TITLE = "CodeGPT"
    CSS = """
    Screen {
        layout: horizontal;
        background: #0d1117;
    }

    #sidebar {
        width: 28;
        background: #161b22;
        border-right: solid #30363d;
        padding: 0;
    }

    #sidebar-header {
        height: 3;
        background: #1a1f29;
        content-align: center middle;
        text-style: bold;
        color: #58a6ff;
        border-bottom: solid #30363d;
    }

    #new-chat-btn {
        width: 100%;
        margin: 1 1;
        background: #238636;
        color: white;
        text-style: bold;
        border: none;
        height: 3;
    }

    #new-chat-btn:hover {
        background: #2ea043;
    }

    #chat-list {
        background: #161b22;
        scrollbar-size: 1 1;
    }

    #chat-list > ListItem {
        padding: 1 1;
        background: #161b22;
        border-bottom: solid #21262d;
    }

    #chat-list > ListItem.-highlight {
        background: #1a2332;
    }

    #main {
        width: 1fr;
        background: #0d1117;
    }

    #messages-scroll {
        height: 1fr;
        scrollbar-size: 1 1;
        padding: 1 2;
    }

    #input-area {
        height: auto;
        max-height: 5;
        dock: bottom;
        padding: 1 2;
        background: #161b22;
        border-top: solid #30363d;
    }

    #chat-input {
        background: #0d1117;
        color: #c9d1d9;
        border: tall #30363d;
        padding: 0 1;
    }

    #chat-input:focus {
        border: tall #58a6ff;
    }

    #status-bar {
        height: 1;
        dock: bottom;
        background: #161b22;
        color: #8b949e;
        padding: 0 2;
        border-top: solid #21262d;
    }

    .welcome-greeting {
        text-align: center;
        text-style: bold;
        color: #c9d1d9;
        width: 100%;
    }

    .welcome-sub {
        text-align: center;
        color: #8b949e;
        width: 100%;
    }

    .suggestion-btn {
        width: 100%;
        margin: 0 4 1 4;
        background: #161b22;
        color: #c9d1d9;
        border: tall #30363d;
        height: 3;
        text-align: left;
    }

    .suggestion-btn:hover {
        background: #1a2332;
        border: tall #58a6ff;
    }

    .user-bubble {
        background: #1a2332;
        color: #c9d1d9;
        margin: 1 0 0 8;
        padding: 1 2;
        border: round #58a6ff;
    }

    .ai-bubble {
        background: #161b22;
        color: #c9d1d9;
        margin: 1 8 0 0;
        padding: 1 2;
        border: round #238636;
    }

    .msg-stats {
        color: #484f58;
        text-align: right;
        margin: 0 8 1 0;
    }

    .msg-label {
        color: #58a6ff;
        text-style: bold;
        margin: 1 0 0 0;
    }

    .msg-label-ai {
        color: #238636;
        text-style: bold;
        margin: 1 0 0 0;
    }

    .streaming-indicator {
        color: #8b949e;
        text-style: italic;
        margin: 0 0 0 1;
    }

    #delete-btn {
        width: 100%;
        margin: 0 1;
        background: #da3633;
        color: white;
        border: none;
        height: 3;
        display: none;
    }

    #delete-btn:hover {
        background: #f85149;
    }

    #action-bar {
        height: 1;
        dock: bottom;
        background: #0d1117;
        padding: 0 2;
        display: none;
    }

    .action-link {
        color: #58a6ff;
        margin: 0 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_chat", "New Chat"),
        Binding("ctrl+s", "save_chat", "Save"),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+q", "quit_app", "Quit"),
        Binding("ctrl+r", "regen", "Regenerate"),
        Binding("ctrl+c", "copy_last", "Copy"),
    ]

    show_sidebar = reactive(True)

    def __init__(self):
        super().__init__()
        self.messages = []
        self.model = DEFAULT_MODEL
        self.system = SYSTEM_PROMPT
        self.available_models = []
        self.last_ai_response = ""
        self.session_start = time.time()
        self.total_tokens = 0
        self.is_streaming = False
        self.active_chat_path = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Static(" CodeGPT", id="sidebar-header")
                yield Button("+ New Chat", id="new-chat-btn")
                yield ListView(id="chat-list")
                yield Button("Delete Selected", id="delete-btn", variant="error")
            with Vertical(id="main"):
                with VerticalScroll(id="messages-scroll"):
                    yield WelcomeView(id="welcome")
                yield Static("", id="status-bar")
                with Horizontal(id="action-bar"):
                    yield Button("Copy", classes="action-link", id="copy-btn")
                    yield Button("Regen", classes="action-link", id="regen-btn")
                yield Input(placeholder="Message CodeGPT...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        self.available_models = ensure_ollama()
        self.refresh_sidebar()
        self.update_status()
        self.query_one("#chat-input", Input).focus()

        # Refresh status bar every second
        self.set_interval(1, self.update_status)

        # Show welcome popup on first launch
        if not WELCOME_FLAG.exists():
            self.push_screen(WelcomeModal())

    def refresh_sidebar(self) -> None:
        """Reload sidebar conversation list."""
        chat_list = self.query_one("#chat-list", ListView)
        chat_list.clear()
        for path in get_saved_chats()[:20]:
            chat_list.append(SidebarItem(path))

        # Show/hide delete button
        try:
            del_btn = self.query_one("#delete-btn", Button)
            del_btn.display = len(get_saved_chats()) > 0
        except NoMatches:
            pass

    def update_status(self) -> None:
        """Update bottom status bar."""
        elapsed = int(time.time() - self.session_start)
        mins = elapsed // 60
        secs = elapsed % 60
        msg_count = len(self.messages)
        now = datetime.now().strftime("%H:%M:%S")
        status = self.query_one("#status-bar", Static)
        status.update(
            f" {self.model}  |  {msg_count} msgs  |  "
            f"{self.total_tokens} tokens  |  {mins}m {secs}s  |  {now}"
        )

    def show_welcome(self) -> None:
        """Show welcome screen."""
        scroll = self.query_one("#messages-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(WelcomeView(id="welcome"))

    def add_user_message(self, text: str) -> None:
        """Add user message to chat."""
        scroll = self.query_one("#messages-scroll", VerticalScroll)
        # Remove welcome if present
        try:
            scroll.query_one("#welcome").remove()
        except NoMatches:
            pass

        scroll.mount(Static("[bright_cyan bold]You[/]", classes="msg-label"))
        scroll.mount(ChatMessage("user", text))
        scroll.scroll_end(animate=False)

    def add_ai_message(self, text: str, stats: str = "") -> None:
        """Add AI message to chat."""
        scroll = self.query_one("#messages-scroll", VerticalScroll)
        scroll.mount(Static("[bright_green bold]AI[/]", classes="msg-label-ai"))
        scroll.mount(ChatMessage("assistant", text, stats))
        scroll.scroll_end(animate=False)

        # Show action bar
        try:
            self.query_one("#action-bar").display = True
        except NoMatches:
            pass

    def add_streaming_placeholder(self) -> None:
        """Add streaming indicator."""
        scroll = self.query_one("#messages-scroll", VerticalScroll)
        scroll.mount(Static("[bright_green bold]AI[/]", classes="msg-label-ai"))
        scroll.mount(Static("Thinking...", classes="streaming-indicator", id="stream-indicator"))
        scroll.scroll_end(animate=False)

    def update_streaming(self, text: str) -> None:
        """Update streaming content."""
        try:
            indicator = self.query_one("#stream-indicator", Static)
            indicator.update(text)
            scroll = self.query_one("#messages-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)
        except NoMatches:
            pass

    def finish_streaming(self, text: str, stats: str = "") -> None:
        """Replace streaming placeholder with final message."""
        try:
            indicator = self.query_one("#stream-indicator")
            parent = indicator.parent
            if parent:
                children = list(parent.children)
                idx = children.index(indicator)
                indicator.remove()
                # Remove the AI label that was mounted before the indicator
                if idx > 0:
                    children[idx - 1].remove()
        except (NoMatches, ValueError):
            pass
        self.add_ai_message(text, stats)

    @work(thread=True)
    def send_message(self, user_text: str) -> None:
        """Send message and stream response."""
        self.is_streaming = True
        self.call_from_thread(self.add_user_message, user_text)

        self.messages.append({"role": "user", "content": user_text})
        self.call_from_thread(self.add_streaming_placeholder)

        ollama_messages = [{"role": "system", "content": self.system}]
        for msg in self.messages:
            ollama_messages.append({"role": msg["role"], "content": msg["content"]})

        try:
            response = requests.post(
                OLLAMA_URL,
                json={"model": self.model, "messages": ollama_messages, "stream": True},
                stream=True,
                timeout=120,
            )
            response.raise_for_status()

            full_response = []
            stats = ""

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
                    # Update every few tokens to avoid UI lag
                    if len(full_response) % 3 == 0:
                        self.call_from_thread(self.update_streaming, current)

                if chunk.get("done"):
                    td = chunk.get("total_duration", 0)
                    ec = chunk.get("eval_count", 0)
                    pec = chunk.get("prompt_eval_count", 0)
                    ds = td / 1e9 if td else 0
                    tps = ec / ds if ds > 0 else 0
                    stats = f"{ec} tok | {ds:.1f}s | {tps:.0f} tok/s"
                    self.total_tokens += ec

            final = "".join(full_response)
            self.last_ai_response = final
            self.messages.append({"role": "assistant", "content": final})

            self.call_from_thread(self.finish_streaming, final, stats)
            self.call_from_thread(self.update_status)

        except requests.ConnectionError:
            # Roll back the user message so history stays consistent
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            self.call_from_thread(self.update_streaming, "Error: Cannot connect to Ollama.")
        except requests.Timeout:
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            self.call_from_thread(self.update_streaming, "Error: Request timed out.")
        except Exception as e:
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            self.call_from_thread(self.update_streaming, f"Error: {e}")
        finally:
            self.is_streaming = False

    # --- Events ---

    @on(Input.Submitted, "#chat-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self.is_streaming:
            return

        event.input.clear()

        # Commands
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            self.handle_command(cmd, text)
            return

        # Suggestion number
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(SUGGESTIONS):
                text = SUGGESTIONS[idx]

        self.send_message(text)

    @on(Button.Pressed, "#new-chat-btn")
    def on_new_chat(self) -> None:
        self.action_new_chat()

    @on(Button.Pressed, "#delete-btn")
    def on_delete_chat(self) -> None:
        chat_list = self.query_one("#chat-list", ListView)
        if chat_list.highlighted_child is not None:
            item = chat_list.highlighted_child
            if isinstance(item, SidebarItem):
                item.chat_path.unlink(missing_ok=True)
                self.refresh_sidebar()
                self.notify("Chat deleted.", severity="warning")

    @on(Button.Pressed, "#copy-btn")
    def on_copy(self) -> None:
        self.action_copy_last()

    @on(Button.Pressed, "#regen-btn")
    def on_regen(self) -> None:
        self.action_regen()

    @on(Button.Pressed, ".suggestion-btn")
    def on_suggestion(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("suggest-"):
            idx = int(btn_id.split("-")[1]) - 1
            if 0 <= idx < len(SUGGESTIONS):
                self.send_message(SUGGESTIONS[idx])

    @on(ListView.Selected, "#chat-list")
    def on_chat_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, SidebarItem):
            msgs, model = load_chat(item.chat_path)
            self.messages = msgs
            self.model = model
            self.active_chat_path = item.chat_path

            # Rebuild chat view
            scroll = self.query_one("#messages-scroll", VerticalScroll)
            scroll.remove_children()

            for msg in self.messages:
                if msg["role"] == "user":
                    scroll.mount(Static("[bright_cyan bold]You[/]", classes="msg-label"))
                    scroll.mount(ChatMessage("user", msg["content"]))
                else:
                    scroll.mount(Static("[bright_green bold]AI[/]", classes="msg-label-ai"))
                    scroll.mount(ChatMessage("assistant", msg["content"]))

            scroll.scroll_end(animate=False)
            self.update_status()

            last_ai = [m for m in self.messages if m["role"] == "assistant"]
            if last_ai:
                self.last_ai_response = last_ai[-1]["content"]

            self.notify(f"Loaded: {chat_display_name(item.chat_path)}")

    # --- Commands ---

    def handle_command(self, cmd: str, full_text: str) -> None:
        if cmd == "/help":
            help_text = "\n".join(f"  {k:<12} {v}" for k, v in {
                "/new": "New conversation (Ctrl+N)",
                "/save": "Save conversation (Ctrl+S)",
                "/model": "Switch model (/model <id>)",
                "/system": "Set system prompt",
                "/copy": "Copy last response (Ctrl+C)",
                "/regen": "Regenerate (Ctrl+R)",
                "/clear": "Clear screen",
                "/quit": "Exit (Ctrl+Q)",
            }.items())
            self.notify(help_text, title="Commands", timeout=8)

        elif cmd == "/model":
            new_model = full_text[len("/model "):].strip()
            if new_model:
                self.model = new_model
                self.update_status()
                self.notify(f"Model: {self.model}")
            else:
                models = ", ".join(self.available_models[:5]) if self.available_models else "none found"
                self.notify(f"Available: {models}\nCurrent: {self.model}", title="Models", timeout=6)

        elif cmd == "/system":
            new_sys = full_text[len("/system "):].strip()
            if new_sys:
                self.system = new_sys
                self.notify(f"System prompt updated.")
            else:
                self.notify(f"Current: {self.system[:80]}...", timeout=6)

        elif cmd == "/clear":
            scroll = self.query_one("#messages-scroll", VerticalScroll)
            scroll.remove_children()
            self.show_welcome()

        elif cmd == "/save":
            self.action_save_chat()

        elif cmd == "/new":
            self.action_new_chat()

        elif cmd == "/copy":
            self.action_copy_last()

        elif cmd == "/regen":
            self.action_regen()

        elif cmd == "/quit":
            self.action_quit_app()

        else:
            self.notify(f"Unknown: {cmd}. Type /help", severity="warning")

    # --- Actions ---

    def action_new_chat(self) -> None:
        if self.messages:
            save_chat(self.messages, self.model)
            self.refresh_sidebar()

        self.messages = []
        self.last_ai_response = ""
        self.active_chat_path = None
        self.show_welcome()
        self.update_status()
        self.query_one("#chat-input", Input).focus()
        try:
            self.query_one("#action-bar").display = False
        except NoMatches:
            pass
        self.notify("New chat started.")

    def action_save_chat(self) -> None:
        if self.messages:
            filename = save_chat(self.messages, self.model)
            self.refresh_sidebar()
            self.notify(f"Saved: {filename}")
        else:
            self.notify("Nothing to save.", severity="warning")

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display

    def action_copy_last(self) -> None:
        if not self.last_ai_response:
            self.notify("No response to copy.", severity="warning")
            return
        try:
            if os.name == "nt":
                subprocess.run("clip", input=self.last_ai_response.encode("utf-8"), check=True)
            elif shutil.which("xclip"):
                subprocess.run(["xclip", "-selection", "clipboard"],
                               input=self.last_ai_response.encode(), check=True)
            elif shutil.which("pbcopy"):
                subprocess.run("pbcopy", input=self.last_ai_response.encode(), check=True)
            else:
                self.notify("No clipboard tool.", severity="error")
                return
            self.notify("Copied to clipboard.")
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_regen(self) -> None:
        if self.is_streaming:
            return
        if self.messages and self.messages[-1]["role"] == "assistant":
            self.messages.pop()
            # Remove last AI message from view (label + ChatMessage = 2 widgets)
            scroll = self.query_one("#messages-scroll", VerticalScroll)
            children = list(scroll.children)
            for child in children[-2:]:
                child.remove()

            # Re-send
            last_user = self.messages[-1]["content"] if self.messages else ""
            if last_user:
                self.send_message(last_user)
        else:
            self.notify("Nothing to regenerate.", severity="warning")

    def action_quit_app(self) -> None:
        if self.messages:
            save_chat(self.messages, self.model)
        self.exit()


if __name__ == "__main__":
    app = CodeGPT()
    app.run()
