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

// Find chat.py
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

// If Python + chat.py found, use full Python CLI
if (python && chatPy) {
  const args = [chatPy, ...process.argv.slice(2)];
  const child = spawn(python, args, {
    stdio: "inherit",
    cwd: path.dirname(chatPy),
    env: { ...process.env, PYTHONUTF8: "1" },
  });
  child.on("exit", (code) => process.exit(code || 0));
} else {
  // Fallback: Node.js chat client (no Python needed)
  if (!python) {
    console.log("  Python not found — using Node.js mode.");
    console.log("  Install Python for the full 80+ command experience.\n");
  } else {
    console.log("  chat.py not found — using Node.js mode.\n");
  }
  require("./chat.js");
}
