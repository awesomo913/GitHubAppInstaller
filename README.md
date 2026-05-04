# GitHub App Manager

A cross-platform desktop GUI for browsing GitHub profiles, installing repos as real desktop apps, updating them, and managing everything from one place.

Works on **Windows** and **Raspberry Pi / Linux**.

---

## Features

- **Browse GitHub** — type any username and browse their public repos
- **My Profile** — log in with a Personal Access Token to access your private repos
- **Install apps** — one-click install from releases, Python source, or git clone
- **Desktop shortcuts** — creates `.lnk` shortcuts on Windows, `.desktop` files on Linux
- **Auto-update** — checks GitHub releases and updates installed apps in-place
- **Uninstall** — removes the app folder and desktop shortcut cleanly
- **Build .exe** — packages the manager itself into a standalone `.exe` via PyInstaller

---

## Quick Start

### Windows

1. Make sure [Python 3.10+](https://www.python.org/downloads/) is installed with "Add to PATH" checked
2. Double-click **`install_and_run.bat`** — installs dependencies and launches the app
3. After first run, use **`run.bat`** for quick launch
4. To build a standalone `.exe`: run **`build_exe.bat`**

### Pre-built .exe (ZIP)

Each push to `main` builds **`GitHubAppManager_Windows.zip`** in [GitHub Actions](https://github.com/awesomo913/GitHubAppManager/actions). Open the latest successful **Build Windows exe** run, then **Artifacts** → download **GitHubAppManager_Windows**; the ZIP contains **`GitHubAppManager.exe`**.

Tags named **`v*`** (for example `v3.2.0`) attach the same ZIP to a [GitHub Release](https://github.com/awesomo913/GitHubAppManager/releases).

### Raspberry Pi / Linux

```bash
# First-time setup
chmod +x install_pi.sh && ./install_pi.sh

# After setup, launch with
./run.sh
```

---

## Private Repos

Go to **Settings** in the sidebar, paste a [GitHub Personal Access Token](https://github.com/settings/tokens) with `repo` scope, and click Save. Your private repos will appear under **My Profile**.

> ⚠️ Never share or commit your token. It is stored locally only.

---

## Files

| File | Purpose |
|------|---------|
| `github_app_manager.py` | Main application (Python 3, tkinter) |
| `requirements.txt` | Python dependencies |
| `install_and_run.bat` | Windows first-time setup + launch |
| `run.bat` | Windows quick launch |
| `build_exe.bat` | Windows: build standalone `.exe` via PyInstaller |
| `install_pi.sh` | Raspberry Pi / Linux first-time setup |
| `run.sh` | Linux quick launch |

---

## Requirements

| Platform | Requirements |
|----------|-------------|
| Windows | Python 3.10+, `requests`, `pywin32` |
| Raspberry Pi / Linux | Python 3, `python3-tk`, `git`, `requests` |

---

## License

MIT
