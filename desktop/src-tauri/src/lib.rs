use serde::Serialize;
#[cfg(not(debug_assertions))]
use std::net::TcpListener;
use std::sync::Mutex;
use tauri::{Manager, State};
use tauri_plugin_shell::process::CommandChild;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::process::CommandEvent;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

#[derive(Clone, Serialize)]
struct ApiRuntime {
    base_url: String,
    token: String,
}

struct ApiSidecar(Mutex<Option<CommandChild>>);

#[tauri::command]
fn api_runtime(runtime: State<'_, ApiRuntime>) -> ApiRuntime {
    runtime.inner().clone()
}

#[cfg(not(debug_assertions))]
fn free_loopback_port() -> Result<u16, std::io::Error> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                app.manage(ApiRuntime {
                    base_url: String::new(),
                    token: "zhiming-dev-token".to_string(),
                });
            }

            #[cfg(not(debug_assertions))]
            {
                let port = free_loopback_port()?;
                let token = uuid::Uuid::new_v4().to_string();
                let data_dir = app.path().app_data_dir()?;
                let resource_dir = app.path().resource_dir()?.join("resources");
                std::fs::create_dir_all(&data_dir)?;
                let runtime = ApiRuntime {
                    base_url: format!("http://127.0.0.1:{port}"),
                    token: token.clone(),
                };
                let command = app
                    .shell()
                    .sidecar("zhiming-api")?
                    .env("ZHIMING_LIFE_API_PORT", port.to_string())
                    .env("ZHIMING_LIFE_API_TOKEN", token)
                    .env("ZHIMING_LIFE_DATA_DIR", data_dir)
                    .env("ZHIMING_LIFE_RESOURCE_DIR", resource_dir)
                    .env("ZHIMING_LIFE_PARENT_PID", std::process::id().to_string());
                let (mut events, child) = command.spawn()?;
                app.manage(ApiSidecar(Mutex::new(Some(child))));
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = events.recv().await {
                        if let CommandEvent::Stderr(bytes) = event {
                            eprintln!("{}", String::from_utf8_lossy(&bytes));
                        }
                    }
                });
                app.manage(runtime);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![api_runtime])
        .on_window_event(|window, event| {
            if matches!(
                event,
                tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed
            ) {
                if let Some(sidecar) = window.try_state::<ApiSidecar>() {
                    if let Some(child) = sidecar.0.lock().ok().and_then(|mut value| value.take()) {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run Zhiming desktop application");
}
