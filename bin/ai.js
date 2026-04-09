#!/usr/bin/env node
const { spawn, spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// --- `codegpt update` — self-update via npm ---
// Intercept BEFORE locating Python so update works even if Python is broken.
if (process.argv[2] === "update" || process.argv[2] === "upgrade") {
  const pkg = require("../package.json");
  const currentVersion = pkg.version;
  console.log(`CodeGPT v${currentVersion} → checking for updates...`);

  // Resolve latest version from registry
  const view = spawnSync("npm", ["view", "codegpt-ai", "version"], {
    encoding: "utf8",
    shell: true,
  });
  if (view.status !== 0) {
    console.error("ERROR: Could not reach npm registry.");
    console.error(view.stderr || view.stdout);
    process.exit(1);
  }
  const latest = (view.stdout || "").trim();
  if (!latest) {
    console.error("ERROR: Empty version response from npm.");
    process.exit(1);
  }

  if (latest === currentVersion) {
    console.log(`Already on latest (${latest}). Nothing to do.`);
    process.exit(0);
  }

  console.log(`Updating ${currentVersion} → ${latest} ...`);

  if (process.platform === "win32") {
    // Windows self-update workaround: the currently-running codegpt.cmd
    // and the ai.js node process both hold file handles on the package
    // directory npm needs to rename. POSIX lets you rename open files,
    // Windows does not — so a plain spawnSync("npm install -g ...") hits
    // EBUSY on rename. Fix: write a small .cmd to TEMP that waits 2s
    // (long enough for THIS process to exit and release the handles),
    // runs the install, reports the result, and pauses so the user can
    // read it. Spawn detached + unref, then exit 0 immediately.
    const os = require("os");
    const ts = Date.now();
    const batPath = path.join(os.tmpdir(), `codegpt-update-${ts}.cmd`);
    const batBody =
      "@echo off\r\n" +
      "timeout /t 2 /nobreak >nul 2>&1\r\n" +
      `echo Updating codegpt-ai to ${latest}...\r\n` +
      `call npm install -g codegpt-ai@${latest}\r\n` +
      "if %ERRORLEVEL% NEQ 0 (\r\n" +
      "  echo.\r\n" +
      "  echo Update failed. Try running in an elevated PowerShell.\r\n" +
      "  pause\r\n" +
      "  del \"%~f0\"\r\n" +
      "  exit /b 1\r\n" +
      ")\r\n" +
      "echo.\r\n" +
      `echo Updated to v${latest}. Run 'codegpt --version' in a new shell to confirm.\r\n` +
      "pause\r\n" +
      "del \"%~f0\"\r\n";

    try {
      fs.writeFileSync(batPath, batBody, "utf8");
    } catch (e) {
      console.error("ERROR: Could not write update script:", e.message);
      console.error("\nManual fallback — run this in a fresh PowerShell:");
      console.error(`  npm install -g codegpt-ai@${latest}\n`);
      process.exit(1);
    }

    // Launch the .cmd in a new window via `start` so the user sees the
    // install progress. detached + ignored stdio releases the parent's
    // grip on the child so we can exit cleanly.
    const child = spawn("cmd", ["/c", "start", "CodeGPT Update", "cmd", "/c", batPath], {
      detached: true,
      stdio: "ignore",
      shell: false,
      windowsHide: false,
    });
    child.unref();

    console.log(
      `\nUpdate dispatched to a new window (Windows file-lock workaround).\n` +
      `This window will return to your prompt; check the new window for install progress.\n`
    );
    process.exit(0);
  }

  // POSIX: direct sync install works — no file-lock issues.
  const install = spawnSync("npm", ["install", "-g", `codegpt-ai@${latest}`], {
    stdio: "inherit",
    shell: true,
  });
  if (install.status !== 0) {
    console.error(`\nERROR: Update failed (exit ${install.status}).`);
    console.error("Try running with elevated privileges or check your npm permissions.");
    process.exit(install.status || 1);
  }

  console.log(`\n✓ Updated to v${latest}. Run 'codegpt --version' to confirm.`);
  process.exit(0);
}

// --- `codegpt --version` / `-v` ---
if (process.argv[2] === "--version" || process.argv[2] === "-v") {
  const pkg = require("../package.json");
  console.log(`codegpt-ai v${pkg.version}`);
  process.exit(0);
}

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
