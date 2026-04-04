#!/usr/bin/env node
/**
 * CodeGPT — Node.js CLI (no Python required)
 * Fallback when Python isn't installed. Connects to Ollama directly.
 */

const readline = require("readline");
const http = require("http");
const os = require("os");
const fs = require("fs");
const path = require("path");

// --- Config ---
const HOME = os.homedir();
const CONFIG_DIR = path.join(HOME, ".codegpt");
const PROFILE_FILE = path.join(CONFIG_DIR, "profiles", "cli_profile.json");
const HISTORY_FILE = path.join(CONFIG_DIR, "node_history.json");
const URL_FILE = path.join(CONFIG_DIR, "ollama_url");

let OLLAMA_HOST = process.env.OLLAMA_URL || "http://localhost:11434";
if (OLLAMA_HOST.includes("/api/chat")) OLLAMA_HOST = OLLAMA_HOST.replace("/api/chat", "");

let MODEL = "llama3.2";
let SYSTEM = "You are a helpful AI assistant. Be concise and technical.";
let messages = [];
let history = [];
let totalTokens = 0;
let startTime = Date.now();

// --- Colors ---
const c = {
  cyan: (s) => `\x1b[36m${s}\x1b[0m`,
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  red: (s) => `\x1b[31m${s}\x1b[0m`,
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
  white: (s) => `\x1b[37m${s}\x1b[0m`,
};

// --- Helpers ---
function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function loadProfile() {
  try {
    if (fs.existsSync(PROFILE_FILE)) return JSON.parse(fs.readFileSync(PROFILE_FILE, "utf8"));
  } catch {}
  return { name: "", model: "llama3.2", persona: "default", total_sessions: 0 };
}

function saveProfile(profile) {
  ensureDir(path.dirname(PROFILE_FILE));
  fs.writeFileSync(PROFILE_FILE, JSON.stringify(profile, null, 2));
}

function loadSavedUrl() {
  try {
    if (fs.existsSync(URL_FILE)) {
      const url = fs.readFileSync(URL_FILE, "utf8").trim();
      if (url) return url.replace("/api/chat", "");
    }
  } catch {}
  return null;
}

// --- Ollama API ---
function ollamaRequest(endpoint, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, OLLAMA_HOST);
    const data = JSON.stringify(body);
    const req = http.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeout: 120000,
    }, (res) => {
      let result = "";
      res.on("data", (chunk) => result += chunk);
      res.on("end", () => {
        try { resolve(JSON.parse(result)); } catch { resolve(result); }
      });
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("timeout")); });
    req.write(data);
    req.end();
  });
}

function ollamaGet(endpoint) {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, OLLAMA_HOST);
    http.get(url, { timeout: 5000 }, (res) => {
      let data = "";
      res.on("data", (chunk) => data += chunk);
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch { resolve(null); }
      });
    }).on("error", reject).on("timeout", function() { this.destroy(); reject(new Error("timeout")); });
  });
}

async function streamChat(msgs) {
  return new Promise((resolve, reject) => {
    const url = new URL("/api/chat", OLLAMA_HOST);
    const body = JSON.stringify({
      model: MODEL,
      messages: [{ role: "system", content: SYSTEM }, ...msgs],
      stream: true,
    });

    const req = http.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeout: 120000,
    }, (res) => {
      let full = "";
      process.stdout.write(`\n  ${c.green("AI")} > `);

      res.on("data", (chunk) => {
        const lines = chunk.toString().split("\n").filter(Boolean);
        for (const line of lines) {
          try {
            const obj = JSON.parse(line);
            if (obj.message?.content) {
              process.stdout.write(obj.message.content);
              full += obj.message.content;
            }
            if (obj.eval_count) totalTokens += obj.eval_count;
          } catch {}
        }
      });

      res.on("end", () => {
        process.stdout.write("\n\n");
        resolve(full);
      });
    });

    req.on("error", (e) => {
      console.log(c.red(`\n  Error: ${e.message}`));
      resolve("");
    });
    req.on("timeout", () => { req.destroy(); resolve(""); });
    req.write(body);
    req.end();
  });
}

async function getModels() {
  try {
    const data = await ollamaGet("/api/tags");
    return data?.models?.map((m) => m.name) || [];
  } catch {
    return [];
  }
}

// --- UI ---
const LOGO = `
  ${c.cyan("██████╗ ██████╗ ██████╗ ███████╗")}${c.white(" ██████╗ ██████╗ ████████╗")}
  ${c.cyan("██╔════╝██╔═══██╗██╔══██╗██╔════╝")}${c.white("██╔════╝ ██╔══██╗╚══██╔══╝")}
  ${c.cyan("██║     ██║   ██║██║  ██║█████╗  ")}${c.white("██║  ███╗██████╔╝   ██║   ")}
  ${c.cyan("██║     ██║   ██║██║  ██║██╔══╝  ")}${c.white("██║   ██║██╔═══╝    ██║   ")}
  ${c.cyan("╚██████╗╚██████╔╝██████╔╝███████╗")}${c.white("╚██████╔╝██║        ██║   ")}
  ${c.cyan(" ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝")}${c.white(" ╚═════╝ ╚═╝        ╚═╝   ")}
  ${c.dim("        Your Local AI Assistant — Node.js Edition")}
`;

const COMMANDS = {
  "/help": "Show commands",
  "/model": "Switch model (/model name)",
  "/models": "List available models",
  "/new": "Start new conversation",
  "/history": "Show conversation",
  "/connect": "Connect to remote Ollama (/connect IP)",
  "/server": "Show current server",
  "/clear": "Clear screen",
  "/quit": "Exit",
};

function printHeader() {
  console.clear();
  console.log(LOGO);
  const elapsed = Math.floor((Date.now() - startTime) / 1000 / 60);
  console.log(c.dim(`  ${MODEL} | ${messages.length} msgs | ${totalTokens} tok | ${elapsed}m | ${OLLAMA_HOST}`));
  console.log();
}

function printHelp() {
  console.log(c.bold("\n  Commands:"));
  for (const [cmd, desc] of Object.entries(COMMANDS)) {
    console.log(`  ${c.cyan(cmd.padEnd(14))} ${c.dim(desc)}`);
  }
  console.log();
}

// --- Main ---
async function main() {
  // Load saved URL
  const savedUrl = loadSavedUrl();
  if (savedUrl) OLLAMA_HOST = savedUrl;

  // Load profile
  const profile = loadProfile();
  if (profile.model) MODEL = profile.model;

  // Check Ollama
  let models = await getModels();
  if (!models.length) {
    // Try common IPs
    for (const ip of ["http://192.168.1.237:11434", "http://10.0.2.2:11434"]) {
      OLLAMA_HOST = ip;
      models = await getModels();
      if (models.length) break;
    }
  }

  printHeader();

  if (!models.length) {
    console.log(c.yellow("  No Ollama server found."));
    console.log(c.dim("  Use /connect IP to connect to a remote server."));
    console.log(c.dim("  Or install Ollama: https://ollama.com\n"));
  } else {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    const name = profile.name || "there";
    console.log(c.bold(`  ${greeting}, ${name}.\n`));
  }

  // Update session count
  profile.total_sessions = (profile.total_sessions || 0) + 1;
  saveProfile(profile);

  // REPL
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: `  ${c.cyan(">")} `,
    historySize: 100,
  });

  rl.prompt();

  rl.on("line", async (line) => {
    const input = line.trim();
    if (!input) { rl.prompt(); return; }

    if (input.startsWith("/")) {
      const cmd = input.split(" ")[0].toLowerCase();
      const args = input.slice(cmd.length).trim();

      switch (cmd) {
        case "/quit":
        case "/q":
        case "/exit":
          const elapsed = Math.floor((Date.now() - startTime) / 1000);
          console.log(c.dim(`\n  ${elapsed}s | ${messages.length} msgs | ${totalTokens} tok`));
          process.exit(0);

        case "/help":
        case "/h":
          printHelp();
          break;

        case "/model":
        case "/m":
          if (args) {
            MODEL = args;
            profile.model = MODEL;
            saveProfile(profile);
            console.log(c.green(`  Model: ${MODEL}`));
          } else {
            console.log(c.dim(`  Current: ${MODEL}`));
          }
          break;

        case "/models":
          const mods = await getModels();
          if (mods.length) {
            console.log(c.bold("\n  Models:"));
            mods.forEach((m) => console.log(`  ${m === MODEL ? c.green("* " + m) : c.dim("  " + m)}`));
            console.log();
          } else {
            console.log(c.red("  Ollama not reachable."));
          }
          break;

        case "/new":
        case "/n":
          messages = [];
          printHeader();
          console.log(c.dim("  New conversation.\n"));
          break;

        case "/history":
          if (!messages.length) { console.log(c.dim("  No messages.\n")); break; }
          messages.forEach((m) => {
            const tag = m.role === "user" ? c.cyan("You") : c.green("AI");
            console.log(`  ${tag} > ${m.content.slice(0, 200)}\n`);
          });
          break;

        case "/connect":
        case "/con":
          if (args) {
            let url = args;
            if (!url.startsWith("http")) url = "http://" + url;
            if (!url.includes(":")) url += ":11434";
            OLLAMA_HOST = url;
            const test = await getModels();
            if (test.length) {
              models = test;
              ensureDir(CONFIG_DIR);
              fs.writeFileSync(URL_FILE, OLLAMA_HOST + "/api/chat");
              console.log(c.green(`  Connected: ${OLLAMA_HOST} (${test.length} models)`));
            } else {
              console.log(c.red(`  Cannot reach ${OLLAMA_HOST}`));
            }
          } else {
            console.log(c.dim("  Usage: /connect 192.168.1.237"));
          }
          break;

        case "/server":
        case "/srv":
          const test2 = await getModels();
          const status = test2.length ? c.green("connected") : c.red("offline");
          console.log(`  ${c.dim("Server:")} ${OLLAMA_HOST} ${status}`);
          break;

        case "/clear":
        case "/c":
          printHeader();
          break;

        default:
          console.log(c.dim(`  Unknown: ${cmd}. Type /help`));
      }

      rl.prompt();
      return;
    }

    // Regular message
    messages.push({ role: "user", content: input });
    const response = await streamChat(messages);
    if (response) {
      messages.push({ role: "assistant", content: response });
    } else {
      messages.pop();
    }
    rl.prompt();
  });

  rl.on("close", () => process.exit(0));
}

main().catch(console.error);
