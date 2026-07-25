[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$CheckerPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\scripts\check-context-budget.ps1'))

if (-not [IO.File]::Exists($CheckerPath)) {
    Write-Error "Checker script not found: $CheckerPath"
    exit 1
}

$Utf8NoBom = New-Object Text.UTF8Encoding($false)
$PowerShellPath = (Get-Process -Id $PID).Path
$TempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$SuiteRoot = Join-Path $TempRoot ("context-budget-test-{0}" -f [guid]::NewGuid().ToString('N'))
$SuiteRootFull = [IO.Path]::GetFullPath($SuiteRoot)
$ExpectedPrefix = $TempRoot + [IO.Path]::DirectorySeparatorChar

if (-not $SuiteRootFull.StartsWith($ExpectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create fixture outside the system temp directory: $SuiteRootFull"
}

function Set-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )

    $parent = Split-Path -Parent $Path
    if (-not [IO.Directory]::Exists($parent)) {
        [void][IO.Directory]::CreateDirectory($parent)
    }
    [IO.File]::WriteAllText($Path, $Content, $script:Utf8NoBom)
}

function New-CleanFixture {
    param([Parameter(Mandatory = $true)][string]$Name)

    $root = Join-Path $script:SuiteRoot $Name
    [void][IO.Directory]::CreateDirectory($root)

    Set-Utf8File (Join-Path $root '.codex\skills\context-handoff\SKILL.md') @'
---
name: context-handoff
description: Use when saving context
---
# Context Handoff
Use check-context-budget.ps1 before handoff.
## Context Budget Trigger
At 70% context usage, save a proactive handoff; at 80% context usage, a handoff is required. Preserve verification quality.
'@
    Set-Utf8File (Join-Path $root '.codex\skills\worktree-tdd\SKILL.md') @'
---
name: worktree-tdd
description: Use when implementing
---
# Worktree TDD
## Test Deduplication
## Gate Classes
## External Architecture References
'@
    Set-Utf8File (Join-Path $root '.codex\skills\review-ship\SKILL.md') @'
---
name: review-ship
description: Use before shipping
---
# Review Ship
## Pre-Commit Optimization
## Test Review
## Stage-End Learning
'@
    Set-Utf8File (Join-Path $root 'plans\v35-execution-status-and-next-slices.md') @'
# V35
Operational addendum: 70% context usage triggers proactive handoff; 80% context usage requires fewer duplicate tests, same quality, and a quality-preserving test budget.
'@
    Set-Utf8File (Join-Path $root 'docs\project-hooks.md') @'
# Project Hooks
check-context-budget.ps1
SPIRO_CONTEXT_USAGE_PERCENT
SPIRO_CONTEXT_HANDOFF_PATH
'@

    return $root
}

function Invoke-Checker {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [string[]]$Arguments = @()
    )

    $output = & $script:PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $script:CheckerPath -RepositoryRoot $RepositoryRoot @Arguments 2>&1
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | Out-String)
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Message
    )

    Assert-True ($Text.Contains($Expected)) "$Message`nActual output:`n$Text"
}

function Assert-Failure {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [Parameter(Mandatory = $true)][string]$ExpectedText,
        [Parameter(Mandatory = $true)][string]$CaseName
    )

    Assert-True ($Result.ExitCode -ne 0) "$CaseName unexpectedly succeeded."
    Assert-Contains $Result.Output 'ERROR:' "$CaseName did not emit an ERROR line."
    Assert-Contains $Result.Output $ExpectedText "$CaseName did not identify the expected violation."
}

try {
    [void][IO.Directory]::CreateDirectory($SuiteRoot)

    $clean = New-CleanFixture 'clean'
    $result = Invoke-Checker $clean
    Assert-True ($result.ExitCode -eq 0) "Clean fixture failed:`n$($result.Output)"
    Assert-Contains $result.Output 'PASS:' 'Clean fixture did not emit a PASS line.'
    Write-Output 'PASS: static context budget hook fixture'

    $proactiveHandoff = New-CleanFixture 'proactive-handoff'
    $result = Invoke-Checker $proactiveHandoff @('-ContextUsagePercent', '70')
    Assert-True ($result.ExitCode -eq 0) "Proactive handoff fixture failed:`n$($result.Output)"
    Assert-Contains $result.Output 'WARN:' 'Proactive handoff fixture did not emit a visible warning.'
    Assert-Contains $result.Output 'proactive handoff band' 'Proactive handoff fixture did not identify the proactive band.'
    Write-Output 'PASS: 70 percent context emits a visible proactive handoff warning'

    $missingHandoff = New-CleanFixture 'missing-handoff'
    Assert-Failure (Invoke-Checker $missingHandoff @('-ContextUsagePercent', '80')) 'HandoffPath' 'missing handoff fixture'
    Write-Output 'PASS: 80 percent context requires a handoff'

    $withHandoff = New-CleanFixture 'with-handoff'
    $handoffPath = Join-Path $withHandoff 'plans\context-budget-handoff.md'
    Set-Utf8File $handoffPath @'
## Goal

## Current State

## Tests

## Remaining Work

Next concrete action: continue verification.
'@
    $result = Invoke-Checker $withHandoff @('-ContextUsagePercent', '80', '-HandoffPath', $handoffPath)
    Assert-True ($result.ExitCode -eq 0) "Valid handoff fixture failed:`n$($result.Output)"
    Assert-Contains $result.Output 'PASS:' 'Valid handoff fixture did not emit a PASS line.'
    Write-Output 'PASS: 80 percent context accepts a valid handoff'

    Write-Output 'PASS: all context budget checker tests passed'
    exit 0
}
catch {
    Write-Error $_
    exit 1
}
finally {
    $cleanupPath = [IO.Path]::GetFullPath($SuiteRoot)
    if (-not $cleanupPath.StartsWith($ExpectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Error "Refusing to clean fixture outside the system temp directory: $cleanupPath"
    }
    elseif ([IO.Directory]::Exists($cleanupPath)) {
        Remove-Item -LiteralPath $cleanupPath -Recurse -Force
    }
}
