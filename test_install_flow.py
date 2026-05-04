#!/usr/bin/env python3
"""End-to-end install test (headless). Clones a tiny public repo, verifies, uninstalls.

Run: py -3 test_install_flow.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OWNER, REPO = "octocat", "Hello-World"


def load():
    spec = importlib.util.spec_from_file_location("github_app_manager", ROOT / "github_app_manager.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    g = load()
    aid = f"{OWNER}/{REPO}"
    out: list[str] = []

    def log(msg, overwrite=False):
        out.append(msg)
        # ASCII-safe (Windows consoles)
        safe = (
            msg.replace("\u2192", "->")
            .replace("\u2713", "[ok]")
            .replace("\u2717", "[x]")
            .replace("\u26a0", "[!]")
        )
        print(safe)

    r = g.AppRegistry()
    api = g.GitHubAPI(r.get_token())
    inst = g.Installer(api, r, log)
    d = g.APPS_DIR / f"{OWNER}__{REPO}"

    if aid in r.apps:
        inst.uninstall(aid)
    if d.exists():
        g.rmtree_robust(d)

    ok = inst.install(OWNER, REPO)
    if not ok or not d.is_dir():
        print("FAIL: install", ok, d)
        return 1
    r2 = subprocess.run(
        ["git", "-C", str(d), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if r2.stdout.strip() != "true":
        print("FAIL: not a git repo", r2.stdout, r2.stderr)
        return 1

    if aid in r.apps:
        inst.uninstall(aid)

    if d.exists():
        g.rmtree_robust(d)
    if d.exists():
        print("FAIL: folder still present after uninstall", d)
        return 1

    print("test_install_flow: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
