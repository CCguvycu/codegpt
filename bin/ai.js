#!/usr/bin/env node
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

// Find Python
const pythonCmds = process.platform === "win32"
  ? ["python", "python3", "py"]
  : ["python3", "python"];

function findPython() {
  for (const cmd of pythonCmds) {
    try {
      require("child_process").execSync(`${cmd} --version`, { stdio: "pipe" });
      return cmd;
    } catch {}
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error("Python not found. Install from https://python.org");
  process.exit(1);
}

// Find chat.py — check npm package dir first, then common locations
const locations = [
  path.join(__dirname, "..", "chat.py"),
  path.join(process.env.HOME || process.env.USERPROFILE, "codegpt", "chat.py"),
  path.join(process.env.HOME || process.env.USERPROFILE, ".codegpt", "src", "chat.py"),
];

let chatPy = null;
for (const loc of locations) {
  if (fs.existsSync(loc)) {
    chatPy = loc;
    break;
  }
}

if (!chatPy) {
  console.error("CodeGPT not found. Run: codegpt-setup");
  process.exit(1);
}

// Pass all args through to Python
const args = [chatPy, ...process.argv.slice(2)];
const child = spawn(python, args, {
  stdio: "inherit",
  cwd: path.dirname(chatPy),
  env: { ...process.env, PYTHONUTF8: "1" },
});

child.on("exit", (code) => process.exit(code || 0));
