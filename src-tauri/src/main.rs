use std::{collections::HashMap, io::{BufRead, BufReader, Read, Write}, os::unix::process::CommandExt, process::{Child, ChildStdin, Command, Stdio}, sync::{Arc, Mutex, atomic::{AtomicU64, Ordering}}, time::{Duration, Instant}};
use tauri::{Emitter, Manager};
use serde_json::{json, Value};

type Reply = std::sync::mpsc::Sender<Result<Value, String>>;
struct Bridge {
    child: Mutex<Option<Child>>,
    input: Mutex<Option<ChildStdin>>,
    pending: Arc<Mutex<HashMap<u64, Reply>>>,
    next: AtomicU64,
    pgid: i32,
}
impl Bridge {
    fn spawn(app: tauri::AppHandle) -> Result<Self, String> {
        let root = std::env::var_os("NARRATORVERSE_ROOT").map(std::path::PathBuf::from)
            .unwrap_or_else(|| std::path::PathBuf::from("/app/share/narratorverse"));
        let launcher = root.join("bin/backend");
        let mut cmd = Command::new(&launcher);
        cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
        // A process group exclusively for this backend and its inference/capture workers.
        unsafe { cmd.pre_exec(|| { if libc::setsid() < 0 { return Err(std::io::Error::last_os_error()); } Ok(()) }); }
        let mut child = cmd.spawn().map_err(|e| format!("Backend {}: {e}", launcher.display()))?;
        let pgid = child.id() as i32;
        let input = child.stdin.take();
        let stdout = child.stdout.take().ok_or("No backend stdout")?;
        let stderr = child.stderr.take().ok_or("No backend stderr")?;
        let pending: Arc<Mutex<HashMap<u64, Reply>>> = Arc::new(Mutex::new(HashMap::new()));
        let readers = pending.clone();
        let events = app.clone();
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                let mut line = String::new();
                match reader.by_ref().take(16 * 1024 * 1024 + 1).read_line(&mut line) {
                    Ok(0) | Err(_) => break,
                    Ok(_) if line.len() > 16 * 1024 * 1024 => break,
                    Ok(_) => {}
                }
                match serde_json::from_str::<Value>(&line) {
                    Ok(value) => {
                        if let Some(id) = value.get("id").and_then(Value::as_u64) {
                            if let Some(tx) = readers.lock().unwrap().remove(&id) {
                                let result = if let Some(error) = value.get("error") { Err(error.as_str().unwrap_or("Backend error").to_string()) }
                                    else { Ok(value.get("result").cloned().unwrap_or(Value::Null)) };
                                let _ = tx.send(result);
                            }
                        } else { let _ = events.emit("backend", &value); }
                    },
                    Err(e) => { let _ = events.emit("backend", json!({"event":"error","data":{"message":format!("Invalid backend protocol: {e}")}})); }
                }
            }
            for (_, tx) in readers.lock().unwrap().drain() { let _ = tx.send(Err("Backend closed unexpectedly".into())); }
            let _ = events.emit("backend", json!({"event":"crashed","data":{"message":"Proces silnika został zamknięty. Uruchom aplikację ponownie."}}));
            // If Python crashes, no persistent workers from that backend may survive.
            unsafe { libc::kill(-pgid, libc::SIGTERM); }
        });
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) { eprintln!("[python] {line}"); }
        });
        Ok(Self {child: Mutex::new(Some(child)), input: Mutex::new(input), pending, next: AtomicU64::new(1), pgid})
    }
    fn call(&self, method: String, params: Value) -> Result<Value, String> {
        const ALLOWED: &[&str] = &["status","profile_create","profile_select","profile_rename","profile_delete","settings","ocr_options","reset","start","change_source","read","pause","stop","preview","region","components_refresh","component_cancel","component","voice_import","voice_remove","voice_preview","quick_settings","quick_read","quick_stop","audio_targets"];
        if !ALLOWED.contains(&method.as_str()) { return Err("Unsupported method".into()); }
        let id = self.next.fetch_add(1, Ordering::Relaxed);
        let (tx, rx) = std::sync::mpsc::channel();
        self.pending.lock().unwrap().insert(id, tx);
        let payload = format!("{}\n", json!({"id":id,"method":method,"params":params}));
        let write = self.input.lock().unwrap().as_mut().ok_or("Backend unavailable".to_string()).and_then(|input| input.write_all(payload.as_bytes()).map_err(|e|e.to_string()));
        if let Err(e) = write { self.pending.lock().unwrap().remove(&id); return Err(e); }
        // Long component jobs are asynchronous to the UI, cancellation uses another command.
        let result = rx.recv_timeout(Duration::from_secs(3600)).map_err(|e|e.to_string());
        self.pending.lock().unwrap().remove(&id);
        result?
    }
    fn shutdown(&self) {
        if let Some(mut input) = self.input.lock().unwrap().take() { let _ = input.write_all(b"{\"method\":\"shutdown\"}\n"); }
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let deadline = Instant::now() + Duration::from_secs(5);
            while Instant::now() < deadline { if matches!(child.try_wait(), Ok(Some(_))) { break; } std::thread::sleep(Duration::from_millis(50)); }
            unsafe { libc::kill(-self.pgid, libc::SIGTERM); }
            std::thread::sleep(Duration::from_millis(150));
            unsafe { libc::kill(-self.pgid, libc::SIGKILL); }
            let _ = child.wait();
        }
    }
}
#[tauri::command]
async fn rpc(bridge: tauri::State<'_, Arc<Bridge>>, method: String, params: Value) -> Result<Value, String> {
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || bridge.call(method, params)).await.map_err(|e|e.to_string())?
}
fn main() {
    let app = tauri::Builder::default().setup(|app| {
        // Wayland shells resolve a named desktop icon, not just the embedded PNG.
        #[cfg(target_os = "linux")]
        {
            use gtk::prelude::GtkWindowExt;
            if let Some(window) = app.get_webview_window("main") {
                window.gtk_window()?.set_icon_name(Some("io.github.DevVoidPL.NarratorVerse"));
            }
        }
        match Bridge::spawn(app.handle().clone()) {
            Ok(bridge) => { app.manage(Arc::new(bridge)); }
            Err(error) => { eprintln!("{error}"); return Err(error.into()); }
        }
        Ok(())
    }).invoke_handler(tauri::generate_handler![rpc]).build(tauri::generate_context!()).expect("Nie udało się uruchomić NarratorVerse");
    app.run(|app, event| { if let tauri::RunEvent::Exit = event { if let Some(bridge) = app.try_state::<Arc<Bridge>>() { bridge.shutdown(); } } });
}