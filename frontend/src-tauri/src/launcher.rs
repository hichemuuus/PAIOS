use std::io::{BufRead, BufReader, Read};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tauri::{AppHandle, Emitter};

pub struct BackendLauncher {
    child: Option<Child>,
    running: Arc<AtomicBool>,
    backend_port: u16,
}

impl BackendLauncher {
    pub fn new() -> Self {
        Self {
            child: None,
            running: Arc::new(AtomicBool::new(false)),
            backend_port: 8000,
        }
    }

    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    pub fn start(&mut self, app: &AppHandle) -> Result<(), String> {
        if self.is_running() {
            return Ok(());
        }
        let child = self.spawn_backend(app)?;
        self.child = Some(child);
        self.running.store(true, Ordering::SeqCst);
        self.monitor_health(app);
        log::info!("Backend started on port {}", self.backend_port);
        Ok(())
    }

    pub fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(mut child) = self.child.take() {
            #[cfg(windows)]
            {
                let _ = Command::new("taskkill")
                    .args(["/PID", &child.id().to_string(), "/F", "/T"])
                    .output();
            }
            #[cfg(not(windows))]
            {
                let _ = child.kill();
            }
            let _ = child.wait();
            log::info!("Backend stopped");
        }
    }

    pub fn wait(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.wait();
        }
    }

    fn spawn_backend(&self, _app: &AppHandle) -> Result<Child, String> {
        // dev: use system Python / uvicorn
        #[cfg(debug_assertions)]
        {
            self.spawn_uvicorn()
        }

        // release: try bundled sidecar first, then fall back
        #[cfg(not(debug_assertions))]
        {
            self.spawn_sidecar(_app).or_else(|_| self.spawn_uvicorn())
        }
    }

    #[cfg(debug_assertions)]
    fn spawn_uvicorn(&self) -> Result<Child, String> {
        let backend_dir = find_backend_dir();
        log::info!("Starting backend from: {:?}", backend_dir);

        let mut child = Command::new("uvicorn")
            .args([
                "veyron.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                &self.backend_port.to_string(),
                "--log-level",
                "info",
            ])
            .env("PYTHONPATH", backend_dir.to_str().unwrap_or("backend"))
            .current_dir(&backend_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| {
                format!(
                    "Cannot start uvicorn: {}\nMake sure uvicorn is installed (pip install uvicorn fastapi)",
                    e
                )
            })?;

        Self::pipe_logs(child.stdout.take(), "backend");
        Self::pipe_logs(child.stderr.take(), "backend");
        Ok(child)
    }

    #[cfg(not(debug_assertions))]
    fn spawn_sidecar(&self, app: &AppHandle) -> Result<Child, String> {
        // Look for the sidecar binary bundled in the app resources
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|e| format!("Cannot resolve resource dir: {}", e))?;

        let sidecar_path = resource_dir
            .join("binaries")
            .join("veyron-backend-x86_64-pc-windows-msvc.exe");

        if !sidecar_path.exists() {
            return Err(format!("Sidecar not found at: {:?}", sidecar_path));
        }

        log::info!("Starting sidecar from: {:?}", sidecar_path);

        let child = Command::new(&sidecar_path)
            .args(["--port", &self.backend_port.to_string()])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to launch sidecar: {}", e))?;

        Self::pipe_logs(child.stdout, "sidecar");
        Self::pipe_logs(child.stderr, "sidecar");
        Ok(child)
    }

    fn pipe_logs<T: Read + Send + 'static>(pipe: Option<T>, label: &'static str) {
        if let Some(reader) = pipe {
            std::thread::spawn(move || {
                let buf = BufReader::new(reader);
                for line in buf.lines() {
                    if let Ok(text) = line {
                        log::info!("[{}] {}", label, text);
                    }
                }
            });
        }
    }

    fn monitor_health(&self, app: &AppHandle) {
        let running = self.running.clone();
        let handle = app.clone();
        let port = self.backend_port;

        std::thread::spawn(move || {
            let client = reqwest::blocking::Client::builder()
                .timeout(Duration::from_secs(5))
                .build()
                .expect("valid reqwest client");

            loop {
                std::thread::sleep(Duration::from_secs(15));
                if !running.load(Ordering::SeqCst) {
                    break;
                }
                match client
                    .get(&format!("http://127.0.0.1:{}/api/health", port))
                    .send()
                {
                    Ok(resp) if resp.status().is_success() => {
                        log::debug!("Backend health OK");
                    }
                    _ => {
                        log::warn!("Backend health check FAILED");
                        let _ = handle.emit("backend-status", "unhealthy");
                    }
                }
            }
        });
    }
}

fn find_backend_dir() -> std::path::PathBuf {
    let candidates: Vec<std::path::PathBuf> = vec![
        {
            let mut cwd = std::env::current_dir().unwrap_or_default();
            cwd.pop();
            cwd.pop();
            cwd.join("backend")
        },
        std::path::PathBuf::from("backend"),
        std::path::PathBuf::from("../backend"),
    ];

    for candidate in &candidates {
        if candidate.join("veyron").join("main.py").exists() {
            return candidate.clone();
        }
    }

    candidates.into_iter().next().unwrap_or_else(|| std::path::PathBuf::from("backend"))
}
