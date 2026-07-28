[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$CheckerPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\scripts\check-project-compile.ps1'))
$RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$PowerShellPath = (Get-Process -Id $PID).Path

function Invoke-Plan {
    param([Parameter(Mandatory = $true)][string]$Scope, [string[]]$Paths = @())
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script:CheckerPath,
        '-RepositoryRoot', $script:RepositoryRoot, '-Scope', $Scope)
    if ($Paths.Count -gt 0) {
        $arguments += @('-ChangedPath', ($Paths -join ','))
    }
    $arguments += '-PlanOnly'
    $output = & $script:PowerShellPath @arguments 2>&1
    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output | Out-String) }
}

function Assert-True {
    param([Parameter(Mandatory = $true)][bool]$Condition, [Parameter(Mandatory = $true)][string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Contains {
    param([Parameter(Mandatory = $true)][string]$Text, [Parameter(Mandatory = $true)][string]$Expected)
    Assert-True ($Text.Contains($Expected)) "Expected '$Expected' in output:`n$Text"
}

$python = Invoke-Plan -Scope 'Auto' -Paths @('src/spirosearch/cli.py')
Assert-True ($python.ExitCode -eq 0) "Python auto plan failed: $($python.Output)"
Assert-Contains $python.Output 'PLAN: Python'
Assert-True (-not $python.Output.Contains('PLAN: Go')) "Python-only path planned Go: $($python.Output)"
Write-Output 'PASS: Python paths select only Python compilation'

$mixed = Invoke-Plan -Scope 'Auto' -Paths @('internal/sourcesnapshot/closure.go', 'frontend/atomreasonx/src/AppShell.tsx', 'frontend/atomreasonx/src-tauri/src/main.rs')
Assert-True ($mixed.ExitCode -eq 0) "Mixed auto plan failed: $($mixed.Output)"
foreach ($target in @('Go', 'Frontend', 'Rust')) { Assert-Contains $mixed.Output "PLAN: $target" }
Write-Output 'PASS: mixed paths select each affected compilation surface'

$docs = Invoke-Plan -Scope 'Auto' -Paths @('docs/project-hooks.md')
Assert-True ($docs.ExitCode -eq 0) "Documentation auto plan failed: $($docs.Output)"
Assert-Contains $docs.Output 'SKIP: no changed paths require a compilation check.'
Write-Output 'PASS: documentation-only paths skip compilation'

$all = Invoke-Plan -Scope 'All'
Assert-True ($all.ExitCode -eq 0) "All plan failed: $($all.Output)"
foreach ($target in @('Python', 'Go', 'Frontend', 'Rust')) { Assert-Contains $all.Output "PLAN: $target" }
Write-Output 'PASS: All scope includes every compilation surface'

Write-Output 'PASS: all project compilation script tests passed'
