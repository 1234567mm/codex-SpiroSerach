[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

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

function Convert-ToRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $normalizedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $normalizedPath = [IO.Path]::GetFullPath($Path)
    if (-not $normalizedPath.StartsWith($normalizedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside repository root: $Path"
    }
    return $normalizedPath.Substring($normalizedRoot.Length)
}

function Invoke-Go {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Output "==> $Name"
    & go @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Spiroctl {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Invoke-Go $Name (@('run', './cmd/spiroctl') + $Arguments)
}

function Convert-ToProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Join-ProcessArguments {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    return (($Arguments | ForEach-Object { Convert-ToProcessArgument $_ }) -join ' ')
}

function Invoke-SpiroctlExpectClosureBlocked {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$ExpectedReason
    )

    Write-Output "==> $Name"
    $processStart = New-Object System.Diagnostics.ProcessStartInfo
    $processStart.FileName = 'go'
    $processStart.Arguments = Join-ProcessArguments (@('run', './cmd/spiroctl') + $Arguments)
    $processStart.WorkingDirectory = (Get-Location).Path
    $processStart.UseShellExecute = $false
    $processStart.RedirectStandardOutput = $true
    $processStart.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::Start($processStart)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $exitCode = $process.ExitCode
    if ($exitCode -eq 0) {
        throw "$Name was expected to fail but passed"
    }
    try {
        $report = $stdout | ConvertFrom-Json
    }
    catch {
        throw "$Name did not emit a JSON closure report on stdout. Stdout: $stdout Stderr: $stderr"
    }
    if ($report.schema_version -ne 'v35.source_closure_readiness.v1') {
        throw "$Name emitted unexpected closure report schema_version: $($report.schema_version)"
    }
    if ($report.closure_gate_status -ne 'blocked' -or $report.ready -ne $false) {
        throw "$Name did not emit a blocked closure report. Report: $stdout"
    }
    if (@($report.reasons) -notcontains $ExpectedReason) {
        throw "$Name did not report expected reason '$ExpectedReason'. Report: $stdout Stderr: $stderr"
    }
}

function Invoke-SpiroctlExpectJson {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$ExpectedSchemaVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedSourceID,
        [Parameter(Mandatory = $true)][string]$ExpectedStatus
    )

    Write-Output "==> $Name"
    $processStart = New-Object System.Diagnostics.ProcessStartInfo
    $processStart.FileName = 'go'
    $processStart.Arguments = Join-ProcessArguments (@('run', './cmd/spiroctl') + $Arguments)
    $processStart.WorkingDirectory = (Get-Location).Path
    $processStart.UseShellExecute = $false
    $processStart.RedirectStandardOutput = $true
    $processStart.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::Start($processStart)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "$Name failed with exit code $($process.ExitCode). Stdout: $stdout Stderr: $stderr"
    }
    try {
        $report = $stdout | ConvertFrom-Json
    }
    catch {
        throw "$Name did not emit JSON on stdout. Stdout: $stdout Stderr: $stderr"
    }
    if ($report.schema_version -ne $ExpectedSchemaVersion) {
        throw "$Name emitted unexpected schema_version: $($report.schema_version)"
    }
    if ($report.source_id -ne $ExpectedSourceID) {
        throw "$Name emitted unexpected source_id: $($report.source_id)"
    }
    if ($report.status -ne $ExpectedStatus) {
        throw "$Name emitted unexpected status: $($report.status)"
    }
    if (@($report.requirements).Count -eq 0) {
        throw "$Name emitted no requirements. Report: $stdout"
    }
}

function Get-V35SourceSnapshotManifestPaths {
    param([Parameter(Mandatory = $true)][string]$Root)

    $scanRoots = @(
        (Join-Path $Root 'data\lib'),
        (Join-Path $Root 'data\public_baselines')
    )
    $paths = New-Object 'System.Collections.Generic.List[string]'
    foreach ($scanRoot in $scanRoots) {
        if (-not [IO.Directory]::Exists($scanRoot)) {
            continue
        }
        foreach ($manifest in Get-ChildItem -LiteralPath $scanRoot -Recurse -Filter 'source-manifest.json' -File) {
            try {
                $json = Get-Content -LiteralPath $manifest.FullName -Raw | ConvertFrom-Json
            }
            catch {
                throw "Source manifest is not valid JSON: $($manifest.FullName)"
            }
            if ($json.PSObject.Properties.Name -contains 'schema_version' -and
                $json.schema_version -eq 'v35.source_snapshot_manifest.v1') {
                $paths.Add((Convert-ToRelativePath $Root $manifest.FullName))
            }
        }
    }
    return $paths | Sort-Object
}

function Assert-SchemaConst {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$PropertyName,
        [Parameter(Mandatory = $true)][string]$ExpectedConst
    )

    Write-Output "==> schema contract validation: $RelativePath"
    $schemaPath = Join-Path (Get-Location).Path $RelativePath
    if (-not [IO.File]::Exists($schemaPath)) {
        throw "Schema file does not exist: $RelativePath"
    }
    $schema = Get-Content -LiteralPath $schemaPath -Raw | ConvertFrom-Json
    $property = $schema.properties.$PropertyName
    if ($property.const -ne $ExpectedConst) {
        throw "$RelativePath property $PropertyName const = $($property.const), want $ExpectedConst"
    }
}

$Root = Get-RepositoryRoot $RepositoryRoot
if (-not [IO.Directory]::Exists($Root)) {
    throw "Repository root does not exist: $Root"
}

Set-Location $Root
if ([string]::IsNullOrWhiteSpace($env:GOCACHE)) {
    $env:GOCACHE = Join-Path $Root '.cache\go-build'
}

Assert-SchemaConst 'schemas/source-closure-requirements.schema.json' `
    'schema_version' `
    'v35.source_closure_requirements.v1'

Invoke-Go 'Go read/validation package tests' @(
    'test',
    '-count=1',
    './internal/sourceregistry',
    './internal/sourcesnapshot',
    './internal/providercache',
    './internal/localbackend',
    './internal/runartifact',
    './internal/readonlyapi',
    './internal/readonlyserver',
    './cmd/spiroctl'
)

Invoke-Spiroctl 'source registry fixture validation' @(
    'source-registry',
    'validate',
    'data/source_registry.json'
)

$snapshotManifestPaths = @(Get-V35SourceSnapshotManifestPaths $Root)
if ($snapshotManifestPaths.Count -eq 0) {
    throw 'No V35 source snapshot manifests were found under data/lib or data/public_baselines.'
}
foreach ($manifestPath in $snapshotManifestPaths) {
    Invoke-Spiroctl "source snapshot fixture validation: $manifestPath" @(
        'source-snapshot',
        'validate',
        $manifestPath
    )
}

Invoke-SpiroctlExpectClosureBlocked 'PubChemQC fixture closure readiness blocks production admission' @(
    'source-closure',
    'validate',
    'data/lib/pubchemqc/source-manifest.json'
) 'pubchemqc_python_oracle_missing'

Invoke-SpiroctlExpectClosureBlocked 'Materials Cloud fixture closure readiness blocks scientific admission' @(
    'source-closure',
    'validate',
    'data/lib/materials_cloud/source-manifest.json'
) 'materials_cloud_metadata_only_records'

Invoke-SpiroctlExpectJson 'PubChemQC closure requirements are machine-readable' @(
    'source-closure',
    'requirements',
    'pubchemqc'
) 'v35.source_closure_requirements.v1' 'pubchemqc' 'inputs_required'

Invoke-SpiroctlExpectJson 'Materials Cloud closure requirements are machine-readable' @(
    'source-closure',
    'requirements',
    'materials_cloud'
) 'v35.source_closure_requirements.v1' 'materials_cloud' 'inputs_required'

Invoke-Spiroctl 'provider cache fixture validation' @(
    'provider-cache',
    'validate',
    'tests/fixtures/artifact_viewer/v11_diagnostic_run/provider-cache.jsonl'
)

Invoke-Spiroctl 'provider cache index fixture validation' @(
    'provider-cache-index',
    'validate',
    'tests/fixtures/artifact_viewer/v11_diagnostic_run/provider-cache-index.json'
)

Invoke-Spiroctl 'run artifact fixture validation' @(
    'run-artifacts',
    'validate',
    'tests/fixtures/artifact_viewer/v11_diagnostic_run'
)

Invoke-Spiroctl 'readonly run fixture validation' @(
    'readonly-run',
    'validate',
    'tests/fixtures/artifact_viewer/v11_diagnostic_run'
)

Write-Output 'PASS: V35 Go read/validation regression closure passed.'
