# GitHub App Manager (this folder)

- **This is the desktop “GitHub app installer”** — `github_app_manager.py`: browse users/orgs, install from releases or clone Python/Node projects, desktop shortcuts, updates. **Not** the same repo as [Claude Token Saver](https://github.com/awesomo913/Claude-Token-Saver) (`claude_interaction_tool` elsewhere on disk).
- **Run the GUI:** `py -3 github_app_manager.py` (or `run.bat` / `install_and_run.bat` on Windows).
- **Verify without GUI:** `py -3 smoke_test.py` (API + `detect_type`)
- **Full install / uninstall test:** `py -3 test_install_flow.py` (clones `octocat/Hello-World`, checks git, cleans up)
- **Needs:** `git` in PATH for clone/Python/Node installs; `requests` (+ `pywin32` on Windows for best shortcuts). Optional GitHub token in ⚙ Settings for private repos and higher API limits.
