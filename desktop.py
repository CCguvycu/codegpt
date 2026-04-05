"""CodeGPT Desktop — Claude Code + OpenClaw style GUI."""
import json
import threading
import time
import requests
import webview
import os
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

# Load profile
profile_file = Path.home() / ".codegpt" / "profiles" / "cli_profile.json"
USERNAME = "User"
if profile_file.exists():
    try:
        p = json.loads(profile_file.read_text())
        USERNAME = p.get("name", "User")
        MODEL = p.get("model", MODEL)
    except Exception:
        pass


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
    --ai-bg: #0d1117;
}

body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', -apple-system, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

/* Header */
.header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    -webkit-app-region: drag;
}

.header h1 {
    font-size: 16px;
    font-weight: 600;
}

.header h1 span.code { color: var(--red); }
.header h1 span.gpt { color: var(--accent); }

.header-info {
    font-size: 12px;
    color: var(--dim);
}

.header-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}

.header-dot.online { background: var(--green); }
.header-dot.offline { background: var(--red); }

/* Messages */
.messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
}

.message {
    margin-bottom: 16px;
    animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}

.message .role {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.message .role .icon {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
}

.message.user .role { color: var(--accent); }
.message.user .role .icon { background: var(--accent); color: var(--bg); }
.message.ai .role { color: var(--green); }
.message.ai .role .icon { background: var(--green); color: var(--bg); }

.message .content {
    font-size: 14px;
    line-height: 1.6;
    padding: 10px 14px;
    border-radius: 8px;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.message.user .content {
    background: var(--user-bg);
    border: 1px solid var(--border);
}

.message.ai .content {
    background: transparent;
    border-left: 2px solid var(--green);
    border-radius: 0;
    padding-left: 14px;
}

.message .content code {
    background: var(--surface);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 13px;
}

.message .content pre {
    background: var(--surface);
    padding: 12px;
    border-radius: 8px;
    margin: 8px 0;
    overflow-x: auto;
    border: 1px solid var(--border);
}

.message .content pre code {
    background: none;
    padding: 0;
}

.message .stats {
    font-size: 11px;
    color: var(--dim);
    margin-top: 4px;
}

/* Thinking indicator */
.thinking {
    display: none;
    margin-bottom: 16px;
    color: var(--dim);
    font-size: 13px;
}

.thinking.active { display: block; }

.thinking .dots span {
    animation: blink 1.4s infinite;
}
.thinking .dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking .dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
    0%, 100% { opacity: 0.2; }
    50% { opacity: 1; }
}

/* Input */
.input-area {
    background: var(--surface);
    border-top: 1px solid var(--border);
    padding: 12px 20px;
}

.input-wrapper {
    display: flex;
    gap: 8px;
    align-items: flex-end;
}

.input-wrapper textarea {
    flex: 1;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 10px 14px;
    font-size: 14px;
    font-family: inherit;
    resize: none;
    outline: none;
    min-height: 42px;
    max-height: 120px;
}

.input-wrapper textarea:focus {
    border-color: var(--accent);
}

.input-wrapper button {
    background: var(--accent);
    border: none;
    border-radius: 8px;
    color: white;
    padding: 10px 16px;
    font-size: 14px;
    cursor: pointer;
    font-weight: 600;
}

.input-wrapper button:hover { opacity: 0.9; }
.input-wrapper button:disabled { opacity: 0.4; cursor: default; }

/* Footer */
.footer {
    background: var(--surface);
    border-top: 1px solid var(--border);
    padding: 6px 20px;
    font-size: 11px;
    color: var(--dim);
    display: flex;
    justify-content: space-between;
}

/* Welcome */
.welcome {
    text-align: center;
    padding: 60px 20px;
    color: var(--dim);
}

.welcome h2 {
    font-size: 24px;
    margin-bottom: 8px;
    color: var(--text);
}

.welcome .suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin-top: 24px;
}

.welcome .suggestions button {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 8px 14px;
    font-size: 13px;
    cursor: pointer;
}

.welcome .suggestions button:hover {
    border-color: var(--accent);
    color: var(--accent);
}
</style>
</head>
<body>

<div class="header">
    <h1><span class="code">Code</span><span class="gpt">GPT</span> <span style="color: var(--dim); font-weight: 400; font-size: 13px;">Desktop</span></h1>
    <div class="header-info">
        <span class="header-dot" id="statusDot"></span>
        <span id="statusText"></span>
        &nbsp;&middot;&nbsp;
        <span id="modelName"></span>
    </div>
</div>

<div class="messages" id="messages">
    <div class="welcome" id="welcome">
        <h2>Welcome, """ + USERNAME + """</h2>
        <p>Type a message or pick a suggestion.</p>
        <div class="suggestions">
            <button onclick="sendSuggestion('Explain how REST APIs work')">REST APIs</button>
            <button onclick="sendSuggestion('Write a Python function to find prime numbers')">Prime numbers</button>
            <button onclick="sendSuggestion('What are the OWASP top 10?')">OWASP Top 10</button>
            <button onclick="sendSuggestion('Design a login system with JWT')">JWT Auth</button>
        </div>
    </div>
    <div class="thinking" id="thinking">
        <span class="dots">Thinking<span>.</span><span>.</span><span>.</span></span>
    </div>
</div>

<div class="input-area">
    <div class="input-wrapper">
        <textarea id="input" placeholder="Type a message..." rows="1" onkeydown="handleKey(event)" autofocus></textarea>
        <button onclick="send()" id="sendBtn">Send</button>
    </div>
</div>

<div class="footer">
    <span id="tokenCount">0 tokens</span>
    <span>CodeGPT v2.0 &middot; Local AI &middot; Powered by Ollama</span>
</div>

<script>
const OLLAMA = '""" + OLLAMA_URL.replace("/api/chat", "") + """';
const MODEL = '""" + MODEL + """';
const SYSTEM = '""" + SYSTEM.replace("'", "\\'").replace("\n", " ") + """';
let messages = [];
let totalTokens = 0;
let isGenerating = false;

// Check connection
async function checkStatus() {
    try {
        const r = await fetch(OLLAMA + '/api/tags', {signal: AbortSignal.timeout(3000)});
        if (r.ok) {
            document.getElementById('statusDot').className = 'header-dot online';
            document.getElementById('statusText').textContent = 'connected';
            const data = await r.json();
            document.getElementById('modelName').textContent = MODEL;
        }
    } catch {
        document.getElementById('statusDot').className = 'header-dot offline';
        document.getElementById('statusText').textContent = 'offline';
    }
}
checkStatus();
setInterval(checkStatus, 30000);

function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
    }
    // Auto-resize
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function sendSuggestion(text) {
    document.getElementById('input').value = text;
    send();
}

function addMessage(role, content, stats) {
    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';

    const div = document.createElement('div');
    div.className = 'message ' + role;

    const icon = role === 'user' ? 'U' : 'AI';
    const label = role === 'user' ? 'You' : 'CodeGPT';

    let html = '<div class="role"><span class="icon">' + icon + '</span>' + label + '</div>';
    html += '<div class="content">' + escapeHtml(content) + '</div>';
    if (stats) html += '<div class="stats">' + stats + '</div>';

    div.innerHTML = html;

    const container = document.getElementById('messages');
    container.insertBefore(div, document.getElementById('thinking'));
    container.scrollTop = container.scrollHeight;
    return div;
}

function escapeHtml(text) {
    // Basic code block rendering
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    text = text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    return text;
}

async function send() {
    const input = document.getElementById('input');
    const text = input.value.trim();
    if (!text || isGenerating) return;

    input.value = '';
    input.style.height = 'auto';
    isGenerating = true;
    document.getElementById('sendBtn').disabled = true;

    addMessage('user', text);
    messages.push({role: 'user', content: text});

    // Show thinking
    document.getElementById('thinking').className = 'thinking active';

    try {
        const start = Date.now();
        const resp = await fetch(OLLAMA + '/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                model: MODEL,
                messages: [{role: 'system', content: SYSTEM}, ...messages],
                stream: false,
            }),
        });

        const data = await resp.json();
        const content = data.message?.content || 'No response.';
        const elapsed = ((Date.now() - start) / 1000).toFixed(1);
        const tokens = data.eval_count || 0;
        totalTokens += tokens;

        messages.push({role: 'assistant', content: content});
        document.getElementById('thinking').className = 'thinking';
        addMessage('ai', content, tokens + ' tokens · ' + elapsed + 's');
        document.getElementById('tokenCount').textContent = totalTokens.toLocaleString() + ' tokens';

    } catch (err) {
        document.getElementById('thinking').className = 'thinking';
        addMessage('ai', 'Error: Cannot reach Ollama. Check /connect in the CLI.');
    }

    isGenerating = false;
    document.getElementById('sendBtn').disabled = false;
    input.focus();
}
</script>
</body>
</html>
"""


def main():
    """Launch the desktop app."""
    window = webview.create_window(
        "CodeGPT",
        html=HTML,
        width=800,
        height=650,
        min_size=(400, 400),
        background_color="#0d1117",
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
