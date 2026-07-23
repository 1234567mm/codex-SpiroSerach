[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$TargetTriple,
    [string]$OutputDirectory,
    [switch]$SkipSmokeTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Utf8NoBom = New-Object Text.UTF8Encoding($false)

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

function Get-TargetTriple {
    param([string]$RequestedTargetTriple)

    if (-not [string]::IsNullOrWhiteSpace($RequestedTargetTriple)) {
        return $RequestedTargetTriple.Trim()
    }

    $hostTriple = & rustc --print host-tuple 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($hostTriple | Select-Object -First 1))) {
        return ($hostTriple | Select-Object -First 1).Trim()
    }

    $goos = (& go env GOOS).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($goos)) {
        throw 'Unable to determine GOOS for fallback target triple.'
    }
    $goarch = (& go env GOARCH).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($goarch)) {
        throw 'Unable to determine GOARCH for fallback target triple.'
    }

    switch ("$goos/$goarch") {
        'windows/amd64' { return 'x86_64-pc-windows-msvc' }
        'windows/arm64' { return 'aarch64-pc-windows-msvc' }
        'windows/386' { return 'i686-pc-windows-msvc' }
        'darwin/amd64' { return 'x86_64-apple-darwin' }
        'darwin/arm64' { return 'aarch64-apple-darwin' }
        'linux/amd64' { return 'x86_64-unknown-linux-gnu' }
        'linux/arm64' { return 'aarch64-unknown-linux-gnu' }
        default { throw "Unsupported fallback Go host for Tauri sidecar target triple: $goos/$goarch" }
    }
}

function Get-GoTarget {
    param([Parameter(Mandatory = $true)][string]$ResolvedTargetTriple)

    switch -Regex ($ResolvedTargetTriple) {
        '^x86_64-pc-windows-' {
            return [pscustomobject]@{ GOOS = 'windows'; GOARCH = 'amd64'; GOARM = ''; Extension = '.exe' }
        }
        '^aarch64-pc-windows-' {
            return [pscustomobject]@{ GOOS = 'windows'; GOARCH = 'arm64'; GOARM = ''; Extension = '.exe' }
        }
        '^i686-pc-windows-' {
            return [pscustomobject]@{ GOOS = 'windows'; GOARCH = '386'; GOARM = ''; Extension = '.exe' }
        }
        '^x86_64-apple-darwin$' {
            return [pscustomobject]@{ GOOS = 'darwin'; GOARCH = 'amd64'; GOARM = ''; Extension = '' }
        }
        '^aarch64-apple-darwin$' {
            return [pscustomobject]@{ GOOS = 'darwin'; GOARCH = 'arm64'; GOARM = ''; Extension = '' }
        }
        '^x86_64-unknown-linux-' {
            return [pscustomobject]@{ GOOS = 'linux'; GOARCH = 'amd64'; GOARM = ''; Extension = '' }
        }
        '^aarch64-unknown-linux-' {
            return [pscustomobject]@{ GOOS = 'linux'; GOARCH = 'arm64'; GOARM = ''; Extension = '' }
        }
        '^armv7-unknown-linux-' {
            return [pscustomobject]@{ GOOS = 'linux'; GOARCH = 'arm'; GOARM = '7'; Extension = '' }
        }
        default {
            throw "Unsupported Tauri sidecar target triple: $ResolvedTargetTriple"
        }
    }
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $normalizedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $normalizedPath = [IO.Path]::GetFullPath($Path)
    if (-not $normalizedPath.StartsWith($normalizedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside repository root: $Path"
    }
    return $normalizedPath.Substring($normalizedRoot.Length).Replace('\', '/')
}

function Invoke-SidecarSmokeTest {
    param(
        [Parameter(Mandatory = $true)][string]$ArtifactPath,
        [Parameter(Mandatory = $true)][string]$Root
    )

    & $ArtifactPath source-registry validate 'data/source_registry.json'
    if ($LASTEXITCODE -ne 0) {
        throw "spiroctl sidecar smoke test failed with exit code $LASTEXITCODE"
    }
}

$Root = Get-RepositoryRoot $RepositoryRoot
if (-not [IO.Directory]::Exists($Root)) {
    throw "Repository root does not exist: $Root"
}
Set-Location $Root

$TargetTriple = Get-TargetTriple $TargetTriple
$goTarget = Get-GoTarget $TargetTriple
$outputRoot = $OutputDirectory
if ([string]::IsNullOrWhiteSpace($outputRoot)) {
    $outputRoot = Join-Path $Root 'frontend\atomreasonx\src-tauri\binaries'
}
$outputRoot = [IO.Path]::GetFullPath($outputRoot)
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

# Tauri bundle.externalBin must stay "binaries/spiroctl"; Tauri looks for
# binaries/spiroctl-<target-triple>[.exe] at build time.
$artifactName = "spiroctl-$TargetTriple$($goTarget.Extension)"
$artifactPath = Join-Path $outputRoot $artifactName
$sha256Path = "$artifactPath.sha256"
$manifestPath = "$artifactPath.manifest.json"

$previousGoos = $env:GOOS
$previousGoarch = $env:GOARCH
$previousGoarm = $env:GOARM
$previousCgo = $env:CGO_ENABLED
$previousGocache = $env:GOCACHE

try {
    $env:GOOS = $goTarget.GOOS
    $env:GOARCH = $goTarget.GOARCH
    if ([string]::IsNullOrWhiteSpace($goTarget.GOARM)) {
        Remove-Item Env:\GOARM -ErrorAction SilentlyContinue
    }
    else {
        $env:GOARM = $goTarget.GOARM
    }
    $env:CGO_ENABLED = '0'
    if ([string]::IsNullOrWhiteSpace($env:GOCACHE)) {
        $env:GOCACHE = Join-Path $Root '.cache\go-build'
    }

    & go build -trimpath -ldflags '-s -w' -o $artifactPath ./cmd/spiroctl
    if ($LASTEXITCODE -ne 0) {
        throw "go build for AtomReasonX spiroctl sidecar failed with exit code $LASTEXITCODE"
    }
}
finally {
    $env:GOOS = $previousGoos
    $env:GOARCH = $previousGoarch
    if ($null -eq $previousGoarm) {
        Remove-Item Env:\GOARM -ErrorAction SilentlyContinue
    }
    else {
        $env:GOARM = $previousGoarm
    }
    $env:CGO_ENABLED = $previousCgo
    $env:GOCACHE = $previousGocache
}

if (-not [IO.File]::Exists($artifactPath)) {
    throw "Expected sidecar artifact was not created: $artifactPath"
}

$artifact = Get-Item -LiteralPath $artifactPath
$sha256 = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($sha256Path, "$sha256  $artifactName`n", $Utf8NoBom)

$sourceCommit = $null
$commit = & git -C $Root rev-parse HEAD 2>$null
if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($commit | Select-Object -First 1))) {
    $sourceCommit = ($commit | Select-Object -First 1).Trim()
}

$goVersion = (& go version 2>$null | Select-Object -First 1)
$manifest = [ordered]@{
    schema_version = 'v35.atomreasonx_spiroctl_sidecar_build.v1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    external_bin_entry = 'binaries/spiroctl'
    artifact_name = $artifactName
    artifact_relpath = Get-RelativePath $Root $artifactPath
    target_triple = $TargetTriple
    goos = $goTarget.GOOS
    goarch = $goTarget.GOARCH
    goarm = if ([string]::IsNullOrWhiteSpace($goTarget.GOARM)) { $null } else { $goTarget.GOARM }
    cgo_enabled = '0'
    source_package = './cmd/spiroctl'
    source_commit = $sourceCommit
    go_version = $goVersion
    sha256 = $sha256
    bytes = $artifact.Length
}
$manifestJson = $manifest | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText($manifestPath, "$manifestJson`n", $Utf8NoBom)

$hostTriple = Get-TargetTriple ''
if (-not $SkipSmokeTest -and $TargetTriple -eq $hostTriple) {
    Invoke-SidecarSmokeTest $artifactPath $Root
}

Write-Output "INFO: bundle.externalBin entry remains binaries/spiroctl."
Write-Output "INFO: built AtomReasonX spiroctl sidecar artifact=$artifactName targetTriple=$TargetTriple sha256=$sha256"
Write-Output "PASS: AtomReasonX spiroctl sidecar build policy completed."
