#!/usr/bin/env bash
# GitHub App Manager — Push to GitHub (Linux / Raspberry Pi)

set -e
cd "$(dirname "$0")"

echo ""
echo "  ============================================================"
echo "    GitHub App Manager — Push to GitHub"
echo "  ============================================================"
echo ""

# Check git
if ! command -v git &>/dev/null; then
    echo "  ERROR: git is not installed."
    echo "  Run: sudo apt install git"
    exit 1
fi

echo "  Enter your GitHub repository URL."
echo "  Example: https://github.com/awesomo913/GitHubAppInstaller"
echo "  (Create the repo on GitHub first — keep it empty, no README)"
echo ""
read -rp "  Repo URL: " REMOTE_URL

if [[ -z "$REMOTE_URL" ]]; then
    echo "  No URL entered. Exiting."
    exit 1
fi

# Init git if needed
if [ ! -d ".git" ]; then
    echo ""
    echo "  Initializing git repository..."
    git init -b main 2>/dev/null || { git init && git checkout -b main; }
fi

# Stage and commit
echo ""
echo "  Staging files..."
git add .
git status --short

echo ""
echo "  Committing..."
git commit -m "Initial commit — GitHub App Manager v3.1" || echo "  (Nothing new to commit)"

# Set remote
echo ""
echo "  Setting remote origin..."
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_URL"

# Push
echo ""
echo "  Pushing to GitHub..."
echo "  (You may be prompted for credentials — use a Personal Access Token as password)"
echo ""
git push -u origin main

echo ""
echo "  ============================================================"
echo "   SUCCESS! Code is now live at:"
echo "   $REMOTE_URL"
echo "  ============================================================"
echo ""
