#!/usr/bin/env node
// Post-install: ensure Python deps are installed
const { execSync } = require("child_process");

const pythonCmds = process.platform === "win32"
  ? ["python", "python3", "py"]
  : ["python3", "python"];

function findPython() {
  for (const cmd of pythonCmds) {
    try {
      execSync(`${cmd} --version`, { stdio: "pipe" });
      return cmd;
    } catch {}
  }
  return null;
}

const python = findPython();

if (!python) {
  console.log("\n  CodeGPT installed but Python not found.");
  console.log("  Install Python from https://python.org");
  console.log("  Then run: pip install requests rich prompt-toolkit\n");
  process.exit(0);
}

// Install Python deps
console.log("  Installing Python dependencies...");
try {
  execSync(`${python} -m pip install requests rich prompt-toolkit --quiet`, {
    stdio: "inherit",
  });
  console.log("  Python dependencies installed.");
} catch {
  console.log("  Warning: Could not install Python deps.");
  console.log("  Run manually: pip install requests rich prompt-toolkit");
}

console.log("\n  CodeGPT ready! Type: ai\n");
