#!/data/data/com.termux/files/usr/bin/bash
# CodeGPT Installer for Termux
# Run: curl -sL https://raw.githubusercontent.com/CCguvycu/codegpt/main/install-termux.sh | bash

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  CodeGPT — Termux Installer          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# --- Verification functions ---
verify_sha256() {
    local file="$1"
    local expected="$2"
    if [ -z "$expected" ]; then return 0; fi
    local actual
    actual=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1)
    if [ "$actual" = "$expected" ]; then
        echo "  Checksum verified."
        return 0
    else
        echo "  CHECKSUM MISMATCH!"
        echo "  Expected: $expected"
        echo "  Got:      $actual"
        echo "  File may be tampered with. Aborting."
        rm -f "$file"
        return 1
    fi
}

verify_https_url() {
    local url="$1"
    # Only allow HTTPS URLs from trusted domains
    case "$url" in
        https://github.com/*|https://raw.githubusercontent.com/*|https://ollama.com/*)
            return 0
            ;;
        *)
            echo "  WARNING: Untrusted URL: $url"
            return 1
            ;;
    esac
}

# Step 1: Install system deps
echo "  [1/6] Installing system packages..."
pkg update -y -q 2>/dev/null
pkg install -y python git curl 2>/dev/null

pip install --quiet requests rich prompt-toolkit 2>/dev/null

# Step 2: Install Ollama (hardened — no curl|sh)
echo "  [2/6] Installing Ollama..."
if command -v ollama &>/dev/null; then
    echo "  Ollama already installed."
else
    ARCH=$(uname -m)
    OLLAMA_INSTALLED=false

    if [ "$ARCH" = "aarch64" ]; then
        echo "  Downloading Ollama for ARM64..."
        OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-linux-arm64"
        OLLAMA_TMP="$HOME/.ollama-download"

        # Download to temp file first
        if curl -fsSL "$OLLAMA_URL" -o "$OLLAMA_TMP" 2>/dev/null; then
            # Verify it's actually a binary (not an HTML error page)
            FILE_TYPE=$(file "$OLLAMA_TMP" 2>/dev/null || echo "unknown")
            if echo "$FILE_TYPE" | grep -qi "ELF"; then
                mv "$OLLAMA_TMP" "$PREFIX/bin/ollama"
                chmod +x "$PREFIX/bin/ollama"
                echo "  Ollama installed (ARM64 binary)."
                OLLAMA_INSTALLED=true
            else
                echo "  Downloaded file is not a valid binary."
                rm -f "$OLLAMA_TMP"
            fi
        else
            echo "  Download failed."
            rm -f "$OLLAMA_TMP"
        fi
    elif [ "$ARCH" = "x86_64" ]; then
        echo "  Downloading Ollama for x86_64..."
        OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64"
        OLLAMA_TMP="$HOME/.ollama-download"

        if curl -fsSL "$OLLAMA_URL" -o "$OLLAMA_TMP" 2>/dev/null; then
            FILE_TYPE=$(file "$OLLAMA_TMP" 2>/dev/null || echo "unknown")
            if echo "$FILE_TYPE" | grep -qi "ELF"; then
                mv "$OLLAMA_TMP" "$PREFIX/bin/ollama"
                chmod +x "$PREFIX/bin/ollama"
                echo "  Ollama installed (x86_64 binary)."
                OLLAMA_INSTALLED=true
            else
                rm -f "$OLLAMA_TMP"
            fi
        else
            rm -f "$OLLAMA_TMP"
        fi
    fi

    if [ "$OLLAMA_INSTALLED" = false ]; then
        echo "  Could not install Ollama automatically."
        echo "  You can connect to your PC's Ollama instead."
        echo "  Use /connect YOUR_PC_IP inside CodeGPT."
    fi
fi

# Step 3: Start Ollama and pull model
echo "  [3/6] Setting up Ollama..."
if command -v ollama &>/dev/null; then
    if ! curl -s http://localhost:11434/api/tags &>/dev/null 2>&1; then
        echo "  Starting Ollama server..."
        ollama serve &>/dev/null &
        sleep 5
    fi

    if ! ollama list 2>/dev/null | grep -q ":"; then
        echo "  Pulling llama3.2:1b (~1.3GB)..."
        ollama pull llama3.2:1b 2>/dev/null && {
            echo "  Model ready."
        } || {
            echo "  Model pull failed. Try: ollama pull llama3.2:1b"
        }
    else
        echo "  Models already available."
    fi

    # Auto-start on Termux boot
    mkdir -p "$HOME/.termux/boot"
    cat > "$HOME/.termux/boot/ollama.sh" << 'BOOT'
#!/data/data/com.termux/files/usr/bin/bash
ollama serve &>/dev/null &
BOOT
    chmod +x "$HOME/.termux/boot/ollama.sh"
    echo "  Ollama auto-start enabled."
else
    echo "  Ollama not available."
    echo "  Use /connect YOUR_PC_IP inside CodeGPT."
fi

# Step 4: Clone or update CodeGPT (via HTTPS only)
INSTALL_DIR="$HOME/codegpt"
REPO_URL="https://github.com/CCguvycu/codegpt.git"
echo "  [4/6] Setting up CodeGPT..."

if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull --quiet 2>/dev/null || true
else
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null
fi

# Step 5: Verify repo integrity
echo "  [5/6] Verifying installation..."
cd "$INSTALL_DIR"

# Check key files exist
MISSING=false
for f in chat.py ai_cli/__init__.py ai_cli/__main__.py; do
    if [ ! -f "$f" ]; then
        echo "  MISSING: $f"
        MISSING=true
    fi
done

if [ "$MISSING" = true ]; then
    echo "  Installation incomplete. Try again."
    exit 1
fi

echo "  All files verified."

# Install ai command
pip install -e . --quiet 2>/dev/null || {
    cat > "$PREFIX/bin/ai" << WRAPPER
#!/data/data/com.termux/files/usr/bin/bash
cd ~/codegpt && python -m ai_cli "\$@"
WRAPPER
    chmod +x "$PREFIX/bin/ai"
}

# Step 6: Create shortcuts
echo "  [6/6] Creating shortcuts..."
mkdir -p "$HOME/.shortcuts"
cat > "$HOME/.shortcuts/CodeGPT" << 'SHORTCUT'
#!/data/data/com.termux/files/usr/bin/bash
command -v ollama &>/dev/null && ! curl -s http://localhost:11434/api/tags &>/dev/null 2>&1 && ollama serve &>/dev/null &
sleep 1
cd ~/codegpt && python chat.py
SHORTCUT
chmod +x "$HOME/.shortcuts/CodeGPT"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  Installation complete!               ║"
echo "  ║                                       ║"
echo "  ║  Type: code                           ║"
echo "  ║                                       ║"
if command -v ollama &>/dev/null; then
echo "  ║  Ollama: installed                    ║"
else
echo "  ║  Ollama: use /connect PC_IP           ║"
fi
echo "  ║  Shortcut: CodeGPT (Termux Widget)    ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
