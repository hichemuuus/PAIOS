pub mod launcher;
pub mod tray;
pub mod updater;
pub mod config;

use tauri::{Emitter, Manager};
use launcher::BackendLauncher;
use tray::VeyronTray;
use config::AppConfig;
use std::sync::{Arc, Mutex};

pub struct AppState {
    pub launcher: Arc<Mutex<BackendLauncher>>,
}

#[tauri::command]
fn get_backend_status(state: tauri::State<AppState>) -> Result<String, String> {
    let launcher = state.launcher.lock().map_err(|e| e.to_string())?;
    Ok(format!("{}", launcher.is_running()))
}

#[tauri::command]
async fn restart_backend(app: tauri::AppHandle, state: tauri::State<'_, AppState>) -> Result<(), String> {
    let mut launcher = state.launcher.lock().map_err(|e| e.to_string())?;
    launcher.stop();
    launcher.start(&app).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_app_config() -> Result<AppConfig, String> {
    Ok(AppConfig::load())
}

#[tauri::command]
fn save_app_config(config: AppConfig) -> Result<(), String> {
    config.save()
}

#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let handle = app.handle().clone();

            let win = handle.get_webview_window("main").ok_or("main window not found")?;
            win.set_title("Veyron AI")?;

            let launcher = Arc::new(Mutex::new(BackendLauncher::new()));
            let state = AppState {
                launcher: launcher.clone(),
            };
            handle.manage(state);

            VeyronTray::create(&handle)?;

            let h_launcher = handle.clone();
            let l_launcher = launcher.clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_secs(2));
                if let Ok(mut guard) = l_launcher.lock() {
                    if let Err(e) = guard.start(&h_launcher) {
                        log::error!("Backend start failed: {}", e);
                        let _ = h_launcher.emit("backend-status", "error");
                    } else {
                        let _ = h_launcher.emit("backend-status", "running");
                    }
                }
            });

            let h_updater = handle.clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_secs(5));
                let rt = tokio::runtime::Runtime::new().unwrap();
                rt.block_on(async {
                    match updater::check_for_update(&h_updater).await {
                        Ok(Some(version)) => {
                            log::info!("Update available: {}", version);
                            let _ = h_updater.emit("update-available", &version);
                        }
                        Ok(None) => log::info!("No update available"),
                        Err(e) => log::warn!("Update check failed: {}", e),
                    }
                });
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_status,
            restart_backend,
            get_app_config,
            save_app_config,
            get_app_version,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Veyron Desktop");
}
