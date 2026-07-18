use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use std::process::Command;
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

                // Attempt to spawn python -m arova.daemon.main or standalone arovad executable
                // In packaged builds, this checks for bundled arovad binary first, then falls back to python runtime
                let mut cmd = if std::path::Path::new("./arovad").exists() {
                    Command::new("./arovad")
                } else if std::path::Path::new("/opt/arova/arovad").exists() {
                    Command::new("/opt/arova/arovad")
                } else {
                    let mut c = Command::new("python");
                    c.args(&["-m", "arova.daemon.main"]);
                    c
                };

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
