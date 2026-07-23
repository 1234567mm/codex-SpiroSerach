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

$Root = Get-RepositoryRoot $RepositoryRoot
if (-not [IO.Directory]::Exists($Root)) {
    throw "Repository root does not exist: $Root"
}

Set-Location $Root
if ([string]::IsNullOrWhiteSpace($env:GOCACHE)) {
    $env:GOCACHE = Join-Path $Root '.cache\go-build'
}

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
