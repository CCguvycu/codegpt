"""CodeGPT Desktop — Claude Code + OpenClaw style GUI."""
import json
import threading
import requests
import webview
import os
import time
from pathlib import Path

# Config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = "llama3.2"
SYSTEM = "You are a helpful AI assistant. Be concise and technical."

# Load saved URL
saved_url = Path.home() / ".codegpt" / "ollama_url"
if saved_url.exists():
    url = saved_url.read_text().strip()
    if url:
        OLLAMA_URL = url
        if "/api/chat" not in OLLAMA_URL:
            OLLAMA_URL = OLLAMA_URL.rstrip("/") + "/api/chat"

# Try connect
def try_connect(url):
    try:
        base = url.replace("/api/chat", "/api/tags")
        r = requests.get(base, timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except:
        return []

# Auto-detect Ollama
if not try_connect(OLLAMA_URL):
    for fallback in ["http://localhost:11434/api/chat", "http://127.0.0.1:11434/api/chat"]:
        if try_connect(fallback):
            OLLAMA_URL = fallback
            break

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


class Api:
    """Python bridge — handles Ollama calls for the JS frontend."""

    def __init__(self):
        self.messages = []
        self.total_tokens = 0

    def check_status(self):
        try:
            r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
            models = [m["name"] for m in r.json().get("models", [])]
            return json.dumps({"online": True, "models": models, "model": MODEL})
        except:
            return json.dumps({"online": False, "models": [], "model": MODEL})

    def send_message(self, text):
        self.messages.append({"role": "user", "content": text})

        try:
            start = time.time()
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": [{"role": "system", "content": SYSTEM}] + self.messages,
                    "stream": False,
                },
                timeout=120,
            )
            data = resp.json()
            content = data.get("message", {}).get("content", "No response.")
            elapsed = round(time.time() - start, 1)
            tokens = data.get("eval_count", 0)
            self.total_tokens += tokens
            self.messages.append({"role": "assistant", "content": content})

            return json.dumps({
                "content": content,
                "tokens": tokens,
                "elapsed": elapsed,
                "total_tokens": self.total_tokens,
            })
        except Exception as e:
            return json.dumps({
                "content": f"Error: {str(e)}",
                "tokens": 0,
                "elapsed": 0,
                "total_tokens": self.total_tokens,
            })

    def new_chat(self):
        self.messages = []
        return "ok"

    def get_username(self):
        return USERNAME


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --dim: #7d8590;
    --accent: #58a6ff;
    --red: #f85149;
    --green: #3fb950;
    --user-bg: #1c2128;
}

body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', -apple-system, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.header h1 { font-size: 16px; font-weight: 600; }
.header h1 .code { color: var(--red); }
.header h1 .gpt { color: var(--accent); }
.header-info { font-size: 12px; color: var(--dim); }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
.dot.on { background: var(--green); }
.dot.off { background: var(--red); }

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
}

.msg { margin-bottom: 16px; animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; } }

.msg .role {
    font-size: 12px; font-weight: 600; margin-bottom: 4px;
    display: flex; align-items: center; gap: 6px;
}
.msg .icon {
    width: 18px; height: 18px; border-radius: 4px;
    display: inline-flex; align-items: center; justify-content: center; font-size: 10px;
}
.msg.user .role { color: var(--accent); }
.msg.user .icon { background: var(--accent); color: var(--bg); }
.msg.ai .role { color: var(--green); }
.msg.ai .icon { background: var(--green); color: var(--bg); }

.msg .body {
    font-size: 14px; line-height: 1.6; padding: 10px 14px;
    white-space: pre-wrap; word-wrap: break-word;
}
.msg.user .body { background: var(--user-bg); border: 1px solid var(--border); border-radius: 8px; }
.msg.ai .body { border-left: 2px solid var(--green); padding-left: 14px; }

.msg .body code { background: var(--surface); padding: 2px 6px; border-radius: 4px; font-family: 'Cascadia Code', monospace; font-size: 13px; }
.msg .body pre { background: var(--surface); padding: 12px; border-radius: 8px; margin: 8px 0; border: 1px solid var(--border); overflow-x: auto; }
.msg .body pre code { background: none; padding: 0; }
.msg .stats { font-size: 11px; color: var(--dim); margin-top: 4px; }

.thinking { display: none; color: var(--dim); font-size: 13px; margin-bottom: 16px; }
.thinking.on { display: block; }
.thinking .d span { animation: blink 1.4s infinite; }
.thinking .d span:nth-child(2) { animation-delay: 0.2s; }
.thinking .d span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,100% { opacity: 0.2; } 50% { opacity: 1; } }

.input-area { background: var(--surface); border-top: 1px solid var(--border); padding: 12px 20px; }
.input-wrap { display: flex; gap: 8px; align-items: flex-end; }
.input-wrap textarea {
    flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); padding: 10px 14px; font-size: 14px; font-family: inherit;
    resize: none; outline: none; min-height: 42px; max-height: 120px;
}
.input-wrap textarea:focus { border-color: var(--accent); }
.input-wrap button {
    background: var(--accent); border: none; border-radius: 8px; color: white;
    padding: 10px 16px; font-size: 14px; cursor: pointer; font-weight: 600;
}
.input-wrap button:hover { opacity: 0.9; }
.input-wrap button:disabled { opacity: 0.4; cursor: default; }

.footer {
    background: var(--surface); border-top: 1px solid var(--border);
    padding: 6px 20px; font-size: 11px; color: var(--dim);
    display: flex; justify-content: space-between;
}

.welcome { text-align: center; padding: 60px 20px; color: var(--dim); }
.welcome h2 { font-size: 24px; margin-bottom: 8px; color: var(--text); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 24px; }
.chips button {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); padding: 8px 14px; font-size: 13px; cursor: pointer;
}
.chips button:hover { border-color: var(--accent); color: var(--accent); }

.new-btn {
    background: transparent; border: 1px solid var(--border); border-radius: 6px;
    color: var(--dim); padding: 4px 10px; font-size: 11px; cursor: pointer;
}
.new-btn:hover { border-color: var(--accent); color: var(--accent); }
</style>
</head>
<body>

<div class="header">
    <h1><span class="code">Code</span><span class="gpt">GPT</span> <span style="color:#7d8590;font-weight:400;font-size:13px">Desktop</span></h1>
    <div class="header-info">
        <span class="dot" id="dot"></span><span id="st"></span>
        &middot; <span id="mn"></span>
        &middot; <button class="new-btn" onclick="newChat()">New Chat</button>
    </div>
</div>

<div class="messages" id="msgs">
    <div class="welcome" id="welcome">
        <h2 id="greeting"></h2>
        <p>Type a message or pick a suggestion.</p>
        <div class="chips">
            <button onclick="go('Explain how REST APIs work')">REST APIs</button>
            <button onclick="go('Write a Python function to find prime numbers')">Prime numbers</button>
            <button onclick="go('What are the OWASP top 10?')">OWASP Top 10</button>
            <button onclick="go('Design a login system with JWT')">JWT Auth</button>
        </div>
    </div>
    <div class="thinking" id="think"><span class="d">Thinking<span>.</span><span>.</span><span>.</span></span></div>
</div>

<div class="input-area">
    <div class="input-wrap">
        <textarea id="inp" placeholder="Type a message..." rows="1" onkeydown="key(event)" autofocus></textarea>
        <button onclick="send()" id="btn">Send</button>
    </div>
</div>

<div class="footer">
    <span id="tc">0 tokens</span>
    <span>CodeGPT v2.0 &middot; Local AI &middot; Ollama</span>
</div>

<script>
let busy = false;

async function init() {
    const name = await pywebview.api.get_username();
    const h = new Date().getHours();
    const g = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    document.getElementById('greeting').textContent = g + ', ' + name + '.';
    checkStatus();
    setInterval(checkStatus, 30000);
}

async function checkStatus() {
    const r = JSON.parse(await pywebview.api.check_status());
    document.getElementById('dot').className = 'dot ' + (r.online ? 'on' : 'off');
    document.getElementById('st').textContent = r.online ? 'connected' : 'offline';
    document.getElementById('mn').textContent = r.model;
}

function esc(t) {
    t = t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    t = t.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    return t;
}

function addMsg(role, content, stats) {
    const w = document.getElementById('welcome');
    if (w) w.style.display = 'none';
    const d = document.createElement('div');
    d.className = 'msg ' + role;
    const icon = role === 'user' ? 'U' : 'AI';
    const label = role === 'user' ? 'You' : 'CodeGPT';
    d.innerHTML = '<div class="role"><span class="icon">' + icon + '</span>' + label + '</div>'
        + '<div class="body">' + esc(content) + '</div>'
        + (stats ? '<div class="stats">' + stats + '</div>' : '');
    const c = document.getElementById('msgs');
    c.insertBefore(d, document.getElementById('think'));
    c.scrollTop = c.scrollHeight;
}

function key(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function go(t) { document.getElementById('inp').value = t; send(); }

async function newChat() {
    await pywebview.api.new_chat();
    document.getElementById('msgs').innerHTML =
        '<div class="welcome" id="welcome"><h2 id="greeting">New conversation</h2><p>Type a message.</p></div>'
        + '<div class="thinking" id="think"><span class="d">Thinking<span>.</span><span>.</span><span>.</span></span></div>';
}

async function send() {
    const inp = document.getElementById('inp');
    const text = inp.value.trim();
    if (!text || busy) return;
    inp.value = ''; inp.style.height = 'auto';
    busy = true;
    document.getElementById('btn').disabled = true;
    addMsg('user', text);
    document.getElementById('think').className = 'thinking on';

    const r = JSON.parse(await pywebview.api.send_message(text));
    document.getElementById('think').className = 'thinking';
    addMsg('ai', r.content, r.tokens + ' tokens · ' + r.elapsed + 's');
    document.getElementById('tc').textContent = r.total_tokens.toLocaleString() + ' tokens';

    busy = false;
    document.getElementById('btn').disabled = false;
    inp.focus();
}

window.addEventListener('pywebviewready', init);
</script>
</body>
</html>
"""


def main():
    api = Api()
    window = webview.create_window(
        "CodeGPT",
        html=HTML,
        js_api=api,
        width=800,
        height=650,
        min_size=(400, 400),
        background_color="#0d1117",
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
