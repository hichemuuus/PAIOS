use tauri::{
    AppHandle,
    Manager,
    Emitter,
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::{TrayIconBuilder, MouseButton, MouseButtonState, TrayIconEvent},
    Runtime,
};

pub struct VeyronTray;

impl VeyronTray {
    pub fn create<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
        let open = MenuItemBuilder::with_id("open", "Open Veyron").build(app)?;
        let separator = PredefinedMenuItem::separator(app)?;
        let restart = MenuItemBuilder::with_id("restart", "Restart AI Engine").build(app)?;
        let stop = MenuItemBuilder::with_id("stop", "Stop AI Engine").build(app)?;
        let separator2 = PredefinedMenuItem::separator(app)?;
        let quit = MenuItemBuilder::with_id("quit", "Quit").build(app)?;

        let menu = MenuBuilder::new(app)
            .item(&open)
            .item(&separator)
            .item(&restart)
            .item(&stop)
            .item(&separator2)
            .item(&quit)
            .build()?;

        let _tray = TrayIconBuilder::new()
            .icon(app.default_window_icon().unwrap().clone())
            .tooltip("Veyron AI")
            .menu(&menu)
            .on_menu_event(move |app, event| {
                match event.id().as_ref() {
                    "open" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "restart" => {
                        log::info!("Restarting AI engine...");
                        let _ = app.emit("engine-command", "restart");
                    }
                    "stop" => {
                        log::info!("Stopping AI engine...");
                        let _ = app.emit("engine-command", "stop");
                    }
                    "quit" => {
                        log::info!("Quitting Veyron...");
                        app.exit(0);
                    }
                    _ => {}
                }
            })
            .on_tray_icon_event(|tray, event| {
                if let TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                } = event
                {
                    let app = tray.app_handle();
                    if let Some(win) = app.get_webview_window("main") {
                        let _ = win.show();
                        let _ = win.set_focus();
                    }
                }
            })
            .build(app)?;

        Ok(())
    }
}
