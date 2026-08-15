//! AtomReasonX desktop settings persistence.
//!
//! Persists the desktop settings payload (the Reasonix-style `SettingsView`
//! subset used by the settings centre) in a single JSON file under the Tauri
//! app data directory. The on-disk shape mirrors the desktop-config convention
//! of the Reasonix desktop app (https://github.com/esengine/DeepSeek-Reasonix,
//! MIT): the stored values object is the UI settings object, wrapped with a
//! schema version so future migrations can be keyed off it.
//!
//! Storage is intentionally small and synchronous: settings writes are rare
//! user actions, not hot-path calls. Writes are atomic (temp file + rename)
//! and guarded by a size cap; a corrupt or unreadable file falls back to
//! defaults instead of blocking the settings centre.

use serde_json::{Map, Value};
use std::fs;
use std::io::Write;
use std::path::Path;

pub const SETTINGS_FILE_NAME: &str = "atomreasonx-settings.json";
pub const SETTINGS_SCHEMA_VERSION: &str = "v1.atomreasonx_desktop_settings.v1";
pub const MAX_SETTINGS_FILE_BYTES: u64 = 1_048_576; // 1 MiB safety cap

#[derive(Debug, Clone, PartialEq)]
pub struct StoredSettings {
    pub schema_version: String,
    pub values: Map<String, Value>,
}

impl StoredSettings {
    pub fn defaults() -> Self {
        StoredSettings {
            schema_version: SETTINGS_SCHEMA_VERSION.to_string(),
            values: Map::new(),
        }
    }
}

/// Returns the settings file path inside `dir`.
pub fn settings_file_path(dir: &Path) -> std::path::PathBuf {
    dir.join(SETTINGS_FILE_NAME)
}

/// Loads settings from `path`.
///
/// - Missing file: returns defaults (first launch).
/// - Unreadable / invalid JSON / wrong top-level shape: returns defaults with
///   `recovered` true so callers can surface a "reset to defaults" note.
/// - Schema version newer than this build: values are still returned so a
///   downgraded build does not destroy data it does not understand.
pub fn load_settings(path: &Path) -> (StoredSettings, bool) {
    match read_settings_file(path) {
        Ok(raw) => parse_settings_document(&raw),
        Err(_) => (StoredSettings::defaults(), true),
    }
}

fn read_settings_file(path: &Path) -> Result<Vec<u8>, String> {
    let meta = fs::metadata(path).map_err(|error| error.to_string())?;
    if meta.len() > MAX_SETTINGS_FILE_BYTES {
        return Err(format!(
            "settings file exceeds {} bytes and is treated as corrupt",
            MAX_SETTINGS_FILE_BYTES
        ));
    }
    fs::read(path).map_err(|error| error.to_string())
}

fn parse_settings_document(raw: &[u8]) -> (StoredSettings, bool) {
    match serde_json::from_slice::<Value>(raw) {
        Ok(Value::Object(mut doc)) => {
            let schema_version = doc
                .remove("schema_version")
                .and_then(|value| value.as_str().map(str::to_string))
                .unwrap_or_else(|| SETTINGS_SCHEMA_VERSION.to_string());
            let values = doc
                .remove("values")
                .and_then(|value| value.as_object().cloned())
                .unwrap_or_default();
            (
                StoredSettings {
                    schema_version,
                    values,
                },
                false,
            )
        }
        Ok(_) => (StoredSettings::defaults(), true),
        Err(_) => (StoredSettings::defaults(), true),
    }
}

/// Serializes settings to the stored document shape.
pub fn serialize_settings(settings: &StoredSettings) -> Value {
    let mut doc = Map::new();
    doc.insert(
        "schema_version".to_string(),
        Value::String(settings.schema_version.clone()),
    );
    doc.insert("values".to_string(), Value::Object(settings.values.clone()));
    Value::Object(doc)
}

/// Atomically writes settings to `path` (temp file + rename), enforcing the
/// size cap.
pub fn save_settings(path: &Path, settings: &StoredSettings) -> Result<(), String> {
    let bytes = serde_json::to_vec_pretty(&serialize_settings(settings))
        .map_err(|error| format!("failed to serialize settings: {error}"))?;
    if bytes.len() as u64 > MAX_SETTINGS_FILE_BYTES {
        return Err(format!(
            "serialized settings exceed {} bytes; refusing to write",
            MAX_SETTINGS_FILE_BYTES
        ));
    }
    let parent = path
        .parent()
        .ok_or_else(|| "settings path has no parent directory".to_string())?;
    fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let tmp = path.with_extension("json.tmp");
    {
        let mut file = fs::File::create(&tmp).map_err(|error| error.to_string())?;
        file.write_all(&bytes).map_err(|error| error.to_string())?;
        file.flush().map_err(|error| error.to_string())?;
    }
    fs::rename(&tmp, path).map_err(|error| error.to_string())?;
    Ok(())
}

/// Recursively merges `patch` into `base` in place. Objects merge key by key;
/// every other value type replaces the existing value. Patch keys that do not
/// exist yet are inserted.
pub fn merge_settings(base: &mut Map<String, Value>, patch: &Value) {
    let Value::Object(patch_obj) = patch else {
        return;
    };
    for (key, patch_value) in patch_obj {
        match (base.get_mut(key), patch_value) {
            (Some(Value::Object(base_obj)), Value::Object(patch_obj)) => {
                merge_settings(base_obj, &Value::Object(patch_obj.clone()));
            }
            (Some(slot), next) => {
                *slot = next.clone();
            }
            (None, next) => {
                base.insert(key.clone(), next.clone());
            }
        }
    }
}

/// Reads, merges a patch, and writes back atomically under `lock_guard` to
/// keep concurrent writers serialized. Returns the merged settings object.
pub fn apply_settings_patch(path: &Path, patch: &Value, _lock_guard: &()) -> Result<Value, String> {
    let (mut stored, _recovered) = load_settings(path);
    merge_settings(&mut stored.values, patch);
    save_settings(path, &stored)?;
    Ok(Value::Object(stored.values))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::fs;

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "atomreasonx-settings-{}-{}",
            name,
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    #[test]
    fn missing_file_yields_defaults() {
        let dir = temp_dir("missing");
        let (settings, recovered) = load_settings(&settings_file_path(&dir));
        assert_eq!(settings, StoredSettings::defaults());
        assert!(recovered);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn roundtrip_preserves_values() {
        let dir = temp_dir("roundtrip");
        let path = settings_file_path(&dir);
        let mut settings = StoredSettings::defaults();
        settings
            .values
            .insert("desktopTheme".to_string(), json!("dark"));
        settings
            .values
            .insert("desktopThemeStyle".to_string(), json!("graphite"));
        save_settings(&path, &settings).expect("save settings");
        let (loaded, recovered) = load_settings(&path);
        assert_eq!(loaded, settings);
        assert!(!recovered);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn corrupt_file_falls_back_to_defaults() {
        let dir = temp_dir("corrupt");
        let path = settings_file_path(&dir);
        fs::create_dir_all(path.parent().unwrap()).expect("create dirs");
        fs::write(&path, b"{not json").expect("write corrupt file");
        let (settings, recovered) = load_settings(&path);
        assert_eq!(settings, StoredSettings::defaults());
        assert!(recovered);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn oversized_file_falls_back_to_defaults() {
        let dir = temp_dir("oversized");
        let path = settings_file_path(&dir);
        fs::create_dir_all(path.parent().unwrap()).expect("create dirs");
        let blob = vec![b' '; (MAX_SETTINGS_FILE_BYTES + 1) as usize];
        fs::write(&path, blob).expect("write oversized file");
        let (settings, recovered) = load_settings(&path);
        assert_eq!(settings, StoredSettings::defaults());
        assert!(recovered);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn merge_is_recursive_and_replacing() {
        let mut base = Map::new();
        base.insert(
            "general".to_string(),
            json!({ "theme": "dark", "width": "cozy" }),
        );
        base.insert("count".to_string(), json!(1));
        let patch = json!({
            "general": { "width": "wide", "newKey": true },
            "count": 2,
            "fresh": "value"
        });
        merge_settings(&mut base, &patch);
        assert_eq!(base["general"]["theme"], json!("dark"));
        assert_eq!(base["general"]["width"], json!("wide"));
        assert_eq!(base["general"]["newKey"], json!(true));
        assert_eq!(base["count"], json!(2));
        assert_eq!(base["fresh"], json!("value"));
    }

    #[test]
    fn non_object_patch_is_ignored() {
        let mut base = Map::new();
        base.insert("keep".to_string(), json!(1));
        merge_settings(&mut base, &json!(42));
        merge_settings(&mut base, &json!("nope"));
        assert_eq!(base["keep"], json!(1));
        assert_eq!(base.len(), 1);
    }

    #[test]
    fn apply_patch_reads_merges_and_writes() {
        let dir = temp_dir("apply");
        let path = settings_file_path(&dir);
        let guard = ();
        let merged = apply_settings_patch(&path, &json!({ "a": 1 }), &guard).expect("first patch");
        assert_eq!(merged, json!({ "a": 1 }));
        let merged =
            apply_settings_patch(&path, &json!({ "a": 2, "b": { "nested": true } }), &guard)
                .expect("second patch");
        assert_eq!(merged, json!({ "a": 2, "b": { "nested": true } }));
        let (loaded, _) = load_settings(&path);
        assert_eq!(loaded.values["a"], json!(2));
        let _ = fs::remove_dir_all(&dir);
    }
}
