"""
Self-updater. On launch the island can check a small JSON file online and, if a
newer version is published, download the new files and swap them in -- no manual
re-download. Fully guarded: any failure (offline, bad URL) is ignored silently.

The JSON it expects (host it anywhere public, e.g. GitHub) looks like:

    { "version": "2.4.0",
      "zip_url": "https://github.com/<you>/<repo>/releases/latest/download/laptop-dynamic-island.zip" }

Files named in PRESERVE (your config + notes) are never overwritten.
"""

import os
import sys
import json
import tempfile
import zipfile
import shutil
import subprocess
import urllib.request

PRESERVE = {"config.json", "notes.txt"}


def _version_tuple(v):
    parts = []
    for chunk in str(v).strip().split("."):
        chunk = "".join(c for c in chunk if c.isdigit())
        parts.append(int(chunk) if chunk else 0)
    return tuple(parts)


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DynamicIsland-Updater"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _find_root(folder):
    """Locate the folder inside the extracted zip that actually holds island.py."""
    for root, _dirs, files in os.walk(folder):
        if "island.py" in files:
            return root
    return None


def _copy_over(src, dst):
    for name in os.listdir(src):
        if name in PRESERVE:
            continue
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)


def check_and_update(current_version, url, base_dir):
    """Return the new version string if an update was applied, else None."""
    if not url:
        return None
    try:
        info = _fetch_json(url)
        remote = info.get("version", "")
        zip_url = info.get("zip_url", "")
        if not remote or not zip_url:
            return None
        if _version_tuple(remote) <= _version_tuple(current_version):
            return None
        tmp = tempfile.mkdtemp(prefix="di_update_")
        zpath = os.path.join(tmp, "update.zip")
        urllib.request.urlretrieve(zip_url, zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)
        src = _find_root(tmp)
        if src is None:
            return None
        _copy_over(src, base_dir)
        return remote
    except Exception:
        return None


def relaunch(base_dir):
    """Start the (now updated) app again, windowless."""
    script = os.path.join(base_dir, "island.py")
    try:
        subprocess.Popen(["pythonw", script], cwd=base_dir)
    except Exception:
        try:
            subprocess.Popen([sys.executable, script], cwd=base_dir)
        except Exception:
            pass
