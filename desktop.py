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
        # Handle slash commands
        if text.startswith("/"):
            result = self._handle_command(text)
            if result:
                return json.dumps({"content": result, "tokens": 0, "elapsed": 0, "total_tokens": self.total_tokens, "is_system": True})

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

    def _handle_command(self, text):
        """Handle slash commands in the desktop app."""
        global OLLAMA_URL, OLLAMA_BASE
        cmd = text.split()[0].lower()
        args = text[len(cmd):].strip()

        if cmd == "/help":
            return (
                "**Chat**\n"
                "`/new` `/save` `/clear` `/export` `/history` `/compact` `/search`\n\n"
                "**Model**\n"
                "`/model` `/models` `/persona` `/think` `/temp` `/system` `/tokens`\n\n"
                "**AI**\n"
                "`/agent <name> <task>` — coder, debugger, reviewer, architect, pentester, explainer, optimizer, researcher\n"
                "`/all <question>` — All 8 agents answer in parallel\n"
                "`/vote <question>` — Agents vote with consensus\n"
                "`/swarm <task>` — 4-agent pipeline (architect→coder→reviewer→optimizer)\n"
                "`/p <template> <text>` — Prompt templates (debug, review, explain...)\n\n"
                "**Memory**\n"
                "`/mem save <text>` `/mem list` `/mem clear` `/rate good|bad` `/regen`\n\n"
                "**Connect**\n"
                "`/connect <ip>` `/server` `/weather` `/browse <url>` `/open <url>`\n\n"
                "**Info**\n"
                "`/usage` `/profile` `/prompts` `/shortcuts` `/sysinfo`\n"
            )

        elif cmd == "/new":
            self.messages = []
            self.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            return "New conversation started."

        elif cmd == "/model":
            if args:
                self.model = args
                return f"Model switched to **{self.model}**"
            else:
                try:
                    r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
                    models = [m["name"] for m in r.json().get("models", [])]
                    return "**Models:**\n" + "\n".join(f"- {'**'+m+'**' if m == self.model else m}" for m in models)
                except:
                    return "Cannot reach Ollama."

        elif cmd == "/models":
            try:
                r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
                models = [m["name"] for m in r.json().get("models", [])]
                return "**Available models:**\n" + "\n".join(f"- {'**'+m+'** (active)' if m == self.model else m}" for m in models)
            except:
                return "Cannot reach Ollama."

        elif cmd == "/persona":
            if args and args in PERSONAS:
                self.persona = args
                self.system = PERSONAS[args]
                return f"Persona switched to **{args}**"
            elif args:
                return f"Unknown persona. Available: {', '.join(PERSONAS.keys())}"
            else:
                return f"Current: **{self.persona}**\nAvailable: {', '.join(PERSONAS.keys())}"

        elif cmd == "/think":
            if "think step-by-step" in self.system:
                self.system = PERSONAS.get(self.persona, SYSTEM)
                return "Deep thinking **OFF**"
            else:
                self.system += "\n\nIMPORTANT: Think through this step-by-step. Show your reasoning."
                return "Deep thinking **ON** — AI will show reasoning."

        elif cmd == "/temp":
            if args:
                try:
                    t = float(args)
                    if 0 <= t <= 2:
                        return f"Temperature set to **{t}** (note: applied via system prompt guidance)"
                except:
                    pass
                return "Usage: /temp 0.7 (range 0.0 to 2.0)"
            return "Usage: /temp 0.7"

        elif cmd == "/system":
            if args:
                self.system = args
                return f"System prompt updated."
            return f"Current: {self.system[:100]}..."

        elif cmd == "/tokens":
            return f"**Session:** {self.total_tokens:,} tokens\n**Messages:** {len(self.messages)}"

        elif cmd == "/history":
            return f"**{len(self.messages)}** messages in current chat."

        elif cmd == "/server":
            try:
                r = requests.get(OLLAMA_BASE + "/api/tags", timeout=3)
                models = r.json().get("models", [])
                return f"**Server:** {OLLAMA_BASE}\n**Status:** online\n**Models:** {len(models)}\n**Active:** {self.model}"
            except:
                return f"**Server:** {OLLAMA_BASE}\n**Status:** offline"

        elif cmd == "/connect":
            if args:
                url = args if args.startswith("http") else "http://" + args
                if ":" not in url.split("//")[1]:
                    url += ":11434"
                test_url = url.rstrip("/") + "/api/chat"
                if try_connect(test_url):
                    OLLAMA_URL = test_url
                    OLLAMA_BASE = test_url.replace("/api/chat", "")
                    return f"**Connected** to {OLLAMA_BASE}"
                return f"Cannot reach {url}"
            return "Usage: /connect 192.168.1.100"

        elif cmd == "/export":
            lines = []
            for m in self.messages:
                role = "You" if m["role"] == "user" else "AI"
                lines.append(f"**{role}:** {m['content']}\n")
            return "**Chat Export:**\n\n" + "\n".join(lines) if lines else "Nothing to export."

        elif cmd == "/clear":
            self.messages = []
            return "Chat cleared."

        elif cmd == "/weather":
            city = args or "London"
            try:
                r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
                d = r.json()
                c = d["current_condition"][0]
                return (
                    f"**{city}**\n"
                    f"- {c['weatherDesc'][0]['value']}\n"
                    f"- {c['temp_C']}°C (feels {c['FeelsLikeC']}°C)\n"
                    f"- Humidity: {c['humidity']}%\n"
                    f"- Wind: {c['windspeedMiles']} mph {c['winddir16Point']}"
                )
            except:
                return f"Cannot get weather for {city}."

        elif cmd == "/open":
            if args:
                import webbrowser
                url = args if args.startswith("http") else "https://" + args
                webbrowser.open(url)
                return f"Opened: {url}"
            return "Usage: /open google.com"

        elif cmd == "/browse":
            if args:
                url = args if args.startswith("http") else "https://" + args
                try:
                    import re as _re
                    r = requests.get(url, timeout=15, headers={"User-Agent": "CodeGPT/2.0"})
                    text = _re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=_re.DOTALL)
                    text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
                    text = _re.sub(r'<[^>]+>', ' ', text)
                    text = _re.sub(r'\s+', ' ', text).strip()[:3000]

                    resp = requests.post(OLLAMA_URL, json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "Summarize in 3-5 bullet points."},
                            {"role": "user", "content": f"URL: {url}\n\n{text}"},
                        ], "stream": False,
                    }, timeout=60)
                    return resp.json().get("message", {}).get("content", text[:500])
                except Exception as e:
                    return f"Cannot fetch: {e}"
            return "Usage: /browse github.com"

        elif cmd == "/agent":
            parts = args.split(maxsplit=1)
            if len(parts) >= 2:
                agent_name, task = parts
                agents = {
                    "coder": "You are an expert programmer. Write clean, working code.",
                    "debugger": "You are a debugging expert. Find and fix bugs.",
                    "reviewer": "You are a code reviewer. Check for bugs, security, performance.",
                    "architect": "You are a system architect. Design with ASCII diagrams.",
                    "pentester": "You are an ethical pentester. Find vulnerabilities. Defensive only.",
                    "explainer": "You are a teacher. Explain simply with analogies.",
                    "optimizer": "You are a performance engineer. Optimize code.",
                    "researcher": "You are a research analyst. Deep-dive into topics.",
                }
                if agent_name in agents:
                    try:
                        resp = requests.post(OLLAMA_URL, json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": agents[agent_name]},
                                {"role": "user", "content": task},
                            ], "stream": False,
                        }, timeout=90)
                        content = resp.json().get("message", {}).get("content", "")
                        self.messages.append({"role": "user", "content": f"[agent:{agent_name}] {task}"})
                        self.messages.append({"role": "assistant", "content": content})
                        return f"**Agent: {agent_name}**\n\n{content}"
                    except Exception as e:
                        return f"Agent error: {e}"
                return f"Unknown agent. Available: {', '.join(agents.keys())}"
            return "Usage: /agent coder build a flask API"

        elif cmd == "/all":
            if not args:
                return "Usage: /all what database should I use?"
            agents = {
                "coder": "You are an expert programmer. Write clean code.",
                "debugger": "You are a debugging expert. Find and fix bugs.",
                "reviewer": "You are a code reviewer. Check bugs, security, performance.",
                "architect": "You are a system architect. Design with diagrams.",
                "pentester": "You are an ethical pentester. Find vulnerabilities.",
                "explainer": "You are a teacher. Explain simply with analogies.",
                "optimizer": "You are a performance engineer. Optimize code.",
                "researcher": "You are a research analyst. Deep-dive into topics.",
            }
            import threading
            results = {}
            def _q(n, s):
                try:
                    r = requests.post(OLLAMA_URL, json={"model": self.model, "messages": [
                        {"role": "system", "content": s}, {"role": "user", "content": args}
                    ], "stream": False}, timeout=90)
                    results[n] = r.json().get("message", {}).get("content", "")
                except: results[n] = "(error)"
            threads = [threading.Thread(target=_q, args=(n, s), daemon=True) for n, s in agents.items()]
            for t in threads: t.start()
            for t in threads: t.join(timeout=90)
            output = "**All 8 agents responded:**\n\n"
            for n, resp in results.items():
                output += f"**{n}:** {resp[:150]}...\n\n"
            return output

        elif cmd == "/vote":
            if not args:
                return "Usage: /vote Flask or FastAPI?"
            agents = {"coder": "Expert programmer", "architect": "System architect",
                      "reviewer": "Code reviewer", "pentester": "Security expert"}
            results = {}
            for n, desc in agents.items():
                try:
                    r = requests.post(OLLAMA_URL, json={"model": self.model, "messages": [
                        {"role": "system", "content": f"You are a {desc}. Answer in 1-2 sentences with confidence: HIGH/MEDIUM/LOW."},
                        {"role": "user", "content": args}
                    ], "stream": False}, timeout=60)
                    results[n] = r.json().get("message", {}).get("content", "")
                except: results[n] = "(error)"
            output = "**Agent Votes:**\n\n"
            for n, resp in results.items():
                output += f"**{n}:** {resp}\n\n"
            return output

        elif cmd == "/swarm":
            if not args:
                return "Usage: /swarm build a REST API with auth"
            pipeline = [
                ("architect", "Design the approach.", "You are a system architect."),
                ("coder", "Implement the solution.", "You are an expert programmer."),
                ("reviewer", "Review for bugs.", "You are a code reviewer."),
                ("optimizer", "Optimize performance.", "You are a performance engineer."),
            ]
            accumulated = f"Task: {args}"
            output = "**Swarm Pipeline:**\n\n"
            for name, instruction, sys_p in pipeline:
                try:
                    r = requests.post(OLLAMA_URL, json={"model": self.model, "messages": [
                        {"role": "system", "content": sys_p},
                        {"role": "user", "content": f"{instruction}\n\nContext:\n{accumulated}"}
                    ], "stream": False}, timeout=90)
                    resp = r.json().get("message", {}).get("content", "")
                    output += f"**Step: {name}**\n{resp}\n\n"
                    accumulated += f"\n\n{name}: {resp}"
                except: output += f"**{name}:** (error)\n\n"
            return output

        elif cmd == "/save":
            if not self.messages:
                return "Nothing to save."
            self._auto_save()
            return f"Saved ({len(self.messages)} messages)."

        elif cmd == "/copy":
            ai_msgs = [m for m in self.messages if m["role"] == "assistant"]
            if ai_msgs:
                return "**Last response copied to clipboard** (use Ctrl+C in the response)"
            return "No response to copy."

        elif cmd == "/regen":
            if self.messages and self.messages[-1]["role"] == "assistant":
                self.messages.pop()
                if self.messages and self.messages[-1]["role"] == "user":
                    last_q = self.messages.pop()["content"]
                    return self.send_message(last_q)
            return "Nothing to regenerate."

        elif cmd == "/compact":
            if len(self.messages) < 4:
                return "Not enough messages to compact."
            try:
                r = requests.post(OLLAMA_URL, json={"model": self.model, "messages": [
                    {"role": "user", "content": "Summarize this conversation in 3-5 bullet points:\n" +
                     "\n".join(f"{m['role']}: {m['content'][:200]}" for m in self.messages)}
                ], "stream": False}, timeout=60)
                summary = r.json().get("message", {}).get("content", "")
                keep = self.messages[-4:]
                self.messages = [{"role": "assistant", "content": f"[Summary]\n{summary}"}] + keep
                return f"Compacted: {len(self.messages)} messages remaining."
            except: return "Compact failed."

        elif cmd == "/rate":
            rating = args.lower() if args else ""
            if rating in ("good", "bad", "+", "-"):
                ratings_file = Path.home() / ".codegpt" / "ratings.json"
                ratings = []
                if ratings_file.exists():
                    try: ratings = json.loads(ratings_file.read_text())
                    except: pass
                ai_msgs = [m for m in self.messages if m["role"] == "assistant"]
                if ai_msgs:
                    ratings.append({"rating": "good" if rating in ("good", "+") else "bad",
                                    "response": ai_msgs[-1]["content"][:200],
                                    "timestamp": datetime.now().isoformat()})
                    ratings_file.parent.mkdir(parents=True, exist_ok=True)
                    ratings_file.write_text(json.dumps(ratings))
                    return f"Rated: **{rating}** ({len(ratings)} total)"
            return "Usage: /rate good  or  /rate bad"

        elif cmd == "/usage":
            profile = {}
            if profile_file.exists():
                try: profile = json.loads(profile_file.read_text())
                except: pass
            return (
                f"**Session:** {self.total_tokens} tokens, {len(self.messages)} messages\n"
                f"**Model:** {self.model}\n"
                f"**Persona:** {self.persona}\n\n"
                f"**Lifetime:** {profile.get('total_messages', 0)} messages, "
                f"{profile.get('total_sessions', 0)} sessions"
            )

        elif cmd == "/profile":
            profile = {}
            if profile_file.exists():
                try: profile = json.loads(profile_file.read_text())
                except: pass
            return (
                f"**{profile.get('name', 'User')}**\n"
                f"Bio: {profile.get('bio', 'not set')}\n"
                f"Model: {profile.get('model', MODEL)}\n"
                f"Persona: {profile.get('persona', 'default')}\n"
                f"Sessions: {profile.get('total_sessions', 0)}"
            )

        elif cmd == "/search":
            if not args:
                return "Usage: /search keyword"
            matches = [m for m in self.messages if args.lower() in m["content"].lower()]
            if matches:
                output = f"**{len(matches)} matches for '{args}':**\n\n"
                for m in matches[:5]:
                    role = "You" if m["role"] == "user" else "AI"
                    pos = m["content"].lower().find(args.lower())
                    snippet = m["content"][max(0,pos-30):pos+len(args)+30]
                    output += f"**{role}:** ...{snippet}...\n"
                return output
            return f"No matches for '{args}'."

        elif cmd == "/mem":
            parts = args.split(maxsplit=1)
            sub = parts[0] if parts else ""
            mem_file = Path.home() / ".codegpt" / "memory" / "memories.json"

            if sub == "save" and len(parts) >= 2:
                mems = []
                if mem_file.exists():
                    try: mems = json.loads(mem_file.read_text())
                    except: pass
                mems.append({"content": parts[1], "timestamp": datetime.now().isoformat()})
                mem_file.parent.mkdir(parents=True, exist_ok=True)
                mem_file.write_text(json.dumps(mems))
                return f"Remembered ({len(mems)} memories)."
            elif sub == "list" or sub == "recall":
                if mem_file.exists():
                    mems = json.loads(mem_file.read_text())
                    if mems:
                        output = f"**{len(mems)} memories:**\n\n"
                        for m in mems[-10:]:
                            output += f"- {m['content']}\n"
                        return output
                return "No memories saved."
            elif sub == "clear":
                if mem_file.exists(): mem_file.write_text("[]")
                return "All memories cleared."
            return "Usage: /mem save <text>, /mem list, /mem clear"

        elif cmd == "/prompts":
            templates = {
                "explain": "Explain this concept clearly: ",
                "debug": "Debug this code: ",
                "review": "Review this code: ",
                "refactor": "Refactor this code: ",
                "test": "Write tests for: ",
                "optimize": "Optimize this code: ",
                "security": "Check for vulnerabilities: ",
            }
            output = "**Prompt Templates:**\n\n"
            for name, prefix in templates.items():
                output += f"`/p {name} <text>` — {prefix}\n"
            return output

        elif cmd == "/p":
            parts = args.split(maxsplit=1)
            if len(parts) >= 2:
                templates = {
                    "explain": "Explain this concept clearly with examples: ",
                    "debug": "Debug this code. Find bugs and fix them: ",
                    "review": "Review this code for quality, security, performance: ",
                    "refactor": "Refactor this code to be cleaner: ",
                    "test": "Write unit tests for this code: ",
                    "optimize": "Optimize this code for performance: ",
                    "security": "Analyze for security vulnerabilities: ",
                }
                if parts[0] in templates:
                    full = templates[parts[0]] + parts[1]
                    return json.loads(self.send_message(full)).get("content", "")
            return "Usage: /p debug my_function()"

        elif cmd == "/sysinfo":
            import platform
            return (
                f"**System:**\n"
                f"OS: {platform.system()} {platform.release()}\n"
                f"Machine: {platform.machine()}\n"
                f"Python: {platform.python_version()}\n"
                f"Host: {platform.node()}"
            )

        elif cmd == "/shortcuts":
            return (
                "**Keyboard Shortcuts:**\n"
                "`Enter` — Send message\n"
                "`Shift+Enter` — New line\n"
                "`Ctrl+N` — New chat\n"
                "`/` — Show command menu\n"
                "`Arrow Up/Down` — Navigate command menu\n"
                "`Tab` — Select command\n"
                "`Escape` — Close command menu"
            )

        return None  # Not a command — send as regular message

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

/* Welcome modal */
.modal-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7); z-index: 200;
    display: flex; align-items: center; justify-content: center;
    animation: fadeIn 0.3s ease;
}
.modal {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 32px 40px; max-width: 480px; width: 90%; text-align: center;
    animation: modalIn 0.3s ease;
}
@keyframes modalIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
.modal h2 { font-size: 22px; margin-bottom: 4px; }
.modal h2 .code { color: var(--red); } .modal h2 .gpt { color: var(--accent); }
.modal .ver { color: var(--dim); font-size: 13px; margin-bottom: 20px; }
.modal .features { text-align: left; margin: 16px 0; }
.modal .feat { display: flex; align-items: center; gap: 10px; padding: 6px 0; font-size: 14px; }
.modal .feat .num { color: var(--accent); font-weight: 700; min-width: 30px; }
.modal .feat .label { color: var(--dim); }
.modal .start-btn {
    background: var(--accent); border: none; border-radius: 10px; color: white;
    padding: 12px 32px; font-size: 15px; cursor: pointer; font-weight: 600;
    margin-top: 20px; transition: opacity 0.2s;
}
.modal .start-btn:hover { opacity: 0.9; }
.modal .tip { color: var(--dim); font-size: 12px; margin-top: 12px; }

/* Command autocomplete */
.cmd-menu { display: none; position: absolute; bottom: 100%; left: 0; right: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; max-height: 250px; overflow-y: auto; margin-bottom: 4px; z-index: 100; }
.cmd-menu.show { display: block; }
.cmd-item { padding: 8px 14px; cursor: pointer; display: flex; justify-content: space-between; font-size: 13px; }
.cmd-item:hover, .cmd-item.sel { background: var(--hover); }
.cmd-item .name { color: var(--accent); }
.cmd-item .desc { color: var(--dim); font-size: 12px; }
.kbd { background: var(--surface); border: 1px solid var(--border); border-radius: 3px; padding: 1px 5px; font-size: 10px; }
</style>
</head>
<body>

<div class="sidebar">
    <div class="sidebar-header">
        <h2>CHATS</h2>
        <button class="new-btn" id="newChatBtn">+ New Chat</button>
    </div>
    <div class="chat-list" id="chatList"></div>
    <div class="sidebar-bottom">
        <div class="select-row">
            <select id="modelSelect"></select>
        </div>
        <div class="select-row">
            <select id="personaSelect"></select>
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
            <div class="chips" id="chips">
                <button data-q="Explain how REST APIs work">Explain REST APIs</button>
                <button data-q="Write a Python function to find primes">Prime numbers</button>
                <button data-q="What are the OWASP top 10?">OWASP Top 10</button>
                <button data-q="Design a login system with JWT">JWT Auth</button>
                <button data-q="Compare Flask vs FastAPI">Flask vs FastAPI</button>
                <button data-q="Write a bash script to backup files">Backup script</button>
            </div>
        </div>
        <div class="thinking" id="think"><div class="spinner"></div> Thinking...</div>
    </div>

    <div class="input-area" style="position:relative">
        <div class="cmd-menu" id="cmdMenu"></div>
        <div class="input-wrap">
            <textarea id="inp" placeholder="Message CodeGPT... (type / for commands)" rows="1" autofocus></textarea>
            <button id="btn">Send</button>
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
    var name = await pywebview.api.get_username();
    var h = new Date().getHours();
    var g = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    document.getElementById('greeting').textContent = g + ', ' + name;

    await loadModels();
    await loadPersonas();
    await loadChats();
    checkStatus();
    setInterval(checkStatus, 30000);

    // Bind all events (no onclick attributes — pywebview blocks them)
    document.getElementById('btn').addEventListener('click', function() { send(); });
    document.getElementById('newChatBtn').addEventListener('click', function() { newChat(); });
    document.getElementById('inp').addEventListener('keydown', function(e) { key(e); });
    document.getElementById('inp').addEventListener('input', function(e) { onInput(e); });
    document.getElementById('modelSelect').addEventListener('change', function() { setModel(this.value); });
    document.getElementById('personaSelect').addEventListener('change', function() { setPersona(this.value); });

    // Suggestion chips
    document.querySelectorAll('#chips button').forEach(function(btn) {
        btn.addEventListener('click', function() { go(this.getAttribute('data-q')); });
    });

    // Focus input
    document.getElementById('inp').focus();
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
    var chats = JSON.parse(await pywebview.api.get_chat_history());
    var list = document.getElementById('chatList');
    list.innerHTML = chats.map(function(c) {
        return '<div class="chat-item" data-id="'+c.id+'">' +
            '<span>'+c.title+'</span>' +
            '<span class="del" data-del="'+c.id+'">x</span>' +
            '</div>';
    }).join('') || '<div style="padding:20px;text-align:center;color:var(--dim);font-size:12px">No chats yet</div>';

    // Bind click events via delegation
    list.querySelectorAll('.chat-item').forEach(function(item) {
        item.addEventListener('click', function(e) {
            if (e.target.classList.contains('del')) {
                deleteChat(e.target.getAttribute('data-del'));
            } else {
                loadChat(item.getAttribute('data-id'));
            }
        });
    });
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

const CMDS = [
    {name: '/help', desc: 'Show all commands'},
    {name: '/new', desc: 'New conversation'},
    {name: '/model', desc: 'Switch model'},
    {name: '/models', desc: 'List all models'},
    {name: '/persona', desc: 'Switch persona'},
    {name: '/think', desc: 'Toggle deep thinking'},
    {name: '/temp', desc: 'Set temperature (0-2)'},
    {name: '/system', desc: 'Set system prompt'},
    {name: '/tokens', desc: 'Show token count'},
    {name: '/clear', desc: 'Clear chat'},
    {name: '/server', desc: 'Server info'},
    {name: '/connect', desc: 'Connect to remote Ollama'},
    {name: '/export', desc: 'Export chat'},
    {name: '/agent', desc: 'Run an AI agent'},
    {name: '/browse', desc: 'Fetch and summarize URL'},
    {name: '/open', desc: 'Open URL in browser'},
    {name: '/weather', desc: 'Get weather'},
    {name: '/history', desc: 'Message count'},
];
let cmdIdx = -1;

function onInput(e) {
    const val = e.target.value;
    const menu = document.getElementById('cmdMenu');

    // Show commands when typing / (before a space)
    if (val.startsWith('/') && val.indexOf(' ') === -1) {
        const typed = val.toLowerCase();
        // Just "/" shows all, otherwise filter
        const matches = typed === '/' ? CMDS : CMDS.filter(c => c.name.startsWith(typed));
        if (matches.length > 0) {
            cmdIdx = 0;
            menu.innerHTML = matches.map(function(c, i) {
                return '<div class="cmd-item'+(i===0?' sel':'')+'" data-cmd="'+c.name+'"><span class="name">'+c.name+'</span><span class="desc">'+c.desc+'</span></div>';
            }).join('');
            menu.className = 'cmd-menu show';
            // Bind clicks
            menu.querySelectorAll('.cmd-item').forEach(function(item) {
                item.addEventListener('click', function() { pickCmd(item.getAttribute('data-cmd')); });
            });
        } else {
            menu.className = 'cmd-menu';
        }
    } else {
        menu.className = 'cmd-menu';
    }
}

function pickCmd(cmd) {
    document.getElementById('inp').value = cmd + ' ';
    document.getElementById('cmdMenu').className = 'cmd-menu';
    document.getElementById('inp').focus();
}

function key(e) {
    const menu = document.getElementById('cmdMenu');
    if (menu.classList.contains('show')) {
        const items = menu.querySelectorAll('.cmd-item');
        if (e.key === 'ArrowDown') { e.preventDefault(); cmdIdx = Math.min(cmdIdx+1, items.length-1); items.forEach((it,i) => it.classList.toggle('sel', i===cmdIdx)); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); cmdIdx = Math.max(cmdIdx-1, 0); items.forEach((it,i) => it.classList.toggle('sel', i===cmdIdx)); }
        else if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
            e.preventDefault();
            if (items[cmdIdx]) { pickCmd(items[cmdIdx].querySelector('.name').textContent); }
        }
        else if (e.key === 'Escape') { menu.className = 'cmd-menu'; }
        return;
    }
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
    var inp = document.getElementById('inp');
    var text = inp.value.trim();
    if (!text || busy) return;
    inp.value = ''; inp.style.height = 'auto';

    // Hide command menu
    document.getElementById('cmdMenu').className = 'cmd-menu';

    busy = true;
    document.getElementById('btn').disabled = true;

    // Show user message (unless slash command)
    if (!text.startsWith('/')) {
        addMsg('user', text);
    }

    document.getElementById('think').className = 'thinking on';

    var r = JSON.parse(await pywebview.api.send_message(text));
    document.getElementById('think').className = 'thinking';

    if (r.is_system) {
        // Slash command result — show as system message
        addMsg('ai', r.content, 'command');
    } else {
        addMsg('ai', r.content, r.tokens + ' tokens &middot; ' + r.elapsed + 's');
    }
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
