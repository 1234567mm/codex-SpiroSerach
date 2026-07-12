[CmdletBinding()]
param(
    [string]$RepositoryRoot
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

if ([IO.File]::Exists((Join-Path $Root 'uv.lock'))) {
    Add-Violation 'uv.lock must not exist at the repository root.'
}

$gitignorePath = Join-Path $Root '.gitignore'
if (-not [IO.File]::Exists($gitignorePath)) {
    Add-Violation '.gitignore is missing the exact .qoder/ ignore rule.'
}
else {
    try {
        $gitignoreLines = [IO.File]::ReadAllLines($gitignorePath)
        if (-not ($gitignoreLines -ccontains '.qoder/')) {
            Add-Violation '.gitignore is missing the exact .qoder/ ignore rule.'
        }
    }
    catch {
        Add-Violation '.gitignore could not be read.'
    }
}

$trackedQoder = @(& git -C $Root ls-files -- '.qoder/*' 2>$null)
if ($LASTEXITCODE -ne 0) {
    Add-Violation 'Git could not inspect tracked .qoder content.'
}
elseif ($trackedQoder.Count -gt 0) {
    Add-Violation 'Git-tracked files exist under .qoder; local .qoder content must remain untracked.'
}

$skillsRoot = Join-Path $Root '.codex\skills'
if (-not [IO.Directory]::Exists($skillsRoot)) {
    Add-Violation '.codex/skills is missing.'
}
else {
    $skillDirectories = @([IO.Directory]::GetDirectories($skillsRoot))
    if ($skillDirectories.Count -eq 0) {
        Add-Violation '.codex/skills contains no skill directories.'
    }

    foreach ($skillDirectory in $skillDirectories) {
        $skillName = [IO.Path]::GetFileName($skillDirectory)
        $skillPath = Join-Path $skillDirectory 'SKILL.md'
        $openAiAgentPath = Join-Path $skillDirectory 'agents\openai.yaml'

        if (-not [IO.File]::Exists($skillPath)) {
            Add-Violation ".codex/skills/$skillName/SKILL.md is missing."
        }
        else {
            try {
                $skillText = Read-StrictUtf8 $skillPath
                $lines = [regex]::Split($skillText, "\r?\n")
                $frontmatterEnd = -1

                if ($lines.Count -gt 0 -and $lines[0] -ceq '---') {
                    for ($lineIndex = 1; $lineIndex -lt $lines.Count; $lineIndex++) {
                        if ($lines[$lineIndex] -ceq '---') {
                            $frontmatterEnd = $lineIndex
                            break
                        }
                    }
                }

                if ($frontmatterEnd -lt 1) {
                    Add-Violation ".codex/skills/$skillName/SKILL.md has no valid YAML frontmatter."
                }
                else {
                    $frontmatter = [string]::Join("`n", $lines[1..($frontmatterEnd - 1)])
                    $nameMatch = [regex]::Match($frontmatter, '(?m)^name:\s*(?<value>.*?)\s*$')
                    $descriptionMatch = [regex]::Match($frontmatter, '(?m)^description:\s*(?<value>.*?)\s*$')

                    if (-not $nameMatch.Success -or [string]::IsNullOrWhiteSpace($nameMatch.Groups['value'].Value)) {
                        Add-Violation ".codex/skills/$skillName/SKILL.md frontmatter is missing name."
                    }
                    else {
                        $declaredName = $nameMatch.Groups['value'].Value.Trim().Trim('"', "'")
                        if ($declaredName -cne $skillName) {
                            Add-Violation ".codex/skills/$skillName/SKILL.md name '$declaredName' does not match directory '$skillName'."
                        }
                    }

                    if (-not $descriptionMatch.Success -or [string]::IsNullOrWhiteSpace($descriptionMatch.Groups['value'].Value)) {
                        Add-Violation ".codex/skills/$skillName/SKILL.md frontmatter is missing description."
                    }
                }
            }
            catch {
                Add-Violation ".codex/skills/$skillName/SKILL.md could not be read as strict UTF-8."
            }
        }

        if (-not [IO.File]::Exists($openAiAgentPath)) {
            Add-Violation ".codex/skills/$skillName/agents/openai.yaml is missing."
        }
    }
}

$reasonixPath = Join-Path $Root 'reasonix.toml'
if (-not [IO.File]::Exists($reasonixPath)) {
    Add-Violation 'reasonix.toml is missing or does not route skills only through .codex/skills.'
}
else {
    try {
        $reasonixText = Read-StrictUtf8 $reasonixPath
        $skillsSection = [regex]::Match($reasonixText, '(?ms)^\s*\[skills\]\s*(?<body>.*?)(?=^\s*\[|\z)')
        $validRoute = $false

        if ($skillsSection.Success) {
            $pathsMatch = [regex]::Match($skillsSection.Groups['body'].Value, '(?ms)^\s*paths\s*=\s*\[(?<items>.*?)\]')
            if ($pathsMatch.Success) {
                $validRoute = [regex]::IsMatch($pathsMatch.Groups['items'].Value, '^\s*["'']\.codex/skills["'']\s*$')
            }
        }

        if (-not $validRoute) {
            Add-Violation 'reasonix.toml [skills] paths must contain only .codex/skills (no .reasonix/skills or user-global skill path).'
        }
    }
    catch {
        Add-Violation 'reasonix.toml could not be read or validated.'
    }
}

$governanceFiles = @(
    'AGENTS.md',
    'CLAUDE.md',
    'docs\agent-collaboration-governance.md',
    'docs\ai-collaboration-instruction-templates.md'
)

foreach ($relativePath in $governanceFiles) {
    $fullPath = Join-Path $Root $relativePath
    $displayPath = $relativePath.Replace('\', '/')

    if (-not [IO.File]::Exists($fullPath)) {
        Add-Violation "$displayPath is missing."
        continue
    }

    try {
        [void](Read-StrictUtf8 $fullPath)
    }
    catch {
        Add-Violation "$displayPath cannot be decoded as strict UTF-8."
    }
}

if ($Violations.Count -gt 0) {
    foreach ($violation in $Violations) {
        Write-Output "ERROR: $violation"
    }
    exit 1
}

Write-Output 'PASS: repository agent hygiene checks passed.'
exit 0
