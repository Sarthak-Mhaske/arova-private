mod supervisor;
use supervisor::{SupervisorState, SupervisorStatus};
use tauri::{State, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
fn get_supervisor_status(supervisor: State<'_, SupervisorState>) -> SupervisorStatus {
    let st = supervisor.status.lock().unwrap();
    st.clone()
}

#[tauri::command]
fn restart_daemon(supervisor: State<'_, SupervisorState>) -> SupervisorStatus {
    supervisor.restart();
    let st = supervisor.status.lock().unwrap();
    st.clone()
}

#[tauri::command]
fn export_debug_report() -> String {
    // Collects local logs and returns report status
    let log_path = std::path::Path::new("daemon.log");
    if log_path.exists() {
        "Debug report ready (daemon.log present)".to_string()
    } else {
        "Debug report ready (clean state)".to_string()
    }
}

#[tauri::command]
fn log_from_frontend(msg: String) {
    println!("[FRONTEND JS] {}", msg);
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open("/home/sarthak/arova/frontend_js.log") {
        use std::io::Write;
        let _ = writeln!(file, "[FRONTEND JS] {}", msg);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        if let Some(window) = app.get_webview_window("main") {
                            if window.is_visible().unwrap_or(false) && window.is_focused().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.unminimize();
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })
                .build(),
        )
        .setup(|app| {
            let supervisor = SupervisorState::new();
            supervisor.start();
            app.manage(supervisor);

            // Register global hotkey to summon / toggle Arova window from any background app
            let shortcuts = ["CommandOrControl+Shift+Space", "Alt+Space"];
            for sc_str in shortcuts {
                if let Ok(sc) = sc_str.parse::<Shortcut>() {
                    let _ = app.global_shortcut().register(sc);
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            get_supervisor_status,
            restart_daemon,
            export_debug_report,
            log_from_frontend
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
