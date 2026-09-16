// video-to-guide desktop shell.
//
// Spawns the PyInstaller-built FastAPI sidecar (bundled as a Tauri
// resource) on a free localhost port, waits for it to accept
// connections, then opens a webview pointed at the server, which serves
// both the API and the built frontend.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const STARTUP_TIMEOUT: Duration = Duration::from_secs(60);

/// Ask the OS for a free localhost port (released before the sidecar binds it).
fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("bind ephemeral port")
        .local_addr()
        .expect("local addr")
        .port()
}

fn server_up(port: u16) -> bool {
    TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn wait_for_server(port: u16) -> bool {
    let deadline = Instant::now() + STARTUP_TIMEOUT;
    while Instant::now() < deadline {
        if server_up(port) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(300));
    }
    false
}

/// Path of the bundled sidecar executable.
///
/// Dev builds run outside the app bundle, so they use the staged copy in
/// `src-tauri/sidecar/`. Release builds resolve inside the installed
/// bundle's resources, with a look-next-to-the-executable fallback.
fn sidecar_path(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    const BIN: &str = if cfg!(windows) {
        "vtg-server.exe"
    } else {
        "vtg-server"
    };

    let mut dirs = Vec::new();
    if cfg!(debug_assertions) {
        dirs.push(
            std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("sidecar")
                .join("vtg-server"),
        );
    }
    if let Ok(dir) = app.path().resource_dir() {
        dirs.push(dir.join("vtg-server"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            dirs.push(parent.join("vtg-server"));
        }
    }

    dirs.iter()
        .map(|dir| dir.join(BIN))
        .find(|bin| bin.is_file())
        .ok_or_else(|| "vtg-server sidecar not found".to_string())
}

struct ServerChild(Mutex<Option<Child>>);

fn kill_server(child: &ServerChild) {
    if let Ok(mut guard) = child.0.lock() {
        if let Some(mut process) = guard.take() {
            let _ = process.kill();
            let _ = process.wait();
        }
    }
}

fn main() {
    let port = free_port();
    let child_state = ServerChild(Mutex::new(None));

    let app = tauri::Builder::default()
        .manage(child_state)
        .setup(move |app| {
            let binary = sidecar_path(app.handle())?;
            let child = Command::new(&binary)
                .arg("--port")
                .arg(port.to_string())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .map_err(|e| format!("failed to spawn sidecar: {e}"))?;
            *app.state::<ServerChild>().0.lock().unwrap() = Some(child);

            if !wait_for_server(port) {
                return Err("video-to-guide server did not start in time".into());
            }

            let url: tauri::Url = format!("http://127.0.0.1:{port}/").parse()?;
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("video-to-guide")
                .inner_size(1280.0, 800.0)
                .min_inner_size(960.0, 600.0)
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            kill_server(app_handle.state::<ServerChild>().inner());
        }
    });
}
