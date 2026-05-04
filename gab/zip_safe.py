"""
Safe archive extraction: blocks zip slip and unsafe tar paths.
"""

from __future__ import annotations

import os
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path


def _is_within(dest: Path, target: Path) -> bool:
    try:
        target.relative_to(dest)
        return True
    except ValueError:
        return False


def extract_zip_safely(zip_path: Path, dest_dir: Path) -> None:
    """
    Extract a zip archive to dest_dir, rejecting paths with '..' or absolute members.
    """
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                continue
            out = (dest_dir / name).resolve()
            if not _is_within(dest_dir, out):
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 65536)
            if info.external_attr:
                # Unix permissions in high 16 bits
                mode = info.external_attr >> 16
                if mode:
                    try:
                        os.chmod(out, mode)
                    except OSError:
                        pass


def _tar_extract_member_safely(tf: tarfile.TarFile, member: tarfile.TarInfo, dest: Path) -> bool:
    dest = dest.resolve()
    if member.issym() or member.islnk():
        return False
    name = member.name
    if not name or name.startswith("/") or ".." in Path(name).parts:
        return False
    out = (dest / name).resolve()
    if not _is_within(dest, out):
        return False
    if member.isdir():
        out.mkdir(parents=True, exist_ok=True)
        return True
    out.parent.mkdir(parents=True, exist_ok=True)
    f = tf.extractfile(member)
    if f is None:
        return False
    with open(out, "wb") as w:
        w.write(f.read())
    if member.mode:
        try:
            os.chmod(out, member.mode)
        except OSError:
            pass
    return True


def extract_tar_safely(tar_path: Path, dest_dir: Path) -> None:
    """
    Extract .tar, .tar.gz, .tgz with path traversal protection.
    """
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    mode = "r:gz" if str(tar_path).lower().endswith((".gz", ".tgz")) else "r"
    with tarfile.open(tar_path, mode) as tf:
        if hasattr(tarfile, "data_filter"):
            # Python 3.12+ — safest
            try:
                tf.extractall(path=dest_dir, filter="data", numeric_owner=False)  # type: ignore[call-arg]
                return
            except TypeError:
                pass
        for m in tf.getmembers():
            _tar_extract_member_safely(tf, m, dest_dir)
