[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$RepositoryRoot,
    [string]$WorkingDirectory,
    [string]$VsInstallationPath,
    [ValidateSet('x64', 'x86', 'arm64')]
    [string]$Arch = 'x64',
    [ValidateSet('x64', 'x86', 'arm64')]
    [string]$HostArch = 'x64',
    [string]$CommandName = 'cargo.exe',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArguments
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

function Resolve-PathUnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $Root
    }
    $candidate = $Path
    if (-not [IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $Root $candidate
    }
    $resolved = [IO.Path]::GetFullPath($candidate)
    $normalizedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved -ne [IO.Path]::GetFullPath($Root) -and
        -not $resolved.StartsWith($normalizedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "WorkingDirectory is outside repository root: $Path"
    }
    if (-not [IO.Directory]::Exists($resolved)) {
        throw "WorkingDirectory does not exist: $resolved"
    }
    return $resolved
}

function Get-VsWherePath {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft Visual Studio\Installer\vswhere.exe')
    )
    foreach ($candidate in $candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and [IO.File]::Exists($candidate)) {
            return $candidate
        }
    }
    throw 'vswhere.exe was not found. Install Visual Studio Build Tools with the C++ toolchain.'
}

function Resolve-VisualStudioInstallation {
    param([string]$RequestedInstallationPath)

    if (-not [string]::IsNullOrWhiteSpace($RequestedInstallationPath)) {
        $resolved = [IO.Path]::GetFullPath($RequestedInstallationPath)
        if (-not [IO.Directory]::Exists($resolved)) {
            throw "Visual Studio installation path does not exist: $resolved"
        }
        return $resolved
    }

    $vswhere = Get-VsWherePath
    $installationPath = & $vswhere `
        -latest `
        -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
        -property installationPath
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($installationPath | Select-Object -First 1))) {
        throw 'Visual Studio Build Tools with the C++ toolchain were not found.'
    }
    return [IO.Path]::GetFullPath(($installationPath | Select-Object -First 1))
}

function Import-VisualStudioDeveloperEnvironment {
    param(
        [Parameter(Mandatory = $true)][string]$InstallationPath,
        [Parameter(Mandatory = $true)][string]$TargetArch,
        [Parameter(Mandatory = $true)][string]$TargetHostArch
    )

    $vsDevCmd = Join-Path $InstallationPath 'Common7\Tools\VsDevCmd.bat'
    if (-not [IO.File]::Exists($vsDevCmd)) {
        throw "VsDevCmd.bat was not found under Visual Studio installation: $InstallationPath"
    }

    $cmdLine = "`"$vsDevCmd`" -arch=$TargetArch -host_arch=$TargetHostArch >nul && set"
    $envLines = & $env:ComSpec @('/s', '/c', $cmdLine)
    if ($LASTEXITCODE -ne 0) {
        throw "VsDevCmd.bat failed with exit code $LASTEXITCODE"
    }
    foreach ($line in $envLines) {
        $parts = [string]$line -split '=', 2
        if ($parts.Count -ne 2 -or [string]::IsNullOrWhiteSpace($parts[0])) {
            continue
        }
        if ($parts[0] -ieq 'PATH') {
            Set-Item -Path Env:Path -Value $parts[1]
            continue
        }
        Set-Item -Path ("Env:{0}" -f $parts[0]) -Value $parts[1]
    }
}

function Resolve-MsvcLinkPath {
    param(
        [Parameter(Mandatory = $true)][string]$InstallationPath,
        [Parameter(Mandatory = $true)][string]$TargetArch,
        [Parameter(Mandatory = $true)][string]$TargetHostArch
    )

    $toolRoot = $env:VCToolsInstallDir
    if ([string]::IsNullOrWhiteSpace($toolRoot)) {
        $msvcRoot = Join-Path $InstallationPath 'VC\Tools\MSVC'
        if ([IO.Directory]::Exists($msvcRoot)) {
            $toolRoot = Get-ChildItem -LiteralPath $msvcRoot -Directory |
                Sort-Object -Property Name -Descending |
                Select-Object -First 1 -ExpandProperty FullName
        }
    }
    if ([string]::IsNullOrWhiteSpace($toolRoot)) {
        throw "Unable to resolve VCToolsInstallDir under Visual Studio installation: $InstallationPath"
    }

    $candidate = Join-Path $toolRoot ("bin\Host{0}\{1}\link.exe" -f $TargetHostArch, $TargetArch)
    if (-not [IO.File]::Exists($candidate)) {
        throw "MSVC link.exe was not found at expected path: $candidate"
    }
    return [IO.Path]::GetFullPath($candidate)
}

$Root = Get-RepositoryRoot $RepositoryRoot
$CargoWorkingDirectory = Resolve-PathUnderRoot $Root $WorkingDirectory
$VsInstall = Resolve-VisualStudioInstallation $VsInstallationPath
Import-VisualStudioDeveloperEnvironment $VsInstall $Arch $HostArch
$MsvcLinkPath = Resolve-MsvcLinkPath $VsInstall $Arch $HostArch
$MsvcLinkDirectory = Split-Path -Parent $MsvcLinkPath
if (-not (($env:Path -split ';') -contains $MsvcLinkDirectory)) {
    $env:Path = "$MsvcLinkDirectory;$env:Path"
}

if ($CommandArguments.Count -eq 0) {
    $CommandArguments = @('--version')
}

Set-Location $CargoWorkingDirectory
if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
    throw "Command was not found after importing the Visual Studio developer environment: $CommandName"
}
Write-Output "INFO: using Visual Studio environment: $VsInstall"
Write-Output "INFO: command working directory: $CargoWorkingDirectory"
Write-Output "INFO: command: $CommandName"
& $CommandName @CommandArguments
exit $LASTEXITCODE
