"""CodeGPT Backend — Flask API server. Supports Groq (cloud) and Ollama (local).

Deploy to Render/Railway/PythonAnywhere for 24/7 access without your laptop.

Usage:
    python server.py                         # Starts on port 5050
    python server.py --port 8080             # Custom port
    GROQ_API_KEY=gsk_... python server.py    # Use Groq cloud backend

Endpoints:
    POST /chat          — Send messages, get AI response (streaming)
    POST /chat/quick    — Non-streaming single response
    GET  /models        — List available models
    GET  /health        — Health check
    GET  /config        — Get server config (model, provider)
"""

import json
import os
import sys
import time
from datetime import datetime

from flask import Flask, request, jsonify, Response, stream_with_context

# Optional: Groq for cloud inference
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

# Optional: requests for Ollama
import requests as http_requests

app = Flask(__name__)

# --- Config ---

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("CODEGPT_MODEL", "llama-3.2-3b-preview")  # Groq model
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
PORT = int(os.environ.get("PORT", 5050))

# Auto-detect provider
if GROQ_API_KEY and HAS_GROQ:
    PROVIDER = "groq"
else:
    PROVIDER = "ollama"

SYSTEM_PROMPT = """You are an AI modeled after a highly technical, system-focused developer mindset.
Be direct, concise, and dense with information. No fluff, no filler, no emojis.
Give conclusions first, then minimal necessary explanation.
Focus on: AI, coding, automation, cybersecurity, system design.
Blunt but intelligent. Slightly dark tone is acceptable.
Keep responses concise for mobile reading."""

PERSONAS = {
    "Default": SYSTEM_PROMPT,
    "Hacker": "You are a cybersecurity expert. Technical jargon, CVEs, attack vectors. Defensive security only. Concise.",
    "Teacher": "You are a patient programming teacher. Step by step, analogies, examples. Concise.",
    "Roast": "You are a brutally sarcastic code reviewer. Roast then fix. Dark humor. Concise.",
    "Minimal": "Shortest possible answer. One line if possible. Code only.",
}

# Stats
server_stats = {"requests": 0, "start": time.time()}


# --- Groq Backend ---

def query_groq(messages, model, system, stream=False):
    """Query Groq cloud API."""
    client = Groq(api_key=GROQ_API_KEY)

    full_messages = [{"role": "system", "content": system}]
    full_messages.extend(messages)

    if stream:
        completion = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=full_messages,
            stream=True,
            max_tokens=4096,
        )

        def generate():
            full = []
            for chunk in completion:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full.append(delta.content)
                    yield json.dumps({
                        "content": delta.content,
                        "done": False,
                    }) + "\n"

            yield json.dumps({
                "content": "",
                "done": True,
                "full_response": "".join(full),
                "model": model or DEFAULT_MODEL,
                "provider": "groq",
            }) + "\n"

        return generate()
    else:
        completion = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=full_messages,
            max_tokens=4096,
        )
        content = completion.choices[0].message.content
        usage = completion.usage
        return {
            "content": content,
            "model": model or DEFAULT_MODEL,
            "provider": "groq",
            "tokens": {
                "input": usage.prompt_tokens if usage else 0,
                "output": usage.completion_tokens if usage else 0,
            },
        }


# --- Ollama Backend ---

def query_ollama(messages, model, system, stream=False):
    """Query local Ollama."""
    ollama_messages = [{"role": "system", "content": system}]
    ollama_messages.extend(messages)

    if stream:
        response = http_requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model or OLLAMA_MODEL, "messages": ollama_messages, "stream": True},
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        def generate():
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
                    out["model"] = model or OLLAMA_MODEL
                    out["provider"] = "ollama"
                    out["tokens"] = {"output": ec}
                    out["stats"] = f"{ec} tok | {ds:.1f}s | {tps:.0f} tok/s"

                yield json.dumps(out) + "\n"

        return generate()
    else:
        response = http_requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model or OLLAMA_MODEL, "messages": ollama_messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        ec = data.get("eval_count", 0)
        td = data.get("total_duration", 0)
        ds = td / 1e9 if td else 0
        return {
            "content": content,
            "model": model or OLLAMA_MODEL,
            "provider": "ollama",
            "tokens": {"output": ec},
            "stats": f"{ec} tok | {ds:.1f}s",
        }


# --- Routes ---

@app.route("/health", methods=["GET"])
def health():
    uptime = int(time.time() - server_stats["start"])
    return jsonify({
        "status": "ok",
        "provider": PROVIDER,
        "model": DEFAULT_MODEL if PROVIDER == "groq" else OLLAMA_MODEL,
        "uptime": uptime,
        "requests": server_stats["requests"],
    })


@app.route("/config", methods=["GET"])
def get_config():
    return jsonify({
        "provider": PROVIDER,
        "model": DEFAULT_MODEL if PROVIDER == "groq" else OLLAMA_MODEL,
        "personas": list(PERSONAS.keys()),
    })


@app.route("/models", methods=["GET"])
def list_models():
    if PROVIDER == "groq":
        # Groq available models
        models = [
            "llama-3.2-3b-preview",
            "llama-3.2-1b-preview",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ]
    else:
        try:
            resp = http_requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            models = []

    return jsonify({"models": models, "provider": PROVIDER})


@app.route("/chat", methods=["POST"])
def chat_stream():
    """Streaming chat endpoint."""
    server_stats["requests"] += 1

    data = request.get_json()
    messages = data.get("messages", [])
    model = data.get("model", "")
    persona = data.get("persona", "Default")
    system = PERSONAS.get(persona, SYSTEM_PROMPT)

    if not messages:
        return jsonify({"error": "No messages"}), 400

    try:
        if PROVIDER == "groq":
            gen = query_groq(messages, model, system, stream=True)
        else:
            gen = query_ollama(messages, model, system, stream=True)

        return Response(
            stream_with_context(gen),
            content_type="application/x-ndjson",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat/quick", methods=["POST"])
def chat_quick():
    """Non-streaming chat endpoint."""
    server_stats["requests"] += 1

    data = request.get_json()
    messages = data.get("messages", [])
    model = data.get("model", "")
    persona = data.get("persona", "Default")
    system = PERSONAS.get(persona, SYSTEM_PROMPT)

    if not messages:
        return jsonify({"error": "No messages"}), 400

    try:
        if PROVIDER == "groq":
            result = query_groq(messages, model, system, stream=False)
        else:
            result = query_ollama(messages, model, system, stream=False)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Main ---

if __name__ == "__main__":
    print("=" * 50)
    print("  CodeGPT Backend Server")
    print("=" * 50)
    print(f"  Provider: {PROVIDER}")
    if PROVIDER == "groq":
        print(f"  Model:    {DEFAULT_MODEL}")
        print(f"  API Key:  {GROQ_API_KEY[:10]}...")
    else:
        print(f"  Model:    {OLLAMA_MODEL}")
        print(f"  Ollama:   {OLLAMA_URL}")
    print(f"  Port:     {PORT}")
    print(f"  Personas: {', '.join(PERSONAS.keys())}")
    print("=" * 50)
    print(f"  http://localhost:{PORT}")
    print(f"  http://0.0.0.0:{PORT}")
    print("  Ctrl+C to stop.\n")

    app.run(host="0.0.0.0", port=PORT, debug=False)
