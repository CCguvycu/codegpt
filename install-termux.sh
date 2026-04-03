#!/data/data/com.termux/files/usr/bin/bash
# CodeGPT Installer for Termux
# Run: curl -sL https://raw.githubusercontent.com/ArukuX/codegpt/main/install-termux.sh | bash

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  CodeGPT — Termux Installer          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Step 1: Install deps
echo "  [1/5] Installing dependencies..."
pkg update -y -q
pkg install -y -q python git ollama 2>/dev/null || pkg install -y -q python git

pip install --quiet requests rich prompt-toolkit

# Step 2: Clone or update repo
INSTALL_DIR="$HOME/codegpt"
echo "  [2/5] Setting up CodeGPT..."

if [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
    git pull --quiet 2>/dev/null || true
else
    git clone https://github.com/ArukuX/codegpt.git "$INSTALL_DIR" 2>/dev/null || {
        # If no repo yet, just download the files
        mkdir -p "$INSTALL_DIR/ai_cli"
        echo "  Downloading source..."
        for f in chat.py ai_cli/__init__.py ai_cli/__main__.py ai_cli/updater.py ai_cli/doctor.py pyproject.toml; do
            curl -sL "https://raw.githubusercontent.com/ArukuX/codegpt/main/$f" -o "$INSTALL_DIR/$f" 2>/dev/null || true
        done
    }
fi

# Step 3: Install package
echo "  [3/5] Installing ai command..."
cd "$INSTALL_DIR"
pip install -e . --quiet 2>/dev/null || {
    # Fallback: create wrapper script
    echo '#!/data/data/com.termux/files/usr/bin/bash' > "$PREFIX/bin/ai"
    echo "cd $INSTALL_DIR && python -m ai_cli \"\$@\"" >> "$PREFIX/bin/ai"
    chmod +x "$PREFIX/bin/ai"
}

# Step 4: Setup Ollama
echo "  [4/5] Checking Ollama..."
if command -v ollama &>/dev/null; then
    echo "  Ollama: found"
    # Start Ollama in background if not running
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        echo "  Starting Ollama..."
        ollama serve &>/dev/null &
        sleep 3
    fi
    # Pull a small model if none exist
    if ! ollama list 2>/dev/null | grep -q "llama"; then
        echo "  Pulling llama3.2 (this takes a few minutes)..."
        ollama pull llama3.2:1b
    fi
else
    echo "  Ollama not available on Termux."
    echo "  Option 1: Run Ollama on your PC and connect remotely"
    echo "  Option 2: Install via: pkg install ollama (if available)"
    echo ""
    echo "  To connect to PC Ollama, set in chat.py:"
    echo "    OLLAMA_URL = 'http://YOUR_PC_IP:11434/api/chat'"
fi

# Step 5: Create shortcut
echo "  [5/5] Creating shortcut..."
mkdir -p "$HOME/.shortcuts"
echo '#!/data/data/com.termux/files/usr/bin/bash' > "$HOME/.shortcuts/CodeGPT"
echo 'ai' >> "$HOME/.shortcuts/CodeGPT"
chmod +x "$HOME/.shortcuts/CodeGPT"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  Installation complete!               ║"
echo "  ║                                       ║"
echo "  ║  Type: ai                             ║"
echo "  ║                                       ║"
echo "  ║  Or use the Termux Widget shortcut    ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
