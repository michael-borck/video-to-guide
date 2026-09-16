# Builds the vtg-server sidecar used by the Tauri desktop app.
# Prereqs: frontend built (frontend/dist), uv sync --group package.
# Build:    uv run pyinstaller --noconfirm vtg-server.spec
# onedir mode: onefile re-extracts opencv to a temp dir on every launch
# (~30s); onedir starts in about a second. Tauri bundles the whole
# dist/vtg-server folder as a resource and spawns the binary inside it.

a = Analysis(
    ["backend/server_entry.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("src/videotoguide/templates", "videotoguide/templates"),
        ("frontend/dist", "frontend_dist"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    excludes=["tkinter", "matplotlib", "pytest", "PyQt5"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vtg-server",
    # Windowed so no console flashes on Windows when Tauri spawns us;
    # server_entry redirects the missing stdio handles to devnull.
    console=False,
    disable_windowed_traceback=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="vtg-server",
)
