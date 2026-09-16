"""Standalone server entry point for the packaged desktop app.

PyInstaller bundles this as the ``vtg-server`` sidecar binary that the
Tauri shell spawns. Projects and exports live under the user's
application-data directory; the frontend is served from data files
bundled inside the executable.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_PORT = 8747


def app_support_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "video-to-guide"


def bundle_dir() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def main() -> None:
    parser = argparse.ArgumentParser(description="video-to-guide desktop server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    # PyInstaller windowed builds have no stdout/stderr; give the logging
    # machinery valid handles so uvicorn does not crash writing logs.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    root = app_support_dir()
    (root / "projects").mkdir(parents=True, exist_ok=True)
    (root / "exports").mkdir(parents=True, exist_ok=True)
    os.environ["VTG_ROOT"] = str(root)

    bundle = bundle_dir()
    if bundle is not None:
        dist = bundle / "frontend_dist"
        if dist.is_dir():
            os.environ["VTG_DIST"] = str(dist)

    import uvicorn

    from backend.main import app

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
