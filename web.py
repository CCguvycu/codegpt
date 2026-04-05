"""CodeGPT Web App — Flask + HTML/JS. Works on phone via Chrome."""

import json
import os
import time
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string

import requests as http_requests

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = "llama-3.2-3b-preview"
OLLAMA_MODEL = "llama3.2"
PROVIDER = "groq" if (GROQ_API_KEY and HAS_GROQ) else "ollama"

SYSTEM_PROMPT = """You are an AI modeled after a highly technical, system-focused developer mindset.
Be direct, concise, and dense with information. No fluff, no filler, no emojis.
Give conclusions first, then minimal necessary explanation.
Blunt but intelligent. Slightly dark tone is acceptable.
Keep responses concise."""

PERSONAS = {
    "Default": SYSTEM_PROMPT,
    "Hacker": "You are a cybersecurity expert. Technical jargon, CVEs, attack vectors. Defensive security only. Concise.",
    "Teacher": "You are a patient programming teacher. Step by step, analogies, examples. Concise.",
    "Roast": "You are a brutally sarcastic code reviewer. Roast then fix. Dark humor. Concise.",
    "Minimal": "Shortest possible answer. One line if possible. Code only.",
}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0d1117">
<title>CodeGPT</title>
<link rel="manifest" href="/manifest.json">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.header {
    background: #161b22;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #30363d;
    flex-shrink: 0;
}
.header h1 { font-size: 18px; color: #58a6ff; font-weight: 700; }
.header-btns { display: flex; gap: 8px; }
.header-btn {
    background: none; border: 1px solid #30363d; color: #8b949e;
    padding: 6px 10px; border-radius: 8px; cursor: pointer; font-size: 13px;
}
.header-btn:hover { border-color: #58a6ff; color: #58a6ff; }
.chat {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    scroll-behavior: smooth;
}
.msg { max-width: 85%; padding: 10px 14px; border-radius: 16px; line-height: 1.5; font-size: 14px; word-wrap: break-word; }
.msg.user {
    align-self: flex-end;
    background: rgba(88,166,255,0.15);
    border: 1px solid rgba(88,166,255,0.2);
    border-bottom-right-radius: 4px;
}
.msg.ai {
    align-self: flex-start;
    background: rgba(35,134,54,0.1);
    border: 1px solid rgba(35,134,54,0.15);
    border-bottom-left-radius: 4px;
}
.msg .role { font-size: 11px; font-weight: 700; margin-bottom: 4px; }
.msg.user .role { color: #58a6ff; }
.msg.ai .role { color: #238636; }
.msg .stats { font-size: 10px; color: #484f58; margin-top: 6px; }
.msg pre {
    background: #161b22; padding: 8px 10px; border-radius: 8px;
    overflow-x: auto; margin: 6px 0; font-size: 13px; border: 1px solid #30363d;
}
.msg code { font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 13px; }
.msg p { margin: 4px 0; }
.msg ul, .msg ol { padding-left: 20px; margin: 4px 0; }
.thinking {
    align-self: flex-start;
    color: #8b949e;
    font-style: italic;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
}
.dot-pulse { display: flex; gap: 4px; }
.dot-pulse span {
    width: 6px; height: 6px; background: #238636; border-radius: 50%;
    animation: pulse 1.4s infinite;
}
.dot-pulse span:nth-child(2) { animation-delay: 0.2s; }
.dot-pulse span:nth-child(3) { animation-delay: 0.4s; }
@keyframes pulse { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
.input-bar {
    display: flex;
    gap: 8px;
    padding: 10px 16px;
    background: #161b22;
    border-top: 1px solid #30363d;
    flex-shrink: 0;
}
#msg-input {
    flex: 1;
    background: #0d1117;
    border: 1px solid #30363d;
    color: #c9d1d9;
    padding: 10px 14px;
    border-radius: 20px;
    font-size: 14px;
    outline: none;
}
#msg-input:focus { border-color: #58a6ff; }
#send-btn {
    background: #238636;
    border: none;
    color: white;
    width: 40px; height: 40px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
#send-btn:hover { background: #2ea043; }
#send-btn:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
.status {
    font-size: 11px; color: #484f58; padding: 4px 16px;
    background: #161b22; flex-shrink: 0;
}
.welcome {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; flex: 1; gap: 16px; padding: 32px;
}
.welcome h2 { color: #58a6ff; font-size: 24px; }
.welcome p { color: #8b949e; font-size: 14px; }
.suggestions { display: flex; flex-direction: column; gap: 8px; width: 100%; max-width: 320px; }
.suggestion {
    background: #161b22; border: 1px solid #30363d; color: #c9d1d9;
    padding: 10px 14px; border-radius: 12px; cursor: pointer;
    text-align: left; font-size: 13px;
}
.suggestion:hover { border-color: #58a6ff; }
.modal-overlay {
    display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7); z-index: 100; align-items: center; justify-content: center;
}
.modal-overlay.active { display: flex; }
.modal {
    background: #161b22; border: 1px solid #30363d; border-radius: 16px;
    padding: 24px; width: 90%; max-width: 360px;
}
.modal h3 { color: #58a6ff; margin-bottom: 16px; }
.modal select, .modal input[type=text] {
    width: 100%; background: #0d1117; border: 1px solid #30363d;
    color: #c9d1d9; padding: 8px 12px; border-radius: 8px; margin: 8px 0; font-size: 14px;
}
.modal-btns { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
.modal-btns button {
    padding: 8px 16px; border-radius: 8px; border: none; cursor: pointer; font-size: 13px;
}
.btn-cancel { background: #21262d; color: #c9d1d9; }
.btn-save { background: #238636; color: white; }
</style>
</head>
<body>

<div class="header">
    <h1>CodeGPT</h1>
    <div class="header-btns">
        <button class="header-btn" onclick="newChat()">New</button>
        <button class="header-btn" onclick="openSettings()">Settings</button>
    </div>
</div>

<div class="chat" id="chat"></div>

<div class="status" id="status">Ready</div>

<div class="input-bar">
    <input type="text" id="msg-input" placeholder="Message CodeGPT..." autocomplete="off">
    <button id="send-btn" onclick="send()">&#9654;</button>
</div>

<div class="modal-overlay" id="settings-modal">
    <div class="modal">
        <h3>Settings</h3>
        <label style="color:#8b949e;font-size:12px">Persona</label>
        <select id="persona-select">
            <option>Default</option><option>Hacker</option><option>Teacher</option>
            <option>Roast</option><option>Minimal</option>
        </select>
        <div style="border-top:1px solid #30363d;margin-top:16px;padding-top:12px">
            <button onclick="showInstallGuide()" style="width:100%;background:#238636;border:none;color:white;padding:10px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:700" id="install-btn-settings">Install App</button>
        </div>
        <div class="modal-btns">
            <button class="btn-cancel" onclick="closeSettings()">Close</button>
            <button class="btn-save" onclick="saveSettings()">Save</button>
        </div>
    </div>
</div>

<script>
const chat = document.getElementById('chat');
const input = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');
const status = document.getElementById('status');

let messages = [];
let persona = localStorage.getItem('persona') || 'Default';
let msgCount = 0;
let streaming = false;

document.getElementById('persona-select').value = persona;

// Welcome
showWelcome();

input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }});

function showWelcome() {
    const suggestions = [
        'Explain how TCP/IP works',
        'Write a Python CPU monitor',
        'OWASP top 10 explained',
        'Design a REST API',
    ];
    chat.innerHTML = `
        <div class="welcome">
            <h2>CodeGPT</h2>
            <p>Local AI assistant</p>
            <div class="suggestions">
                ${suggestions.map(s => `<button class="suggestion" onclick="sendText('${s}')">${s}</button>`).join('')}
            </div>
        </div>
    `;
}

function sendText(text) { input.value = text; send(); }

function addMsg(role, content, stats) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    let html = `<div class="role">${role === 'user' ? 'You' : 'AI'}</div>`;
    if (role === 'ai') {
        html += formatMarkdown(content);
    } else {
        html += `<div>${escapeHtml(content)}</div>`;
    }
    if (stats) html += `<div class="stats">${stats}</div>`;
    div.innerHTML = html;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function addThinking() {
    const div = document.createElement('div');
    div.className = 'thinking';
    div.id = 'thinking';
    div.innerHTML = '<div class="dot-pulse"><span></span><span></span><span></span></div> Thinking...';
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

function removeThinking() {
    const el = document.getElementById('thinking');
    if (el) el.remove();
}

async function send() {
    const text = input.value.trim();
    if (!text || streaming) return;

    // Clear welcome
    const welcome = chat.querySelector('.welcome');
    if (welcome) welcome.remove();

    input.value = '';
    addMsg('user', text);
    addThinking();
    messages.push({role: 'user', content: text});
    msgCount++;
    streaming = true;
    sendBtn.disabled = true;
    status.textContent = 'Streaming...';

    try {
        const resp = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({messages, persona}),
        });

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let full = '';
        let stats = '';
        let aiDiv = null;

        removeThinking();

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            const lines = decoder.decode(value, {stream: true}).split('\\n');
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const chunk = JSON.parse(line);
                    if (chunk.content) full += chunk.content;
                    if (chunk.done) {
                        stats = chunk.stats || `${chunk.provider || ''}`;
                    }

                    if (aiDiv) {
                        aiDiv.querySelector('.ai-content').innerHTML = formatMarkdown(full);
                    } else {
                        aiDiv = document.createElement('div');
                        aiDiv.className = 'msg ai';
                        aiDiv.innerHTML = `<div class="role">AI</div><div class="ai-content">${formatMarkdown(full)}</div><div class="stats"></div>`;
                        chat.appendChild(aiDiv);
                    }
                    chat.scrollTop = chat.scrollHeight;
                } catch(e) {}
            }
        }

        if (aiDiv && stats) {
            aiDiv.querySelector('.stats').textContent = stats;
        }

        if (full) {
            messages.push({role: 'assistant', content: full});
        }

    } catch(e) {
        removeThinking();
        addMsg('ai', 'Error: ' + e.message);
        if (messages.length && messages[messages.length-1].role === 'user') messages.pop();
    }

    streaming = false;
    sendBtn.disabled = false;
    status.textContent = `${persona} | ${msgCount} msgs`;
    input.focus();
}

function newChat() {
    messages = [];
    msgCount = 0;
    showWelcome();
    status.textContent = 'Ready';
}

function openSettings() { document.getElementById('settings-modal').classList.add('active'); }
function closeSettings() { document.getElementById('settings-modal').classList.remove('active'); }
function saveSettings() {
    persona = document.getElementById('persona-select').value;
    localStorage.setItem('persona', persona);
    status.textContent = `Persona: ${persona}`;
    closeSettings();
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function formatMarkdown(text) {
    // Sanitize HTML to prevent XSS from AI output
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Code blocks
    text = text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    text = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
    // Italic
    text = text.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
    // Lists
    text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
    text = text.replace(/^\\d+\\. (.+)$/gm, '<li>$1</li>');
    // Paragraphs
    text = text.replace(/\\n\\n/g, '</p><p>');
    text = text.replace(/\\n/g, '<br>');
    return '<p>' + text + '</p>';
}

// --- PWA Install ---
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallBanner();
});

function showInstallBanner() {
    if (document.getElementById('install-banner')) return;
    const banner = document.createElement('div');
    banner.id = 'install-banner';
    banner.style.cssText = `
        position: fixed; bottom: 70px; left: 16px; right: 16px;
        background: linear-gradient(135deg, #238636, #1a7f2b);
        color: white; padding: 14px 18px; border-radius: 14px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 4px 20px rgba(35,134,54,0.4);
        z-index: 200; animation: slideUp 0.3s ease;
        font-size: 14px;
    `;
    banner.innerHTML = `
        <div>
            <div style="font-weight:700">Install CodeGPT</div>
            <div style="font-size:12px;opacity:0.8">Add to home screen for the full app experience</div>
        </div>
        <div style="display:flex;gap:8px">
            <button onclick="dismissInstall()" style="background:rgba(255,255,255,0.2);border:none;color:white;padding:8px 12px;border-radius:8px;cursor:pointer;font-size:13px">Later</button>
            <button onclick="installApp()" style="background:white;border:none;color:#238636;padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:700;font-size:13px">Install</button>
        </div>
    `;
    document.body.appendChild(banner);
}

async function installApp() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const result = await deferredPrompt.userChoice;
    if (result.outcome === 'accepted') {
        document.getElementById('install-banner')?.remove();
    }
    deferredPrompt = null;
}

function dismissInstall() {
    document.getElementById('install-banner')?.remove();
}

function showInstallGuide() {
    if (deferredPrompt) {
        installApp();
        return;
    }
    // Manual install instructions
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const isAndroid = /Android/.test(navigator.userAgent);
    let steps = '';
    if (isIOS) {
        steps = `
            <div style="font-size:14px;line-height:1.8">
                <b>iOS Install:</b><br>
                1. Tap the <b>Share</b> button (box with arrow)<br>
                2. Scroll down and tap <b>"Add to Home Screen"</b><br>
                3. Tap <b>"Add"</b>
            </div>`;
    } else if (isAndroid) {
        steps = `
            <div style="font-size:14px;line-height:1.8">
                <b>Android Install:</b><br>
                1. Tap the <b>3-dot menu</b> (top right)<br>
                2. Tap <b>"Add to Home Screen"</b><br>
                   or <b>"Install app"</b><br>
                3. Tap <b>"Install"</b>
            </div>`;
    } else {
        steps = `
            <div style="font-size:14px;line-height:1.8">
                <b>Desktop Install:</b><br>
                1. Click the <b>install icon</b> in the URL bar<br>
                   (right side, looks like a monitor with arrow)<br>
                2. Click <b>"Install"</b>
            </div>`;
    }

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';
    overlay.id = 'install-guide';
    overlay.innerHTML = `
        <div class="modal">
            <h3>Install CodeGPT</h3>
            ${steps}
            <div class="modal-btns">
                <button class="btn-save" onclick="document.getElementById('install-guide').remove()">Got it</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

window.addEventListener('appinstalled', () => {
    document.getElementById('install-banner')?.remove();
    deferredPrompt = null;
});

// Hide install button if already installed
if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone) {
    const ib = document.getElementById('install-btn-settings');
    if (ib) ib.style.display = 'none';
}

// Register service worker
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
}
</script>

<style>
@keyframes slideUp {
    from { transform: translateY(100px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}
</style>
</body>
</html>"""

SW_JS = """self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('fetch', e => e.respondWith(fetch(e.request).catch(() => new Response('Offline'))));"""

MANIFEST = """{
    "name": "CodeGPT",
    "short_name": "CodeGPT",
    "description": "Local AI coding assistant",
    "start_url": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0d1117",
    "theme_color": "#0d1117",
    "categories": ["productivity", "utilities"],
    "icons": [
        {"src": "/icon", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable"},
        {"src": "/icon-512", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}
    ]
}"""


# --- Routes ---

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/sw.js")
def service_worker():
    return Response(SW_JS, content_type="application/javascript")


@app.route("/manifest.json")
def manifest():
    return Response(MANIFEST, content_type="application/json")


@app.route("/icon")
def icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
        <rect width="192" height="192" rx="32" fill="#0d1117"/>
        <text x="96" y="120" text-anchor="middle" font-family="monospace" font-size="72" font-weight="bold" fill="#58a6ff">G</text>
    </svg>'''
    return Response(svg, content_type="image/svg+xml")


@app.route("/icon-512")
def icon_512():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
        <rect width="512" height="512" rx="64" fill="#0d1117"/>
        <text x="256" y="320" text-anchor="middle" font-family="monospace" font-size="192" font-weight="bold" fill="#58a6ff">G</text>
    </svg>'''
    return Response(svg, content_type="image/svg+xml")


@app.route("/chat", methods=["POST"])
def chat_stream():
    data = request.get_json()
    msgs = data.get("messages", [])
    persona = data.get("persona", "Default")
    system = PERSONAS.get(persona, SYSTEM_PROMPT)

    if not msgs:
        return jsonify({"error": "No messages"}), 400

    try:
        if PROVIDER == "groq":
            gen = _stream_groq(msgs, system)
        else:
            gen = _stream_ollama(msgs, system)
        return Response(stream_with_context(gen), content_type="application/x-ndjson")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _stream_groq(messages, system):
    client = Groq(api_key=GROQ_API_KEY)
    full_messages = [{"role": "system", "content": system}] + messages
    completion = client.chat.completions.create(
        model=DEFAULT_MODEL, messages=full_messages, stream=True, max_tokens=4096,
    )
    for chunk in completion:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield json.dumps({"content": delta.content, "done": False}) + "\n"
    yield json.dumps({"content": "", "done": True, "provider": "groq", "stats": "groq cloud"}) + "\n"


def _stream_ollama(messages, system):
    full_messages = [{"role": "system", "content": system}] + messages
    response = http_requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": full_messages, "stream": True},
        stream=True, timeout=120,
    )
    response.raise_for_status()
    for line in response.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = chunk.get("message", {}).get("content", "")
        done = chunk.get("done", False)
        out = {"content": content, "done": done}
        if done:
            ec = chunk.get("eval_count", 0)
            td = chunk.get("total_duration", 0)
            ds = td / 1e9 if td else 0
            tps = ec / ds if ds > 0 else 0
            out["stats"] = f"{ec} tok | {ds:.1f}s | {tps:.0f} tok/s"
            out["provider"] = "ollama"
        yield json.dumps(out) + "\n"


@app.route("/health")
def health():
    return jsonify({"status": "ok", "provider": PROVIDER})


def generate_ssl_cert():
    """Generate self-signed SSL cert for HTTPS (required for PWA install)."""
    cert_dir = Path.home() / ".codegpt" / "ssl"
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"

    if cert_file.exists() and key_file.exists():
        return str(cert_file), str(key_file)

    cert_dir.mkdir(parents=True, exist_ok=True)

    try:
        from OpenSSL import crypto
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        cert = crypto.X509()
        cert.get_subject().CN = "CodeGPT"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)  # 1 year
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, "sha256")

        cert_file.write_bytes(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        key_file.write_bytes(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

        return str(cert_file), str(key_file)
    except ImportError:
        print("  pyopenssl not installed. Running HTTP only (PWA install won't work).")
        return None, None


if __name__ == "__main__":
    import ssl
    PORT = int(os.environ.get("PORT", 5050))

    cert, key = generate_ssl_cert()

    print(f"\n  CodeGPT Web App")
    print(f"  Provider: {PROVIDER}")
    if cert:
        print(f"  https://localhost:{PORT}")
        print(f"  https://192.168.1.237:{PORT}  (open on phone)")
        print(f"  HTTPS enabled - PWA install ready")
    else:
        print(f"  http://localhost:{PORT}")
        print(f"  http://192.168.1.237:{PORT}  (open on phone)")
    print()

    if cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        app.run(host="0.0.0.0", port=PORT, debug=False, ssl_context=context)
    else:
        app.run(host="0.0.0.0", port=PORT, debug=False)
