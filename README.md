# eBible · Ethiopian Orthodox Bible (TUI)

Amharic Bible TUI with on-the-spot translation.

## Quick Install (Termux)
    mkdir -p ~/apps && cd ~/apps
    git clone https://github.com/joeltco/ebible-tui.git
    cd ebible-tui
    pkg install -y python pip translate-shell
    pip install "textual==0.62.0" "rich==13.7.1" "pyyaml"

## Quick Install (Debian/Ubuntu)
    mkdir -p ~/apps && cd ~/apps
    git clone https://github.com/joeltco/ebible-tui.git
    cd ebible-tui
    sudo apt update && sudo apt install -y python3 python3-pip translate-shell
    pip3 install "textual==0.62.0" "rich==13.7.1" "pyyaml"

## Optional: one-time launcher (no venv)
    mkdir -p ~/bin
    cat > ~/bin/ebible <<LAUNCH
    #!/usr/bin/env bash
    set -e
    cd "$HOME/apps/ebible-tui" || exit 1
    python3 -c "import textual,rich,yaml" 2>/dev/null || pip3 install textual==0.62.0 rich==13.7.1 pyyaml >/dev/null
    exec python3 -m ebible_tui "$@"
    LAUNCH
    chmod +x ~/bin/ebible

## Run
    ebible

Notes:
- No virtualenv required.
- Translation uses translate-shell (the "trans" command).
- SSH keys/tokens are only needed if you plan to push to GitHub; cloning via HTTPS is public.
