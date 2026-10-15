# SPDX-License-Identifier: AGPL-3.0-only
# Manual guest build. Reuses the existing qualified suppliers and build venv.
[CmdletBinding()]
param(
    [switch]$ConfirmGuestBuild,
    [string]$CompilerPath = 'C:\FieltraInno\ISCC.exe',
    [string]$InnoInputDir = 'C:\FieltraInnoInput',
    [string]$InnoSignatureDir = 'C:\FieltraInnoSignatures',
    [string]$VCToolsDir = '',
    [string]$WindowsSdkDir = '',
    [string]$ReuseLauncherPath = '',
    [string]$PredecessorIdentity = '',
    [string]$WindowsSdkVersion = '10.0.26100.0',
    [string]$OutputDir = 'C:\FieltraOutput',
    [ValidatePattern('^$|^[0-9a-f]{40}$')][string]$SourceCommit = ''
)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmGuestBuild -or $env:USERNAME -ine 'WDAGUtilityAccount' -or
    $env:USERPROFILE -notmatch '(?i)\\WDAGUtilityAccount$' -or
    -not [Environment]::Is64BitProcess) {
    throw 'Run manually in 64-bit Windows Sandbox with -ConfirmGuestBuild. Never build on the host.'
}
$repo = Split-Path -Parent $PSScriptRoot
$output = [IO.Path]::GetFullPath($OutputDir).TrimEnd('\')
if (Test-Path -LiteralPath $output) { throw 'Fresh output required. Preserve previous results; no automatic retry.' }
$config = Get-Content (Join-Path $PSScriptRoot 'windows-rc.json') -Raw | ConvertFrom-Json
if ($config.product -cne 'Fieltra' -or $config.version -cne '1.0.0' -or $config.channel -cne 'stable') {
    throw 'Expected Fieltra 1.0.0 stable source.'
}
$lock = Get-Content (Join-Path $PSScriptRoot 'windows-tls-inputs.json') -Raw | ConvertFrom-Json
$python = [IO.Path]::GetFullPath((Join-Path $repo ($lock.python.build_venv + '\Scripts\python.exe')))
if (-not (Test-Path -LiteralPath $CompilerPath)) {
    # The retained offline compiler and accepted signatures are separate inputs.
    # Assemble them only in this disposable guest; no dependency rebuild.
    $innoDir = Split-Path -Parent $CompilerPath
    if (Test-Path -LiteralPath $innoDir) { throw 'Incomplete existing Inno directory; preserve it and stop.' }
    foreach ($dir in @($InnoInputDir, $InnoSignatureDir)) {
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) { throw "Missing retained input: $dir" }
    }
    [IO.Directory]::CreateDirectory($innoDir) | Out-Null
    Get-ChildItem -LiteralPath $InnoInputDir -File | Copy-Item -Destination $innoDir
    Get-ChildItem -LiteralPath $InnoSignatureDir -File | Copy-Item -Destination $innoDir
}
$requiredInputs = @($python, $CompilerPath)
if ($ReuseLauncherPath) {
    $requiredInputs += $ReuseLauncherPath
} else {
    if (-not $VCToolsDir -or -not $WindowsSdkDir) { throw 'Pass compiler/SDK paths when building a new launcher.' }
    $requiredInputs += (Join-Path $VCToolsDir 'bin\Hostx64\x64\cl.exe'), (Join-Path $WindowsSdkDir "bin\$WindowsSdkVersion\x64\rc.exe")
}
if ($PredecessorIdentity) { $requiredInputs += $PredecessorIdentity }
foreach ($path in $requiredInputs) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing existing build input: $path" }
}
if ((Get-FileHash -LiteralPath $CompilerPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    '0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7') {
    throw 'Use the accepted Inno Setup 6.7.3 compiler and its complete signature supplement.'
}
[IO.Directory]::CreateDirectory($output) | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:MASTIXA_DATA_HOME = Join-Path $output 'SyntheticProfile'

function Invoke-GuestProcess([string]$Name, [string]$Executable, [string[]]$Arguments, [string]$Directory) {
    # OS stream redirection preserves normal PyInstaller stderr in PowerShell 5.1.
    $quoted = foreach ($arg in $Arguments) {
        if ($arg -match '["\r\n]') { throw 'Invalid process argument' }
        '"' + [regex]::Replace($arg, '(\\+)$', '$1$1') + '"'
    }
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $Executable
    $info.Arguments = $quoted -join ' '
    $info.WorkingDirectory = $Directory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    $stdout = $null; $stderr = $null
    try {
        $stdout = [IO.File]::Open((Join-Path $output "$Name.stdout.log"), [IO.FileMode]::CreateNew)
        $stderr = [IO.File]::Open((Join-Path $output "$Name.stderr.log"), [IO.FileMode]::CreateNew)
        if (-not $process.Start()) { throw "$Name did not start" }
        $outTask = $process.StandardOutput.BaseStream.CopyToAsync($stdout)
        $errTask = $process.StandardError.BaseStream.CopyToAsync($stderr)
        $process.WaitForExit()
        $outTask.GetAwaiter().GetResult()
        $errTask.GetAwaiter().GetResult()
        $code = $process.ExitCode
    } finally {
        if ($stdout) { $stdout.Dispose() }
        if ($stderr) { $stderr.Dispose() }
        $process.Dispose()
    }
    if ($null -eq $code -or $code -ne 0) { throw "$Name failed ($code). Keep logs in $output and stop; no retry." }
}
$shell = Join-Path $PSHOME 'powershell.exe'
$dist = Join-Path $output 'Dist'
Write-Host 'Building the changed application once, using existing qualified dependencies...'
Invoke-GuestProcess 'application' $shell @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'RemoteSigned',
    '-File', (Join-Path $PSScriptRoot 'build_release.ps1'), '-SkipInstaller', '-PythonPath', $python,
    '-PyInstallerWorkPath', (Join-Path $output 'Work'), '-PyInstallerDistPath', $dist) $repo
$payload = Join-Path $dist 'Fieltra'
if ($ReuseLauncherPath) {
    $launcher = (Resolve-Path -LiteralPath $ReuseLauncherPath).Path
    Write-Host 'Reusing the existing Fieltra launcher unchanged.'
} else {
    $launcherDir = Join-Path $output 'Launcher'
    Write-Host 'Building the changed first-party launcher once...'
    Invoke-GuestProcess 'launcher' $shell @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'RemoteSigned',
        '-File', (Join-Path $PSScriptRoot 'build_windows_launcher.ps1'), '-OutputDir', $launcherDir,
        '-VCToolsDir', $VCToolsDir, '-WindowsSdkDir', $WindowsSdkDir, '-WindowsSdkVersion', $WindowsSdkVersion) $repo
    $launcher = Join-Path $launcherDir 'Fieltra.exe'
    Invoke-GuestProcess 'launcher-audit' $python @('-B', (Join-Path $PSScriptRoot 'launcher_audit.py'), $launcher) $repo
}
$identity = Join-Path $output 'build-identity.json'
$identityArgs = @('-B', (Join-Path $PSScriptRoot 'installer_identity.py'),
    '--payload', $payload, '--launcher', $launcher, '--compiler', $CompilerPath,
    '--version', '1.0.0', '--output', $identity)
if ($PredecessorIdentity) { $identityArgs += '--predecessor', $PredecessorIdentity }
Invoke-GuestProcess 'identity' $python $identityArgs $repo
Write-Host 'Compiling the final installer once...'
Invoke-GuestProcess 'installer' $CompilerPath @("/O$output", '/FFieltra-1.0.0-Setup',
    "/DMyAppSourceDir=$payload", "/DMyLauncherPath=$launcher", '/DMyPrerequisiteMode=external-launch',
    "/DMyBuildIdentityFile=$([IO.Path]::ChangeExtension($identity, '.iss'))",
    (Join-Path $repo 'installer\MastixaManager.iss')) (Join-Path $repo 'installer')
$setup = Join-Path $output 'Fieltra-1.0.0-Setup.exe'
foreach ($path in @($setup, $launcher, (Join-Path $payload 'Fieltra.exe'))) {
    $info = [Diagnostics.FileVersionInfo]::GetVersionInfo($path)
    if ($info.ProductName.Trim() -cne 'Fieltra' -or $info.ProductVersion.Trim() -ne '1.0.0' -or
        $info.FileMajorPart -ne 1 -or $info.FileMinorPart -ne 0 -or
        $info.FileBuildPart -ne 0 -or $info.FilePrivatePart -ne 0) {
        throw "Final product/version metadata disagrees: $path"
    }
}
$hash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $output 'SHA256SUMS.txt'), "$hash  Fieltra-1.0.0-Setup.exe`r`n", [Text.Encoding]::ASCII)
[ordered]@{
    product='Fieltra';version='1.0.0';channel='stable';installer='Fieltra-1.0.0-Setup.exe'
    size=(Get-Item -LiteralPath $setup).Length;sha256=$hash
    source_commit=$(if ($SourceCommit) { $SourceCommit } else { $null })
    source_binding=$(if ($SourceCommit) { 'Owner-supplied commit; matching source review required' } else { 'Pending owner-approved source commit' })
    guest_installation='NOT TESTED';guest_launch='NOT TESTED';publication_authorized=$false
} | ConvertTo-Json | Set-Content (Join-Path $output 'RELEASE_BUILD.json') -Encoding UTF8
Write-Host "BUILD COMPLETE: $setup"
Write-Host "SHA-256: $hash"
Write-Host 'Next: install and open Fieltra manually INSIDE Sandbox. Verify Dashboard, title and About 1.0.0.'
Write-Host 'Export the installer, SHA256SUMS.txt and RELEASE_BUILD.json before closing Sandbox. No publication is authorized.'
