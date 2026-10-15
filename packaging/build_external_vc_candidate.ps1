[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [Parameter(Mandatory=$true)][string]$PayloadManifest,
    [Parameter(Mandatory=$true)][string]$LauncherPath,
    [Parameter(Mandatory=$true)][string]$CompilerPath,
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [string[]]$PredecessorIdentity = @(),
    [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$OutputBaseName = 'Fieltra-1.0.0-Setup'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = [IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $output) { throw 'Fresh external-runtime candidate output required; no overwrite or automatic retry' }
$ancestor = Split-Path -Parent $output
while ($ancestor) {
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse output ancestor refused'
    }
    $ancestor = Split-Path -Parent $ancestor
}
if ((Get-FileHash -LiteralPath $CompilerPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    '0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7') {
    throw 'Candidate compiler differs from the retained qualified Inno Setup compiler'
}
New-Item -ItemType Directory -Path $output | Out-Null
$layout = Join-Path $output 'install-layout'
$receiptPath = Join-Path $output 'layout-receipt.json'
& $PythonPath -B (Join-Path $PSScriptRoot 'external_vc_layout.py') --payload $PayloadDir --launcher $LauncherPath --output $layout --expected-manifest $PayloadManifest --receipt $receiptPath *> (Join-Path $output 'layout.log')
if ($LASTEXITCODE -ne 0) { throw 'External launcher layout validation failed; preserve and stop' }
$identityPath = Join-Path $output 'build-identity.json'
$identityArgs = @('--layout-receipt', $receiptPath, '--output', $identityPath, '--version', (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'windows-rc.json') -Raw | ConvertFrom-Json).version, '--compiler', $CompilerPath)
foreach ($predecessor in $PredecessorIdentity) { $identityArgs += @('--predecessor', $predecessor) }
& $PythonPath -B (Join-Path $PSScriptRoot 'installer_identity.py') @identityArgs *> (Join-Path $output 'identity.log')
if ($LASTEXITCODE -ne 0) { throw 'Build identity generation failed; preserve and stop' }
$installerOutput = Join-Path $output 'installer'
New-Item -ItemType Directory -Path $installerOutput | Out-Null
& $CompilerPath "/O$installerOutput" "/F$OutputBaseName" "/DMyAppSourceDir=$(Join-Path $layout 'engine')" "/DMyLauncherPath=$(Join-Path $layout 'Fieltra.exe')" "/DMyPrerequisiteMode=external-launch" "/DMyBuildIdentityFile=$([IO.Path]::ChangeExtension($identityPath, '.iss'))" (Join-Path $repoRoot 'installer\MastixaManager.iss') *> (Join-Path $output 'compiler.log')
$code = $LASTEXITCODE
if ($code -ne 0) { throw "Inno compile failed ($code); preserve diagnostics; do not retry automatically" }
$setup = Join-Path $installerOutput ($OutputBaseName + '.exe')
$receipt = [ordered]@{
    mode='external-launch';installer=$setup;size=(Get-Item -LiteralPath $setup).Length
    sha256=(Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
    build_identity=(Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json).id
    installed_payload_logical_bytes=(Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json).logical_installed_payload_bytes
    supplied_payload_copied_unchanged=$true;installer_or_launcher_executed=$false
    redist_bundled=$false;redist_downloaded_or_executed=$false;native_install_validation='NOT TESTED'
}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'candidate-receipt.json') -Encoding utf8
$receipt | ConvertTo-Json
