#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# --- Root Check ---
if [ "$EUID" -ne 0 ]; then
    echo "Warning: You may need root privileges for symlinks."
    echo "If it fails, try: sudo ./lin.sh"
    echo ""
fi

# --- Resolve Python and Launch ---
if command -v python3 &> /dev/null; then
    python3 deploy/deploy_all.py "$@"
else
    python deploy/deploy_all.py "$@"
fi
