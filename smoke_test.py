#!/usr/bin/env python3
"""Non-GUI smoke test for GitHub App Manager — run: py -3 smoke_test.py"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location("github_app_manager", ROOT / "github_app_manager.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _zip_slip_safe() -> None:
    import io
    import tempfile
    import zipfile

    from gab.zip_safe import extract_zip_safely

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../zip_slip_evil.txt", "nope")
        zf.writestr("ok/nested.txt", "yes")
    buf.seek(0)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        zpath = root / "t.zip"
        zpath.write_bytes(buf.getvalue())
        out = root / "out"
        extract_zip_safely(zpath, out)
        assert not (root / "zip_slip_evil.txt").exists()
        assert (out / "ok" / "nested.txt").read_text() == "yes"


def main() -> int:
    g = _load()
    assert g.parse_github_url("https://github.com/foo/bar.git") == ("foo", "bar")
    assert g.parse_github_url("x/y") == ("x", "y")
    _zip_slip_safe()
    api = g.GitHubAPI()
    rem, lim = api.rate_limit()
    assert rem is not None and lim
    t = api.detect_type("psf", "requests")
    assert t in ("python", "clone", "release", "nodejs"), t
    print("smoke_test: ok (parse_url, zip_safe, rate_limit, detect_type)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
