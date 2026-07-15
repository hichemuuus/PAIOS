use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppConfig {
    pub llm_provider: LlmProviderConfig,
    pub storage: StorageConfig,
    pub privacy: PrivacyConfig,
    pub updates: UpdateConfig,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LlmProviderConfig {
    pub provider: String,
    pub model: String,
    pub remote_enabled: bool,
    pub remote_url: String,
    pub micro_models_enabled: bool,
    pub confidence_threshold: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct StorageConfig {
    pub data_dir: String,
    pub max_history_days: u32,
    pub auto_backup: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PrivacyConfig {
    pub telemetry_enabled: bool,
    pub collect_interactions: bool,
    pub local_only: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct UpdateConfig {
    pub auto_check: bool,
    pub channel: String,
    pub last_check: Option<String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            llm_provider: LlmProviderConfig {
                provider: "ollama".to_string(),
                model: "qwen2.5:3b-instruct".to_string(),
                remote_enabled: false,
                remote_url: "".to_string(),
                micro_models_enabled: true,
                confidence_threshold: 0.6,
            },
            storage: StorageConfig {
                data_dir: default_data_dir(),
                max_history_days: 30,
                auto_backup: false,
            },
            privacy: PrivacyConfig {
                telemetry_enabled: false,
                collect_interactions: true,
                local_only: true,
            },
            updates: UpdateConfig {
                auto_check: true,
                channel: "stable".to_string(),
                last_check: None,
            },
        }
    }
}

impl AppConfig {
    pub fn load() -> Self {
        let path = config_path();
        if path.exists() {
            match std::fs::read_to_string(&path) {
                Ok(content) => {
                    match serde_json::from_str(&content) {
                        Ok(cfg) => return cfg,
                        Err(e) => log::warn!("Failed to parse config, using defaults: {}", e),
                    }
                }
                Err(e) => log::warn!("Failed to read config, using defaults: {}", e),
            }
        }
        let cfg = AppConfig::default();
        let _ = cfg.save();
        cfg
    }

    pub fn save(&self) -> Result<(), String> {
        let path = config_path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let content = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        std::fs::write(&path, content).map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn update<F>(f: F) -> Result<Self, String>
    where
        F: FnOnce(&mut Self),
    {
        let mut cfg = Self::load();
        f(&mut cfg);
        cfg.save()?;
        Ok(cfg)
    }
}

fn default_data_dir() -> String {
    let base = if cfg!(target_os = "windows") {
        std::env::var("APPDATA")
            .map(|d| PathBuf::from(d).join("Veyron"))
            .unwrap_or_else(|_| PathBuf::from(".").join("veyron_data"))
    } else if cfg!(target_os = "macos") {
        dirs_fallback().join("Library/Application Support/Veyron")
    } else {
        dirs_fallback().join(".local/share/veyron")
    };
    base.to_str().unwrap_or(".").to_string()
}

fn dirs_fallback() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn config_path() -> PathBuf {
    PathBuf::from(default_data_dir()).join("config.json")
}
