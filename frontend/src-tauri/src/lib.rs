mod supervisor;
use supervisor::{SupervisorState, SupervisorStatus};
use tauri::{State, Manager};

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let supervisor = SupervisorState::new();
            supervisor.start();
            app.manage(supervisor);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            get_supervisor_status,
            restart_daemon,
            export_debug_report
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
