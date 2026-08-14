// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, HashSet},
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdout, Command, Output, Stdio},
    sync::{mpsc, Mutex},
    time::{Duration, Instant},
};
use tauri::Manager;

const DEFAULT_READONLY_SIDECAR_ADDR: &str = "127.0.0.1:0";
const READONLY_SIDECAR_HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(10);
const CONFIG_COMMAND_RUNTIME_TIMEOUT: Duration = Duration::from_secs(120);
const WORKFLOW_TASK_EXECUTION_TIMEOUT: Duration = Duration::from_secs(600);
const MINIMUM_READONLY_TOKEN_LENGTH: usize = 16;
const OPERATOR_TASK_EXECUTION_REQUEST_SCHEMA_VERSION: &str =
    "v35.operator_task_execution_request.v1";
const OPERATOR_TASK_EXECUTION_SCHEMA_VERSION: &str = "v35.operator_task_execution.v1";
const OPERATOR_TASK_RESTORE_SCHEMA_VERSION: &str = "v35.operator_task_restore.v1";
const OPERATOR_TASK_RESTORE_READ_SCOPE: &str = "operator_task_snapshots_readonly";
const DEFAULT_OPERATOR_TASK_LEDGER_PATH: &str =
    "data/lib/operator_tasks/operator-task-ledger.jsonl";
const NOMAD_EXECUTION_TARGET_PREFIX: &str = "data/lib/nomad_perla_psc/snapshots/run-";

#[derive(Default)]
struct ReadonlySidecarProcesses {
    children_by_output_dir: Mutex<HashMap<PathBuf, Child>>,
}

#[derive(Default)]
struct WorkflowTaskExecutionState {
    running_task_ids: Mutex<HashSet<String>>,
}

struct WorkflowTaskExecutionGuard<'a> {
    task_id: String,
    state: &'a WorkflowTaskExecutionState,
}

impl Drop for WorkflowTaskExecutionGuard<'_> {
    fn drop(&mut self) {
        if let Ok(mut running) = self.state.running_task_ids.lock() {
            running.remove(&self.task_id);
        }
    }
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

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct WorkflowTaskExecutionRequest {
    schema_version: String,
    task_id: String,
    ledger_path: String,
    target_data_library_path: String,
    authorize_live_provider_calls: bool,
    execution_contract: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct WorkflowTaskExecutionReport {
    schema_version: String,
    task_id: String,
    action_type: String,
    provider: String,
    admission_hash: String,
    execution_status: String,
    write_authorization_scope: String,
    live_calls_authorized: bool,
    provider_cache_written: bool,
    local_backend_written: bool,
    scoring_written: bool,
    experiment_written: bool,
    started_at: String,
    target_data_library_path: String,
    source_manifest_path: String,
    normalized_record_count: u64,
    provider_response_hash: String,
    raw_search_hash: String,
    raw_archive_hash: String,
    archive_status: String,
    review_required: bool,
    review_reasons: Vec<String>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct WorkflowTaskRestoreReport {
    schema_version: String,
    read_authorization_scope: String,
    provider_cache_written: bool,
    local_backend_written: bool,
    scoring_written: bool,
    experiment_written: bool,
    restored_tasks: Vec<RestoredWorkflowTask>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct RestoredWorkflowTask {
    schema_version: String,
    task_id: String,
    action_type: String,
    provider: String,
    provider_scope: String,
    status: String,
    queue_scope: String,
    declared_effects: Vec<String>,
    writes_authorized: bool,
    execution_started: bool,
    created_at: Option<String>,
    config: serde_json::Map<String, serde_json::Value>,
    admission_status: String,
    admission_hash: String,
    ledger_path: String,
    admission_source: String,
    execution_report: WorkflowTaskExecutionReport,
}

#[tauri::command]
fn start_readonly_sidecar(
    app: tauri::AppHandle,
    state: tauri::State<'_, ReadonlySidecarProcesses>,
    output_dir: String,
) -> Result<ReadonlySidecarLaunch, String> {
    let output_dir = canonical_output_dir(&output_dir)?;
    stop_existing_sidecar_for_output_dir(&state, &output_dir)?;
    let executable = resolve_spiroctl_path(&app);
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

#[tauri::command]
fn submit_config_command(request: serde_json::Value) -> Result<serde_json::Value, String> {
    validate_config_command_request(&request)?;
    let repo_root = resolve_repository_root()?;
    let python = resolve_python_path(&repo_root);
    run_config_command_runtime(python, repo_root, request)
}

#[tauri::command]
fn execute_workflow_task(
    app: tauri::AppHandle,
    state: tauri::State<'_, WorkflowTaskExecutionState>,
    request: serde_json::Value,
) -> Result<WorkflowTaskExecutionReport, String> {
    let request = validate_workflow_task_execution_request(request)?;
    let _guard = acquire_workflow_task_execution_guard(state.inner(), &request.task_id)?;
    let repo_root = resolve_repository_root()?;
    let executable = resolve_workflow_execution_spiroctl_path(&app)?;
    run_workflow_task_execution(executable, repo_root, request)
}

#[tauri::command]
fn restore_workflow_tasks(app: tauri::AppHandle) -> Result<WorkflowTaskRestoreReport, String> {
    let repo_root = resolve_repository_root()?;
    let executable = resolve_spiroctl_path(&app);
    run_workflow_task_restore(executable, repo_root)
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
        child.kill().ok();
        let _ = child.wait();
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(ReadonlySidecarProcesses::default())
        .manage(WorkflowTaskExecutionState::default())
        .invoke_handler(tauri::generate_handler![
            start_readonly_sidecar,
            stop_readonly_sidecar,
            submit_config_command,
            execute_workflow_task,
            restore_workflow_tasks
        ])
        .run(tauri::generate_context!())
        .expect("error while running AtomReasonX application");
}

fn validate_config_command_request(request: &serde_json::Value) -> Result<(), String> {
    if !request.is_object() {
        return Err("config command request must be an object".to_string());
    }
    let schema_version = request
        .get("schema_version")
        .and_then(|value| value.as_str())
        .unwrap_or_default();
    if schema_version != "v23.action_request.v1" {
        return Err("config command request schema_version is not supported".to_string());
    }
    let action_type = request
        .get("action_type")
        .and_then(|value| value.as_str())
        .unwrap_or_default();
    if !is_config_command_action(action_type) {
        return Err("config command action_type is not supported by this bridge".to_string());
    }
    Ok(())
}

fn is_config_command_action(action_type: &str) -> bool {
    matches!(
        action_type,
        "config_write" | "key_rotate" | "key_remove" | "test_connection" | "model_list_refresh" | "chat_completion"
    )
}

fn run_config_command_runtime(
    python: PathBuf,
    repo_root: PathBuf,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let request_json = serde_json::to_vec(&request)
        .map_err(|error| format!("failed to serialize config command request: {error}"))?;
    let mut child = Command::new(python)
        .args(["-m", "spirosearch.config_command_runtime"])
        .current_dir(&repo_root)
        .env("SPIROSEARCH_REPOSITORY_ROOT", &repo_root)
        .env("PYTHONPATH", pythonpath_with_repo_src(&repo_root))
        .env_remove("SPIROSEARCH_CONFIG_ROOT")
        .env_remove("MATERIALS_PROJECT_API_KEY")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("failed to start config command runtime: {error}"))?;
    {
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| "config command runtime stdin was not captured".to_string())?;
        stdin
            .write_all(&request_json)
            .map_err(|error| format!("failed to write config command request: {error}"))?;
    }
    let output = wait_for_config_command_output(child)?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if !output.status.success() {
        return Err(format!(
            "config command runtime failed with exit code {}",
            output
                .status
                .code()
                .map(|value| value.to_string())
                .unwrap_or_else(|| "unknown".to_string())
        ));
    }
    serde_json::from_str(&stdout)
        .map_err(|error| format!("config command runtime returned invalid JSON: {error}"))
}

fn validate_workflow_task_execution_request(
    request: serde_json::Value,
) -> Result<WorkflowTaskExecutionRequest, String> {
    if contains_forbidden_credential_fragment(&request) {
        return Err("workflow task execution request contains credential-shaped input".to_string());
    }
    let parsed: WorkflowTaskExecutionRequest = serde_json::from_value(request)
        .map_err(|error| format!("workflow task execution request is invalid: {error}"))?;
    if parsed.schema_version != OPERATOR_TASK_EXECUTION_REQUEST_SCHEMA_VERSION {
        return Err("workflow task execution request schema_version is not supported".to_string());
    }
    if !safe_nomad_task_id(&parsed.task_id) {
        return Err("workflow task execution request task_id is unsafe".to_string());
    }
    if parsed.ledger_path != DEFAULT_OPERATOR_TASK_LEDGER_PATH {
        return Err("workflow task execution ledger path is not supported".to_string());
    }
    let expected_target = format!("{}{}", NOMAD_EXECUTION_TARGET_PREFIX, parsed.task_id);
    if parsed.target_data_library_path != expected_target {
        return Err("workflow task execution target path is not supported".to_string());
    }
    if !parsed.authorize_live_provider_calls {
        return Err(
            "workflow task execution requires explicit live-call authorization".to_string(),
        );
    }
    if parsed.execution_contract != OPERATOR_TASK_EXECUTION_SCHEMA_VERSION {
        return Err("workflow task execution contract is not supported".to_string());
    }
    Ok(parsed)
}

fn run_workflow_task_execution(
    executable: PathBuf,
    repo_root: PathBuf,
    request: WorkflowTaskExecutionRequest,
) -> Result<WorkflowTaskExecutionReport, String> {
    let mut command = Command::new(executable);
    command
        .args([
            "workflow-task",
            "execute",
            "--task-id",
            &request.task_id,
            "--ledger",
            &request.ledger_path,
            "--authorize-live-provider-calls",
            "--target",
            &request.target_data_library_path,
        ])
        .current_dir(&repo_root)
        .env("SPIROSEARCH_REPOSITORY_ROOT", &repo_root)
        .env_remove("SPIROSEARCH_CONFIG_ROOT")
        .env_remove("MATERIALS_PROJECT_API_KEY")
        .env_remove("SPIROCTL_PATH")
        .env_remove("SPIROSEARCH_PYTHON")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    remove_credential_shaped_env(&mut command);
    let child = command
        .spawn()
        .map_err(|error| format!("failed to start workflow task execution: {error}"))?;
    let output = wait_for_child_output(
        child,
        WORKFLOW_TASK_EXECUTION_TIMEOUT,
        "workflow task execution",
    )?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if !output.status.success() {
        return Err(format!(
            "workflow task execution failed with exit code {}",
            output
                .status
                .code()
                .map(|value| value.to_string())
                .unwrap_or_else(|| "unknown".to_string())
        ));
    }
    let report: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|error| format!("workflow task execution returned invalid JSON: {error}"))?;
    validate_workflow_task_execution_report(report, &request)
}

fn run_workflow_task_restore(
    executable: PathBuf,
    repo_root: PathBuf,
) -> Result<WorkflowTaskRestoreReport, String> {
    let mut command = Command::new(executable);
    command
        .args([
            "workflow-task",
            "restore",
            "--ledger",
            DEFAULT_OPERATOR_TASK_LEDGER_PATH,
        ])
        .current_dir(&repo_root)
        .env("SPIROSEARCH_REPOSITORY_ROOT", &repo_root)
        .env_remove("SPIROSEARCH_CONFIG_ROOT")
        .env_remove("MATERIALS_PROJECT_API_KEY")
        .env_remove("SPIROSEARCH_PYTHON")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    remove_credential_shaped_env(&mut command);
    let child = command
        .spawn()
        .map_err(|error| format!("failed to start workflow task restore: {error}"))?;
    let output = wait_for_child_output(
        child,
        CONFIG_COMMAND_RUNTIME_TIMEOUT,
        "workflow task restore",
    )?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if !output.status.success() {
        return Err(format!(
            "workflow task restore failed with exit code {}",
            output
                .status
                .code()
                .map(|value| value.to_string())
                .unwrap_or_else(|| "unknown".to_string())
        ));
    }
    let report: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|error| format!("workflow task restore returned invalid JSON: {error}"))?;
    validate_workflow_task_restore_report(report)
}

fn validate_workflow_task_execution_report(
    report: serde_json::Value,
    request: &WorkflowTaskExecutionRequest,
) -> Result<WorkflowTaskExecutionReport, String> {
    if contains_forbidden_credential_fragment(&report) {
        return Err("workflow task execution report contains credential-shaped output".to_string());
    }
    let report: WorkflowTaskExecutionReport = serde_json::from_value(report)
        .map_err(|error| format!("workflow task execution report is invalid: {error}"))?;
    if report.schema_version != OPERATOR_TASK_EXECUTION_SCHEMA_VERSION {
        return Err("workflow task execution report schema_version is not supported".to_string());
    }
    if report.task_id != request.task_id
        || report.action_type != "start_nomad_sync"
        || report.provider != "nomad_perla_psc"
        || report.execution_status != "source_snapshot_written"
        || report.write_authorization_scope != "source_snapshot_only"
    {
        return Err(
            "workflow task execution report does not match the requested NOMAD task".to_string(),
        );
    }
    if report.target_data_library_path != request.target_data_library_path {
        return Err("workflow task execution report target does not match request".to_string());
    }
    let expected_manifest = format!("{}/source-manifest.json", request.target_data_library_path);
    if report.source_manifest_path != expected_manifest {
        return Err(
            "workflow task execution report manifest path does not match target".to_string(),
        );
    }
    if report.provider_cache_written
        || report.local_backend_written
        || report.scoring_written
        || report.experiment_written
    {
        return Err("workflow task execution report writer flags must be false".to_string());
    }
    if !report.live_calls_authorized {
        return Err(
            "workflow task execution report live_calls_authorized must be true".to_string(),
        );
    }
    for value in [
        &report.admission_hash,
        &report.provider_response_hash,
        &report.raw_search_hash,
        &report.raw_archive_hash,
    ] {
        if !is_sha256_hex(value) {
            return Err("workflow task execution report hash field is invalid".to_string());
        }
    }
    if !safe_nomad_target_path(&report.target_data_library_path)
        || report.started_at.trim().is_empty()
        || !is_archive_status(&report.archive_status)
        || report
            .review_reasons
            .iter()
            .any(|item| item.trim().is_empty())
    {
        return Err("workflow task execution report field value is invalid".to_string());
    }
    Ok(report)
}

fn validate_workflow_task_restore_report(
    report: serde_json::Value,
) -> Result<WorkflowTaskRestoreReport, String> {
    if contains_forbidden_credential_fragment(&report) {
        return Err("workflow task restore report contains credential-shaped output".to_string());
    }
    let report: WorkflowTaskRestoreReport = serde_json::from_value(report)
        .map_err(|error| format!("workflow task restore report is invalid: {error}"))?;
    if report.schema_version != OPERATOR_TASK_RESTORE_SCHEMA_VERSION
        || report.read_authorization_scope != OPERATOR_TASK_RESTORE_READ_SCOPE
        || report.provider_cache_written
        || report.local_backend_written
        || report.scoring_written
        || report.experiment_written
    {
        return Err("workflow task restore report metadata is invalid".to_string());
    }
    for task in &report.restored_tasks {
        validate_restored_workflow_task(task)?;
    }
    Ok(report)
}

fn validate_restored_workflow_task(task: &RestoredWorkflowTask) -> Result<(), String> {
    if task.schema_version != "v35.operator_task.v1"
        || !safe_nomad_task_id(&task.task_id)
        || task.action_type != "start_nomad_sync"
        || task.provider != "nomad_perla_psc"
        || task.provider_scope != "source"
        || task.status != "queued"
        || task.queue_scope != "operator_local"
        || task.declared_effects.as_slice() != ["provider_sync_jobs"]
        || task.writes_authorized
        || task.execution_started
        || task.created_at.is_some()
        || task.config.get("transport").and_then(|value| value.as_str())
            != Some("operator_task_queue")
        || task.config.get("runtime_writes").and_then(|value| value.as_bool()) != Some(false)
        || task.config.get("config_source").and_then(|value| value.as_str())
            != Some("workflow_command_allowlist")
        || task.admission_status != "admitted"
        || !is_sha256_hex(&task.admission_hash)
        || task.ledger_path != DEFAULT_OPERATOR_TASK_LEDGER_PATH
        || task.admission_source != "operator_task_ledger"
        || task.execution_report.task_id != task.task_id
        || task.execution_report.admission_hash != task.admission_hash
    {
        return Err("restored workflow task metadata is invalid".to_string());
    }
    let request = WorkflowTaskExecutionRequest {
        schema_version: OPERATOR_TASK_EXECUTION_REQUEST_SCHEMA_VERSION.to_string(),
        task_id: task.task_id.clone(),
        ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH.to_string(),
        target_data_library_path: format!("{}{}", NOMAD_EXECUTION_TARGET_PREFIX, task.task_id),
        authorize_live_provider_calls: true,
        execution_contract: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION.to_string(),
    };
    let report_value = serde_json::to_value(&task.execution_report)
        .map_err(|error| format!("failed to revalidate restored execution report: {error}"))?;
    validate_workflow_task_execution_report(report_value, &request)?;
    Ok(())
}

fn wait_for_config_command_output(child: Child) -> Result<Output, String> {
    wait_for_child_output(
        child,
        CONFIG_COMMAND_RUNTIME_TIMEOUT,
        "config command runtime",
    )
}

fn wait_for_child_output(
    mut child: Child,
    timeout: Duration,
    process_name: &str,
) -> Result<Output, String> {
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => {
                return child
                    .wait_with_output()
                    .map_err(|error| format!("failed to collect {process_name} output: {error}"));
            }
            Ok(None) => {
                if started.elapsed() >= timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err(format!("{process_name} timed out"));
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(error) => {
                return Err(format!("failed to poll {process_name}: {error}"));
            }
        }
    }
}

fn safe_nomad_task_id(value: &str) -> bool {
    let Some(suffix) = value.strip_prefix("task-start_nomad_sync-") else {
        return false;
    };
    !suffix.is_empty()
        && suffix.len() <= 16
        && suffix != "api_key"
        && suffix
            .chars()
            .all(|item| item.is_ascii_lowercase() || item.is_ascii_digit())
}

fn safe_nomad_target_path(value: &str) -> bool {
    value.starts_with(NOMAD_EXECUTION_TARGET_PREFIX)
        && !value.contains('\\')
        && !value.contains(':')
        && !value.contains("//")
        && !value.contains("/../")
        && !value.ends_with("/..")
}

fn is_archive_status(value: &str) -> bool {
    matches!(
        value,
        "available"
            | "empty"
            | "unavailable"
            | "rate_limited"
            | "schema_unrecognized"
            | "not_requested"
    )
}

fn is_sha256_hex(value: &str) -> bool {
    value.len() == 64
        && value
            .chars()
            .all(|item| item.is_ascii_digit() || ('a'..='f').contains(&item))
}

fn acquire_workflow_task_execution_guard<'a>(
    state: &'a WorkflowTaskExecutionState,
    task_id: &str,
) -> Result<WorkflowTaskExecutionGuard<'a>, String> {
    let mut running = state
        .running_task_ids
        .lock()
        .map_err(|_| "workflow task execution state is poisoned".to_string())?;
    if !running.insert(task_id.to_string()) {
        return Err("workflow task execution is already in progress".to_string());
    }
    Ok(WorkflowTaskExecutionGuard {
        task_id: task_id.to_string(),
        state,
    })
}

fn remove_credential_shaped_env(command: &mut Command) {
    for (key, _) in std::env::vars() {
        let lower = key.to_ascii_lowercase();
        if lower.contains("api_key")
            || lower.contains("token")
            || lower.contains("secret")
            || lower.contains("credential")
            || lower == "authorization"
        {
            command.env_remove(key);
        }
    }
}

fn contains_forbidden_credential_fragment(value: &serde_json::Value) -> bool {
    let blob = value.to_string();
    let lower = blob.to_ascii_lowercase();
    [
        "api_key",
        "readonly_token",
        "bearer ",
        "mp-secret",
        "spiroctl_path",
        "spiroctl.exe",
    ]
    .iter()
    .any(|item| lower.contains(item))
}

fn pythonpath_with_repo_src(repo_root: &PathBuf) -> String {
    let src = repo_root.join("src").to_string_lossy().to_string();
    match std::env::var("PYTHONPATH") {
        Ok(existing) if !existing.trim().is_empty() => {
            format!("{}{}{}", src, env_path_separator(), existing)
        }
        _ => src,
    }
}

fn env_path_separator() -> &'static str {
    if cfg!(target_os = "windows") {
        ";"
    } else {
        ":"
    }
}

fn resolve_python_path(repo_root: &PathBuf) -> PathBuf {
    if let Ok(value) = std::env::var("SPIROSEARCH_PYTHON") {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    let venv_python = if cfg!(target_os = "windows") {
        repo_root.join(".venv").join("Scripts").join("python.exe")
    } else {
        repo_root.join(".venv").join("bin").join("python")
    };
    if venv_python.is_file() {
        return venv_python;
    }
    PathBuf::from("python")
}

fn resolve_repository_root() -> Result<PathBuf, String> {
    if let Ok(value) = std::env::var("SPIROSEARCH_REPOSITORY_ROOT") {
        let candidate = PathBuf::from(value.trim());
        if validate_repository_root(&candidate) {
            return Ok(candidate);
        }
    }
    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        let mut candidate = PathBuf::from(manifest_dir);
        for _ in 0..3 {
            if let Some(parent) = candidate.parent() {
                candidate = parent.to_path_buf();
            }
        }
        if validate_repository_root(&candidate) {
            return Ok(candidate);
        }
    }
    if let Ok(current_dir) = std::env::current_dir() {
        for candidate in current_dir.ancestors() {
            let candidate = candidate.to_path_buf();
            if validate_repository_root(&candidate) {
                return Ok(candidate);
            }
        }
    }
    Err("unable to resolve SpiroSearch repository root for config command runtime".to_string())
}

fn validate_repository_root(candidate: &PathBuf) -> bool {
    candidate
        .join("data")
        .join("source_registry.json")
        .is_file()
        && candidate.join("src").join("spirosearch").is_dir()
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

fn resolve_spiroctl_path(app: &tauri::AppHandle) -> PathBuf {
    if let Some(path) = resolve_spiroctl_env_override() {
        return path;
    }
    resolve_bundled_spiroctl_path(app).unwrap_or_else(|| PathBuf::from("spiroctl"))
}

fn resolve_workflow_execution_spiroctl_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        if let Some(path) = resolve_spiroctl_env_override() {
            return Ok(path);
        }
    }
    resolve_bundled_spiroctl_path(app)
        .ok_or_else(|| "workflow task execution requires bundled spiroctl".to_string())
}

fn resolve_spiroctl_env_override() -> Option<PathBuf> {
    std::env::var("SPIROCTL_PATH")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
}

fn resolve_bundled_spiroctl_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    let artifact_name = bundled_spiroctl_artifact_name();
    let mut candidates = Vec::new();

    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join("binaries").join(&artifact_name));
        candidates.push(resource_dir.join(&artifact_name));
    }
    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            candidates.push(exe_dir.join("binaries").join(&artifact_name));
            candidates.push(exe_dir.join(&artifact_name));
        }
    }
    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        candidates.push(
            PathBuf::from(manifest_dir)
                .join("binaries")
                .join(&artifact_name),
        );
    }

    candidates.into_iter().find(|path| path.is_file())
}

fn bundled_spiroctl_artifact_name() -> String {
    let extension = if cfg!(target_os = "windows") {
        ".exe"
    } else {
        ""
    };
    format!("spiroctl-{}{}", bundled_spiroctl_target_triple(), extension)
}

fn bundled_spiroctl_target_triple() -> &'static str {
    if cfg!(all(
        target_os = "windows",
        target_arch = "x86_64",
        target_env = "gnu"
    )) {
        "x86_64-pc-windows-gnu"
    } else if cfg!(all(target_os = "windows", target_arch = "x86_64")) {
        "x86_64-pc-windows-msvc"
    } else if cfg!(all(target_os = "windows", target_arch = "aarch64")) {
        "aarch64-pc-windows-msvc"
    } else if cfg!(all(target_os = "windows", target_arch = "x86")) {
        "i686-pc-windows-msvc"
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        "x86_64-apple-darwin"
    } else if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        "aarch64-apple-darwin"
    } else if cfg!(all(
        target_os = "linux",
        target_arch = "x86_64",
        target_env = "musl"
    )) {
        "x86_64-unknown-linux-musl"
    } else if cfg!(all(target_os = "linux", target_arch = "x86_64")) {
        "x86_64-unknown-linux-gnu"
    } else if cfg!(all(
        target_os = "linux",
        target_arch = "aarch64",
        target_env = "musl"
    )) {
        "aarch64-unknown-linux-musl"
    } else if cfg!(all(target_os = "linux", target_arch = "aarch64")) {
        "aarch64-unknown-linux-gnu"
    } else if cfg!(all(target_os = "linux", target_arch = "arm")) {
        "armv7-unknown-linux-gnueabihf"
    } else {
        "unsupported-target"
    }
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
    fn bundled_spiroctl_artifact_name_matches_external_bin_policy() {
        let artifact_name = bundled_spiroctl_artifact_name();
        assert!(artifact_name.starts_with("spiroctl-"));
        assert!(!artifact_name.contains("SPIROCTL_PATH"));
        assert!(!artifact_name.contains("readonly_token"));
        if cfg!(target_os = "windows") {
            assert!(artifact_name.ends_with(".exe"));
        } else {
            assert!(!artifact_name.ends_with(".exe"));
        }
    }

    #[test]
    fn config_command_bridge_accepts_only_config_plane_actions() {
        for action_type in [
            "config_write",
            "key_rotate",
            "key_remove",
            "test_connection",
            "model_list_refresh",
        ] {
            assert!(is_config_command_action(action_type));
        }
        for action_type in [
            "start_nomad_sync",
            "provider_execution",
            "readonly-run",
            "import_pubchemqc_snapshot",
        ] {
            assert!(!is_config_command_action(action_type));
        }
    }

    #[test]
    fn validates_fixed_workflow_task_execution_request() {
        let request = serde_json::json!({
            "schema_version": "v35.operator_task_execution_request.v1",
            "task_id": "task-start_nomad_sync-ab12cd",
            "ledger_path": "data/lib/operator_tasks/operator-task-ledger.jsonl",
            "target_data_library_path": "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd",
            "authorize_live_provider_calls": true,
            "execution_contract": "v35.operator_task_execution.v1"
        });

        let parsed = validate_workflow_task_execution_request(request)
            .expect("fixed request should validate");

        assert_eq!(parsed.task_id, "task-start_nomad_sync-ab12cd");
        assert!(parsed.authorize_live_provider_calls);
    }

    #[test]
    fn rejects_mutable_or_secret_shaped_workflow_task_execution_request() {
        let base = fixed_workflow_task_execution_request_json();
        let mut cases = Vec::new();
        cases.push({
            let mut value = base.clone();
            value["ledger_path"] =
                serde_json::json!("data/lib/provider_cache/operator-task-ledger.jsonl");
            value
        });
        cases.push({
            let mut value = base.clone();
            value["target_data_library_path"] =
                serde_json::json!("data/lib/nomad_perla_psc/snapshots/../escape");
            value
        });
        cases.push({
            let mut value = base.clone();
            value["authorize_live_provider_calls"] = serde_json::json!(false);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["task_id"] = serde_json::json!("task-start_nomad_sync-api_key");
            value
        });
        cases.push({
            let mut value = base.clone();
            value["api_key"] = serde_json::json!("mp-secret");
            value
        });

        for case in cases {
            assert!(validate_workflow_task_execution_request(case).is_err());
        }
    }

    #[test]
    fn validates_fixed_workflow_task_execution_report() {
        let request = fixed_workflow_task_execution_request();
        let report = validate_workflow_task_execution_report(
            fixed_workflow_task_execution_report_json(),
            &request,
        )
        .expect("fixed report should validate");

        assert_eq!(report.schema_version, "v35.operator_task_execution.v1");
        assert_eq!(report.task_id, "task-start_nomad_sync-ab12cd");
        assert_eq!(report.provider, "nomad_perla_psc");
        assert_eq!(report.execution_status, "source_snapshot_written");
        assert_eq!(report.write_authorization_scope, "source_snapshot_only");
        assert!(report.live_calls_authorized);
        assert!(!report.provider_cache_written);
        assert!(!report.local_backend_written);
        assert!(!report.scoring_written);
        assert!(!report.experiment_written);
        assert_eq!(report.normalized_record_count, 1);
    }

    #[test]
    fn validates_fixed_workflow_task_restore_report() {
        let report = validate_workflow_task_restore_report(fixed_workflow_task_restore_report_json())
            .expect("restore report should validate");

        assert_eq!(report.schema_version, "v35.operator_task_restore.v1");
        assert_eq!(
            report.read_authorization_scope,
            "operator_task_snapshots_readonly"
        );
        assert_eq!(report.restored_tasks.len(), 1);
        assert_eq!(
            report.restored_tasks[0].execution_report.source_manifest_path,
            "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd/source-manifest.json"
        );
        assert!(!report.provider_cache_written);
        assert!(!report.local_backend_written);
        assert!(!report.scoring_written);
        assert!(!report.experiment_written);
    }

    #[test]
    fn rejects_workflow_task_restore_report_schema_drift() {
        let base = fixed_workflow_task_restore_report_json();
        let mut cases = Vec::new();
        cases.push({
            let mut value = base.clone();
            value["extra"] = serde_json::json!(true);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["provider_cache_written"] = serde_json::json!(true);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["restored_tasks"][0]["execution_report"]["admission_hash"] =
                serde_json::json!("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee");
            value
        });

        for case in cases {
            assert!(validate_workflow_task_restore_report(case).is_err());
        }
    }

    #[test]
    fn rejects_workflow_task_execution_report_writer_flags() {
        let request = fixed_workflow_task_execution_request();
        let mut report = fixed_workflow_task_execution_report_json();
        report["provider_cache_written"] = serde_json::json!(true);

        assert!(validate_workflow_task_execution_report(report, &request).is_err());
    }

    #[test]
    fn rejects_workflow_task_execution_report_schema_drift() {
        let request = fixed_workflow_task_execution_request();
        let base = fixed_workflow_task_execution_report_json();
        let mut cases = Vec::new();
        cases.push({
            let mut value = base.clone();
            value["extra"] = serde_json::json!(true);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["archive_status"] = serde_json::json!("accepted");
            value
        });
        cases.push({
            let mut value = base.clone();
            value["normalized_record_count"] = serde_json::json!(-1);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["review_reasons"] = serde_json::json!([123]);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["review_reasons"] = serde_json::json!([""]);
            value
        });
        cases.push({
            let mut value = base.clone();
            value["provider_response_hash"] = serde_json::json!(
                "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
            );
            value
        });
        cases.push({
            let mut value = base.clone();
            value["source_manifest_path"] = serde_json::json!(
                "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd/../source-manifest.json"
            );
            value
        });

        for case in cases {
            assert!(validate_workflow_task_execution_report(case, &request).is_err());
        }
    }

    #[test]
    fn workflow_task_execution_guard_rejects_same_task_reentry() {
        let state = WorkflowTaskExecutionState::default();
        let first = acquire_workflow_task_execution_guard(&state, "task-start_nomad_sync-ab12cd")
            .expect("first guard should be acquired");

        assert!(
            acquire_workflow_task_execution_guard(&state, "task-start_nomad_sync-ab12cd").is_err()
        );
        assert!(
            acquire_workflow_task_execution_guard(&state, "task-start_nomad_sync-ef34gh").is_ok()
        );

        drop(first);
        assert!(
            acquire_workflow_task_execution_guard(&state, "task-start_nomad_sync-ab12cd").is_ok()
        );
    }

    fn fixed_workflow_task_execution_request() -> WorkflowTaskExecutionRequest {
        validate_workflow_task_execution_request(fixed_workflow_task_execution_request_json())
            .expect("request should validate")
    }

    fn fixed_workflow_task_execution_request_json() -> serde_json::Value {
        serde_json::json!({
            "schema_version": "v35.operator_task_execution_request.v1",
            "task_id": "task-start_nomad_sync-ab12cd",
            "ledger_path": "data/lib/operator_tasks/operator-task-ledger.jsonl",
            "target_data_library_path": "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd",
            "authorize_live_provider_calls": true,
            "execution_contract": "v35.operator_task_execution.v1"
        })
    }

    fn fixed_workflow_task_execution_report_json() -> serde_json::Value {
        serde_json::json!({
            "schema_version": "v35.operator_task_execution.v1",
            "task_id": "task-start_nomad_sync-ab12cd",
            "action_type": "start_nomad_sync",
            "provider": "nomad_perla_psc",
            "admission_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "execution_status": "source_snapshot_written",
            "write_authorization_scope": "source_snapshot_only",
            "live_calls_authorized": true,
            "provider_cache_written": false,
            "local_backend_written": false,
            "scoring_written": false,
            "experiment_written": false,
            "started_at": "2026-07-24T00:00:00Z",
            "target_data_library_path": "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd",
            "source_manifest_path": "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd/source-manifest.json",
            "normalized_record_count": 1,
            "provider_response_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "raw_search_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "raw_archive_hash": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "archive_status": "available",
            "review_required": false,
            "review_reasons": []
        })
    }

    fn fixed_workflow_task_restore_report_json() -> serde_json::Value {
        serde_json::json!({
            "schema_version": "v35.operator_task_restore.v1",
            "read_authorization_scope": "operator_task_snapshots_readonly",
            "provider_cache_written": false,
            "local_backend_written": false,
            "scoring_written": false,
            "experiment_written": false,
            "restored_tasks": [{
                "schema_version": "v35.operator_task.v1",
                "task_id": "task-start_nomad_sync-ab12cd",
                "action_type": "start_nomad_sync",
                "provider": "nomad_perla_psc",
                "provider_scope": "source",
                "status": "queued",
                "queue_scope": "operator_local",
                "declared_effects": ["provider_sync_jobs"],
                "writes_authorized": false,
                "execution_started": false,
                "created_at": null,
                "config": {
                    "transport": "operator_task_queue",
                    "runtime_writes": false,
                    "config_source": "workflow_command_allowlist"
                },
                "admission_status": "admitted",
                "admission_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "ledger_path": "data/lib/operator_tasks/operator-task-ledger.jsonl",
                "admission_source": "operator_task_ledger",
                "execution_report": fixed_workflow_task_execution_report_json()
            }]
        })
    }
}
