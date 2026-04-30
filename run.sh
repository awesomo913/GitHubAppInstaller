#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
    echo "Python 3 not found. Install with: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv --system-site-packages
fi

source .venv/bin/activate
pip install -r requirements.txt -q 2>/dev/null

python3 github_app_manager.py
