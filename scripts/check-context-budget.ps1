[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [int]$ContextUsagePercent = -1,
    [int]$ThresholdPercent = 80,
    [int]$ProactiveHandoffPercent = 70,
    [string]$HandoffPath
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

function Assert-RequiredText {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string[]]$RequiredText
    )

    $fullPath = Join-Path $Root $RelativePath
    $displayPath = $RelativePath.Replace('\', '/')
    if (-not [IO.File]::Exists($fullPath)) {
        Add-Violation "$displayPath is missing required context-budget guardrails."
        return
    }

    try {
        $text = Read-StrictUtf8 $fullPath
        foreach ($fragment in $RequiredText) {
            if (-not $text.Contains($fragment)) {
                Add-Violation "$displayPath is missing required context-budget guardrail text: $fragment"
            }
        }
    }
    catch {
        Add-Violation "$displayPath could not be read for context-budget guardrail checks."
    }
}

function Resolve-RepositoryPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([IO.Path]::IsPathRooted($Path)) {
        return [IO.Path]::GetFullPath($Path)
    }
    return [IO.Path]::GetFullPath((Join-Path $Root $Path))
}

function Test-IsUnderPath {
    param(
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Child
    )

    $normalizedParent = [IO.Path]::GetFullPath($Parent).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $normalizedChild = [IO.Path]::GetFullPath($Child)
    return $normalizedChild.StartsWith($normalizedParent, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-HandoffFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolvedPath = Resolve-RepositoryPath $Path
    if (-not [IO.File]::Exists($resolvedPath)) {
        Add-Violation "Context usage is at or above $ThresholdPercent%; handoff file does not exist: $Path"
        return
    }

    $allowedRoots = @(
        (Join-Path $Root 'docs'),
        (Join-Path $Root 'plans')
    )
    $isAllowed = $false
    foreach ($allowedRoot in $allowedRoots) {
        if (Test-IsUnderPath $allowedRoot $resolvedPath) {
            $isAllowed = $true
            break
        }
    }
    if (-not $isAllowed) {
        Add-Violation 'Context handoff must be saved under docs/ or plans/ for repository-durable review.'
        return
    }

    try {
        $text = Read-StrictUtf8 $resolvedPath
        foreach ($fragment in @('## Goal', '## Current State', '## Tests', '## Remaining Work', 'Next concrete action')) {
            if (-not $text.Contains($fragment)) {
                Add-Violation "Context handoff is missing required section or marker: $fragment"
            }
        }
    }
    catch {
        Add-Violation "Context handoff could not be read as strict UTF-8: $Path"
    }
}

try {
    $Root = Get-RepositoryRoot $RepositoryRoot
}
catch {
    Write-Output "ERROR: $($_.Exception.Message)"
    exit 1
}

if (-not [IO.Directory]::Exists($Root)) {
    Write-Output "ERROR: Repository root does not exist: $Root"
    exit 1
}

if ($ThresholdPercent -lt 1 -or $ThresholdPercent -gt 100) {
    Add-Violation 'ThresholdPercent must be between 1 and 100.'
}

if ($ProactiveHandoffPercent -lt 1 -or $ProactiveHandoffPercent -gt 100) {
    Add-Violation 'ProactiveHandoffPercent must be between 1 and 100.'
}
elseif ($ProactiveHandoffPercent -gt $ThresholdPercent) {
    Add-Violation 'ProactiveHandoffPercent must be less than or equal to ThresholdPercent.'
}

if ($ContextUsagePercent -lt 0 -and -not [string]::IsNullOrWhiteSpace($env:SPIRO_CONTEXT_USAGE_PERCENT)) {
    $parsedContextUsage = 0
    if ([int]::TryParse($env:SPIRO_CONTEXT_USAGE_PERCENT, [ref]$parsedContextUsage)) {
        $ContextUsagePercent = $parsedContextUsage
    }
    else {
        Add-Violation 'SPIRO_CONTEXT_USAGE_PERCENT must be an integer from 0 to 100 when set.'
    }
}

if ($ContextUsagePercent -gt 100) {
    Add-Violation 'ContextUsagePercent must be between 0 and 100.'
}

if ([string]::IsNullOrWhiteSpace($HandoffPath) -and -not [string]::IsNullOrWhiteSpace($env:SPIRO_CONTEXT_HANDOFF_PATH)) {
    $HandoffPath = $env:SPIRO_CONTEXT_HANDOFF_PATH
}

Assert-RequiredText '.codex\skills\context-handoff\SKILL.md' @(
    'Context Budget Trigger',
    '70% context usage',
    '80% context usage',
    'check-context-budget.ps1'
)
Assert-RequiredText '.codex\skills\worktree-tdd\SKILL.md' @(
    'Test Deduplication',
    'Gate Classes',
    'External Architecture References'
)
Assert-RequiredText '.codex\skills\review-ship\SKILL.md' @(
    'Pre-Commit Optimization',
    'Test Review',
    'Stage-End Learning'
)
Assert-RequiredText 'plans\v35-execution-status-and-next-slices.md' @(
    '70% context usage',
    '80% context usage',
    'fewer duplicate tests',
    'quality-preserving test budget'
)
Assert-RequiredText 'docs\project-hooks.md' @(
    'check-context-budget.ps1',
    'SPIRO_CONTEXT_USAGE_PERCENT',
    'SPIRO_CONTEXT_HANDOFF_PATH'
)

if ($ContextUsagePercent -ge $ThresholdPercent) {
    if ([string]::IsNullOrWhiteSpace($HandoffPath)) {
        Add-Violation "Context usage is at or above $ThresholdPercent%; pass -HandoffPath or set SPIRO_CONTEXT_HANDOFF_PATH before continuing."
    }
    else {
        Assert-HandoffFile $HandoffPath
    }
}

if ($Violations.Count -gt 0) {
    foreach ($violation in $Violations) {
        Write-Output "ERROR: $violation"
    }
    exit 1
}

if ($ContextUsagePercent -ge $ThresholdPercent) {
    Write-Output "PASS: context budget handoff gate passed at $ContextUsagePercent%."
}
elseif ($ContextUsagePercent -ge $ProactiveHandoffPercent) {
    Write-Output "WARN: context usage $ContextUsagePercent% reached proactive handoff band $ProactiveHandoffPercent%; save or refresh a concise handoff before the hard $ThresholdPercent% gate."
    Write-Output "PASS: context usage $ContextUsagePercent% is below hard threshold $ThresholdPercent%; static context-budget hook checks passed."
}
elseif ($ContextUsagePercent -ge 0) {
    Write-Output "PASS: context usage $ContextUsagePercent% is below threshold $ThresholdPercent%; static context-budget hook checks passed."
}
else {
    Write-Output 'PASS: static context-budget hook checks passed; no context usage percentage supplied.'
}
exit 0
