use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use std::process::Command;
use serde::{Serialize, Deserialize};

#[cfg(unix)]
use std::os::unix::process::CommandExt;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SupervisorStatus {
    pub is_running: bool,
    pub crash_count: u32,
    pub safe_mode: bool,
    pub last_error: Option<String>,
}

pub struct SupervisorState {
    pub status: Arc<Mutex<SupervisorStatus>>,
    pub stop_signal: Arc<Mutex<bool>>,
}

impl SupervisorState {
    pub fn new() -> Self {
        Self {
            status: Arc::new(Mutex::new(SupervisorStatus {
                is_running: false,
                crash_count: 0,
                safe_mode: false,
                last_error: None,
            })),
            stop_signal: Arc::new(Mutex::new(false)),
        }
    }

    pub fn start(&self) {
        let status = Arc::clone(&self.status);
        let stop_signal = Arc::clone(&self.stop_signal);

        thread::spawn(move || {
            let mut crash_counter = 0;

            loop {
                {
                    let stop = stop_signal.lock().unwrap();
                    if *stop {
                        break;
                    }
                }

                // 1. Check if background daemon is ALREADY running on port 8765
                let is_port_active = std::net::TcpStream::connect_timeout(
                    &std::net::SocketAddr::from(([127, 0, 0, 1], 8765)),
                    Duration::from_millis(350)
                ).is_ok();

                if is_port_active {
                    {
                        let mut st = status.lock().unwrap();
                        st.is_running = true;
                        st.safe_mode = false;
                        st.last_error = None;
                    }
                    // Background daemon is actively tracking! Monitor health in loop
                    while !*stop_signal.lock().unwrap() {
                        thread::sleep(Duration::from_secs(2));
                        if std::net::TcpStream::connect_timeout(
                            &std::net::SocketAddr::from(([127, 0, 0, 1], 8765)),
                            Duration::from_millis(500)
                        ).is_err() {
                            break; // Daemon stopped or killed, fall through to respawn
                        }
                    }
                    continue;
                }

                if crash_counter > 5 {
                    let mut st = status.lock().unwrap();
                    st.is_running = false;
                    st.safe_mode = true;
                    st.last_error = Some("Daemon crashed > 5 times. Safe Mode activated.".to_string());
                    break;
                }

                // Resolve bundled binary or python runtime across Deb, RPM, AppImage, and local dev.
                let exe_dir = std::env::current_exe()
                    .ok()
                    .and_then(|p| p.parent().map(|p| p.to_path_buf()))
                    .unwrap_or_else(|| std::path::PathBuf::from("."));

                let appdir = std::env::var_os("APPDIR").map(std::path::PathBuf::from);
                let resource_dir = std::env::var_os("TAURI_RESOURCE_DIR")
                    .map(std::path::PathBuf::from)
                    .or_else(|| {
                        let cands = [
                            exe_dir.join("resources"),
                            exe_dir.join("../resources"),
                            exe_dir.join("../lib/Arova/resources"),
                        ];
                        cands.into_iter().find(|p| p.exists())
                    });

                let mut candidate_paths = vec![
                    exe_dir.join("arovad"),
                    exe_dir.join("arovad.exe"),
                    exe_dir.join("resources").join("arovad"),
                    exe_dir.join("resources").join("arovad.exe"),
                    exe_dir.join("resources").join("arovad").join("arovad"),
                    exe_dir.join("resources").join("arovad").join("arovad.exe"),
                    exe_dir.join("../Resources").join("arovad"),
                    exe_dir.join("../Resources").join("arovad").join("arovad"),
                    exe_dir.join("../resources").join("arovad"),
                    exe_dir.join("../resources").join("arovad.exe"),
                    exe_dir.join("../resources").join("arovad").join("arovad"),
                    exe_dir.join("../resources").join("arovad").join("arovad.exe"),
                    exe_dir.join("../lib/Arova/resources/arovad"),
                    exe_dir.join("../lib/Arova/resources/arovad/arovad"),
                    exe_dir.join("../lib/Arova/_up_/_up_/dist/arovad"),
                    exe_dir.join("../../dist/arovad"),
                    exe_dir.join("../../dist/arovad/arovad"),
                    exe_dir.join("../../dist/arovad/arovad.exe"),
                    exe_dir.join("../../../dist/arovad"),
                    exe_dir.join("../../../dist/arovad/arovad"),
                    std::path::PathBuf::from("/usr/lib/Arova/resources/arovad"),
                    std::path::PathBuf::from("/usr/lib/Arova/resources/arovad/arovad"),
                    std::path::PathBuf::from("/usr/lib/arova/resources/arovad"),
                    std::path::PathBuf::from("/opt/arova/arovad"),
                    std::path::PathBuf::from("/opt/arova/resources/arovad/arovad"),
                ];

                if let Some(home_val) = std::env::var_os("HOME") {
                    let h = std::path::PathBuf::from(home_val);
                    candidate_paths.insert(0, h.join(".local/share/arova/resources/arovad/arovad"));
                    candidate_paths.insert(1, h.join(".local/share/arova/resources/arovad"));
                    candidate_paths.insert(2, h.join(".local/share/arova/arovad"));
                    candidate_paths.insert(3, h.join("Library/Application Support/Arova/resources/arovad/arovad"));
                }

                if let Some(appdata_val) = std::env::var_os("LOCALAPPDATA") {
                    let ad = std::path::PathBuf::from(appdata_val);
                    candidate_paths.insert(0, ad.join("Arova/resources/arovad/arovad.exe"));
                    candidate_paths.insert(1, ad.join("Arova/resources/arovad.exe"));
                    candidate_paths.insert(2, ad.join("Arova/arovad.exe"));
                }

                if let Some(ref rd) = resource_dir {
                    candidate_paths.insert(0, rd.join("arovad").join("arovad"));
                    candidate_paths.insert(1, rd.join("arovad").join("arovad.exe"));
                    candidate_paths.insert(2, rd.join("arovad"));
                    candidate_paths.insert(3, rd.join("dist").join("arovad"));
                }
                if let Some(ref ad) = appdir {
                    candidate_paths.insert(0, ad.join("usr/bin/arovad"));
                    candidate_paths.insert(1, ad.join("usr/lib/Arova/resources/arovad/arovad"));
                    candidate_paths.insert(2, ad.join("usr/lib/Arova/resources/arovad"));
                    candidate_paths.insert(3, ad.join("resources/arovad/arovad"));
                    candidate_paths.insert(4, ad.join("resources/arovad"));
                    candidate_paths.insert(5, ad.join("arovad"));
                }

                let found_binary = candidate_paths.into_iter().find_map(|p| {
                    if p.is_file() {
                        Some(p)
                    } else if p.is_dir() && p.join("arovad").is_file() {
                        Some(p.join("arovad"))
                    } else if p.is_dir() && p.join("arovad.exe").is_file() {
                        Some(p.join("arovad.exe"))
                    } else {
                        None
                    }
                });

                let resource_py_dir = resource_dir
                    .clone()
                    .unwrap_or_else(|| exe_dir.join("resources"));

                let mut cmd = if let Some(bin_path) = found_binary {
                    let mut c = Command::new(&bin_path);
                    if let Some(parent) = bin_path.parent() {
                        c.current_dir(parent);
                    }
                    c.env_remove("PYTHONHOME");
                    c.env_remove("PYTHONPATH");
                    c
                } else {
                    let mut venv_candidates = vec![
                        std::path::PathBuf::from("/home/sarthak/arova/venv/bin/python"),
                        std::path::PathBuf::from("../venv/bin/python"),
                        std::path::PathBuf::from("../venv/Scripts/python.exe"),
                        std::path::PathBuf::from("../../venv/bin/python"),
                        std::path::PathBuf::from("../../venv/Scripts/python.exe"),
                        std::path::PathBuf::from("./venv/bin/python"),
                        std::path::PathBuf::from("./venv/Scripts/python.exe"),
                        exe_dir.join("../lib/Arova/_up_/_up_/venv/bin/python"),
                    ];
                    if let Some(ref ad) = appdir {
                        venv_candidates.insert(0, ad.join("usr/lib/Arova/venv/bin/python"));
                        venv_candidates.insert(1, ad.join("venv/bin/python"));
                    }
                    let py_bin = venv_candidates
                        .into_iter()
                        .find(|p| p.exists())
                        .map(|p| p.to_string_lossy().to_string())
                        .unwrap_or_else(|| {
                            if cfg!(windows) { "python.exe".to_string() } else { "python3".to_string() }
                        });

                    let mut c = Command::new(py_bin);
                    c.env_remove("PYTHONHOME");
                    if !cfg!(windows) {
                        c.env("TMPDIR", "/var/tmp");
                    }

                    let mut py_dir_candidates = vec![
                        std::path::PathBuf::from("/home/sarthak/arova"),
                        std::path::PathBuf::from(".."),
                        std::path::PathBuf::from("../.."),
                        resource_py_dir.clone(),
                        exe_dir.join("../lib/Arova/_up_/_up_"),
                        exe_dir.join("../../.."),
                    ];
                    if let Some(ref ad) = appdir {
                        py_dir_candidates.insert(0, ad.join("usr/lib/Arova/resources"));
                        py_dir_candidates.insert(1, ad.join("resources"));
                    }

                    if let Some(target_dir) = py_dir_candidates.into_iter().find(|d| d.join("arova").exists()) {
                        c.env("PYTHONPATH", &target_dir);
                        c.current_dir(&target_dir);
                    }

                    c.args(&["-m", "arova.daemon.main"]);
                    c
                };

                if crash_counter > 5 {
                    cmd.arg("--safe-mode");
                }

                // Prepare log output destination
                let log_path = if cfg!(windows) {
                    std::env::var_os("LOCALAPPDATA")
                        .map(std::path::PathBuf::from)
                        .map(|p| p.join("Arova"))
                        .unwrap_or_else(|| exe_dir.clone())
                        .join("daemon_supervisor.log")
                } else {
                    std::env::var_os("HOME")
                        .map(std::path::PathBuf::from)
                        .map(|p| p.join(".config/arova"))
                        .unwrap_or_else(|| std::path::PathBuf::from("/tmp"))
                        .join("daemon_supervisor.log")
                };

                if let Some(parent) = log_path.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }

                if let Ok(file) = std::fs::OpenOptions::new().create(true).append(true).open(&log_path) {
                    if let Ok(err_file) = file.try_clone() {
                        cmd.stdout(std::process::Stdio::from(file));
                        cmd.stderr(std::process::Stdio::from(err_file));
                    }
                }

                // Detach daemon process group so it keeps running in the background when frontend UI closes
                #[cfg(unix)]
                {
                    cmd.process_group(0);
                }

                #[cfg(windows)]
                {
                    use std::os::windows::process::CommandExt;
                    // CREATE_NO_WINDOW (0x08000000) + CREATE_NEW_PROCESS_GROUP (0x00000200)
                    cmd.creation_flags(0x08000000 | 0x00000200);
                }

                match cmd.spawn() {
                    Ok(mut child) => {
                        {
                            let mut st = status.lock().unwrap();
                            st.is_running = true;
                            st.safe_mode = false;
                        }

                        // Block until child process exits or crashes
                        let exit_status = child.wait();

                        {
                            let mut st = status.lock().unwrap();
                            st.is_running = false;
                            match exit_status {
                                Ok(code) => {
                                    if !code.success() {
                                        crash_counter += 1;
                                        st.crash_count = crash_counter;
                                        st.last_error = Some(format!("Daemon exited with code: {}", code));
                                    }
                                }
                                Err(err) => {
                                    crash_counter += 1;
                                    st.crash_count = crash_counter;
                                    st.last_error = Some(format!("Failed to wait on daemon: {}", err));
                                }
                            }
                        }

                        // Wait 1 second before attempting auto-restart
                        thread::sleep(Duration::from_secs(1));
                    }
                    Err(err) => {
                        crash_counter += 1;
                        {
                            let mut st = status.lock().unwrap();
                            st.is_running = false;
                            st.crash_count = crash_counter;
                            st.last_error = Some(format!("Failed to spawn daemon: {}", err));
                        }
                        thread::sleep(Duration::from_secs(2));
                    }
                }
            }
        });
    }

    pub fn restart(&self) {
        {
            let mut st = self.status.lock().unwrap();
            st.crash_count = 0;
            st.safe_mode = false;
            st.last_error = None;
        }
        {
            let mut stop = self.stop_signal.lock().unwrap();
            *stop = false;
        }
        self.start();
    }
}
