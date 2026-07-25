[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$CheckerPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\scripts\check-agent-hygiene.ps1'))

if (-not [IO.File]::Exists($CheckerPath)) {
    Write-Error "Checker script not found: $CheckerPath"
    exit 1
}

$Utf8NoBom = New-Object Text.UTF8Encoding($false)
$PowerShellPath = (Get-Process -Id $PID).Path
$TempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$SuiteRoot = Join-Path $TempRoot ("agent-hygiene-test-{0}" -f [guid]::NewGuid().ToString('N'))
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

    Set-Utf8File (Join-Path $root '.gitignore') ".qoder/`n"
    Set-Utf8File (Join-Path $root 'reasonix.toml') "[skills]`npaths = [`".codex/skills`"]`n"
    Set-Utf8File (Join-Path $root '.githooks\pre-commit') @'
#!/bin/sh
repo_root=$(git rev-parse --show-toplevel)
exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$repo_root/scripts/check-agent-hygiene.ps1" -RepositoryRoot "$repo_root"
'@
    Set-Utf8File (Join-Path $root 'scripts\check-context-budget.ps1') @'
[CmdletBinding()]
param([string]$RepositoryRoot)
Write-Output 'PASS: context budget hook fixture passed.'
exit 0
'@
    Set-Utf8File (Join-Path $root 'AGENTS.md') "# Agents`n"
    Set-Utf8File (Join-Path $root 'CLAUDE.md') "# Claude`nUse a milestone gate, then targeted reverification for bounded review fixes.`n"
    Set-Utf8File (Join-Path $root 'docs\agent-collaboration-governance.md') "# Governance`nUse broad gates as milestone evidence and report verification scope.`n"
    Set-Utf8File (Join-Path $root 'docs\ai-collaboration-instruction-templates.md') "# Templates`n"
    Set-Utf8File (Join-Path $root 'docs\project-hooks.md') "# Project Hooks`nUse check-context-budget.ps1 with SPIRO_CONTEXT_USAGE_PERCENT and SPIRO_CONTEXT_HANDOFF_PATH.`n"
    Set-Utf8File (Join-Path $root 'plans\v35-execution-status-and-next-slices.md') "# V35`nOperational addendum: roughly 80% context usage requires fewer duplicate tests and a quality-preserving test budget.`n"
    Set-Utf8File (Join-Path $root '.codex\skills\example\SKILL.md') "---`nname: example`ndescription: Example skill`n---`n"
    Set-Utf8File (Join-Path $root '.codex\skills\example\agents\openai.yaml') "interface:`n  display_name: Example`n"
    Set-Utf8File (Join-Path $root '.codex\skills\context-handoff\SKILL.md') "---`nname: context-handoff`ndescription: Context handoff skill`n---`n# Context Handoff`n## Context Budget Trigger`nAt 80% context usage, run check-context-budget.ps1.`n"
    Set-Utf8File (Join-Path $root '.codex\skills\context-handoff\agents\openai.yaml') "interface:`n  display_name: Context Handoff`n"
    Set-Utf8File (Join-Path $root '.codex\skills\review-ship\SKILL.md') "---`nname: review-ship`ndescription: Review ship skill`n---`n# Review Ship`nUse targeted reverification.`n## Review-Fix Verification Record`n"
    Set-Utf8File (Join-Path $root '.codex\skills\review-ship\agents\openai.yaml') "interface:`n  display_name: Review Ship`n"
    Set-Utf8File (Join-Path $root '.codex\skills\worktree-tdd\SKILL.md') "---`nname: worktree-tdd`ndescription: Worktree TDD skill`n---`n## Targeted Reverification`n"
    Set-Utf8File (Join-Path $root '.codex\skills\worktree-tdd\agents\openai.yaml') "interface:`n  display_name: Worktree TDD`n"
    Set-Utf8File (Join-Path $root '.codex\skills\codebase-memory-mcp\SKILL.md') "---`nname: codebase-memory-mcp`ndescription: Codebase memory skill`n---`n## Discovery Budget`n"
    Set-Utf8File (Join-Path $root '.codex\skills\codebase-memory-mcp\agents\openai.yaml') "interface:`n  display_name: Codebase Memory`n"
    Set-Utf8File (Join-Path $root '.codex\skills\contract-debugging\SKILL.md') "---`nname: contract-debugging`ndescription: Contract debugging skill`n---`n## Failure Triage Budget`n"
    Set-Utf8File (Join-Path $root '.codex\skills\contract-debugging\agents\openai.yaml') "interface:`n  display_name: Contract Debugging`n"
    Set-Utf8File (Join-Path $root '.codex\skills\artifact-validation\SKILL.md') "---`nname: artifact-validation`ndescription: Artifact validation skill`n---`n## Validation Matrix`n"
    Set-Utf8File (Join-Path $root '.codex\skills\artifact-validation\agents\openai.yaml') "interface:`n  display_name: Artifact Validation`n"
    Set-Utf8File (Join-Path $root '.qoder\local-only.txt') "local state`n"

    $gitOutput = & git -C $root init --quiet 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git init failed for fixture '$Name': $($gitOutput -join [Environment]::NewLine)"
    }

    $gitOutput = & git -C $root config core.hooksPath .githooks 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git config core.hooksPath failed for fixture '$Name': $($gitOutput -join [Environment]::NewLine)"
    }

    return $root
}

function Invoke-Checker {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $output = & $script:PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $script:CheckerPath -RepositoryRoot $RepositoryRoot 2>&1
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
    Assert-Contains $result.Output 'context budget hook fixture passed' 'Clean fixture did not show context-budget hook execution.'
    Assert-True (-not $result.Output.Contains('ERROR:')) "Clean fixture emitted an ERROR line:`n$($result.Output)"
    Write-Output 'PASS: clean repository'

    $uvLock = New-CleanFixture 'uv-lock'
    Set-Utf8File (Join-Path $uvLock 'uv.lock') "generated`n"
    Assert-Failure (Invoke-Checker $uvLock) 'uv.lock' 'uv.lock fixture'
    Write-Output 'PASS: uv.lock is rejected'

    $qoderIgnore = New-CleanFixture 'qoder-ignore'
    Set-Utf8File (Join-Path $qoderIgnore '.gitignore') ".qoder/*`n"
    Assert-Failure (Invoke-Checker $qoderIgnore) '.qoder/' 'qoder ignore fixture'
    Write-Output 'PASS: missing exact .qoder ignore rule is rejected'

    $qoderTracked = New-CleanFixture 'qoder-tracked'
    $gitOutput = & git -c core.autocrlf=false -C $qoderTracked add -f -- '.qoder/local-only.txt' 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git add failed for tracked .qoder fixture: $($gitOutput -join [Environment]::NewLine)"
    }
    Assert-Failure (Invoke-Checker $qoderTracked) 'tracked' 'tracked qoder fixture'
    Write-Output 'PASS: tracked .qoder content is rejected'

    $skill = New-CleanFixture 'skill-frontmatter'
    Set-Utf8File (Join-Path $skill '.codex\skills\example\SKILL.md') "---`nname: wrong-name`n---`n"
    $result = Invoke-Checker $skill
    Assert-Failure $result 'description' 'skill frontmatter fixture'
    Assert-Contains $result.Output 'wrong-name' 'Skill name mismatch was not reported.'
    Write-Output 'PASS: invalid skill frontmatter is rejected'

    $reasonix = New-CleanFixture 'reasonix-route'
    Set-Utf8File (Join-Path $reasonix 'reasonix.toml') "[skills]`npaths = [`".codex/skills`", `".reasonix/skills`"]`n"
    Assert-Failure (Invoke-Checker $reasonix) 'reasonix.toml' 'Reasonix route fixture'
    Write-Output 'PASS: invalid Reasonix skill route is rejected'

    $invalidUtf8 = New-CleanFixture 'invalid-utf8'
    [IO.File]::WriteAllBytes((Join-Path $invalidUtf8 'CLAUDE.md'), [byte[]](0x43, 0xC3, 0x28))
    Assert-Failure (Invoke-Checker $invalidUtf8) 'UTF-8' 'invalid UTF-8 fixture'
    Write-Output 'PASS: invalid UTF-8 governance file is rejected'

    $guardrail = New-CleanFixture 'process-guardrail'
    Set-Utf8File (Join-Path $guardrail 'CLAUDE.md') "# Claude`nUse a milestone gate only.`n"
    Assert-Failure (Invoke-Checker $guardrail) 'targeted reverification' 'process guardrail fixture'
    Write-Output 'PASS: missing process guardrail text is rejected'

    $hookPath = New-CleanFixture 'hook-path'
    $gitOutput = & git -C $hookPath config --unset core.hooksPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git config --unset core.hooksPath failed for fixture: $($gitOutput -join [Environment]::NewLine)"
    }
    Assert-Failure (Invoke-Checker $hookPath) 'core.hooksPath' 'hook path fixture'
    Write-Output 'PASS: missing Git hooksPath config is rejected'

    $contextBudgetHook = New-CleanFixture 'context-budget-hook'
    Set-Utf8File (Join-Path $contextBudgetHook 'scripts\check-context-budget.ps1') @'
[CmdletBinding()]
param([string]$RepositoryRoot)
Write-Output 'ERROR: context budget hook was executed.'
exit 1
'@
    Assert-Failure (Invoke-Checker $contextBudgetHook) 'context budget hook was executed' 'context budget hook fixture'
    Write-Output 'PASS: context budget hook failures are rejected'

    Write-Output 'PASS: all agent hygiene checker tests passed'
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
