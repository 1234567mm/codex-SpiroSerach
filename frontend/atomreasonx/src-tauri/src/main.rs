// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    io::{BufRead, BufReader},
    path::PathBuf,
    process::{Child, ChildStdout, Command, Stdio},
    sync::{mpsc, Mutex},
    time::Duration,
};

const DEFAULT_READONLY_SIDECAR_ADDR: &str = "127.0.0.1:0";
const READONLY_SIDECAR_HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(10);
const MINIMUM_READONLY_TOKEN_LENGTH: usize = 16;

#[derive(Default)]
struct ReadonlySidecarProcesses {
    children_by_output_dir: Mutex<HashMap<PathBuf, Child>>,
}

impl Drop for ReadonlySidecarProcesses {
    fn drop(&mut self) {
        if let Ok(children) = self.children_by_output_dir.get_mut() {
            for (_, child) in children.drain() {
                stop_child(Some(child));
            }
        }
    }
}

#[derive(Debug, Deserialize)]
struct ReadonlySidecarAnnouncement {
    base_url: String,
    run_id: String,
    read_only: bool,
    readonly_token: String,
}

#[derive(Debug, Serialize)]
struct ReadonlySidecarLaunch {
    base_url: String,
    run_id: String,
    read_only: bool,
    readonly_token: String,
    process_id: u32,
}

#[tauri::command]
fn start_readonly_sidecar(
    state: tauri::State<'_, ReadonlySidecarProcesses>,
    output_dir: String,
) -> Result<ReadonlySidecarLaunch, String> {
    let output_dir = canonical_output_dir(&output_dir)?;
    stop_existing_sidecar_for_output_dir(&state, &output_dir)?;
    let executable = resolve_spiroctl_path();
    let mut child = Command::new(executable)
        .args([
            "readonly-run",
            "serve",
            output_dir
                .to_str()
                .ok_or_else(|| "readonly output_dir is not valid UTF-8".to_string())?,
            "--addr",
            DEFAULT_READONLY_SIDECAR_ADDR,
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("failed to start readonly sidecar: {error}"))?;

    let process_id = child.id();
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "readonly sidecar stdout was not captured".to_string())?;

    let launch = match read_startup_announcement(stdout) {
        Ok(line) => parse_startup_announcement(&line, process_id),
        Err(error) => Err(error),
    };
    if launch.is_err() {
        let _ = child.kill();
        let _ = child.wait();
        return launch;
    }

    let mut children = state
        .children_by_output_dir
        .lock()
        .map_err(|_| "readonly sidecar process state is poisoned".to_string())?;
    children.insert(output_dir, child);
    launch
}

#[tauri::command]
fn stop_readonly_sidecar(
    state: tauri::State<'_, ReadonlySidecarProcesses>,
    process_id: u32,
) -> Result<(), String> {
    let mut children = state
        .children_by_output_dir
        .lock()
        .map_err(|_| "readonly sidecar process state is poisoned".to_string())?;
    let key = children.iter().find_map(|(output_dir, child)| {
        if child.id() == process_id {
            Some(output_dir.clone())
        } else {
            None
        }
    });
    if let Some(key) = key {
        stop_child(children.remove(&key));
    }
    Ok(())
}

fn stop_existing_sidecar_for_output_dir(
    state: &tauri::State<'_, ReadonlySidecarProcesses>,
    output_dir: &PathBuf,
) -> Result<(), String> {
    let mut children = state
        .children_by_output_dir
        .lock()
        .map_err(|_| "readonly sidecar process state is poisoned".to_string())?;
    stop_child(children.remove(output_dir));
    Ok(())
}

fn stop_child(child: Option<Child>) {
    if let Some(mut child) = child {
        child
            .kill()
            .ok();
        let _ = child.wait();
    }
}

fn main() {
    tauri::Builder::default()
        .manage(ReadonlySidecarProcesses::default())
        .invoke_handler(tauri::generate_handler![
            start_readonly_sidecar,
            stop_readonly_sidecar
        ])
        .run(tauri::generate_context!())
        .expect("error while running AtomReasonX application");
}

fn canonical_output_dir(output_dir: &str) -> Result<PathBuf, String> {
    let trimmed = output_dir.trim();
    if trimmed.is_empty() {
        return Err("readonly output_dir is required".to_string());
    }
    let path = PathBuf::from(trimmed);
    let canonical = path
        .canonicalize()
        .map_err(|error| format!("readonly output_dir is not accessible: {error}"))?;
    if !canonical.is_dir() {
        return Err("readonly output_dir must be a directory".to_string());
    }
    if !canonical.join("run-manifest.json").is_file() {
        return Err("readonly output_dir must contain run-manifest.json".to_string());
    }
    Ok(canonical)
}

fn resolve_spiroctl_path() -> String {
    std::env::var("SPIROCTL_PATH")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "spiroctl".to_string())
}

fn read_startup_announcement(stdout: ChildStdout) -> Result<String, String> {
    let (sender, receiver) = mpsc::channel();
    std::thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        let result = reader.read_line(&mut line).map(|_| line);
        let _ = sender.send(result);
    });

    match receiver.recv_timeout(READONLY_SIDECAR_HANDSHAKE_TIMEOUT) {
        Ok(Ok(line)) if !line.trim().is_empty() => Ok(line),
        Ok(Ok(_)) => Err("readonly sidecar startup announcement was empty".to_string()),
        Ok(Err(error)) => Err(format!("failed to read readonly sidecar startup: {error}")),
        Err(_) => Err("readonly sidecar startup timed out".to_string()),
    }
}

fn parse_startup_announcement(
    line: &str,
    process_id: u32,
) -> Result<ReadonlySidecarLaunch, String> {
    let announcement: ReadonlySidecarAnnouncement = serde_json::from_str(line)
        .map_err(|error| format!("invalid readonly sidecar startup JSON: {error}"))?;
    if !announcement.read_only {
        return Err("readonly sidecar did not report read_only=true".to_string());
    }
    if !is_loopback_base_url(&announcement.base_url) {
        return Err("readonly sidecar base_url must be loopback HTTP".to_string());
    }
    if announcement.run_id.trim().is_empty() {
        return Err("readonly sidecar run_id is required".to_string());
    }
    if announcement.readonly_token.trim().len() < MINIMUM_READONLY_TOKEN_LENGTH {
        return Err("readonly sidecar token is missing or too short".to_string());
    }
    Ok(ReadonlySidecarLaunch {
        base_url: announcement.base_url,
        run_id: announcement.run_id,
        read_only: true,
        readonly_token: announcement.readonly_token,
        process_id,
    })
}

fn is_loopback_base_url(value: &str) -> bool {
    let Some(authority) = value.strip_prefix("http://") else {
        return false;
    };
    if authority.contains('@') {
        return false;
    }
    let Some((host, port)) = split_host_port(authority) else {
        return false;
    };
    (host == "127.0.0.1" || host == "localhost" || host == "[::1]")
        && !port.is_empty()
        && port.chars().all(|item| item.is_ascii_digit())
}

fn split_host_port(authority: &str) -> Option<(&str, &str)> {
    if authority.starts_with("[::1]:") {
        return Some(("[::1]", &authority[6..]));
    }
    authority.split_once(':')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_private_readonly_sidecar_startup_json() {
        let launch = parse_startup_announcement(
            r#"{"base_url":"http://127.0.0.1:49152","run_id":"run-1","read_only":true,"readonly_token":"0123456789abcdef","output_dir":"C:\\run"}"#,
            42,
        )
        .expect("startup JSON should parse");

        assert_eq!(launch.base_url, "http://127.0.0.1:49152");
        assert_eq!(launch.run_id, "run-1");
        assert_eq!(launch.readonly_token, "0123456789abcdef");
        assert_eq!(launch.process_id, 42);
        assert!(launch.read_only);
    }

    #[test]
    fn rejects_non_loopback_or_missing_token_startup_json() {
        for line in [
            r#"{"base_url":"http://0.0.0.0:49152","run_id":"run-1","read_only":true,"readonly_token":"0123456789abcdef"}"#,
            r#"{"base_url":"http://127.0.0.1:49152","run_id":"run-1","read_only":false,"readonly_token":"0123456789abcdef"}"#,
            r#"{"base_url":"http://127.0.0.1:49152","run_id":"run-1","read_only":true,"readonly_token":"short"}"#,
            r#"{"base_url":"http://127.0.0.1:49152","run_id":"","read_only":true,"readonly_token":"0123456789abcdef"}"#,
        ] {
            assert!(parse_startup_announcement(line, 42).is_err());
        }
    }

    #[test]
    fn validates_loopback_base_url_without_userinfo_or_paths() {
        for value in [
            "http://127.0.0.1:49152",
            "http://localhost:49152",
            "http://[::1]:49152",
        ] {
            assert!(is_loopback_base_url(value));
        }
        for value in [
            "https://127.0.0.1:49152",
            "http://user:pass@127.0.0.1:49152",
            "http://127.0.0.1",
            "http://127.0.0.1:49152/path",
            "http://0.0.0.0:49152",
        ] {
            assert!(!is_loopback_base_url(value));
        }
    }

    #[test]
    fn resolves_spiroctl_path_without_logging_or_requiring_secret_state() {
        assert!(!resolve_spiroctl_path().trim().is_empty());
    }
}
