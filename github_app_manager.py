#!/usr/bin/env python3
from __future__ import annotations
"""GitHub App Manager v4.0 — Windows & Raspberry Pi / Linux  (self-contained)"""
import tkinter as tk
from tkinter import ttk, messagebox
import json, os, sys, subprocess, shutil, tarfile, zipfile, webbrowser
import threading, queue, traceback, re, stat
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional
from pathlib import Path
from datetime import datetime

# ── Inlined utilities (replaces external gab module) ──────────────────────────

class TokenStore:
    """Thin wrapper that holds token in the settings dict and tracks dirty state."""
    def __init__(self, _path):  # path arg kept for API compat; not used
        self.dirty = False

    def get(self, settings: dict) -> str:
        return settings.get("token", "")

    def set(self, settings: dict, token: str) -> None:
        settings["token"] = token
        self.dirty = True

    def mark_flushed(self) -> None:
        self.dirty = False


def extract_zip_safely(path: Path, dest: Path) -> None:
    dest = Path(dest).resolve()
    with zipfile.ZipFile(path) as zf:
        for member in zf.namelist():
            if Path(member).is_absolute() or ".." in Path(member).parts:
                raise OSError(f"Unsafe zip path: {member}")
        zf.extractall(dest)


def extract_tar_safely(path: Path, dest: Path) -> None:
    dest = Path(dest).resolve()
    with tarfile.open(path) as tf:
        for m in tf.getmembers():
            target = (dest / m.name).resolve()
            if not str(target).startswith(str(dest)):
                raise OSError(f"Unsafe tar path: {m.name}")
        tf.extractall(dest)


def git_env_no_prompt() -> dict:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return env


def git_clone_args(owner: str, repo: str, dest: str, token: str = "") -> list:
    url = f"https://github.com/{owner}/{repo}.git"
    args = ["git", "clone", "--depth=1"]
    if token:
        args += ["-c", f"url.https://oauth2:{token}@github.com/.insteadOf=https://github.com/"]
    args += [url, dest]
    return args


def git_pull_args(dest: str, token: str = "") -> list:
    args = ["git", "-C", dest]
    if token:
        args += ["-c", f"url.https://oauth2:{token}@github.com/.insteadOf=https://github.com/"]
    args += ["pull", "--ff-only"]
    return args

# ── Constants ──────────────────────────────────────────────────────────────────

APP_NAME = "GitHub App Manager"
VER      = "4.0"

IS_WIN  = sys.platform == "win32"
IS_PI   = sys.platform.startswith("linux")

if IS_WIN:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

if IS_WIN:
    APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "GitHubAppManager"
    DESKTOP = Path.home() / "Desktop"
else:
    APP_DIR = Path.home() / ".local" / "share" / "GitHubAppManager"
    try:
        DESKTOP = Path(subprocess.check_output(["xdg-user-dir", "DESKTOP"], text=True).strip())
    except Exception:
        DESKTOP = Path.home() / "Desktop"
    DESKTOP.mkdir(parents=True, exist_ok=True)

APPS_DIR   = APP_DIR / "apps"
REGISTRY   = APP_DIR / "registry.json"
_token_store = TokenStore(REGISTRY)
GITHUB_API = "https://api.github.com"
GITHUB_NEW_TOKEN_URL = (
    "https://github.com/settings/tokens/new"
    "?description=GitHubAppManager&scopes=repo,read%3Auser"
)

VENV_BIN = "Scripts" if IS_WIN else "bin"
VENV_PY  = "python.exe"  if IS_WIN else "python3"
VENV_PIW = "pythonw.exe" if IS_WIN else "python3"
VENV_PIP = "pip.exe"     if IS_WIN else "pip"

APP_DIR.mkdir(parents=True, exist_ok=True)
APPS_DIR.mkdir(parents=True, exist_ok=True)

C = dict(
    bg="#16213e", panel="#0f3460", card="#1a1a2e",
    surface="#1e2a4a", input="#253360", border="#2d4070",
    accent="#e94560", accent2="#0f9b8e", fg="#e0e0e0",
    muted="#8899aa", green="#4caf50", red="#ef5350",
    yellow="#ffb74d", blue="#42a5f5", white="#ffffff",
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_github_url(url):
    url = url.strip().rstrip("/")
    for p in [r"github\.com[/:]([^/\s]+)/([^/\s\.]+?)(?:\.git)?$",
               r"^([^/\s]+)/([^/\s\.]+?)(?:\.git)?$"]:
        m = re.search(p, url)
        if m: return m.group(1), m.group(2)
    return None


CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_GH_TOKEN_RE = re.compile(
    r"^(ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}"
    r"|ghs_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})$"
)


def looks_like_gh_token(s: str) -> bool:
    return bool(_GH_TOKEN_RE.match((s or "").strip()))


def find_chrome_exe() -> Optional[Path]:
    if IS_WIN:
        for base in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            p = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if p.is_file(): return p
        la = os.environ.get("LocalAppData", "")
        if la:
            p = Path(la) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if p.is_file(): return p
        w = shutil.which("chrome")
        return Path(w) if w else None
    for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        w = shutil.which(name)
        if w: return Path(w)
    return None


def resolve_owner_repo_from_input(raw: str):
    s = (raw or "").strip()
    if not s:
        return None, None, "Empty"
    p = parse_github_url(s)
    if p: return p[0], p[1], None
    if "github.com/" in s:
        try:
            tail = s.split("github.com/", 1)[1].split("?")[0].rstrip("/")
            parts = [x for x in tail.split("/") if x and x not in (".git",)]
            if len(parts) >= 2: return parts[0], parts[1], None
        except Exception: pass
    if s.startswith("http://") or s.startswith("https://"):
        try:
            r = requests.get(s, allow_redirects=True, timeout=20,
                             headers={"User-Agent": CHROME_UA, "Accept": "text/html,application/json"})
            p = parse_github_url(r.url)
            if p: return p[0], p[1], None
            if "github.com/" in r.url:
                tail = r.url.split("github.com/", 1)[1].split("?")[0].rstrip("/")
                parts = [x for x in tail.split("/") if x and x not in (".git",)]
                if len(parts) >= 2: return parts[0], parts[1], None
        except requests.RequestException as e:
            return None, None, str(e)[:200]
    return None, None, "Use owner/repo or a full https://github.com/… URL"


def open_github_in_chrome(owner: str, repo: str) -> str:
    url = f"https://github.com/{owner}/{repo}"
    ch = find_chrome_exe()
    if ch:
        subprocess.Popen([str(ch), url])
        return "chrome"
    webbrowser.open(url)
    return "default"


def git_available():
    try: subprocess.run(["git", "--version"], capture_output=True, check=True); return True
    except Exception: return False


def _now(): return datetime.now().strftime("%Y-%m-%d %H:%M")


def open_folder(path):
    p = str(path)
    try:
        if IS_WIN: subprocess.Popen(["explorer", p])
        else: subprocess.Popen(["xdg-open", p])
    except Exception: pass


def rmtree_robust(path) -> None:
    p = Path(path)
    if not p.exists(): return

    def _onerr(func, fpath, exc):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception: pass

    import time
    for attempt in range(8):
        try:
            if IS_WIN: shutil.rmtree(p, onerror=_onerr)
            else: shutil.rmtree(p)
            if not p.exists(): return
        except OSError: pass
        shutil.rmtree(p, ignore_errors=True)
        if not p.exists(): return
        time.sleep(0.15 * (attempt + 1))
    shutil.rmtree(p, ignore_errors=True)

# ── GitHub API ─────────────────────────────────────────────────────────────────

def _make_session(token: str = "") -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"GitHubAppManager/{VER}",
    })
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


class GitHubAPI:
    def __init__(self, token=""):
        self.token = token
        self.s = _make_session(token)

    def _get(self, path, **kw):
        r = self.s.get(f"{GITHUB_API}{path}", timeout=15, **kw)
        r.raise_for_status()
        return r.json()

    def get_latest_release(self, owner, repo):
        try: return self._get(f"/repos/{owner}/{repo}/releases/latest")
        except requests.HTTPError as e:
            if e.response.status_code == 404: return None
            raise

    def get_contents(self, owner, repo, path=""):
        try: return self._get(f"/repos/{owner}/{repo}/contents/{path}")
        except requests.HTTPError: return None

    def get_my_repos(self):
        if not self.token:
            return [], "No token set. Add your GitHub token in ⚙ Settings."
        results, page = [], 1
        while True:
            try:
                data = self._get("/user/repos", params={
                    "per_page": 100, "page": page,
                    "sort": "updated",
                    "affiliation": "owner,collaborator,organization_member",
                })
            except requests.HTTPError as e:
                code = e.response.status_code
                if code == 401: return [], "Token invalid or expired — regenerate in ⚙ Settings."
                if code == 403: return [], "Token missing 'repo' scope — regenerate with repo access."
                return [], f"GitHub API error {code}: {e.response.text[:200]}"
            except requests.RequestException as e:
                return [], f"Network error: {e}"
            if not data: break
            results.extend(data); page += 1
            if len(data) < 100: break
        return results, None

    def get_user_repos(self, username):
        results, page = [], 1
        while True:
            try:
                try:
                    data = self._get(f"/users/{username}/repos",
                                     params={"per_page": 100, "page": page, "sort": "updated"})
                except requests.HTTPError as e:
                    if e.response.status_code == 404:
                        data = self._get(f"/orgs/{username}/repos",
                                         params={"per_page": 100, "page": page, "sort": "updated"})
                    else: raise
            except requests.HTTPError as e:
                code = e.response.status_code
                if code == 404: return [], f"User/org '{username}' not found."
                return [], f"GitHub API error {code}"
            except requests.RequestException as e:
                return [], f"Network error: {e}"
            if not data: break
            results.extend(data); page += 1
            if len(data) < 100: break
        return results, None

    def get_me(self):
        if not self.token: return None, "No token set"
        try: return self._get("/user"), None
        except requests.HTTPError as e:
            if e.response.status_code == 401: return None, "Invalid token"
            return None, f"API error {e.response.status_code}"
        except Exception as e: return None, str(e)

    def get_repo(self, owner, repo):
        try:
            r = self.s.get(f"{GITHUB_API}/repos/{owner}/{repo}", timeout=15)
            if r.status_code == 200: return r.json(), None
            if r.status_code == 404: return None, "not_found"
            return None, f"api_http_{r.status_code}"
        except requests.Timeout as e: return None, f"network:{e}"
        except requests.RequestException as e: return None, f"network:{e}"

    def detect_type(self, owner, repo):
        rel = self.get_latest_release(owner, repo)
        if rel and rel.get("assets"):
            exts = (".exe", ".zip", ".msi") if IS_WIN else (".tar.gz", ".zip", ".AppImage", ".deb", ".sh")
            if any(a["name"].lower().endswith(exts) for a in rel["assets"]): return "release"
        c = self.get_contents(owner, repo)
        if c and isinstance(c, list):
            names = {f["name"].lower() for f in c}
            if names & {"requirements.txt", "setup.py", "pyproject.toml", "setup.cfg"}: return "python"
            if "package.json" in names: return "nodejs"
        return "clone"

    def check_for_update(self, owner, repo, current):
        rel = self.get_latest_release(owner, repo)
        if rel:
            latest = rel.get("tag_name", "")
            return latest != current, latest
        return False, current

    def rate_limit(self):
        try:
            d = self._get("/rate_limit")
            return d["rate"]["remaining"], d["rate"]["limit"]
        except Exception: return None, None

# ── Registry ───────────────────────────────────────────────────────────────────

class AppRegistry:
    def __init__(self):
        self._d = self._load()

    def _load(self):
        if REGISTRY.exists():
            try: return json.loads(REGISTRY.read_text())
            except Exception: pass
        return {"apps": {}, "settings": {"token": ""}}

    def save(self): REGISTRY.write_text(json.dumps(self._d, indent=2))

    @property
    def apps(self): return self._d.setdefault("apps", {})

    def add(self, k, v):    self.apps[k] = v;          self.save()
    def update(self, k, p):
        if k in self.apps: self.apps[k].update(p);     self.save()
    def remove(self, k):    self.apps.pop(k, None);    self.save()

    def get_token(self):
        t = _token_store.get(self._d.setdefault("settings", {"token": ""}))
        if _token_store.dirty:
            self.save()
            _token_store.mark_flushed()
        return t

    def set_token(self, t: str) -> None:
        _token_store.set(self._d.setdefault("settings", {"token": ""}), t)
        self.save()
        _token_store.mark_flushed()

# ── Shortcut creation ──────────────────────────────────────────────────────────

def make_shortcut(name, target, work_dir=None, icon=None):
    target = Path(target)
    work   = str(work_dir or (target if target.is_dir() else target.parent))
    if IS_WIN:
        sc = DESKTOP / f"{name}.lnk"
        tgt = str(target)
        ico = str(icon) if icon else (tgt if target.suffix == ".exe" else "")
        try:
            import win32com.client
            sh = win32com.client.Dispatch("WScript.Shell")
            s  = sh.CreateShortCut(str(sc))
            s.Targetpath = tgt; s.WorkingDirectory = work
            if ico: s.IconLocation = ico
            s.save()
        except ImportError:
            v  = 'Set o=WScript.CreateObject("WScript.Shell")\n'
            v += f'Set lnk=o.CreateShortcut("{sc}")\n'
            v += f'lnk.TargetPath="{tgt}"\nlnk.WorkingDirectory="{work}"\n'
            if ico: v += f'lnk.IconLocation="{ico}"\n'
            v += "lnk.Save\n"
            tmp = APP_DIR / "_sc.vbs"; tmp.write_text(v)
            subprocess.run(["cscript", "//nologo", str(tmp)], capture_output=True)
            tmp.unlink(missing_ok=True)
        return sc
    else:
        sc = DESKTOP / f"{name}.desktop"
        if target.is_dir():
            exec_line = f"xdg-open {target}"
        elif target.suffix == ".sh":
            exec_line = f"bash {target}"
        elif target.suffix == ".py":
            exec_line = f"python3 {target}"
        else:
            exec_line = str(target)
        ico_line = f"Icon={icon}" if icon else "Icon=applications-other"
        sc.write_text(
            f"[Desktop Entry]\nVersion=1.0\nType=Application\nName={name}\n"
            f"Exec={exec_line}\nPath={work}\n{ico_line}\nTerminal=false\nStartupNotify=true\n"
        )
        sc.chmod(sc.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        try:
            subprocess.run(["gio", "set", str(sc), "metadata::trusted", "true"], capture_output=True)
        except Exception: pass
        return sc

# ── Installer ──────────────────────────────────────────────────────────────────

class Installer:
    def __init__(self, api, registry, log):
        self.api = api; self.registry = registry; self.log = log

    def install(self, owner, repo, force_type=None):
        aid = f"{owner}/{repo}"
        d   = APPS_DIR / f"{owner}__{repo}"
        d.mkdir(parents=True, exist_ok=True)
        try:
            t = force_type or self._detect(owner, repo)
            if   t == "release": return self._release(owner, repo, d, aid)
            elif t == "python":  return self._python(owner, repo, d, aid)
            elif t == "nodejs":  return self._node(owner, repo, d, aid)
            else:                return self._clone(owner, repo, d, aid)
        except Exception:
            self.log(f"  ✗ Unexpected error:\n{traceback.format_exc()}"); return False

    def update(self, aid):
        app = self.registry.apps.get(aid)
        if not app: self.log("App not found."); return False
        owner, repo, atype, d = app["owner"], app["repo"], app["type"], Path(app["install_dir"])
        try:
            if atype == "release":
                rel = self.api.get_latest_release(owner, repo)
                if rel and rel.get("tag_name") == app.get("version"):
                    self.log(f"  Already up to date ({app['version']})."); return True
                rmtree_robust(d); d.mkdir(parents=True, exist_ok=True)
                return self._release(owner, repo, d, aid)
            else:
                self.log("  Pulling latest changes...")
                r = subprocess.run(
                    git_pull_args(str(d), self.api.token),
                    env=git_env_no_prompt(), capture_output=True, text=True,
                )
                self.log(f"  {r.stdout.strip() or 'Already up to date.'}")
                if atype == "python":
                    pip = d / ".venv" / VENV_BIN / VENV_PIP; req = d / "requirements.txt"
                    if req.exists() and pip.exists():
                        self.log("  Updating requirements...")
                        subprocess.run([str(pip), "install", "-r", str(req), "-q"], capture_output=True)
                ver = self._hash(d)
                self.registry.update(aid, {"version": ver, "updated_at": _now()})
                self.log(f"  ✓ Updated to {ver}"); return True
        except Exception: self.log(f"  ✗ {traceback.format_exc()}")
        return False

    def uninstall(self, aid):
        app = self.registry.apps.get(aid)
        if not app: return False
        try: Path(app.get("shortcut_path", "")).unlink(missing_ok=True)
        except Exception: pass
        rmtree_robust(app.get("install_dir", ""))
        self.registry.remove(aid)
        self.log(f"  Uninstalled {app['name']}."); return True

    def _detect(self, owner, repo):
        self.log("  Auto-detecting repo type...")
        t = self.api.detect_type(owner, repo)
        self.log(f"  → Detected: {t}"); return t

    def _release(self, owner, repo, d, aid):
        self.log("  Fetching latest release...")
        rel = self.api.get_latest_release(owner, repo)
        if not rel: self.log("  ✗ No GitHub Releases found."); return False
        ver   = rel.get("tag_name", "unknown")
        asset = self._pick_asset(rel.get("assets", []))
        if not asset: self.log("  ✗ No suitable asset found for this platform."); return False
        dest = d / asset["name"]
        self.log(f"  Downloading {asset['name']}  ({asset['size'] // 1024:,} KB)...")
        self._dl(asset["browser_download_url"], dest)
        exe = self._unpack(dest, d)
        if not exe: self.log("  ✗ Could not locate runnable file after download."); return False
        sc = make_shortcut(repo, exe)
        self.log(f"  ✓ Shortcut created on Desktop")
        self.registry.add(aid, {"name": repo, "owner": owner, "repo": repo, "type": "release",
            "version": ver, "install_dir": str(d), "exe_path": str(exe),
            "shortcut_path": str(sc), "installed_at": _now(), "updated_at": _now()})
        self.log(f"  ✓ Installed {repo} {ver}!"); return True

    def _python(self, owner, repo, d, aid):
        if not git_available(): self.log("  ✗ git not found. Install it first."); return False
        if not (d / ".git").exists():
            self.log(f"  Cloning {owner}/{repo}...")
            r = subprocess.run(
                git_clone_args(owner, repo, str(d), self.api.token),
                env=git_env_no_prompt(), capture_output=True, text=True,
            )
            if r.returncode != 0:
                self.log(f"  ✗ Clone failed:\n{r.stderr[:500]}")
                if "Authentication" in r.stderr or "could not read" in r.stderr.lower():
                    self.log("  ℹ Private repo? Token needs 'repo' scope in ⚙ Settings.")
                return False
        venv = d / ".venv"
        self.log("  Creating virtual environment...")
        venv_args = [sys.executable, "-m", "venv", str(venv)]
        if IS_PI: venv_args.append("--system-site-packages")
        r = subprocess.run(venv_args, capture_output=True, text=True)
        if r.returncode != 0:
            self.log(f"  ✗ venv failed:\n{r.stderr[:200]}"); return False
        pip = str(d / ".venv" / VENV_BIN / VENV_PIP)
        py  = str(d / ".venv" / VENV_BIN / VENV_PY)
        pyw = str(d / ".venv" / VENV_BIN / VENV_PIW)
        subprocess.run([pip, "install", "--upgrade", "pip", "-q"], capture_output=True)
        req = d / "requirements.txt"
        if req.exists():
            self.log("  Installing requirements.txt...")
            r = subprocess.run([pip, "install", "-r", str(req), "-q"], capture_output=True, text=True)
            if r.returncode != 0: self.log(f"  ⚠ Some deps failed:\n{r.stderr[:300]}")
        if (d / "setup.py").exists() or (d / "pyproject.toml").exists():
            self.log("  Installing package (pip install -e .)...")
            subprocess.run([pip, "install", "-e", ".", "-q"], cwd=str(d), capture_output=True)
        entry = self._entry(d)
        if not entry:
            self.log("  ⚠ No entry point found. Shortcut will open the project folder.")
            sc = make_shortcut(repo, d); exe_path = str(d)
        else:
            self.log(f"  Entry point: {entry.relative_to(d)}")
            is_gui  = self._is_gui(d, entry)
            runner  = pyw if (IS_WIN and is_gui and Path(pyw).exists()) else py
            launcher = self._make_launcher(repo, d, runner, entry)
            sc = make_shortcut(repo, launcher)
            exe_path = str(launcher)
            self.log(f"  Runner: {Path(runner).name}")
        self.log(f"  ✓ Shortcut created on Desktop")
        ver = self._hash(d)
        self.registry.add(aid, {"name": repo, "owner": owner, "repo": repo, "type": "python",
            "version": ver, "install_dir": str(d), "exe_path": exe_path,
            "shortcut_path": str(sc), "installed_at": _now(), "updated_at": _now()})
        self.log(f"  ✓ Installed {repo} ({ver})!"); return True

    def _node(self, owner, repo, d, aid):
        if not git_available():
            self.log("  ✗ git not found."); return False
        if not shutil.which("node"):
            self.log("  ✗ node not found. Install Node.js and add it to PATH."); return False
        if not shutil.which("npm"):
            self.log("  ✗ npm not found. Install Node.js (npm ships with it)."); return False
        if not (d / ".git").exists():
            r = subprocess.run(
                git_clone_args(owner, repo, str(d), self.api.token),
                env=git_env_no_prompt(), capture_output=True, text=True,
            )
            if r.returncode != 0:
                self.log(f"  ✗ Clone failed:\n{r.stderr[:300]}"); return False
        self.log("  Running npm install...")
        subprocess.run(["npm", "install", "--silent"], cwd=str(d), capture_output=True)
        if IS_WIN:
            launcher = d / f"_launch_{repo}.bat"
            launcher.write_text(f"@echo off\ncd /d \"{d}\"\nnpm start\nif errorlevel 1 pause\n")
        else:
            launcher = d / f"_launch_{repo}.sh"
            launcher.write_text(f"#!/bin/bash\ncd \"{d}\"\nnpm start\n")
            launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
        sc = make_shortcut(repo, launcher)
        ver = self._hash(d)
        self.registry.add(aid, {"name": repo, "owner": owner, "repo": repo, "type": "nodejs",
            "version": ver, "install_dir": str(d), "exe_path": str(launcher),
            "shortcut_path": str(sc), "installed_at": _now(), "updated_at": _now()})
        self.log(f"  ✓ Installed {repo}!"); return True

    def _clone(self, owner, repo, d, aid):
        if not git_available():
            self.log("  ✗ git not found."); return False
        self.log(f"  Cloning {owner}/{repo}...")
        r = subprocess.run(
            git_clone_args(owner, repo, str(d), self.api.token),
            env=git_env_no_prompt(), capture_output=True, text=True,
        )
        if r.returncode != 0:
            self.log(f"  ✗ Clone failed:\n{r.stderr[:400]}")
            if "Authentication" in r.stderr or "could not read" in r.stderr.lower():
                self.log("  ℹ Private repo? Check token has 'repo' scope in ⚙ Settings.")
            return False
        names = {f.name.lower() for f in d.iterdir()}
        if names & {"requirements.txt", "setup.py", "pyproject.toml"}:
            self.log("  Detected Python project — switching installer.")
            return self._python(owner, repo, d, aid)
        if "package.json" in names:
            self.log("  Detected Node.js — switching installer.")
            return self._node(owner, repo, d, aid)
        sc = make_shortcut(repo, d)
        self.registry.add(aid, {"name": repo, "owner": owner, "repo": repo, "type": "clone",
            "version": self._hash(d), "install_dir": str(d), "exe_path": str(d),
            "shortcut_path": str(sc), "installed_at": _now(), "updated_at": _now()})
        self.log(f"  ✓ Cloned — shortcut opens the project folder."); return True

    def _pick_asset(self, assets):
        def score(a):
            n = a["name"].lower(); s = 0
            if IS_WIN:
                if any(t in n for t in ("win", "windows", "x64", "x86", "amd64")): s += 10
                if n.endswith(".exe"): s += 5
                elif n.endswith(".msi"): s += 4
                elif n.endswith(".zip"): s += 2
            else:
                if any(t in n for t in ("arm", "aarch", "rpi", "raspberry", "linux")): s += 10
                if n.endswith(".AppImage"): s += 5
                elif n.endswith(".deb"): s += 4
                elif n.endswith(".tar.gz"): s += 3
                elif n.endswith(".sh"): s += 2
                elif n.endswith(".zip"): s += 1
            return s
        ranked = sorted(assets, key=score, reverse=True)
        for a in ranked:
            n = a["name"].lower()
            if IS_WIN and n.endswith((".exe", ".msi", ".zip")): return a
            if IS_PI  and n.endswith((".AppImage", ".deb", ".tar.gz", ".sh", ".zip")): return a
        return ranked[0] if ranked else None

    def _dl(self, url, dest):
        get = self.api.s.get if self.api.token else requests.get
        with get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0) or 0)
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk); done += len(chunk)
                    if total:
                        self.log(f"  Downloading... {done * 100 // total}%", overwrite=True)
        self.log(f"  Downloaded {done // 1024:,} KB")

    def _unpack(self, path: Path, d: Path):
        n = path.name.lower()
        if n.endswith(".zip"):
            self.log("  Extracting zip (path-safe)…")
            try:
                extract_zip_safely(path, d)
            except (zipfile.BadZipFile, OSError) as e:
                self.log(f"  ✗ Bad or unsafe zip: {e}"); return None
            path.unlink(missing_ok=True)
            if IS_WIN:
                exes = [f for f in d.rglob("*.exe")
                        if not any(x in f.name.lower() for x in ("uninstall", "uninst", "setup"))]
                return sorted(exes, key=lambda f: len(f.parts))[0] if exes else None
            else:
                for ext in (".AppImage", ".sh", ""):
                    for f in d.rglob(f"*{ext}"):
                        if f.is_file() and not f.name.startswith("."):
                            f.chmod(f.stat().st_mode | stat.S_IEXEC); return f
                return None
        elif n.endswith(".tar.gz") or n.endswith(".tgz"):
            self.log("  Extracting tarball (path-safe)…")
            try:
                extract_tar_safely(path, d)
            except (tarfile.TarError, OSError) as e:
                self.log(f"  ✗ Bad or unsafe tar: {e}"); return None
            path.unlink(missing_ok=True)
            for f in d.rglob("*"):
                if f.is_file() and not f.suffix and not f.name.startswith("."):
                    f.chmod(f.stat().st_mode | stat.S_IEXEC); return f
            return None
        elif n.endswith(".appimage"):
            path.chmod(path.stat().st_mode | stat.S_IEXEC); return path
        elif n.endswith(".deb"):
            self.log("  Installing .deb package (sudo dpkg -i)...")
            r = subprocess.run(["sudo", "dpkg", "-i", str(path)], capture_output=True, text=True)
            if r.returncode != 0: self.log(f"  ⚠ dpkg: {r.stderr[:200]}")
            return path
        elif n.endswith(".sh"):
            path.chmod(path.stat().st_mode | stat.S_IEXEC); return path
        elif n.endswith((".exe", ".msi")):
            return path
        return path

    def _entry(self, d):
        for n in ["main.py", "app.py", "run.py", "__main__.py", "gui.py", "ui.py",
                  "start.py", "launch.py", "cli.py"]:
            if (d / n).exists(): return d / n
        src = d / "src"
        if src.is_dir():
            for n in ["main.py", "app.py", "run.py", "__main__.py", "gui.py"]:
                if (src / n).exists(): return src / n
            for sub in src.iterdir():
                if sub.is_dir() and (sub / "__main__.py").exists(): return sub / "__main__.py"
        for sub in d.iterdir():
            if sub.is_dir() and not sub.name.startswith((".", "-", "_")) and (sub / "__main__.py").exists():
                return sub / "__main__.py"
        for f in sorted(d.glob("*.py")):
            if not f.name.startswith(("_", "test", "setup", "conf", "requirements")): return f
        return None

    def _is_gui(self, d, entry):
        markers = {"tkinter", "PyQt", "PySide", "wx", "kivy", "pygame", "customtkinter"}
        req = d / "requirements.txt"
        if req.exists() and any(m.lower() in req.read_text().lower() for m in markers): return True
        try: return any(m.lower() in entry.read_text(errors="ignore").lower() for m in markers)
        except Exception: return False

    def _make_launcher(self, repo, d, py, entry):
        if IS_WIN:
            bat = d / f"_launch_{repo}.bat"
            bat.write_text(
                f'@echo off\ncd /d "{d}"\n"{py}" "{entry}" %*\n'
                f'if errorlevel 1 (echo.\necho -- Error --\npause)\n'
            )
            return bat
        else:
            sh = d / f"_launch_{repo}.sh"
            sh.write_text(f'#!/bin/bash\ncd "{d}"\n"{py}" "{entry}" "$@"\n')
            sh.chmod(sh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            return sh

    def _hash(self, d):
        r = subprocess.run(["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "unknown"

# ── UI widgets ─────────────────────────────────────────────────────────────────

def styled_btn(parent, text, cmd, primary=False, small=False, danger=False, **kw):
    bg = C["accent"] if primary else (C["red"] if danger else C["surface"])
    fs = 8 if small else 10
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=C["white"],
                  font=("Segoe UI", fs, "bold" if primary else "normal"),
                  relief="flat", bd=0, padx=12 if not small else 8,
                  pady=6 if not small else 3, cursor="hand2",
                  activebackground=C["accent2"], activeforeground=C["white"], **kw)
    b.bind("<Enter>", lambda e: b.configure(bg=C["accent2"] if primary else (C["border"] if not danger else "#c62828")))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def entry_w(parent, textvariable=None, **kw):
    e = tk.Entry(parent, bg=C["input"], fg=C["fg"], insertbackground=C["fg"],
                 relief="flat", font=("Segoe UI", 10), bd=0,
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["accent"], **kw)
    if textvariable: e.configure(textvariable=textvariable)
    return e


class LogPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["card"], **kw)
        hdr = tk.Frame(self, bg=C["panel"]); hdr.pack(fill="x")
        tk.Label(hdr, text="  Activity Log", bg=C["panel"], fg=C["fg"],
                 font=("Segoe UI", 10, "bold")).pack(side="left", pady=5)
        platform_txt = "Windows" if IS_WIN else "Raspberry Pi / Linux"
        tk.Label(hdr, text=f"  [{platform_txt}]", bg=C["panel"], fg=C["muted"],
                 font=("Segoe UI", 8)).pack(side="left")
        styled_btn(hdr, "✕ Clear", self.clear, small=True).pack(side="right", padx=6, pady=3)
        self.txt = tk.Text(self, state="disabled", wrap="word", bg=C["card"], fg=C["fg"],
                           font=("Courier" if IS_PI else "Consolas", 9),
                           relief="flat", bd=0, padx=8, pady=4)
        sb = tk.Scrollbar(self, orient="vertical", command=self.txt.yview,
                          bg=C["panel"], troughcolor=C["card"], width=10)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, col in [("ok", C["green"]), ("err", C["red"]), ("warn", C["yellow"]), ("hd", C["blue"])]:
            self.txt.tag_configure(tag, foreground=col)
        self.txt.tag_configure("hd", font=("Courier" if IS_PI else "Consolas", 9, "bold"))
        self._ow = False

    def write(self, msg, overwrite=False):
        self.txt.configure(state="normal")
        if overwrite and self._ow: self.txt.delete("end-2l", "end-1c")
        tag = ("ok" if msg.strip().startswith("✓") else
               "err" if msg.strip().startswith("✗") else
               "warn" if msg.strip().startswith("⚠") else
               "hd" if msg[:1] in ("─", "═", "▶") else "")
        self.txt.insert("end", msg + "\n", tag); self.txt.see("end")
        self.txt.configure(state="disabled"); self._ow = overwrite

    def clear(self):
        self.txt.configure(state="normal"); self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled"); self._ow = False


class RepoList(tk.Frame):
    COLS = [("name", "Repository", 200), ("private", "", 30), ("lang", "Language", 100),
            ("stars", "★", 60), ("status", "Status", 85), ("desc", "Description", 1)]

    def __init__(self, parent, on_install, **kw):
        super().__init__(parent, bg=C["card"], **kw)
        self.on_install = on_install; self._repos = {}; self._installed = set()

        hdr = tk.Frame(self, bg=C["surface"]); hdr.pack(fill="x", pady=(0, 1))
        self._sv = tk.StringVar(); self._sv.trace_add("write", lambda *_: self._filter())
        tk.Label(hdr, text="  🔍", bg=C["surface"], fg=C["muted"], font=("Segoe UI", 11)).pack(side="left")
        entry_w(hdr, textvariable=self._sv, width=26).pack(side="left", padx=4, pady=5)
        self._cl = tk.Label(hdr, text="", bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9))
        self._cl.pack(side="right", padx=10)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("R.Treeview", background=C["card"], fieldbackground=C["card"],
                    foreground=C["fg"], rowheight=28, font=("Segoe UI", 9))
        s.configure("R.Treeview.Heading", background=C["surface"], foreground=C["blue"],
                    font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("R.Treeview", background=[("selected", C["accent"])], foreground=[("selected", C["white"])])

        w = tk.Frame(self, bg=C["card"]); w.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(w, columns=[c[0] for c in self.COLS],
                                 show="headings", selectmode="browse", style="R.Treeview")
        for col, txt, wd in self.COLS:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=wd, minwidth=20, stretch=(col == "desc"))
        sb2 = tk.Scrollbar(w, orient="vertical", command=self.tree.yview,
                           bg=C["surface"], troughcolor=C["card"], width=10)
        self.tree.configure(yscrollcommand=sb2.set)
        self.tree.pack(side="left", fill="both", expand=True); sb2.pack(side="right", fill="y")
        self.tree.bind("<Double-Button-1>", lambda _: self._go())
        self.tree.bind("<Return>", lambda _: self._go())

        act = tk.Frame(self, bg=C["panel"]); act.pack(fill="x")
        self._ibtn = styled_btn(act, "⬇  Install Selected", self._go, primary=True)
        self._ibtn.pack(side="left", padx=8, pady=5)
        tk.Label(act, text="or double-click", bg=C["panel"], fg=C["muted"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.tree.bind("<<TreeviewSelect>>",
            lambda _: self._ibtn.configure(state="normal" if self.tree.selection() else "disabled"))
        self._ibtn.configure(state="disabled")

    def load(self, repos, installed_aids):
        self._repos = {}; self._installed = installed_aids
        for r in self.tree.get_children(): self.tree.delete(r)
        for repo in repos:
            owner = repo.get("owner", {}).get("login", ""); name = repo.get("name", "")
            aid = f"{owner}/{name}"
            priv = "🔒" if repo.get("private") else ""
            lang = repo.get("language") or "—"
            stars = repo.get("stargazers_count", 0)
            status = "✓" if aid in installed_aids else ""
            desc = (repo.get("description") or "").strip()
            self._repos[aid] = repo
            self.tree.insert("", "end", iid=aid,
                             values=(name, priv, lang, f"{stars:,}", status, desc[:150]),
                             tags=(("inst",) if status else ()))
        self.tree.tag_configure("inst", foreground=C["green"])
        self._cl.configure(text=f"{len(repos)} repos")
        self._filter()

    def refresh_marks(self, installed_aids):
        self._installed = installed_aids
        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            vals[4] = "✓" if iid in installed_aids else ""
            self.tree.item(iid, values=vals, tags=(("inst",) if vals[4] else ()))
        self.tree.tag_configure("inst", foreground=C["green"])

    def _filter(self):
        q = self._sv.get().lower()
        for iid in list(self.tree.get_children()): self.tree.detach(iid)
        for iid, r in self._repos.items():
            txt = f"{r.get('name', '')} {r.get('description', '')} {r.get('language', '')}".lower()
            if not q or q in txt: self.tree.reattach(iid, "", "end")

    def _go(self):
        sel = self.tree.selection()
        if not sel: return
        r = self._repos.get(sel[0])
        if not r: return
        self.on_install(r.get("owner", {}).get("login", ""), r.get("name", ""))

# ── Main App ───────────────────────────────────────────────────────────────────

class App(tk.Tk):
    P_INST = "installed"; P_MY = "myrepos"; P_BROWSE = "browse"; P_URL = "install"

    def __init__(self):
        super().__init__()
        platform_str = "Raspberry Pi" if IS_PI else "Windows"
        self.title(f"{APP_NAME}  v{VER}  [{platform_str}]")
        self.geometry("1080x740"); self.minsize(800, 540)
        self.configure(bg=C["bg"])
        self.registry = AppRegistry()
        self._rebuild_api()
        self._q = queue.Queue()
        self._browse_repos = {}
        self._my_repos = {}
        self._last_clip = ""
        self._build_ui()
        self._refresh_installed()
        self._poll()
        self._clipboard_poll()
        threading.Thread(target=self._startup_checks, daemon=True).start()

    def _startup_checks(self):
        if not git_available():
            hint = "Install from: https://git-scm.com" if IS_WIN else "Run: sudo apt install git"
            self._tlog(f"⚠ git not found — Python/clone installs won't work.  {hint}")
        self._check_token_status()
        if not self.registry.get_token():
            self.after(800, self._show_token_banner)

    def _build_ui(self):
        top = tk.Frame(self, bg=C["panel"], height=50); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="  🐙  GitHub App Manager", bg=C["panel"], fg=C["white"],
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=4)
        self._auth_lbl = tk.Label(top, text="⚪ No token", bg=C["panel"], fg=C["muted"],
                                  font=("Segoe UI", 9)); self._auth_lbl.pack(side="right", padx=14)
        self._rate_lbl = tk.Label(top, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8))
        self._rate_lbl.pack(side="right", padx=4)
        styled_btn(top, "⚙ Settings", self._open_settings, small=True).pack(side="right", padx=8, pady=10)

        # Token detection banner (hidden until a token is spotted in clipboard)
        self._banner = tk.Frame(self, bg=C["accent2"], height=34)
        self._banner_lbl = tk.Label(self._banner, text="", bg=C["accent2"], fg=C["white"],
                                    font=("Segoe UI", 9, "bold"))
        self._banner_lbl.pack(side="left", padx=12)
        styled_btn(self._banner, "Import Token →", self._import_clipboard_token,
                   primary=False, small=True).pack(side="left", padx=4)
        styled_btn(self._banner, "✕", self._hide_banner, small=True).pack(side="right", padx=8)

        body = tk.Frame(self, bg=C["bg"]); body.pack(fill="both", expand=True)

        sb = tk.Frame(body, bg=C["panel"], width=176); sb.pack(side="left", fill="y"); sb.pack_propagate(False)
        tk.Label(sb, text="NAVIGATION", bg=C["panel"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(16, 4))
        self._nav_btns = {}
        for page, label in [(self.P_INST, "📦  Installed Apps"), (self.P_MY, "👤  My Profile"),
                            (self.P_BROWSE, "🔍  Browse GitHub"), (self.P_URL, "🔗  Install by URL")]:
            b = tk.Button(sb, text=label, anchor="w", bg=C["panel"], fg=C["fg"],
                          font=("Segoe UI", 10), relief="flat", bd=0, padx=14, pady=10,
                          cursor="hand2", command=lambda p=page: self._nav(p),
                          activebackground=C["surface"], activeforeground=C["white"])
            b.pack(fill="x"); self._nav_btns[page] = b
        tk.Frame(sb, bg=C["border"], height=1).pack(fill="x", padx=10, pady=10)
        tk.Label(sb, text="TOOLS", bg=C["panel"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(0, 4))
        styled_btn(sb, "🔨  Build .exe" if IS_WIN else "📦  Package App",
                   self._open_build, small=True).pack(fill="x", padx=10, pady=2)
        styled_btn(sb, "📂  App Folder", lambda: open_folder(APP_DIR), small=True).pack(fill="x", padx=10, pady=2)

        self._content = tk.Frame(body, bg=C["bg"]); self._content.pack(side="left", fill="both", expand=True)
        self._pages = {}
        self._build_installed_page()
        self._build_my_page()
        self._build_browse_page()
        self._build_url_page()

        self._logpanel = LogPanel(self, height=170); self._logpanel.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=C["card"], fg=C["muted"],
                 font=("Segoe UI", 8), anchor="w", padx=10).pack(fill="x", side="bottom")

        self._nav(self.P_INST)

    def _show_token_banner(self):
        self._banner_lbl.configure(
            text="🔑 No GitHub token — add one to browse private repos and raise rate limits"
        )
        self._banner.pack(fill="x", before=self._content.master)

    def _hide_banner(self):
        self._banner.pack_forget()

    def _clipboard_poll(self):
        try:
            clip = self.clipboard_get()
        except Exception:
            clip = ""
        if clip != self._last_clip:
            self._last_clip = clip
            if looks_like_gh_token(clip) and clip != self.registry.get_token():
                self._banner_lbl.configure(
                    text="🔑 GitHub token detected in clipboard — click to import"
                )
                self._banner.pack(fill="x", before=self._content.master)
        self.after(2000, self._clipboard_poll)

    def _import_clipboard_token(self):
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            clip = ""
        if not looks_like_gh_token(clip):
            messagebox.showwarning(APP_NAME,
                "Clipboard doesn't contain a valid GitHub token.\n\n"
                "Tokens look like: ghp_xxxx… or github_pat_xxxx…")
            return
        self._save_and_validate_token(clip)

    def _save_and_validate_token(self, token: str):
        self._auth_lbl.configure(text="⏳ Validating…", fg=C["yellow"])
        def _check():
            api = GitHubAPI(token)
            me, err = api.get_me()
            if me:
                self.registry.set_token(token)
                self._rebuild_api()
                login = me.get("login", "?")
                name  = me.get("name", "")
                self.after(0, lambda: (
                    self._auth_lbl.configure(
                        text=f"🟢 {login}" + (f"  ({name})" if name else ""),
                        fg=C["green"],
                    ),
                    self._hide_banner(),
                    self._log(f"  ✓ Token saved — logged in as {login}"),
                ))
                rem, lim = api.rate_limit()
                if rem:
                    self.after(0, lambda: self._rate_lbl.configure(text=f"API {rem}/{lim}"))
            else:
                self.after(0, lambda: (
                    self._auth_lbl.configure(text=f"🔴 Token invalid: {err}", fg=C["red"]),
                    messagebox.showerror(APP_NAME,
                        f"Token validation failed:\n{err}\n\nMake sure you copied the full token."),
                ))
        threading.Thread(target=_check, daemon=True).start()

    def _nav(self, page):
        for p, b in self._nav_btns.items():
            b.configure(bg=C["accent"] if p == page else C["panel"],
                        fg=C["white"] if p == page else C["fg"])
        for p, f in self._pages.items():
            (f.pack(fill="both", expand=True) if p == page else f.pack_forget())

    def _mk_page(self, pid):
        f = tk.Frame(self._content, bg=C["bg"]); self._pages[pid] = f; return f

    def _build_installed_page(self):
        p = self._mk_page(self.P_INST)
        hdr = tk.Frame(p, bg=C["bg"]); hdr.pack(fill="x", padx=20, pady=(14, 6))
        tk.Label(hdr, text="Installed Apps", bg=C["bg"], fg=C["white"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        styled_btn(hdr, "↻ Refresh", self._refresh_installed, small=True).pack(side="right")

        s = ttk.Style()
        s.configure("I.Treeview", background=C["card"], fieldbackground=C["card"],
                    foreground=C["fg"], rowheight=30, font=("Segoe UI", 10))
        s.configure("I.Treeview.Heading", background=C["surface"], foreground=C["blue"],
                    font=("Segoe UI", 10, "bold"), relief="flat")
        s.map("I.Treeview", background=[("selected", C["accent"])], foreground=[("selected", C["white"])])

        w = tk.Frame(p, bg=C["card"]); w.pack(fill="both", expand=True, padx=20)
        self._tree = ttk.Treeview(w, columns=("name", "type", "version", "updated"),
                                  show="headings", selectmode="browse", style="I.Treeview")
        for col, txt, wd, a in [("name", "App Name", 220, "w"), ("type", "Type", 90, "center"),
                                 ("version", "Version", 130, "center"), ("updated", "Updated", 120, "center")]:
            self._tree.heading(col, text=txt); self._tree.column(col, width=wd, anchor=a, minwidth=40)
        sb2 = tk.Scrollbar(w, orient="vertical", command=self._tree.yview,
                           bg=C["surface"], troughcolor=C["card"], width=10)
        self._tree.configure(yscrollcommand=sb2.set)
        self._tree.pack(side="left", fill="both", expand=True, pady=6)
        sb2.pack(side="right", fill="y", pady=6)
        self._tree.bind("<<TreeviewSelect>>", self._on_sel)
        self._tree.bind("<Double-Button-1>", self._on_launch)

        act = tk.Frame(p, bg=C["bg"]); act.pack(fill="x", padx=20, pady=6)
        self._btn_l = styled_btn(act, "▶  Launch",      self._on_launch,    primary=True)
        self._btn_u = styled_btn(act, "↑  Update",      self._on_update)
        self._btn_x = styled_btn(act, "✕  Uninstall",   self._on_uninstall, danger=True)
        self._btn_c = styled_btn(act, "⟳  Check Update", self._on_chk)
        for b in (self._btn_l, self._btn_u, self._btn_x, self._btn_c):
            b.pack(side="left", padx=(0, 8)); b.configure(state="disabled")

    def _build_my_page(self):
        p = self._mk_page(self.P_MY)
        hdr = tk.Frame(p, bg=C["bg"]); hdr.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(hdr, text="My GitHub Profile", bg=C["bg"], fg=C["white"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self._my_st = tk.Label(hdr, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9))
        self._my_st.pack(side="left", padx=10)
        styled_btn(hdr, "⟳ Load / Refresh", self._load_my_repos, primary=True, small=True).pack(side="right")
        self._my_info = tk.Label(p, text="  Add a GitHub token in ⚙ Settings to see your private repos.",
                                 bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9), anchor="w")
        self._my_info.pack(fill="x", padx=20, pady=(0, 4))
        self._my_list = RepoList(p, self._start_install)
        self._my_list.pack(fill="both", expand=True, padx=20, pady=(0, 6))

    def _build_browse_page(self):
        p = self._mk_page(self.P_BROWSE)
        hdr = tk.Frame(p, bg=C["bg"]); hdr.pack(fill="x", padx=20, pady=(14, 8))
        tk.Label(hdr, text="Browse GitHub User / Org", bg=C["bg"], fg=C["white"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self._bvar = tk.StringVar()
        ent = entry_w(hdr, textvariable=self._bvar, width=22)
        ent.pack(side="left", padx=10); ent.bind("<Return>", lambda _: self._browse_load())
        styled_btn(hdr, "Browse →", self._browse_load, primary=True, small=True).pack(side="left")
        self._binfo = tk.Label(hdr, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9))
        self._binfo.pack(side="left", padx=10)
        self._browse_list = RepoList(p, self._start_install)
        self._browse_list.pack(fill="both", expand=True, padx=20, pady=(0, 6))

    def _build_url_page(self):
        p = self._mk_page(self.P_URL)
        tk.Label(p, text="Install by URL", bg=C["bg"], fg=C["white"],
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(14, 10))
        card = tk.Frame(p, bg=C["card"], pady=20, padx=20); card.pack(fill="x", padx=20)
        tk.Label(card, text="GitHub URL or owner/repo", bg=C["card"], fg=C["muted"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(card, bg=C["card"]); row.pack(fill="x")
        self._uvar = tk.StringVar()
        ent = entry_w(row, textvariable=self._uvar)
        ent.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=6)
        ent.bind("<Return>", lambda _: self._on_install_url())
        styled_btn(row, "  Install  ",        self._on_install_url,     primary=True).pack(side="left", padx=(0, 6))
        styled_btn(row, "  Verify  ",         self._on_verify_github,   small=True).pack(side="left", padx=(0, 6))
        styled_btn(row, "  Open in Browser  ", self._on_open_in_chrome, small=True).pack(side="left")
        self._url_verify_lbl = tk.Label(
            card, text="Verify checks the repo exists before installing.",
            bg=C["card"], fg=C["muted"], font=("Segoe UI", 9), wraplength=640, justify="left",
        )
        self._url_verify_lbl.pack(anchor="w", pady=(10, 0))
        tk.Label(card,
                 text="Examples:\n  https://github.com/awesomo913/rainforge\n  nicegui/nicegui",
                 bg=C["card"], fg=C["muted"], font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(6, 0))

    # ── Core ──────────────────────────────────────────────────────────────────

    def _rebuild_api(self):
        self.api = GitHubAPI(self.registry.get_token())
        self.installer = Installer(self.api, self.registry, self._tlog)

    def _tlog(self, msg, overwrite=False): self._q.put((msg, overwrite))
    def _log(self, msg): self._tlog(msg)

    def _poll(self):
        try:
            while True:
                msg, ow = self._q.get_nowait()
                self._logpanel.write(msg, ow)
                self._status_var.set(msg.strip()[:110])
        except queue.Empty: pass
        self.after(80, self._poll)

    def _run(self, fn, *a, done=None):
        def w():
            try: res = fn(*a)
            except Exception: self._tlog(f"  ✗ Error:\n{traceback.format_exc()}"); res = False
            if done: self.after(0, lambda: done(res))
        threading.Thread(target=w, daemon=True).start()

    def _check_token_status(self):
        if not self.registry.get_token():
            self.after(0, lambda: self._auth_lbl.configure(text="⚪ No token — public only", fg=C["muted"]))
            return
        me, err = self.api.get_me()
        if me:
            n = me.get("login", "?"); d = me.get("name", "")
            self.after(0, lambda: self._auth_lbl.configure(
                text=f"🟢 {n}" + (f"  ({d})" if d else ""), fg=C["green"]))
            rem, lim = self.api.rate_limit()
            if rem: self.after(0, lambda: self._rate_lbl.configure(text=f"API {rem}/{lim}"))
        else:
            self.after(0, lambda: self._auth_lbl.configure(text=f"🔴 Token error: {err}", fg=C["red"]))

    def _refresh_installed(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        apps = self.registry.apps
        if not apps:
            self._tree.insert("", "end", values=("No apps installed yet", "", "", "")); return
        for aid, a in apps.items():
            self._tree.insert("", "end", iid=aid,
                              values=(a.get("name", aid), a.get("type", "?"),
                                      a.get("version", "?"), a.get("updated_at", "")[:10]))

    def _on_sel(self, _=None):
        sel = self._tree.selection(); ok = bool(sel) and sel[0] in self.registry.apps
        for b in (self._btn_l, self._btn_u, self._btn_x, self._btn_c):
            b.configure(state="normal" if ok else "disabled")

    def _sel_id(self): s = self._tree.selection(); return s[0] if s else None

    def _on_launch(self, _=None):
        aid = self._sel_id()
        if not aid: return
        app = self.registry.apps.get(aid, {}); exe = Path(app.get("exe_path", ""))
        if not exe.exists():
            messagebox.showerror(APP_NAME, f"Cannot find:\n{exe}\n\nTry reinstalling."); return
        try:
            if IS_WIN: subprocess.Popen([str(exe)], cwd=str(exe.parent if exe.is_file() else exe))
            else: subprocess.Popen(["bash" if exe.suffix == ".sh" else "xdg-open", str(exe)])
            self._log(f"▶ Launched {app['name']}")
        except Exception as e: messagebox.showerror(APP_NAME, f"Launch error:\n{e}")

    def _on_update(self):
        aid = self._sel_id()
        if not aid: return
        self._log(f"─── Updating {aid} ───"); self._btn_u.configure(state="disabled")
        def done(ok):
            self._refresh_installed(); self._btn_u.configure(state="normal")
            self._log("✓ Done!" if ok else "✗ Failed.")
        self._run(self.installer.update, aid, done=done)

    def _on_uninstall(self):
        aid = self._sel_id()
        if not aid: return
        app = self.registry.apps[aid]
        if messagebox.askyesno(APP_NAME, f'Uninstall "{app["name"]}"?\nRemoves all files and the Desktop shortcut.'):
            self._log(f"─── Uninstalling {aid} ───")
            self.installer.uninstall(aid); self._refresh_installed(); self._on_sel()

    def _on_chk(self):
        aid = self._sel_id()
        if not aid: return
        app = self.registry.apps[aid]
        if app["type"] != "release":
            self._log("  ℹ Click ↑ Update to pull latest for git-based apps."); return
        self._log(f"  Checking {app['name']}...")
        def _c():
            has, latest = self.api.check_for_update(app["owner"], app["repo"], app.get("version", ""))
            self._log(f"  🆕 New: {latest} — click ↑ Update." if has else f"  ✓ Up to date ({app.get('version')}).")
        self._run(_c)

    def _load_my_repos(self):
        if not self.registry.get_token():
            self._open_settings(); return
        self._my_st.configure(text="Loading...", fg=C["yellow"])
        def _f(): return self.api.get_my_repos(), self.api.get_me()
        def done(result):
            (repos, err), (me, _) = result
            if err:
                self._my_st.configure(text=f"❌ {err}", fg=C["red"])
                self._my_info.configure(text=f"  Error: {err}")
                self._log(f"  ✗ {err}"); return
            installed = set(self.registry.apps.keys())
            self._my_list.load(repos, installed)
            priv = sum(1 for r in repos if r.get("private"))
            self._my_st.configure(text=f"✓ {len(repos)} repos  ({priv} private)", fg=C["green"])
            self._my_info.configure(text="  🔒 = private   ✓ = installed   Double-click to install")
            if me: self._auth_lbl.configure(text=f"🟢 {me.get('login', '?')}", fg=C["green"])
            rem, lim = self.api.rate_limit()
            if rem: self._rate_lbl.configure(text=f"API {rem}/{lim}")
        self._run(_f, done=done)

    def _browse_load(self):
        uname = self._bvar.get().strip()
        if not uname: messagebox.showwarning(APP_NAME, "Enter a GitHub username or org."); return
        self._binfo.configure(text="Loading...")
        def _f(): return uname, self.api.get_user_repos(uname)
        def done(r):
            uname, (repos, err) = r
            if err: self._binfo.configure(text=f"Error: {err}"); self._log(f"  ✗ {err}"); return
            self._browse_list.load(repos, set(self.registry.apps.keys()))
            self._binfo.configure(text=f"{len(repos)} repos for {uname}")
        self._run(_f, done=done)

    def _on_verify_github(self):
        raw = self._uvar.get().strip()
        if not raw: messagebox.showwarning(APP_NAME, "Enter a URL or owner/repo first."); return
        self._url_verify_lbl.configure(text="Verifying…", fg=C["yellow"])
        def work():
            o, r, err = resolve_owner_repo_from_input(raw)
            if err or not o: return False, err or "Parse failed", None, None
            if self.registry.get_token():
                data, rerr = self.api.get_repo(o, r)
                if data: return True, f"OK (API) — {data.get('full_name', f'{o}/{r}')}", o, r
                if rerr == "not_found":
                    msg = "Not found or no access (private repo needs a token with repo scope)."
                elif rerr and str(rerr).startswith("network"):
                    msg = f"Network error — {rerr.split(':', 1)[-1].strip()[:120]}"
                else:
                    msg = f"API check failed: {rerr or 'unknown'}"
                return False, msg, o, r
            url = f"https://github.com/{o}/{r}"
            try:
                resp = requests.get(url, allow_redirects=True, timeout=20, headers={"User-Agent": CHROME_UA})
            except requests.RequestException as e:
                return False, str(e)[:200], o, r
            if resp.status_code == 404:
                return False, "HTTP 404 — add a token in Settings for private repos.", o, r
            if 200 <= resp.status_code < 400:
                t = (resp.text or "")[:8000]
                if "Page not found · GitHub" in t:
                    return False, "Not found or private (add a token to verify).", o, r
                return True, f"OK — page loads — {o}/{r}", o, r
            return False, f"HTTP {resp.status_code}", o, r
        def done(res):
            if res is False:
                self._url_verify_lbl.configure(text="Verify failed — see activity log.", fg=C["red"]); return
            ok, msg, o, r = res
            self._url_verify_lbl.configure(text=msg, fg=C["green"] if ok else C["red"])
            if ok and o and r: self._uvar.set(f"{o}/{r}")
        self._run(work, done=done)

    def _on_open_in_chrome(self):
        raw = self._uvar.get().strip()
        o, r, err = resolve_owner_repo_from_input(raw)
        if err or not o:
            messagebox.showwarning(APP_NAME, f"Enter a valid URL or owner/repo first.\n{err or 'Could not parse.'}"); return
        how = open_github_in_chrome(o, r)
        self._log(f"  Opened https://github.com/{o}/{r} ({how} browser)")

    def _on_install_url(self):
        raw = self._uvar.get().strip()
        if not raw: messagebox.showwarning(APP_NAME, "Enter a URL."); return
        o, r, err = resolve_owner_repo_from_input(raw)
        if err or not o:
            messagebox.showerror(APP_NAME, f"Can't parse GitHub URL:\n{err or raw}"); return
        self._uvar.set("")
        self._start_install(o, r)

    def _start_install(self, owner, repo):
        aid = f"{owner}/{repo}"
        if aid in self.registry.apps:
            if not messagebox.askyesno(APP_NAME, f'"{repo}" already installed. Reinstall?'): return
        self._log(f"─── Installing {owner}/{repo} ───")
        def done(ok):
            self._refresh_installed()
            installed = set(self.registry.apps.keys())
            self._my_list.refresh_marks(installed)
            self._browse_list.refresh_marks(installed)
            self._log(f"✓ {repo} installed — shortcut on your Desktop!" if ok else "✗ Installation failed. See log above.")
        self._run(self.installer.install, owner, repo, done=done)

    def _open_build(self):
        win = tk.Toplevel(self); win.title("Build .exe"); win.geometry("620x480")
        win.configure(bg=C["bg"]); win.grab_set()
        title_txt = "Build Standalone .exe (Windows)" if IS_WIN else "Package App (Linux / Pi)"
        desc_txt = (
            "Compiles GitHub App Manager into a single file — no Python required to run.\n"
            "Output goes to your Desktop in 'GitHubAppManager_EXE'.\n\n"
            "Requires PyInstaller (installed automatically if missing)."
        ) if IS_WIN else (
            "Compiles this app into a single executable via PyInstaller.\n"
            "The output runs on the same architecture (e.g. ARM for Pi).\n\n"
            "Requires: pip install pyinstaller"
        )
        tk.Label(win, text=title_txt, bg=C["bg"], fg=C["white"],
                 font=("Segoe UI", 12, "bold")).pack(padx=24, pady=(18, 4), anchor="w")
        tk.Label(win, text=desc_txt, bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9),
                 justify="left").pack(padx=24, anchor="w")
        out = tk.Text(win, bg=C["card"], fg=C["fg"],
                      font=("Courier" if IS_PI else "Consolas", 8),
                      relief="flat", bd=0, state="disabled", height=14)
        out.pack(fill="x", padx=24, pady=10)
        st = tk.Label(win, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9))
        st.pack(padx=24, anchor="w")

        def _w(msg):
            out.configure(state="normal"); out.insert("end", msg + "\n"); out.see("end")
            out.configure(state="disabled"); win.update_idletasks()

        def _build():
            script  = Path(sys.argv[0]).resolve()
            out_dir = DESKTOP / ("GitHubAppManager_EXE" if IS_WIN else "GitHubAppManager_bin")
            out_dir.mkdir(parents=True, exist_ok=True)
            _w(f"Script : {script}"); _w(f"Output : {out_dir}")
            _w("Installing / upgrading PyInstaller…")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller", "-q"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                _w(f"pip error:\n{r.stderr[-400:]}"); st.configure(text="pip failed.", fg=C["red"]); return
            _w("Running PyInstaller… (this takes 1-3 minutes)")
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--onefile",
                "--windowed" if IS_WIN else "--console",
                "--clean",
                "--noconfirm",
                f"--name=GitHubAppManager",
                f"--distpath={out_dir}",
                f"--workpath={APP_DIR / '_build'}",
                f"--specpath={APP_DIR}",
                "--hidden-import=requests",
                "--hidden-import=urllib3",
                "--hidden-import=certifi",
                "--hidden-import=charset_normalizer",
                "--hidden-import=idna",
                "--hidden-import=tkinter",
                "--hidden-import=tkinter.ttk",
                "--hidden-import=tkinter.messagebox",
                "--collect-all=requests",
                str(script),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            _w(r.stdout[-1200:] if r.stdout else "")
            if r.returncode != 0:
                _w(f"Error:\n{r.stderr[-800:]}"); st.configure(text="Build failed.", fg=C["red"]); return
            exe_name = "GitHubAppManager.exe" if IS_WIN else "GitHubAppManager"
            exe = out_dir / exe_name
            if exe.exists():
                if not IS_WIN: exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
                sc = make_shortcut("GitHubAppManager", exe)
                _w(f"\n✓ Built: {exe}\n✓ Shortcut: {sc}")
                st.configure(text=f"✓ Done!  Saved to: {out_dir}", fg=C["green"])
            else:
                st.configure(text="Build finished but output file not found — check log.", fg=C["yellow"])

        row = tk.Frame(win, bg=C["bg"]); row.pack(pady=6)
        def _go(): go_btn.configure(state="disabled"); threading.Thread(target=_build, daemon=True).start()
        go_btn = styled_btn(row, "🔨  Build .exe Now" if IS_WIN else "📦  Build Executable Now",
                            _go, primary=True)
        go_btn.pack(side="left", padx=8)
        styled_btn(row, "Close", win.destroy, small=True).pack(side="left")

    def _open_settings(self):
        win = tk.Toplevel(self); win.title("Settings — GitHub Token"); win.geometry("600x420")
        win.configure(bg=C["bg"]); win.grab_set(); win.resizable(False, False)

        tk.Label(win, text="GitHub Personal Access Token", bg=C["bg"], fg=C["white"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=24, pady=(20, 2))
        tk.Label(win,
                 text="A token unlocks private repos and raises the rate limit from 60 → 5000 req/hr.",
                 bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(0, 10))

        # Token entry row
        tv = tk.StringVar(value=self.registry.get_token())
        row = tk.Frame(win, bg=C["bg"]); row.pack(fill="x", padx=24)
        ent = entry_w(row, textvariable=tv); ent.configure(show="•")
        ent.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 6))
        styled_btn(row, "👁", lambda: ent.configure(show="" if ent.cget("show") else "•"),
                   small=True).pack(side="left", padx=(0, 4))
        styled_btn(row, "📋 Paste", lambda: tv.set(self._safe_clip()), small=True).pack(side="left")

        # Token type hint
        hint_lbl = tk.Label(win, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 8))
        hint_lbl.pack(anchor="w", padx=26, pady=(4, 0))
        def _update_hint(*_):
            t = tv.get().strip()
            if t.startswith("ghp_"):           hint_lbl.configure(text="Classic PAT (ghp_…)")
            elif t.startswith("github_pat_"):  hint_lbl.configure(text="Fine-grained PAT (github_pat_…)")
            elif t.startswith("gho_"):         hint_lbl.configure(text="OAuth token (gho_…)")
            elif t:                            hint_lbl.configure(text="⚠ Unrecognised format")
            else:                              hint_lbl.configure(text="")
        tv.trace_add("write", _update_hint)

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=24, pady=12)

        tk.Label(win, text="How to create a token:", bg=C["bg"], fg=C["fg"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=24)
        steps = (
            "  1.  Click the button below → GitHub opens in your browser\n"
            "  2.  Scroll down → click  Generate token\n"
            "  3.  Copy the token (starts with ghp_ or github_pat_)\n"
            "  4.  Come back here → click  📋 Paste  →  Test & Save"
        )
        tk.Label(win, text=steps, bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", padx=24, pady=(2, 10))

        btn_row = tk.Frame(win, bg=C["bg"]); btn_row.pack(padx=24, anchor="w")
        styled_btn(btn_row, "🌐 Open GitHub Token Page", lambda: webbrowser.open(GITHUB_NEW_TOKEN_URL),
                   small=True).pack(side="left", padx=(0, 8))
        def _save():
            t = tv.get().strip()
            if not t:
                self.registry.set_token(""); self._rebuild_api()
                win.destroy()
                self._auth_lbl.configure(text="⚪ No token — public only", fg=C["muted"]); return
            win.destroy()
            self._save_and_validate_token(t)
        styled_btn(btn_row, "✓ Test & Save", _save, primary=True, small=True).pack(side="left")
        styled_btn(btn_row, "Cancel", win.destroy, small=True).pack(side="left", padx=8)

    def _safe_clip(self) -> str:
        try: return self.clipboard_get().strip()
        except Exception: return ""


if __name__ == "__main__":
    App().mainloop()
