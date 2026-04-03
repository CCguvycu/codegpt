#!/data/data/com.termux/files/usr/bin/bash
# CodeGPT Installer for Termux
# Run: curl -sL https://raw.githubusercontent.com/CCguvycu/codegpt/main/install-termux.sh | bash

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  CodeGPT — Termux Installer          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Step 1: Install system deps
echo "  [1/6] Installing system packages..."
pkg update -y -q 2>/dev/null
pkg install -y python git cmake golang curl 2>/dev/null

pip install --quiet requests rich prompt-toolkit 2>/dev/null

# Step 2: Install Ollama
echo "  [2/6] Installing Ollama..."
if command -v ollama &>/dev/null; then
    echo "  Ollama already installed."
else
    echo "  Building Ollama from source (this takes a few minutes)..."

    # Method 1: Try the official install script
    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null && {
        echo "  Ollama installed via official script."
    } || {
        # Method 2: Build from Go source
        echo "  Official script failed. Building from Go..."
        pkg install -y golang 2>/dev/null

        OLLAMA_BUILD="$HOME/.ollama-build"
        rm -rf "$OLLAMA_BUILD"
        git clone --depth 1 https://github.com/ollama/ollama.git "$OLLAMA_BUILD" 2>/dev/null

        cd "$OLLAMA_BUILD"
        go build -o "$PREFIX/bin/ollama" . 2>/dev/null && {
            echo "  Ollama built from source."
        } || {
            # Method 3: Download pre-built ARM binary
            echo "  Go build failed. Trying pre-built binary..."
            ARCH=$(uname -m)
            if [ "$ARCH" = "aarch64" ]; then
                curl -sL "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-arm64" -o "$PREFIX/bin/ollama" 2>/dev/null && {
                    chmod +x "$PREFIX/bin/ollama"
                    echo "  Ollama binary downloaded."
                } || {
                    echo "  WARNING: Could not install Ollama."
                    echo "  You can connect to your PC's Ollama instead."
                }
            else
                echo "  WARNING: Unsupported arch ($ARCH). Connect to PC Ollama."
            fi
        }

        rm -rf "$OLLAMA_BUILD"
        cd "$HOME"
    }
fi

# Step 3: Start Ollama and pull model
echo "  [3/6] Setting up Ollama..."
if command -v ollama &>/dev/null; then
    # Start Ollama in background
    if ! curl -s http://localhost:11434/api/tags &>/dev/null 2>&1; then
        echo "  Starting Ollama server..."
        ollama serve &>/dev/null &
        sleep 5
    fi

    # Pull smallest model if none exist
    if ! ollama list 2>/dev/null | grep -q ":"; then
        echo "  Pulling llama3.2:1b (smallest model, ~1.3GB)..."
        echo "  This may take a few minutes on mobile data."
        ollama pull llama3.2:1b 2>/dev/null && {
            echo "  Model ready."
        } || {
            echo "  WARNING: Model pull failed. Try manually: ollama pull llama3.2:1b"
        }
    else
        echo "  Models already available."
    fi

    # Auto-start Ollama on Termux boot
    mkdir -p "$HOME/.termux/boot"
    echo '#!/data/data/com.termux/files/usr/bin/bash' > "$HOME/.termux/boot/ollama.sh"
    echo 'ollama serve &>/dev/null &' >> "$HOME/.termux/boot/ollama.sh"
    chmod +x "$HOME/.termux/boot/ollama.sh"
    echo "  Ollama auto-start enabled."
else
    echo "  Ollama not available. You can connect to your PC:"
    echo "  When ai asks, enter: http://YOUR_PC_IP:11434/api/chat"
fi

# Step 4: Clone or update CodeGPT
INSTALL_DIR="$HOME/codegpt"
echo "  [4/6] Setting up CodeGPT..."

if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull --quiet 2>/dev/null || true
else
    rm -rf "$INSTALL_DIR"
    git clone https://github.com/CCguvycu/codegpt.git "$INSTALL_DIR" 2>/dev/null
fi

# Step 5: Install ai command
echo "  [5/6] Installing ai command..."
cd "$INSTALL_DIR"
pip install -e . --quiet 2>/dev/null || {
    # Fallback: create wrapper script
    cat > "$PREFIX/bin/ai" << 'WRAPPER'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/codegpt && python -m ai_cli "$@"
WRAPPER
    chmod +x "$PREFIX/bin/ai"
}

# Step 6: Create shortcuts
echo "  [6/6] Creating shortcuts..."
mkdir -p "$HOME/.shortcuts"
cat > "$HOME/.shortcuts/CodeGPT" << 'SHORTCUT'
#!/data/data/com.termux/files/usr/bin/bash
# Start Ollama if not running
command -v ollama &>/dev/null && ! curl -s http://localhost:11434/api/tags &>/dev/null 2>&1 && ollama serve &>/dev/null &
sleep 1
ai
SHORTCUT
chmod +x "$HOME/.shortcuts/CodeGPT"

# Also add alias to bashrc
if ! grep -q "alias ai=" "$HOME/.bashrc" 2>/dev/null; then
    echo '# CodeGPT' >> "$HOME/.bashrc"
    echo 'command -v ollama &>/dev/null && ! curl -s http://localhost:11434/api/tags &>/dev/null 2>&1 && ollama serve &>/dev/null &' >> "$HOME/.bashrc"
    echo "" >> "$HOME/.bashrc"
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  Installation complete!               ║"
echo "  ║                                       ║"
echo "  ║  Type: ai                             ║"
echo "  ║                                       ║"
if command -v ollama &>/dev/null; then
echo "  ║  Ollama: installed                    ║"
echo "  ║  Model:  llama3.2:1b                  ║"
else
echo "  ║  Ollama: not available                ║"
echo "  ║  Connect to PC when prompted          ║"
fi
echo "  ║                                       ║"
echo "  ║  Termux Widget shortcut created       ║"
echo "  ║  Ollama auto-starts on boot           ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
