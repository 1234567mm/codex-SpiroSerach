[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [ValidateSet('Auto', 'All', 'Python', 'Go', 'Frontend', 'Rust')]
    [string]$Scope = 'Auto',
    [string[]]$ChangedPath,
    [string]$PythonExecutable,
    [switch]$PlanOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-RepositoryRoot {
    param([string]$RequestedRoot)

    if (-not [string]::IsNullOrWhiteSpace($RequestedRoot)) {
        $resolved = [IO.Path]::GetFullPath($RequestedRoot)
    }
    else {
        $detectedRoot = & git -C (Get-Location).Path rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($detectedRoot | Select-Object -First 1))) {
            throw 'Unable to determine the repository root. Pass -RepositoryRoot explicitly.'
        }
        $resolved = [IO.Path]::GetFullPath(($detectedRoot | Select-Object -First 1))
    }

    if (-not [IO.File]::Exists((Join-Path $resolved 'pyproject.toml')) -or
        -not [IO.File]::Exists((Join-Path $resolved 'go.mod'))) {
        throw "Repository root does not look like SpiroSearch: $resolved"
    }
    return $resolved
}

function Get-ChangedPaths {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string[]]$ProvidedPaths
    )

    if ($null -ne $ProvidedPaths) {
        return @($ProvidedPaths |
            ForEach-Object { $_ -split ',' } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Sort-Object -Unique)
    }

    $tracked = @(& git -c core.safecrlf=false -C $Root diff --name-only HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { throw 'Git could not list changed tracked files.' }
    $untracked = @(& git -c core.safecrlf=false -C $Root ls-files --others --exclude-standard 2>$null)
    if ($LASTEXITCODE -ne 0) { throw 'Git could not list untracked files.' }
    return @($tracked + $untracked | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
}

function Resolve-CompileTargets {
    param(
        [Parameter(Mandatory = $true)][string]$RequestedScope,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Paths
    )

    if ($RequestedScope -eq 'All') { return @('Python', 'Go', 'Frontend', 'Rust') }
    if ($RequestedScope -ne 'Auto') { return @($RequestedScope) }

    $targets = New-Object 'System.Collections.Generic.List[string]'
    foreach ($path in $Paths) {
        $normalized = $path.Replace('\', '/')
        if ($normalized -match '^(src|tests)/.*\.py$' -or $normalized -match '^scripts/.*\.py$') {
            if (-not $targets.Contains('Python')) { $targets.Add('Python') }
        }
        if ($normalized -match '\.go$' -or $normalized -match '^(go\.mod|go\.sum)$') {
            if (-not $targets.Contains('Go')) { $targets.Add('Go') }
        }
        if ($normalized -match '^frontend/atomreasonx/(src/.*\.(ts|tsx)$|package(-lock)?\.json$|tsconfig.*\.json$|vite\.config\..*$)') {
            if (-not $targets.Contains('Frontend')) { $targets.Add('Frontend') }
        }
        if ($normalized -match '^frontend/atomreasonx/src-tauri/' -or $normalized -match '^frontend/atomreasonx/(Cargo\.toml|Cargo\.lock)$') {
            if (-not $targets.Contains('Rust')) { $targets.Add('Rust') }
        }
    }
    return @($targets)
}

function Get-PythonCompileInputs {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RequestedScope,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Paths
    )

    if ($RequestedScope -eq 'Auto') {
        return @($Paths |
            Where-Object { $_.Replace('\', '/') -match '^(src|tests)/.*\.py$' -or $_.Replace('\', '/') -match '^scripts/.*\.py$' } |
            ForEach-Object { Join-Path $Root $_ } |
            Where-Object { [IO.File]::Exists($_) })
    }

    return @('src', 'tests', 'scripts' |
        ForEach-Object { Join-Path $Root $_ } |
        Where-Object { [IO.Directory]::Exists($_) })
}

function Invoke-PythonCompile {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RequestedScope,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Paths,
        [string]$Executable
    )

    $inputs = @(Get-PythonCompileInputs -Root $Root -RequestedScope $RequestedScope -Paths $Paths)
    if ($inputs.Count -eq 0) {
        Write-Output 'SKIP: no Python files are available for syntax compilation.'
        return
    }
    $compilerProgram = @'
from pathlib import Path
import sys

failures = []
for raw in sys.argv[1:]:
    candidate = Path(raw)
    paths = [candidate] if candidate.is_file() else candidate.rglob('*.py')
    for path in paths:
        try:
            compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
        except (OSError, SyntaxError, UnicodeError) as exc:
            failures.append(f'{path}: {exc}')
if failures:
    print('\n'.join(failures), file=sys.stderr)
    raise SystemExit(1)
'@

    if (-not [string]::IsNullOrWhiteSpace($Executable)) {
        $resolvedExecutable = [IO.Path]::GetFullPath($Executable)
        if (-not [IO.File]::Exists($resolvedExecutable)) {
            throw "PythonExecutable does not exist: $resolvedExecutable"
        }
        & $resolvedExecutable -c $compilerProgram @inputs
    }
    else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($null -ne $python) { & $python.Source -c $compilerProgram @inputs }
        elseif ($null -ne $pythonLauncher) { & $pythonLauncher.Source -3.11 -c $compilerProgram @inputs }
        else { & uv run --no-project --python 3.11 python -c $compilerProgram @inputs }
    }
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed with exit code $LASTEXITCODE." }
}

function Invoke-GoCompile {
    param([Parameter(Mandatory = $true)][string]$Root)
    $originalGoCache = $env:GOCACHE
    $env:GOCACHE = Join-Path ([IO.Path]::GetTempPath()) 'spirosearch-go-build'
    Push-Location $Root
    try {
        & go test -run '^$' ./...
        if ($LASTEXITCODE -ne 0) { throw "Go compilation failed with exit code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
        $env:GOCACHE = $originalGoCache
    }
}

function Invoke-FrontendCompile {
    param([Parameter(Mandatory = $true)][string]$Root)
    Push-Location (Join-Path $Root 'frontend\atomreasonx')
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend compilation failed with exit code $LASTEXITCODE." }
    }
    finally { Pop-Location }
}

function Invoke-RustCompile {
    param([Parameter(Mandatory = $true)][string]$Root)
    $wrapper = Join-Path $Root 'scripts\invoke-msvc-cargo.ps1'
    & $wrapper -RepositoryRoot $Root -WorkingDirectory 'frontend/atomreasonx/src-tauri' check --locked
    if ($LASTEXITCODE -ne 0) { throw "Rust compilation failed with exit code $LASTEXITCODE." }
}

$Root = Get-RepositoryRoot $RepositoryRoot
$paths = @(Get-ChangedPaths -Root $Root -ProvidedPaths $ChangedPath)
$targets = @(Resolve-CompileTargets -RequestedScope $Scope -Paths $paths)
$descriptions = @{
    Python = 'in-memory Python syntax compilation (no __pycache__ writes)'
    Go = "go test -run '^$' ./..."
    Frontend = 'npm.cmd run build (frontend/atomreasonx)'
    Rust = 'invoke-msvc-cargo.ps1 ... check --locked'
}

if ($targets.Count -eq 0) {
    Write-Output 'SKIP: no changed paths require a compilation check.'
    exit 0
}

foreach ($target in $targets) { Write-Output "PLAN: $target - $($descriptions[$target])" }
if ($PlanOnly) { exit 0 }

try {
    foreach ($target in $targets) {
        Write-Output "CHECK: $target"
        switch ($target) {
            'Python' { Invoke-PythonCompile -Root $Root -RequestedScope $Scope -Paths $paths -Executable $PythonExecutable }
            'Go' { Invoke-GoCompile -Root $Root }
            'Frontend' { Invoke-FrontendCompile -Root $Root }
            'Rust' { Invoke-RustCompile -Root $Root }
            default { throw "Unsupported compilation target: $target" }
        }
        Write-Output "PASS: $target"
    }
}
catch {
    Write-Error "FAIL: compilation verification failed. $($_.Exception.Message)"
    exit 1
}

Write-Output 'PASS: requested compilation verification completed.'
