#!/usr/bin/env node
/**
 * Post-install: check environment, DO NOT auto-install pip packages.
 * Users must explicitly run `ai setup` or `pip install` themselves.
 * This prevents supply chain attacks via transitive dependency hijacking.
 */

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

console.log("\n  CodeGPT installed successfully.\n");

if (python) {
  // Check if deps are already installed
  let depsOk = true;
  try {
    execSync(`${python} -c "import requests, rich, prompt_toolkit"`, { stdio: "pipe" });
  } catch {
    depsOk = false;
  }

  if (depsOk) {
    console.log("  Python dependencies: ready");
  } else {
    console.log("  Python found but dependencies missing.");
    console.log("  Run: pip install requests rich prompt-toolkit");
  }
} else {
  console.log("  Python not found — Node.js mode will be used.");
  console.log("  Install Python for the full 80+ command experience.");
}

console.log("\n  Type: ai");
console.log("  Docs: https://github.com/CCguvycu/codegpt\n");
