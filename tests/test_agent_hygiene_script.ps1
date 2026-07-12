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
    Set-Utf8File (Join-Path $root 'AGENTS.md') "# Agents`n"
    Set-Utf8File (Join-Path $root 'CLAUDE.md') "# Claude`n"
    Set-Utf8File (Join-Path $root 'docs\agent-collaboration-governance.md') "# Governance`n"
    Set-Utf8File (Join-Path $root 'docs\ai-collaboration-instruction-templates.md') "# Templates`n"
    Set-Utf8File (Join-Path $root '.codex\skills\example\SKILL.md') "---`nname: example`ndescription: Example skill`n---`n"
    Set-Utf8File (Join-Path $root '.codex\skills\example\agents\openai.yaml') "interface:`n  display_name: Example`n"
    Set-Utf8File (Join-Path $root '.qoder\local-only.txt') "local state`n"

    $gitOutput = & git -C $root init --quiet 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git init failed for fixture '$Name': $($gitOutput -join [Environment]::NewLine)"
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
