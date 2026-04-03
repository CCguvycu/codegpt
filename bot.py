"""CodeGPT Telegram Bot — Full-featured AI assistant via Telegram + Ollama."""

import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests
from telegram import (
    Update, BotCommand, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, InlineQueryHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from telegram.constants import ChatAction, ParseMode

# --- Config ---

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"
VISION_MODEL = "llava"  # Change to your vision-capable model
MAX_HISTORY = 20
BOT_TOKEN = os.environ.get("CODEGPT_BOT_TOKEN", "")
ADMIN_IDS = []  # Add your Telegram user ID here for /admin access
ALLOWED_USERS = []  # Empty = open access

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
Deliver high-value, efficient, technically sharp responses with zero wasted words.

IMPORTANT: Format responses for Telegram. Use Markdown formatting.
Keep responses under 4000 characters when possible."""

# --- Personas ---

PERSONAS = {
    "default": SYSTEM_PROMPT,
    "hacker": (
        "You are a cybersecurity expert and ethical hacker. You speak in technical jargon, "
        "reference CVEs, talk about attack vectors and defense strategies. You're paranoid "
        "about security and see vulnerabilities everywhere. Dark humor about data breaches. "
        "Always ethical — defensive security only. Format for Telegram Markdown."
    ),
    "teacher": (
        "You are a patient programming teacher. You explain concepts step by step, "
        "use analogies, give examples, and check understanding. You encourage questions. "
        "You adapt your explanation level to the student. Format for Telegram Markdown."
    ),
    "roast": (
        "You are a brutally sarcastic code reviewer. You roast bad code mercilessly but "
        "always give the correct solution after. You use dark humor, compare bad code to "
        "disasters, and question life choices. But deep down you care. Format for Telegram Markdown."
    ),
    "architect": (
        "You are a senior system architect. You think in terms of scalability, "
        "distributed systems, microservices, and infrastructure. You draw ASCII diagrams. "
        "You always consider trade-offs. Format for Telegram Markdown."
    ),
    "minimal": (
        "You give the shortest possible answer. One line if possible. No explanation "
        "unless asked. Code only, no commentary. Format for Telegram Markdown."
    ),
}

# --- Daily Tips ---

DAILY_TIPS = [
    "Use `git stash` to temporarily save changes without committing.",
    "Python tip: `collections.Counter` counts hashable objects in one line.",
    "Security: Never store passwords in plain text. Use bcrypt or argon2.",
    "Docker tip: Use multi-stage builds to reduce image size by 80%+.",
    "bash: `ctrl+r` does reverse search through command history.",
    "Python: Use `__slots__` in classes to reduce memory usage by 40%.",
    "Networking: `curl -I` shows only HTTP headers — great for debugging.",
    "Git: `git bisect` binary-searches commits to find where a bug was introduced.",
    "Security: Use `nmap -sV` for service version detection on open ports.",
    "Python: `functools.lru_cache` adds memoization with one decorator.",
    "Linux: `htop` > `top`. Install it. Use it. Love it.",
    "API design: Use HTTP status codes correctly. 201 for created, 204 for no content.",
    "Python: `pathlib.Path` > `os.path`. It's cleaner and more Pythonic.",
    "Docker: `docker system prune -a` reclaims disk space from unused images.",
    "Git: `git log --oneline --graph --all` gives you the best commit visualization.",
    "Security: Set `HttpOnly` and `Secure` flags on all session cookies.",
    "Python: `dataclasses` save you from writing __init__, __repr__, __eq__.",
    "bash: `!!` repeats the last command. `sudo !!` runs it as root.",
    "Networking: DNS over HTTPS (DoH) prevents ISP snooping on your queries.",
    "Python: `breakpoint()` drops you into pdb. No imports needed (3.7+).",
    "Linux: `watch -n 1 command` runs a command every second and shows output.",
    "API: Rate limit everything. 429 is your friend, not your enemy.",
    "Git: `git cherry-pick <hash>` applies a single commit to your current branch.",
    "Python: `textwrap.dedent()` cleans up indented multi-line strings.",
    "Security: Use CSP headers to prevent XSS. `Content-Security-Policy: default-src 'self'`.",
    "Docker: `docker compose up -d` starts services detached. `logs -f` to tail.",
    "Python: `sys.getsizeof()` shows memory usage of any object in bytes.",
    "bash: `xargs` converts stdin to arguments. `find . -name '*.py' | xargs wc -l`.",
    "Networking: `ss -tlnp` shows listening TCP ports with process names.",
    "Python: `contextlib.suppress(Error)` is cleaner than try/except/pass.",
]

# --- Profiles ---

PROFILES_DIR = Path.home() / ".codegpt" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROFILE = {
    "display_name": "",
    "bio": "",
    "model": DEFAULT_MODEL,
    "persona": "default",
    "language": "en",
    "daily_tips": True,
    "code_autorun": False,
    "created": None,
}

LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
}


def load_profile(uid):
    """Load user profile from disk, or create default."""
    path = PROFILES_DIR / f"{uid}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            # Merge with defaults for any missing keys
            profile = {**DEFAULT_PROFILE, **data}
            return profile
        except Exception:
            pass
    return {**DEFAULT_PROFILE, "created": datetime.now().isoformat()}


def save_profile(uid, profile):
    """Save user profile to disk."""
    path = PROFILES_DIR / f"{uid}.json"
    path.write_text(json.dumps(profile, indent=2))


def get_profile_field(uid, field):
    """Get a single profile field."""
    return load_profile(uid).get(field, DEFAULT_PROFILE.get(field))


def set_profile_field(uid, field, value):
    """Set a single profile field and save."""
    profile = load_profile(uid)
    profile[field] = value
    save_profile(uid, profile)


# --- State ---

user_conversations = defaultdict(list)
user_models = defaultdict(lambda: DEFAULT_MODEL)
user_personas = defaultdict(lambda: "default")
user_stats = defaultdict(lambda: {"messages": 0, "first_seen": None, "last_seen": None})
rate_limits = defaultdict(list)  # user_id -> list of timestamps

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 15  # max messages per window

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# --- Helpers ---

def ensure_ollama():
    try:
        requests.get("http://localhost:11434/api/tags", timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        logger.info("Starting Ollama...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
        )
        for _ in range(30):
            time.sleep(2)
            try:
                requests.get("http://localhost:11434/api/tags", timeout=5)
                return True
            except (requests.ConnectionError, requests.Timeout):
                continue
        return False


def get_available_models():
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def is_allowed(user_id):
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def is_admin(user_id):
    return user_id in ADMIN_IDS


def check_rate_limit(user_id):
    """Returns True if user is within rate limit."""
    now = time.time()
    # Clean old entries
    rate_limits[user_id] = [t for t in rate_limits[user_id] if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limits[user_id]) >= RATE_LIMIT_MAX:
        return False
    rate_limits[user_id].append(now)
    return True


def track_user(user):
    """Track user stats and sync profile."""
    uid = user.id
    now = datetime.now().isoformat()
    if user_stats[uid]["first_seen"] is None:
        user_stats[uid]["first_seen"] = now
        user_stats[uid]["username"] = getattr(user, "username", None)
        user_stats[uid]["name"] = user.first_name
        # Load saved profile preferences
        profile = load_profile(uid)
        if not profile["display_name"]:
            profile["display_name"] = user.first_name
            profile["created"] = now
            save_profile(uid, profile)
        user_models[uid] = profile["model"]
        user_personas[uid] = profile["persona"]
    user_stats[uid]["last_seen"] = now
    user_stats[uid]["messages"] += 1


def query_ollama(messages, model, system=None):
    """Send messages to Ollama and return response (non-streaming)."""
    sys_prompt = system or SYSTEM_PROMPT
    ollama_messages = [{"role": "system", "content": sys_prompt}]
    ollama_messages.extend(messages)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": ollama_messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "No response.")
        ec = data.get("eval_count", 0)
        td = data.get("total_duration", 0)
        ds = td / 1e9 if td else 0
        tps = ec / ds if ds > 0 else 0
        stats = f"\n\n`{ec} tok | {ds:.1f}s | {tps:.0f} tok/s`"
        return content, stats

    except requests.ConnectionError:
        return "Error: Cannot connect to Ollama.", ""
    except requests.Timeout:
        return "Error: Request timed out.", ""
    except Exception as e:
        return f"Error: {e}", ""


def stream_ollama(messages, model, system=None):
    """Stream response from Ollama, yielding (full_text_so_far, is_done, stats) tuples."""
    sys_prompt = system or SYSTEM_PROMPT
    ollama_messages = [{"role": "system", "content": sys_prompt}]
    ollama_messages.extend(messages)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": ollama_messages, "stream": True},
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        full = []
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "message" in chunk and "content" in chunk["message"]:
                full.append(chunk["message"]["content"])

            if chunk.get("done"):
                ec = chunk.get("eval_count", 0)
                td = chunk.get("total_duration", 0)
                ds = td / 1e9 if td else 0
                tps = ec / ds if ds > 0 else 0
                stats = f"\n\n`{ec} tok | {ds:.1f}s | {tps:.0f} tok/s`"
                yield "".join(full), True, stats
            else:
                yield "".join(full), False, ""

    except requests.ConnectionError:
        yield "Error: Cannot connect to Ollama.", True, ""
    except requests.Timeout:
        yield "Error: Request timed out.", True, ""
    except Exception as e:
        yield f"Error: {e}", True, ""


def query_ollama_vision(prompt_text, image_bytes, model):
    """Send image + text to Ollama vision model."""
    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": prompt_text or "Describe this image in detail.",
                    "images": [b64],
                }],
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "No response."), ""
    except Exception as e:
        return f"Error: {e}", ""


async def safe_reply(message, text, parse_mode=ParseMode.MARKDOWN):
    """Send reply, falling back to plain text if markdown fails."""
    if len(text) <= 4096:
        try:
            await message.reply_text(text, parse_mode=parse_mode)
        except Exception:
            await message.reply_text(text)
    else:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            try:
                await message.reply_text(chunk, parse_mode=parse_mode)
            except Exception:
                await message.reply_text(chunk)


def extract_code_blocks(text):
    """Extract Python code blocks from markdown text."""
    pattern = r'```(?:python)?\s*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches


def run_python_code(code, timeout=10):
    """Execute Python code in a subprocess with timeout."""
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
        return "Error: Code execution timed out (10s limit).", 1
    except Exception as e:
        return f"Error: {e}", 1


# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    track_user(update.effective_user)
    user = update.effective_user.first_name

    keyboard = [
        [
            InlineKeyboardButton("Commands", callback_data="show_help"),
            InlineKeyboardButton("Profile", callback_data="show_profile"),
        ],
        [
            InlineKeyboardButton("Models", callback_data="show_models"),
            InlineKeyboardButton("Personas", callback_data="show_personas"),
        ],
    ]

    await update.message.reply_text(
        f"*CodeGPT*\n\n"
        f"Hey {user}. Your local AI assistant, on Telegram.\n\n"
        f"*Quick start:*\n"
        f"  Send a message to chat\n"
        f"  Send a voice note for voice chat\n"
        f"  Send a photo for image analysis\n"
        f"  Send a file to discuss it\n\n"
        f"Tap a button below or type /help",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    text = (
        "*Commands*\n\n"
        "*Chat*\n"
        "`/new` — New conversation\n"
        "`/run` — Execute last code block\n"
        "`/export` — Export chat as file\n"
        "`/tip` — Random coding tip\n\n"
        "*Profile*\n"
        "`/profile` — View & edit your profile\n"
        "`/setname` — Set display name\n"
        "`/setbio` — Set bio\n"
        "`/setlang` — Set language\n\n"
        "*Settings*\n"
        "`/model` — Switch model\n"
        "`/models` — List models\n"
        "`/persona` — Switch personality\n"
        "`/personas` — List personalities\n"
        "`/stats` — Your stats\n"
        "`/help` — This message\n"
    )
    if is_admin(update.effective_user.id):
        text += "\n*Admin*\n`/admin` — User stats & usage\n"

    await safe_reply(update.message, text)


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    count = len(user_conversations[uid])
    user_conversations[uid] = []
    await update.message.reply_text(f"Cleared. ({count} messages removed)")


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    if context.args:
        new_model = " ".join(context.args)
        user_models[uid] = new_model
        await safe_reply(update.message, f"Model: `{new_model}`")
    else:
        await safe_reply(update.message, f"Current: `{user_models[uid]}`\nUsage: `/model llama3.2`")


async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    models = get_available_models()
    current = user_models[uid]

    if models:
        lines = []
        for m in models:
            marker = " <" if m == current or m.startswith(current + ":") else ""
            lines.append(f"  `{m}`{marker}")
        text = "*Available Models*\n\n" + "\n".join(lines)
    else:
        text = "No models found."

    await safe_reply(update.message, text)


async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    if context.args:
        name = context.args[0].lower()
        if name in PERSONAS:
            user_personas[uid] = name
            await update.message.reply_text(f"Persona: {name}")
        else:
            available = ", ".join(PERSONAS.keys())
            await update.message.reply_text(f"Unknown persona. Available: {available}")
    else:
        current = user_personas[uid]
        await update.message.reply_text(f"Current: {current}\nUsage: /persona hacker")


async def personas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    keyboard = []
    row = []
    for name in PERSONAS:
        row.append(InlineKeyboardButton(name.title(), callback_data=f"persona_{name}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    uid = update.effective_user.id
    current = user_personas[uid]

    await update.message.reply_text(
        f"*Personas*\nCurrent: {current}\n\nTap to switch:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute the last code block from AI response."""
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    # Find last AI message with code
    for msg in reversed(user_conversations[uid]):
        if msg["role"] == "assistant":
            blocks = extract_code_blocks(msg["content"])
            if blocks:
                code = blocks[-1]  # Run the last code block
                await update.message.reply_text(f"Running...\n```python\n{code[:200]}{'...' if len(code) > 200 else ''}\n```", parse_mode=ParseMode.MARKDOWN)

                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                output, returncode = run_python_code(code)

                status = "OK" if returncode == 0 else "FAIL"
                result = f"*Output* ({status}):\n```\n{output[:3000]}\n```"
                await safe_reply(update.message, result)
                return

    await update.message.reply_text("No code blocks found in recent messages.")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export conversation as a text file."""
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    messages = user_conversations[uid]

    if not messages:
        await update.message.reply_text("No messages to export.")
        return

    # Build text file
    lines = [f"CodeGPT Chat Export — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    lines.append(f"Model: {user_models[uid]}")
    lines.append(f"Persona: {user_personas[uid]}")
    lines.append(f"Messages: {len(messages)}\n")
    lines.append("=" * 60 + "\n")

    for msg in messages:
        role = "YOU" if msg["role"] == "user" else "AI"
        lines.append(f"[{role}]")
        lines.append(msg["content"])
        lines.append("")

    content = "\n".join(lines)
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = f"codegpt_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

    await update.message.reply_document(document=buf, caption="Chat exported.")


async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a random coding tip."""
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    import random
    tip = random.choice(DAILY_TIPS)
    await update.message.reply_text(f"*Tip of the moment:*\n\n{tip}", parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    s = user_stats[uid]
    model = user_models[uid]
    persona = user_personas[uid]
    history = len(user_conversations[uid])

    await safe_reply(update.message,
        f"*Your Stats*\n\n"
        f"Model: `{model}`\n"
        f"Persona: `{persona}`\n"
        f"Messages sent: {s['messages']}\n"
        f"History: {history}/{MAX_HISTORY}\n"
        f"First seen: {s['first_seen'][:16] if s['first_seen'] else 'now'}\n"
        f"Rate limit: {RATE_LIMIT_MAX}/{RATE_LIMIT_WINDOW}s"
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel — usage stats."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return

    total_users = len(user_stats)
    total_messages = sum(s["messages"] for s in user_stats.values())
    active_convos = sum(1 for c in user_conversations.values() if c)

    text = (
        f"*Admin Panel*\n\n"
        f"Total users: {total_users}\n"
        f"Total messages: {total_messages}\n"
        f"Active conversations: {active_convos}\n\n"
    )

    # Top users
    if user_stats:
        text += "*Top Users:*\n"
        sorted_users = sorted(user_stats.items(), key=lambda x: x[1]["messages"], reverse=True)
        for uid, s in sorted_users[:10]:
            name = s.get("name", "Unknown")
            username = s.get("username", "")
            uname = f" (@{username})" if username else ""
            text += f"  {name}{uname}: {s['messages']} msgs\n"

    # Models in use
    if user_models:
        model_counts = defaultdict(int)
        for m in user_models.values():
            model_counts[m] += 1
        text += "\n*Models in use:*\n"
        for m, count in model_counts.items():
            text += f"  `{m}`: {count} users\n"

    await safe_reply(update.message, text)


# --- Profile ---

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user profile card with edit buttons."""
    if not is_allowed(update.effective_user.id):
        return
    track_user(update.effective_user)

    uid = update.effective_user.id
    profile = load_profile(uid)
    s = user_stats[uid]
    username = getattr(update.effective_user, "username", None)

    # Profile card
    name = profile["display_name"] or update.effective_user.first_name
    bio = profile["bio"] or "No bio set"
    model = profile["model"]
    persona = profile["persona"]
    lang = LANGUAGES.get(profile["language"], profile["language"])
    tips = "On" if profile["daily_tips"] else "Off"
    autorun = "On" if profile["code_autorun"] else "Off"
    msgs = s["messages"]
    since = profile["created"][:10] if profile.get("created") else "today"

    text = (
        f"*Your Profile*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Name:* {name}\n"
        f"{'@' + username if username else ''}\n"
        f"*Bio:* {bio}\n\n"
        f"*Model:* `{model}`\n"
        f"*Persona:* {persona}\n"
        f"*Language:* {lang}\n"
        f"*Daily tips:* {tips}\n"
        f"*Code autorun:* {autorun}\n\n"
        f"*Messages:* {msgs}\n"
        f"*Member since:* {since}\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("Edit Name", callback_data="profile_edit_name"),
            InlineKeyboardButton("Edit Bio", callback_data="profile_edit_bio"),
        ],
        [
            InlineKeyboardButton("Model", callback_data="profile_pick_model"),
            InlineKeyboardButton("Persona", callback_data="profile_pick_persona"),
        ],
        [
            InlineKeyboardButton("Language", callback_data="profile_pick_lang"),
            InlineKeyboardButton("Tips: " + tips, callback_data="profile_toggle_tips"),
        ],
        [
            InlineKeyboardButton("Autorun: " + autorun, callback_data="profile_toggle_autorun"),
            InlineKeyboardButton("Reset Profile", callback_data="profile_reset"),
        ],
    ]

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def setname_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick set display name: /setname <name>"""
    if not is_allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    if context.args:
        name = " ".join(context.args)[:30]
        set_profile_field(uid, "display_name", name)
        await update.message.reply_text(f"Name set: *{name}*", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Usage: `/setname Your Name`", parse_mode=ParseMode.MARKDOWN)


async def setbio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick set bio: /setbio <text>"""
    if not is_allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    if context.args:
        bio = " ".join(context.args)[:160]
        set_profile_field(uid, "bio", bio)
        await update.message.reply_text(f"Bio set: _{bio}_", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Usage: `/setbio I build things`", parse_mode=ParseMode.MARKDOWN)


async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick set language: /setlang <code>"""
    if not is_allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    if context.args:
        code = context.args[0].lower()
        if code in LANGUAGES:
            set_profile_field(uid, "language", code)
            # Update system prompt to include language preference
            await update.message.reply_text(f"Language: {LANGUAGES[code]}")
        else:
            langs = ", ".join(f"`{k}`={v}" for k, v in LANGUAGES.items())
            await update.message.reply_text(f"Available:\n{langs}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Usage: `/setlang en`", parse_mode=ParseMode.MARKDOWN)


# --- Message Handlers ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages with live streaming updates."""
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    uid = update.effective_user.id
    track_user(update.effective_user)

    if not check_rate_limit(uid):
        await update.message.reply_text(f"Slow down. Max {RATE_LIMIT_MAX} messages per {RATE_LIMIT_WINDOW}s.")
        return

    user_text = update.message.text
    if not user_text:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    user_conversations[uid].append({"role": "user", "content": user_text})
    if len(user_conversations[uid]) > MAX_HISTORY:
        user_conversations[uid] = user_conversations[uid][-MAX_HISTORY:]

    model = user_models[uid]
    persona = user_personas[uid]
    system = PERSONAS.get(persona, SYSTEM_PROMPT)

    # Send initial "thinking" message
    live_msg = await update.message.reply_text("Thinking...")

    # Stream with live edits
    last_edit = 0
    last_text = ""
    response_text = ""
    stats = ""
    edit_interval = 1.0  # Edit at most once per second (Telegram rate limit)
    token_count = 0

    for text_so_far, is_done, chunk_stats in stream_ollama(user_conversations[uid], model, system):
        response_text = text_so_far
        token_count = len(text_so_far.split())
        now = time.time()

        if is_done:
            stats = chunk_stats
            break

        # Update message periodically
        if now - last_edit >= edit_interval and text_so_far != last_text:
            display = text_so_far + f"\n\n_streaming... {token_count} words_"
            if len(display) > 4096:
                display = display[-4000:]
            try:
                await live_msg.edit_text(display, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                try:
                    await live_msg.edit_text(display)
                except Exception:
                    pass
            last_edit = now
            last_text = text_so_far

    # Final edit with complete response
    # Only append to history if we got a real response (not an error string)
    if response_text and not response_text.startswith("Error:"):
        user_conversations[uid].append({"role": "assistant", "content": response_text})
        if len(user_conversations[uid]) > MAX_HISTORY:
            user_conversations[uid] = user_conversations[uid][-MAX_HISTORY:]
    else:
        # Remove the user message we already appended since request failed
        if user_conversations[uid] and user_conversations[uid][-1]["role"] == "user":
            user_conversations[uid].pop()

    # Check for code blocks
    code_blocks = extract_code_blocks(response_text)
    reply_markup = None
    if code_blocks:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("Run Code", callback_data="run_code"),
            InlineKeyboardButton("Copy", callback_data="copy_code"),
        ]])

    full = response_text + stats
    if len(full) <= 4096:
        try:
            await live_msg.edit_text(full, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception:
            try:
                await live_msg.edit_text(full, reply_markup=reply_markup)
            except Exception:
                pass
    else:
        # For long responses, edit with truncated version + send rest as new messages
        try:
            await live_msg.edit_text(full[:4000] + "\n\n_...continued below_", parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await live_msg.edit_text(full[:4000])

        remaining = full[4000:]
        chunks = [remaining[i:i+4000] for i in range(0, len(remaining), 4000)]
        for i, chunk in enumerate(chunks):
            rm = reply_markup if i == len(chunks) - 1 else None
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=rm)
            except Exception:
                await update.message.reply_text(chunk, reply_markup=rm)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages — transcribe with Whisper then respond."""
    if not is_allowed(update.effective_user.id):
        return

    uid = update.effective_user.id
    track_user(update.effective_user)

    if not check_rate_limit(uid):
        await update.message.reply_text(f"Slow down. Rate limited.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Download voice file
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        ogg_path = os.path.join(tmpdir, "voice.ogg")
        wav_path = os.path.join(tmpdir, "voice.wav")

        await file.download_to_drive(ogg_path)

        # Convert OGG to WAV with ffmpeg
        try:
            subprocess.run(
                ["ffmpeg", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
                capture_output=True, timeout=15,
            )
        except FileNotFoundError:
            await update.message.reply_text(
                "Voice not supported: ffmpeg not installed.\n"
                "Install: `winget install ffmpeg` or `choco install ffmpeg`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        except Exception as e:
            await update.message.reply_text(f"Audio conversion failed: {e}")
            return

        if not os.path.exists(wav_path):
            await update.message.reply_text("Audio conversion failed.")
            return

        # Transcribe with speech_recognition
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            transcript = recognizer.recognize_google(audio_data)
        except ImportError:
            await update.message.reply_text(
                "Voice not supported: install `SpeechRecognition`\n"
                "`pip install SpeechRecognition`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        except sr.UnknownValueError:
            await update.message.reply_text("Could not understand the audio.")
            return
        except Exception as e:
            await update.message.reply_text(f"Transcription failed: {e}")
            return

    # Show what was heard
    await update.message.reply_text(f"_Heard:_ {transcript}", parse_mode=ParseMode.MARKDOWN)

    # Process as regular message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    user_conversations[uid].append({"role": "user", "content": transcript})
    if len(user_conversations[uid]) > MAX_HISTORY:
        user_conversations[uid] = user_conversations[uid][-MAX_HISTORY:]

    model = user_models[uid]
    persona = user_personas[uid]
    system = PERSONAS.get(persona, SYSTEM_PROMPT)

    response_text, stats = query_ollama(user_conversations[uid], model, system)
    user_conversations[uid].append({"role": "assistant", "content": response_text})

    await safe_reply(update.message, response_text + stats)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photos — analyze with vision model."""
    if not is_allowed(update.effective_user.id):
        return

    uid = update.effective_user.id
    track_user(update.effective_user)

    if not check_rate_limit(uid):
        await update.message.reply_text("Rate limited.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Get the largest photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    # Download to bytes
    photo_bytes = await file.download_as_bytearray()

    caption = update.message.caption or "Describe this image in detail. If it contains code, analyze it."

    await update.message.reply_text(f"_Analyzing image with {VISION_MODEL}..._", parse_mode=ParseMode.MARKDOWN)

    response_text, stats = query_ollama_vision(caption, bytes(photo_bytes), VISION_MODEL)

    # Add to conversation as text
    user_conversations[uid].append({"role": "user", "content": f"[Image sent] {caption}"})
    user_conversations[uid].append({"role": "assistant", "content": response_text})

    await safe_reply(update.message, response_text + stats)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle file uploads — read and discuss."""
    if not is_allowed(update.effective_user.id):
        return

    uid = update.effective_user.id
    track_user(update.effective_user)

    if not check_rate_limit(uid):
        await update.message.reply_text("Rate limited.")
        return

    doc = update.message.document
    if not doc:
        return

    # Size limit: 1MB
    if doc.file_size and doc.file_size > 1_000_000:
        await update.message.reply_text("File too large. Max 1MB.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()

    # Try to decode as text
    try:
        content = bytes(file_bytes).decode("utf-8")
    except UnicodeDecodeError:
        await update.message.reply_text("Cannot read file. Only text/code files are supported.")
        return

    # Truncate if too long
    if len(content) > 8000:
        content = content[:8000] + "\n\n... (truncated)"

    caption = update.message.caption or "Analyze this file."
    prompt = f"File: {doc.file_name}\n\n```\n{content}\n```\n\n{caption}"

    user_conversations[uid].append({"role": "user", "content": prompt})
    if len(user_conversations[uid]) > MAX_HISTORY:
        user_conversations[uid] = user_conversations[uid][-MAX_HISTORY:]

    model = user_models[uid]
    persona = user_personas[uid]
    system = PERSONAS.get(persona, SYSTEM_PROMPT)

    response_text, stats = query_ollama(user_conversations[uid], model, system)
    user_conversations[uid].append({"role": "assistant", "content": response_text})

    await safe_reply(update.message, response_text + stats)


# --- Inline Mode ---

async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries — @botname <query> in any chat."""
    query = update.inline_query.query.strip()
    if not query:
        return

    uid = update.inline_query.from_user.id
    if not is_allowed(uid):
        return

    # Quick query — no conversation history
    model = user_models[uid]
    response_text, _ = query_ollama(
        [{"role": "user", "content": query}],
        model,
        "Be extremely concise. Max 200 words. Format for Telegram.",
    )

    results = [
        InlineQueryResultArticle(
            id="1",
            title=f"CodeGPT: {query[:50]}",
            description=response_text[:100],
            input_message_content=InputTextMessageContent(
                f"*Q:* {query}\n\n*A:* {response_text}",
                parse_mode=ParseMode.MARKDOWN,
            ),
        )
    ]

    await update.inline_query.answer(results, cache_time=30)


# --- Callback Handlers ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if data == "show_help":
        text = (
            "*Commands*\n\n"
            "/new — New conversation\n"
            "/model — Switch model\n"
            "/persona — Switch personality\n"
            "/run — Execute code block\n"
            "/export — Export chat\n"
            "/tip — Coding tip\n"
            "/stats — Your stats"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "show_profile":
        profile = load_profile(uid)
        name = profile["display_name"] or "Not set"
        bio = profile["bio"] or "Not set"
        model = profile["model"]
        persona = profile["persona"]
        lang = LANGUAGES.get(profile["language"], profile["language"])
        text = (
            f"*Your Profile*\n\n"
            f"*Name:* {name}\n"
            f"*Bio:* {bio}\n"
            f"*Model:* `{model}`\n"
            f"*Persona:* {persona}\n"
            f"*Language:* {lang}\n\n"
            f"Type /profile for full view with edit buttons."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "show_models":
        models = get_available_models()
        current = user_models[uid]
        if models:
            lines = [f"  {'>' if m.startswith(current) else ' '} {m}" for m in models]
            text = "*Models*\n\n" + "\n".join(lines)
        else:
            text = "No models found."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "show_personas":
        current = user_personas[uid]
        lines = [f"  {'>' if k == current else ' '} {k}" for k in PERSONAS]
        text = "*Personas*\n\n" + "\n".join(lines) + "\n\nUse: /persona <name>"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("persona_"):
        name = data[8:]
        if name in PERSONAS:
            user_personas[uid] = name
            await query.edit_message_text(f"Persona switched to: *{name}*", parse_mode=ParseMode.MARKDOWN)

    elif data == "run_code":
        # Find last code block in conversation
        for msg in reversed(user_conversations[uid]):
            if msg["role"] == "assistant":
                blocks = extract_code_blocks(msg["content"])
                if blocks:
                    code = blocks[-1]
                    output, rc = run_python_code(code)
                    status = "OK" if rc == 0 else "FAIL"
                    result = f"*Output* ({status}):\n```\n{output[:3000]}\n```"
                    try:
                        await query.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        await query.message.reply_text(f"Output ({status}):\n{output[:3000]}")
                    return
        await query.message.reply_text("No code blocks found.")

    elif data == "copy_code":
        for msg in reversed(user_conversations[uid]):
            if msg["role"] == "assistant":
                blocks = extract_code_blocks(msg["content"])
                if blocks:
                    code = blocks[-1]
                    await query.message.reply_text(f"```python\n{code}\n```", parse_mode=ParseMode.MARKDOWN)
                    return
        await query.message.reply_text("No code blocks found.")

    # --- Profile callbacks ---

    elif data == "profile_edit_name":
        await query.edit_message_text(
            "Send your new name with:\n`/setname Your Name`",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "profile_edit_bio":
        await query.edit_message_text(
            "Send your bio with:\n`/setbio I build cool stuff`",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "profile_pick_model":
        models = get_available_models()
        if models:
            keyboard = []
            row = []
            for m in models[:12]:
                short = m.split(":")[0] if ":" in m else m
                row.append(InlineKeyboardButton(short, callback_data=f"pmodel_{m}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            await query.edit_message_text(
                "*Pick a model:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await query.edit_message_text("No models found.")

    elif data.startswith("pmodel_"):
        model = data[7:]
        user_models[uid] = model
        set_profile_field(uid, "model", model)
        await query.edit_message_text(f"Model set: `{model}`\n\nType /profile to see your profile.", parse_mode=ParseMode.MARKDOWN)

    elif data == "profile_pick_persona":
        keyboard = []
        row = []
        for name in PERSONAS:
            row.append(InlineKeyboardButton(name.title(), callback_data=f"ppersona_{name}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        await query.edit_message_text(
            "*Pick a persona:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("ppersona_"):
        name = data[9:]
        if name in PERSONAS:
            user_personas[uid] = name
            set_profile_field(uid, "persona", name)
            await query.edit_message_text(f"Persona: *{name}*\n\nType /profile to see your profile.", parse_mode=ParseMode.MARKDOWN)

    elif data == "profile_pick_lang":
        keyboard = []
        row = []
        for code, lang_name in LANGUAGES.items():
            row.append(InlineKeyboardButton(f"{lang_name}", callback_data=f"plang_{code}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        await query.edit_message_text(
            "*Pick a language:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("plang_"):
        code = data[6:]
        if code in LANGUAGES:
            set_profile_field(uid, "language", code)
            await query.edit_message_text(f"Language: {LANGUAGES[code]}\n\nType /profile to see your profile.", parse_mode=ParseMode.MARKDOWN)

    elif data == "profile_toggle_tips":
        current = get_profile_field(uid, "daily_tips")
        set_profile_field(uid, "daily_tips", not current)
        state = "On" if not current else "Off"
        await query.edit_message_text(f"Daily tips: *{state}*\n\nType /profile to see your profile.", parse_mode=ParseMode.MARKDOWN)

    elif data == "profile_toggle_autorun":
        current = get_profile_field(uid, "code_autorun")
        set_profile_field(uid, "code_autorun", not current)
        state = "On" if not current else "Off"
        await query.edit_message_text(f"Code autorun: *{state}*\n\nType /profile to see your profile.", parse_mode=ParseMode.MARKDOWN)

    elif data == "profile_reset":
        profile = {**DEFAULT_PROFILE, "display_name": query.from_user.first_name, "created": datetime.now().isoformat()}
        save_profile(uid, profile)
        user_models[uid] = DEFAULT_MODEL
        user_personas[uid] = "default"
        await query.edit_message_text("Profile reset to defaults.\n\nType /profile to see your profile.", parse_mode=ParseMode.MARKDOWN)


# --- Scheduled Tasks ---

async def send_daily_tip(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily tip to users who have tips enabled."""
    import random
    tip = random.choice(DAILY_TIPS)
    for uid, stats in user_stats.items():
        if stats.get("last_seen"):
            # Check profile — only send if tips enabled
            if not get_profile_field(uid, "daily_tips"):
                continue
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"*Daily Tip*\n\n{tip}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass  # User may have blocked the bot


# --- Error Handler ---

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("Something went wrong. Try again.")


# --- Main ---

def main():
    if not BOT_TOKEN:
        print("Error: No bot token.")
        print("  Set: export CODEGPT_BOT_TOKEN='your-token'")
        print("  Get token from @BotFather on Telegram.")
        return

    if not ensure_ollama():
        print("Error: Could not start Ollama.")
        return

    print("=" * 50)
    print("  CodeGPT Telegram Bot")
    print("=" * 50)
    print(f"  Model:    {DEFAULT_MODEL}")
    print(f"  Vision:   {VISION_MODEL}")
    print(f"  Ollama:   {OLLAMA_URL}")
    print(f"  Access:   {'restricted' if ALLOWED_USERS else 'open'}")
    print(f"  Admins:   {ADMIN_IDS or 'none'}")
    print(f"  Rate:     {RATE_LIMIT_MAX} msgs / {RATE_LIMIT_WINDOW}s")
    print("=" * 50)
    print("  Bot running. Ctrl+C to stop.\n")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("models", models_command))
    app.add_handler(CommandHandler("persona", persona_command))
    app.add_handler(CommandHandler("personas", personas_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("tip", tip_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("setname", setname_command))
    app.add_handler(CommandHandler("setbio", setbio_command))
    app.add_handler(CommandHandler("setlang", setlang_command))

    # Message types
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Inline mode
    app.add_handler(InlineQueryHandler(handle_inline))

    # Callbacks (button presses)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Error handler
    app.add_error_handler(error_handler)

    # Daily tip at 9:00 AM
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_daily(
            send_daily_tip,
            time=datetime.strptime("09:00", "%H:%M").time(),
            name="daily_tip",
        )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
