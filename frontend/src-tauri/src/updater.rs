use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_updater::UpdaterExt;

#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateInfo {
    pub version: String,
    pub date: String,
    pub body: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct Release {
    tag_name: String,
    html_url: String,
    body: Option<String>,
    published_at: String,
}

/// Use Tauri's built-in updater plugin to check for updates.
pub async fn check_for_update(app: &AppHandle) -> Result<Option<String>, String> {
    match app.updater() {
        Ok(updater) => {
            match updater.check().await {
                Ok(Some(update)) => {
                    log::info!("Update found: {} — {}", update.version, update.body.as_deref().unwrap_or("no notes"));
                    Ok(Some(update.version.to_string()))
                }
                Ok(None) => Ok(None),
                Err(e) => {
                    log::warn!("Updater check error: {}", e);
                    Ok(None)
                }
            }
        }
        Err(e) => {
            log::warn!("Updater plugin not initialized: {}", e);
            // Fallback to GitHub releases API
            check_github_releases().await
        }
    }
}

/// Fallback: check GitHub releases API for latest version.
async fn check_github_releases() -> Result<Option<String>, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| e.to_string())?;

    let resp = client
        .get("https://api.github.com/repos/anomalyco/veyron/releases/latest")
        .header("User-Agent", "Veyron-Desktop/1.0")
        .header("Accept", "application/vnd.github.v3+json")
        .send()
        .await
        .map_err(|e| format!("GitHub API error: {}", e))?;

    if !resp.status().is_success() {
        return Ok(None);
    }

    let release: Release = resp.json().await.map_err(|e| format!("Parse error: {}", e))?;
    let current = "1.0.0";
    let latest = release.tag_name.trim_start_matches('v');

    if latest > current {
        log::info!("Update available via GitHub: v{}", latest);
        Ok(Some(latest.to_string()))
    } else {
        Ok(None)
    }
}

/// Get current application version from Cargo.toml
pub fn current_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
