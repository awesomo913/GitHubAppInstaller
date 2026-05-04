"""
Build git command lines for GitHub HTTPS without putting the token in the clone URL
(process argv / .git config remote URL), using http.https://github.com/.extraheader instead.
"""

from __future__ import annotations

import base64
import os
from typing import List, Optional

# Classic PAT: username "git" + token as password in Basic, per common Git clients.
def github_auth_header_value(token: str) -> str:
    b64 = base64.b64encode(f"git:{token}".encode("utf-8")).decode("ascii")
    return f"Authorization: Basic {b64}"


def git_auth_prefix_args(token: Optional[str]) -> List[str]:
    if not (token and token.strip()):
        return []
    h = github_auth_header_value(token.strip())
    return ["-c", f"http.https://github.com/.extraheader={h}"]


def _git_with_github_auth(token: Optional[str], *args: str) -> List[str]:
    return ["git", *git_auth_prefix_args(token), *args]


def git_clone_args(owner: str, repo: str, dest: str, token: Optional[str]) -> List[str]:
    u = f"https://github.com/{owner}/{repo}.git"
    return _git_with_github_auth(token, "clone", "--depth=1", u, dest)


def git_pull_args(repo_dir: str, token: Optional[str]) -> List[str]:
    return _git_with_github_auth(token, "-C", repo_dir, "pull")


def git_env_no_prompt() -> dict:
    """Non-interactive git: avoid terminal prompts (auth is via -c extraheader)."""
    e = dict(os.environ)
    e.setdefault("GIT_TERMINAL_PROMPT", "0")
    return e
