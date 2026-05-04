#!/bin/bash
# GitHub App Manager — Raspberry Pi first-time setup
echo ""
echo "  =================================================="
echo "   GitHub App Manager — Raspberry Pi Setup"
echo "  =================================================="
echo ""

# Update package list quietly
echo "  [1/4] Updating package list..."
sudo apt-get update -q

# Install git if missing
echo "  [2/4] Installing git..."
sudo apt-get install git -y -q

# Install Python tkinter (needed for the GUI)
echo "  [3/4] Installing python3-tk..."
sudo apt-get install python3-tk python3-pip -y -q

# Install Python packages
echo "  [4/4] Installing Python packages..."
pip3 install requests --quiet

echo ""
echo "  =================================================="
echo "   Setup complete! Launching the app..."
echo "  =================================================="
echo ""

python3 "$(dirname "$0")/github_app_manager.py"
