use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use std::process::Command;
use std::io::Write;
use serde::{Serialize, Deserialize};

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

                if crash_counter > 5 {
                    let mut st = status.lock().unwrap();
                    st.is_running = false;
                    st.safe_mode = true;
                    st.last_error = Some("Daemon crashed > 5 times. Safe Mode activated.".to_string());
                    break;
                }

                // Resolve bundled binary or python runtime across Deb, RPM, AppImage, and local dev
                let exe_dir = std::env::current_exe()
                    .ok()
                    .and_then(|p| p.parent().map(|p| p.to_path_buf()))
                    .unwrap_or_else(|| std::path::PathBuf::from("."));

                let candidate_paths = vec![
                    exe_dir.join("arovad"),
                    exe_dir.join("resources").join("arovad"),
                    exe_dir.join("../lib/Arova/resources/arovad"),
                    exe_dir.join("../lib/Arova/_up_/_up_/dist/arovad"),
                    exe_dir.join("../../dist/arovad"),
                    std::path::PathBuf::from("/usr/lib/Arova/resources/arovad"),
                    std::path::PathBuf::from("/usr/lib/Arova/_up_/_up_/dist/arovad"),
                    std::path::PathBuf::from("/usr/lib/arova/resources/arovad"),
                    std::path::PathBuf::from("/opt/arova/arovad"),
                ];

                let found_binary = candidate_paths.into_iter().find(|p| p.exists());
                let resource_py_dir = exe_dir.join("resources");

                // Clean up any stale PyInstaller temp folders before launching daemon to prevent tmpfs quota exhaustion
                for dir_path in &["/tmp", "/var/tmp"] {
                    if let Ok(entries) = std::fs::read_dir(dir_path) {
                        for entry in entries.flatten() {
                            if let Some(name) = entry.file_name().to_str() {
                                if name.starts_with("_MEI") {
                                    let _ = std::fs::remove_dir_all(entry.path());
                                }
                            }
                        }
                    }
                }

                let mut cmd = if let Some(bin_path) = found_binary {
                    let mut c = Command::new(bin_path);
                    // PyInstaller standalone binaries crash with "No module named 'encodings'" if PYTHONHOME or incompatible PYTHONPATH is inherited from AppRun/AppImage
                    c.env_remove("PYTHONHOME");
                    c.env_remove("PYTHONPATH");
                    c.env("TMPDIR", "/var/tmp");
                    c
                } else {
                    let venv_py = exe_dir.join("../lib/Arova/_up_/_up_/venv/bin/python");
                    let py_bin = if venv_py.exists() {
                        venv_py.to_string_lossy().to_string()
                    } else if std::path::Path::new("./venv/bin/python").exists() {
                        "./venv/bin/python".to_string()
                    } else {
                        "python3".to_string()
                    };
                    let mut c = Command::new(py_bin);
                    c.env_remove("PYTHONHOME");
                    c.env("TMPDIR", "/var/tmp");
                    let py_dir = if resource_py_dir.join("arova").exists() {
                        resource_py_dir
                    } else {
                        exe_dir.join("../lib/Arova/_up_/_up_")
                    };
                    if py_dir.join("arova").exists() {
                        c.env("PYTHONPATH", &py_dir);
                        c.current_dir(&py_dir);
                    }
                    c.args(&["-m", "arova.daemon.main"]);
                    c
                };

                if let Ok(addr) = "127.0.0.1:8765".parse() {
                    let probe = |addr: &std::net::SocketAddr| -> bool {
                        if let Ok(mut s) = std::net::TcpStream::connect_timeout(addr, Duration::from_millis(250)) {
                            let _ = s.write_all(b"GET / HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n\r\n");
                            return true;
                        }
                        false
                    };
                    if probe(&addr) {
                        {
                            let mut st = status.lock().unwrap();
                            st.is_running = true;
                            st.safe_mode = false;
                        }
                        loop {
                            {
                                let stop = stop_signal.lock().unwrap();
                                if *stop {
                                    break;
                                }
                            }
                            if !probe(&addr) {
                                break;
                            }
                            thread::sleep(Duration::from_secs(5));
                        }
                        continue;
                    }
                }

                if crash_counter > 5 {
                    cmd.arg("--safe-mode");
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
