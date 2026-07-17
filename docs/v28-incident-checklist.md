# V28 Incident And Restore Checklist

> Status: implemented_local_only
> Date: 2026-07-17
> Ticket: T28-O2

## Boundary

- Local / operator workstation only
- `hosted_deployment: false`
- `external_credentials_required: false`

## Checklist Payload Contract

Machine-readable builder: `spirosearch.v28_local_readiness.build_v28_incident_checklist`.

Example pass payload:

```json
{
  "schema_version": "v28.incident_checklist.v1",
  "incident_checklist_id": "v28-incident-checklist",
  "release_profile_id": "v28-local",
  "status": "pass",
  "reason_codes": [],
  "backup_scope": [
    "run-manifest.json",
    "artifacts",
    "schemas",
    "command_outputs",
    "handoff_artifacts",
    "v28_evidence_docs"
  ],
  "external_credentials_required": false,
  "hosted_deployment": false,
  "restore_checks": [
    {
      "kind": "run-manifest",
      "status": "pass",
      "path": "run-manifest.json",
      "notes": null
    }
  ],
  "dependency_scan_status": "skipped_local_only",
  "rollback_procedure_documented": true,
  "steps": [
    "Stop local writes to the affected run directory.",
    "Preserve run-manifest.json and artifact hashes.",
    "Restore from last known-good local backup.",
    "Re-validate schema refs and sha256 values.",
    "Re-run focused unittest gate before continuing scientific work.",
    "Do not open hosted deployment paths during V28 recovery."
  ]
}
```

## Manual Operator Checks

1. Confirm `run-manifest.json` and artifact hashes are preserved.
2. Restore from local backup only.
3. Re-validate schema refs and sha256.
4. Re-run focused unit tests before scientific work.
5. Do not open hosting, credentials, or external writes during V28 recovery.
