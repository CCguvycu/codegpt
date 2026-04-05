"""CodeGPT Desktop — Claude + ChatGPT + OpenClaw style GUI."""
import json
import time
import requests
import webview
import os
from pathlib import Path
from datetime import datetime

# Config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = "llama3.2"
SYSTEM = "You are a helpful AI assistant. Be concise and technical."

saved_url = Path.home() / ".codegpt" / "ollama_url"
if saved_url.exists():
    url = saved_url.read_text().strip()
    if url:
        OLLAMA_URL = url
        if "/api/chat" not in OLLAMA_URL:
            OLLAMA_URL = OLLAMA_URL.rstrip("/") + "/api/chat"

def try_connect(url):
    try:
        r = requests.get(url.replace("/api/chat", "/api/tags"), timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except:
        return []

if not try_connect(OLLAMA_URL):
    for fb in ["http://localhost:11434/api/chat", "http://127.0.0.1:11434/api/chat"]:
        if try_connect(fb):
            OLLAMA_URL = fb
            break

profile_file = Path.home() / ".codegpt" / "profiles" / "cli_profile.json"
USERNAME = "User"
PERSONA = "default"
if profile_file.exists():
    try:
        p = json.loads(profile_file.read_text())
        USERNAME = p.get("name", "User")
        MODEL = p.get("model", MODEL)
        PERSONA = p.get("persona", "default")
    except:
        pass

OLLAMA_BASE = OLLAMA_URL.replace("/api/chat", "")
CHATS_DIR = Path.home() / ".codegpt" / "desktop_chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

PERSONAS = {
    "default": "You are a helpful AI assistant. Be concise and technical.",
    "hacker": "You are a cybersecurity expert. Technical jargon, CVEs, defensive security. Dark humor.",
    "teacher": "You are a patient programming teacher. Step by step, analogies, examples.",
    "roast": "You are a brutally sarcastic code reviewer. Roast bad code but always give the fix.",
    "architect": "You are a senior system architect. Scalability, distributed systems, ASCII diagrams.",
    "minimal": "Shortest possible answer. One line if possible. Code only.",
}


class Api:
    def __init__(self):
        self.messages = []
        self.total_tokens = 0
        self.model = MODEL
        self.persona = PERSONA
        self.system = PERSONAS.get(PERSONA, SYSTEM)
        self.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def check_status(self):
        try:
            r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
            models = [m["name"] for m in r.json().get("models", [])]
            return json.dumps({"online": True, "models": models, "model": self.model, "persona": self.persona})
        except:
            return json.dumps({"online": False, "models": [], "model": self.model, "persona": self.persona})

    def send_message(self, text):
        self.messages.append({"role": "user", "content": text})
        try:
            start = time.time()
            resp = requests.post(OLLAMA_URL, json={
                "model": self.model,
                "messages": [{"role": "system", "content": self.system}] + self.messages,
                "stream": False,
            }, timeout=120)
            data = resp.json()
            content = data.get("message", {}).get("content", "No response.")
            elapsed = round(time.time() - start, 1)
            tokens = data.get("eval_count", 0)
            self.total_tokens += tokens
            self.messages.append({"role": "assistant", "content": content})
            self._auto_save()
            return json.dumps({"content": content, "tokens": tokens, "elapsed": elapsed, "total_tokens": self.total_tokens})
        except Exception as e:
            return json.dumps({"content": f"Error: {e}", "tokens": 0, "elapsed": 0, "total_tokens": self.total_tokens})

    def new_chat(self):
        self._auto_save()
        self.messages = []
        self.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        return "ok"

    def set_model(self, model):
        self.model = model
        return json.dumps({"model": self.model})

    def set_persona(self, persona):
        self.persona = persona
        self.system = PERSONAS.get(persona, SYSTEM)
        return json.dumps({"persona": self.persona})

    def get_models(self):
        try:
            r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
            return json.dumps([m["name"] for m in r.json().get("models", [])])
        except:
            return json.dumps([])

    def get_personas(self):
        return json.dumps(list(PERSONAS.keys()))

    def get_username(self):
        return USERNAME

    def get_chat_history(self):
        chats = []
        for f in sorted(CHATS_DIR.glob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(f.read_text())
                first_msg = ""
                for m in data.get("messages", []):
                    if m["role"] == "user":
                        first_msg = m["content"][:40]
                        break
                chats.append({"id": f.stem, "title": first_msg or "Empty chat", "date": f.stem[:8]})
            except:
                pass
        return json.dumps(chats)

    def load_chat(self, chat_id):
        f = CHATS_DIR / f"{chat_id}.json"
        if f.exists():
            data = json.loads(f.read_text())
            self.messages = data.get("messages", [])
            self.chat_id = chat_id
            self.model = data.get("model", self.model)
            return json.dumps({"messages": self.messages, "model": self.model})
        return json.dumps({"messages": [], "model": self.model})

    def delete_chat(self, chat_id):
        f = CHATS_DIR / f"{chat_id}.json"
        if f.exists():
            f.unlink()
        return "ok"

    def _auto_save(self):
        if self.messages:
            data = {"messages": self.messages, "model": self.model, "saved": datetime.now().isoformat()}
            (CHATS_DIR / f"{self.chat_id}.json").write_text(json.dumps(data))


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
    --dim: #7d8590; --accent: #58a6ff; --red: #f85149; --green: #3fb950;
    --user-bg: #1c2128; --sidebar: #0d1117; --hover: #1c2128;
}
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', -apple-system, sans-serif; height: 100vh; display: flex; overflow: hidden; }

/* Sidebar */
.sidebar {
    width: 260px; background: var(--sidebar); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
.sidebar-header h2 { font-size: 14px; color: var(--dim); margin-bottom: 10px; }
.new-btn {
    width: 100%; background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); padding: 10px; font-size: 13px;
    cursor: pointer; text-align: left; display: flex; align-items: center; gap: 8px;
}
.new-btn:hover { border-color: var(--accent); }
.chat-list { flex: 1; overflow-y: auto; padding: 8px; }
.chat-item {
    padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 2px;
    font-size: 13px; color: var(--dim); display: flex; justify-content: space-between; align-items: center;
}
.chat-item:hover { background: var(--hover); color: var(--text); }
.chat-item.active { background: var(--hover); color: var(--text); }
.chat-item .del { opacity: 0; color: var(--red); cursor: pointer; font-size: 11px; }
.chat-item:hover .del { opacity: 1; }

/* Bottom controls */
.sidebar-bottom { padding: 12px; border-top: 1px solid var(--border); }
.select-row { display: flex; gap: 6px; margin-bottom: 6px; }
.select-row select {
    flex: 1; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); padding: 6px 8px; font-size: 12px; outline: none;
}
.sidebar-info { font-size: 11px; color: var(--dim); text-align: center; }

/* Main */
.main { flex: 1; display: flex; flex-direction: column; }
.header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 12px 20px; display: flex; align-items: center; justify-content: space-between;
}
.header h1 { font-size: 16px; font-weight: 600; }
.header .code { color: var(--red); }
.header .gpt { color: var(--accent); }
.header-info { font-size: 12px; color: var(--dim); display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.on { background: var(--green); } .dot.off { background: var(--red); }

.messages { flex: 1; overflow-y: auto; padding: 20px; }
.msg { margin-bottom: 20px; animation: fadeIn 0.2s ease; max-width: 800px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; } }
.msg .role { font-size: 12px; font-weight: 600; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.msg .icon { width: 20px; height: 20px; border-radius: 5px; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; }
.msg.user .role { color: var(--accent); } .msg.user .icon { background: var(--accent); color: var(--bg); }
.msg.ai .role { color: var(--green); } .msg.ai .icon { background: var(--green); color: var(--bg); }
.msg .body { font-size: 14px; line-height: 1.7; padding: 12px 16px; white-space: pre-wrap; word-wrap: break-word; }
.msg.user .body { background: var(--user-bg); border: 1px solid var(--border); border-radius: 10px; }
.msg.ai .body { border-left: 2px solid var(--green); padding-left: 16px; }
.msg .body code { background: var(--surface); padding: 2px 6px; border-radius: 4px; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 13px; }
.msg .body pre { background: var(--surface); padding: 12px 16px; border-radius: 8px; margin: 10px 0; border: 1px solid var(--border); overflow-x: auto; position: relative; }
.msg .body pre code { background: none; padding: 0; }
.copy-btn { position: absolute; top: 8px; right: 8px; background: var(--border); border: none; border-radius: 4px; color: var(--dim); padding: 4px 8px; font-size: 11px; cursor: pointer; opacity: 0; transition: opacity 0.2s; }
pre:hover .copy-btn { opacity: 1; }
.copy-btn:hover { color: var(--text); }
.msg .stats { font-size: 11px; color: var(--dim); margin-top: 6px; }
.thinking { display: none; color: var(--dim); font-size: 13px; margin-bottom: 16px; }
.thinking.on { display: flex; align-items: center; gap: 8px; }
.spinner { width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.welcome { text-align: center; padding: 80px 20px; }
.welcome h2 { font-size: 28px; margin-bottom: 8px; }
.welcome p { color: var(--dim); margin-bottom: 24px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; max-width: 500px; margin: 0 auto; }
.chips button { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; color: var(--text); padding: 10px 16px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
.chips button:hover { border-color: var(--accent); color: var(--accent); transform: translateY(-1px); }

.input-area { background: var(--surface); border-top: 1px solid var(--border); padding: 16px 20px; }
.input-wrap { display: flex; gap: 8px; align-items: flex-end; max-width: 800px; }
.input-wrap textarea { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; color: var(--text); padding: 12px 16px; font-size: 14px; font-family: inherit; resize: none; outline: none; min-height: 44px; max-height: 150px; transition: border-color 0.2s; }
.input-wrap textarea:focus { border-color: var(--accent); }
.input-wrap button { background: var(--accent); border: none; border-radius: 10px; color: white; padding: 12px 18px; font-size: 14px; cursor: pointer; font-weight: 600; transition: opacity 0.2s; }
.input-wrap button:hover { opacity: 0.9; } .input-wrap button:disabled { opacity: 0.3; }
.footer { padding: 6px 20px; font-size: 11px; color: var(--dim); display: flex; justify-content: space-between; }
.kbd { background: var(--surface); border: 1px solid var(--border); border-radius: 3px; padding: 1px 5px; font-size: 10px; }
</style>
</head>
<body>

<div class="sidebar">
    <div class="sidebar-header">
        <h2>CHATS</h2>
        <button class="new-btn" onclick="newChat()">+ New Chat</button>
    </div>
    <div class="chat-list" id="chatList"></div>
    <div class="sidebar-bottom">
        <div class="select-row">
            <select id="modelSelect" onchange="setModel(this.value)"></select>
        </div>
        <div class="select-row">
            <select id="personaSelect" onchange="setPersona(this.value)"></select>
        </div>
        <div class="sidebar-info" id="sidebarInfo">CodeGPT v2.0</div>
    </div>
</div>

<div class="main">
    <div class="header">
        <h1><span class="code">Code</span><span class="gpt">GPT</span></h1>
        <div class="header-info">
            <span class="dot" id="dot"></span>
            <span id="statusText"></span>
        </div>
    </div>

    <div class="messages" id="msgs">
        <div class="welcome" id="welcome">
            <h2 id="greeting"></h2>
            <p>How can I help you today?</p>
            <div class="chips">
                <button onclick="go('Explain how REST APIs work')">Explain REST APIs</button>
                <button onclick="go('Write a Python function to find primes')">Prime numbers</button>
                <button onclick="go('What are the OWASP top 10?')">OWASP Top 10</button>
                <button onclick="go('Design a login system with JWT')">JWT Auth</button>
                <button onclick="go('Compare Flask vs FastAPI')">Flask vs FastAPI</button>
                <button onclick="go('Write a bash script to backup files')">Backup script</button>
            </div>
        </div>
        <div class="thinking" id="think"><div class="spinner"></div> Thinking...</div>
    </div>

    <div class="input-area">
        <div class="input-wrap">
            <textarea id="inp" placeholder="Message CodeGPT..." rows="1" onkeydown="key(event)" autofocus></textarea>
            <button onclick="send()" id="btn">Send</button>
        </div>
    </div>
    <div class="footer">
        <span id="tc">0 tokens</span>
        <span><span class="kbd">Enter</span> send &middot; <span class="kbd">Shift+Enter</span> new line &middot; <span class="kbd">Ctrl+N</span> new chat</span>
    </div>
</div>

<script>
let busy = false;

async function init() {
    const name = await pywebview.api.get_username();
    const h = new Date().getHours();
    const g = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    document.getElementById('greeting').textContent = g + ', ' + name;

    await loadModels();
    await loadPersonas();
    await loadChats();
    checkStatus();
    setInterval(checkStatus, 30000);
}

async function checkStatus() {
    const r = JSON.parse(await pywebview.api.check_status());
    document.getElementById('dot').className = 'dot ' + (r.online ? 'on' : 'off');
    document.getElementById('statusText').textContent = r.online ? r.model : 'offline';
}

async function loadModels() {
    const models = JSON.parse(await pywebview.api.get_models());
    const sel = document.getElementById('modelSelect');
    sel.innerHTML = models.map(m => '<option value="'+m+'"'+(m===MODEL?' selected':'')+'>'+m+'</option>').join('');
}

async function loadPersonas() {
    const personas = JSON.parse(await pywebview.api.get_personas());
    const sel = document.getElementById('personaSelect');
    sel.innerHTML = personas.map(p => '<option value="'+p+'">'+p+'</option>').join('');
}

async function loadChats() {
    const chats = JSON.parse(await pywebview.api.get_chat_history());
    const list = document.getElementById('chatList');
    list.innerHTML = chats.map(c =>
        '<div class="chat-item" onclick="loadChat(\''+c.id+'\')">' +
        '<span>'+c.title+'</span>' +
        '<span class="del" onclick="event.stopPropagation();deleteChat(\''+c.id+'\')">x</span>' +
        '</div>'
    ).join('') || '<div style="padding:20px;text-align:center;color:var(--dim);font-size:12px">No chats yet</div>';
}

async function loadChat(id) {
    const r = JSON.parse(await pywebview.api.load_chat(id));
    clearMessages();
    r.messages.forEach(m => addMsg(m.role === 'user' ? 'user' : 'ai', m.content));
    document.getElementById('modelSelect').value = r.model;
}

async function deleteChat(id) {
    await pywebview.api.delete_chat(id);
    loadChats();
}

function esc(t) {
    t = t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    // Code blocks with copy button
    t = t.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, function(m, lang, code) {
        return '<pre><code>'+code+'</code><button class="copy-btn" onclick="copyCode(this)">Copy</button></pre>';
    });
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    t = t.replace(/^### (.+)$/gm, '<h3 style="margin:8px 0 4px;font-size:15px">$1</h3>');
    t = t.replace(/^## (.+)$/gm, '<h3 style="margin:8px 0 4px;font-size:16px">$1</h3>');
    t = t.replace(/^- (.+)$/gm, '&bull; $1');
    return t;
}

function copyCode(btn) {
    const code = btn.previousElementSibling.textContent;
    navigator.clipboard.writeText(code);
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1500);
}

function clearMessages() {
    const w = document.getElementById('welcome');
    if (w) w.style.display = 'none';
    const msgs = document.getElementById('msgs');
    msgs.querySelectorAll('.msg').forEach(m => m.remove());
}

function addMsg(role, content, stats) {
    const w = document.getElementById('welcome');
    if (w) w.style.display = 'none';
    const d = document.createElement('div');
    d.className = 'msg ' + role;
    const icon = role === 'user' ? 'U' : 'AI';
    const label = role === 'user' ? 'You' : 'CodeGPT';
    d.innerHTML = '<div class="role"><span class="icon">'+icon+'</span>'+label+'</div>'
        + '<div class="body">'+esc(content)+'</div>'
        + (stats ? '<div class="stats">'+stats+'</div>' : '');
    const c = document.getElementById('msgs');
    c.insertBefore(d, document.getElementById('think'));
    c.scrollTop = c.scrollHeight;
}

function key(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    if (e.ctrlKey && e.key === 'n') { e.preventDefault(); newChat(); }
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

function go(t) { document.getElementById('inp').value = t; send(); }

async function newChat() {
    await pywebview.api.new_chat();
    document.getElementById('msgs').innerHTML =
        '<div class="welcome" id="welcome"><h2>New conversation</h2><p>How can I help?</p></div>'
        + '<div class="thinking" id="think"><div class="spinner"></div> Thinking...</div>';
    loadChats();
    document.getElementById('inp').focus();
}

async function setModel(m) { await pywebview.api.set_model(m); checkStatus(); }
async function setPersona(p) { await pywebview.api.set_persona(p); }

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
    addMsg('ai', r.content, r.tokens + ' tokens &middot; ' + r.elapsed + 's');
    document.getElementById('tc').textContent = r.total_tokens.toLocaleString() + ' tokens';

    busy = false;
    document.getElementById('btn').disabled = false;
    inp.focus();
    loadChats();
}

window.addEventListener('pywebviewready', init);
const MODEL = '""" + MODEL + """';
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
        width=1000,
        height=700,
        min_size=(600, 400),
        background_color="#0d1117",
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
