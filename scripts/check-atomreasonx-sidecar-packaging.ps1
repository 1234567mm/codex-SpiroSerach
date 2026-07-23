[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [switch]$RequireBundledSidecar
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Violations = New-Object 'System.Collections.Generic.List[string]'
$StrictUtf8 = New-Object Text.UTF8Encoding($false, $true)

function Add-Violation {
    param([Parameter(Mandatory = $true)][string]$Message)
    $script:Violations.Add($Message)
}

function Read-StrictUtf8 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [IO.File]::ReadAllBytes($Path)
    return $script:StrictUtf8.GetString($bytes)
}

function Get-RepositoryRoot {
    param([string]$RequestedRoot)

    if (-not [string]::IsNullOrWhiteSpace($RequestedRoot)) {
        return [IO.Path]::GetFullPath($RequestedRoot)
    }

    $detectedRoot = & git -C (Get-Location).Path rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($detectedRoot | Select-Object -First 1))) {
        throw 'Unable to determine the repository root. Pass -RepositoryRoot explicitly.'
    }

    return [IO.Path]::GetFullPath(($detectedRoot | Select-Object -First 1))
}

function Test-JsonProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    return $Object.PSObject.Properties.Name -contains $Name
}

function Test-RelativeBundlePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    if ([IO.Path]::IsPathRooted($Path)) {
        return $false
    }
    if ($Path -match '(^|[\\/])\.\.([\\/]|$)') {
        return $false
    }
    if ($Path -match '^[A-Za-z]:') {
        return $false
    }
    return $true
}

try {
    $Root = Get-RepositoryRoot $RepositoryRoot
}
catch {
    Write-Output "ERROR: $($_.Exception.Message)"
    exit 1
}

$TauriConfigPath = Join-Path $Root 'frontend\atomreasonx\src-tauri\tauri.conf.json'
$RustBridgePath = Join-Path $Root 'frontend\atomreasonx\src-tauri\src\main.rs'
$TypeScriptBridgePath = Join-Path $Root 'frontend\atomreasonx\src\adapters\tauri-readonly-sidecar.ts'
$SpiroctlMainPath = Join-Path $Root 'cmd\spiroctl\main.go'

foreach ($requiredPath in @($TauriConfigPath, $RustBridgePath, $TypeScriptBridgePath, $SpiroctlMainPath)) {
    if (-not [IO.File]::Exists($requiredPath)) {
        Add-Violation "Required sidecar packaging file is missing: $requiredPath"
    }
}

if ($Violations.Count -eq 0) {
    try {
        $config = Read-StrictUtf8 $TauriConfigPath | ConvertFrom-Json
    }
    catch {
        Add-Violation 'frontend/atomreasonx/src-tauri/tauri.conf.json is not valid JSON.'
    }

    if ($Violations.Count -eq 0) {
        if (-not (Test-JsonProperty $config 'bundle')) {
            Add-Violation 'tauri.conf.json must define bundle configuration.'
        }
        else {
            $externalBin = @()
            if ((Test-JsonProperty $config.bundle 'externalBin') -and $null -ne $config.bundle.externalBin) {
                $externalBin = @($config.bundle.externalBin)
            }
            $resources = @()
            if ((Test-JsonProperty $config.bundle 'resources') -and $null -ne $config.bundle.resources) {
                $resources = @($config.bundle.resources)
            }

            if ($externalBin.Count -eq 0) {
                if ($RequireBundledSidecar) {
                    Add-Violation 'bundle.externalBin must include binaries/spiroctl for production sidecar packaging.'
                }
            }
            else {
                if (-not ($externalBin -contains 'binaries/spiroctl')) {
                    Add-Violation 'bundle.externalBin must include binaries/spiroctl as the release-owned Go sidecar entry.'
                }
                foreach ($entry in $externalBin) {
                    if ($entry -isnot [string] -or -not (Test-RelativeBundlePath $entry)) {
                        Add-Violation "bundle.externalBin entry must be a safe relative path: $entry"
                    }
                    if ($entry -match 'spiroctlPath|readonly_token|api_key') {
                        Add-Violation "bundle.externalBin entry exposes forbidden command or credential naming: $entry"
                    }
                }
            }

            foreach ($resource in $resources) {
                if ($resource -is [string] -and $resource -match 'spiroctl') {
                    Add-Violation 'spiroctl must be packaged through bundle.externalBin, not bundle.resources.'
                }
            }
        }
    }

    $rustBridge = Read-StrictUtf8 $RustBridgePath
    foreach ($requiredToken in @(
        'start_readonly_sidecar',
        'Command::new(executable)',
        '"readonly-run"',
        '"serve"',
        'SPIROCTL_PATH'
    )) {
        if (-not $rustBridge.Contains($requiredToken)) {
            Add-Violation "Rust readonly sidecar bridge is missing required token: $requiredToken"
        }
    }
    foreach ($forbiddenToken in @(
        'spiroctl_path:',
        'spiroctlPath',
        'shell()',
        'emit(',
        'println!'
    )) {
        if ($rustBridge.Contains($forbiddenToken)) {
            Add-Violation "Rust readonly sidecar bridge contains forbidden token: $forbiddenToken"
        }
    }

    $typescriptBridge = Read-StrictUtf8 $TypeScriptBridgePath
    foreach ($requiredToken in @('start_readonly_sidecar', 'stop_readonly_sidecar')) {
        if (-not $typescriptBridge.Contains($requiredToken)) {
            Add-Violation "TypeScript readonly sidecar bridge is missing required token: $requiredToken"
        }
    }
    foreach ($forbiddenToken in @('spiroctlPath', 'localStorage', 'console.')) {
        if ($typescriptBridge.Contains($forbiddenToken)) {
            Add-Violation "TypeScript readonly sidecar bridge contains forbidden token: $forbiddenToken"
        }
    }
}

if ($Violations.Count -gt 0) {
    foreach ($violation in $Violations) {
        Write-Output "ERROR: $violation"
    }
    exit 1
}

$mode = 'dev_path_only'
if ($externalBin.Count -gt 0) {
    $mode = 'bundled_external_bin'
}

if ($mode -eq 'dev_path_only') {
    Write-Output 'INFO: mode=dev_path_only externalBin=[]; release builds must provide SPIROCTL_PATH/PATH or enable bundle.externalBin with binaries/spiroctl.'
}
else {
    Write-Output 'INFO: mode=bundled_external_bin externalBin includes binaries/spiroctl.'
}
Write-Output "PASS: AtomReasonX sidecar packaging preflight passed (mode=$mode)."
