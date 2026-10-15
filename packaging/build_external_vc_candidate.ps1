# SPDX-License-Identifier: AGPL-3.0-only
# NEW implementation, reviewed 2026-10-15. Not the missing historical builder.
# Adapted from the retained 3,714-byte builder (SHA-256
# 57fb14e0b2c1bf651db758cf26afc1176bcf108f120915d4c23ba5a06ed0b3be).
# Build-identity generation is intentionally omitted: the selected installer
# does not consume that later protocol. See docs/PUBLICATION_CANDIDATE.md.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [Parameter(Mandatory=$true)][string]$PayloadManifest,
    [Parameter(Mandatory=$true)][string]$LauncherPath,
    [Parameter(Mandatory=$true)][string]$CompilerPath,
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$OutputBaseName = 'MastixaManager-1.0.0-rc.2-Setup-public-source'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = [IO.Path]::GetFullPath($OutputDir)
$payload = [IO.Path]::GetFullPath($PayloadDir)
$sourceRoot = [IO.Path]::GetFullPath($repoRoot).TrimEnd('\')
if (Test-Path -LiteralPath $output) { throw 'Fresh candidate output required; no overwrite or automatic retry' }
foreach ($inputRoot in @($sourceRoot, $payload.TrimEnd('\'))) {
    if ($output -ieq $inputRoot -or $output.StartsWith($inputRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Output must be outside the source and supplied payload'
    }
}
$ancestor = Split-Path -Parent $output
while ($ancestor) {
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse output ancestor refused'
    }
    $ancestor = Split-Path -Parent $ancestor
}
foreach ($inputFile in @($PayloadManifest, $LauncherPath, $CompilerPath, $PythonPath)) {
    if (-not (Test-Path -LiteralPath $inputFile -PathType Leaf)) { throw 'A required explicit build input is missing' }
}
if ((Get-FileHash -LiteralPath $CompilerPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    '0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7') {
    throw 'Compiler differs from the retained Inno Setup compiler'
}
$installerScript = Join-Path $repoRoot 'installer\MastixaManager.iss'
New-Item -ItemType Directory -Path $output | Out-Null
# Validate the newly built payload against this source's legal/resource/TLS policies.
& $PythonPath -B (Join-Path $PSScriptRoot 'validate_windows_release.py') --bundle $payload *> (Join-Path $output 'payload-validation.log')
if ($LASTEXITCODE -ne 0) { throw 'Payload legal/resource validation failed; preserve and stop' }
& $PythonPath -B (Join-Path $PSScriptRoot 'tls_inputs.py') --bundle $payload *> (Join-Path $output 'tls-validation.log')
if ($LASTEXITCODE -ne 0) { throw 'Payload TLS input validation failed; preserve and stop' }
$layout = Join-Path $output 'install-layout'
$receiptPath = Join-Path $output 'layout-receipt.json'
# PayloadManifest is a nonempty JSON object: relative path -> SHA-256, not an array.
& $PythonPath -B (Join-Path $PSScriptRoot 'external_vc_layout.py') --payload $payload --launcher $LauncherPath --output $layout --expected-manifest $PayloadManifest --receipt $receiptPath *> (Join-Path $output 'layout.log')
if ($LASTEXITCODE -ne 0) { throw 'External launcher layout validation failed; preserve and stop' }
$installerOutput = Join-Path $output 'installer'
New-Item -ItemType Directory -Path $installerOutput | Out-Null
& $CompilerPath "/O$installerOutput" "/F$OutputBaseName" "/DMyAppSourceDir=$(Join-Path $layout 'engine')" "/DMyLauncherPath=$(Join-Path $layout 'MastixaManager.exe')" '/DMyPrerequisiteMode=external-launch' $installerScript *> (Join-Path $output 'compiler.log')
if ($LASTEXITCODE -ne 0) { throw "Inno compile failed ($LASTEXITCODE); preserve diagnostics; do not retry automatically" }
$setup = Join-Path $installerOutput ($OutputBaseName + '.exe')
$layoutReceipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
$receipt = [ordered]@{
    builder_kind='new-public-source-implementation';historical_source_equivalence=$false
    mode='external-launch';installer=$setup;size=(Get-Item -LiteralPath $setup).Length
    sha256=(Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
    builder_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    installer_source_sha256=(Get-FileHash -LiteralPath $installerScript -Algorithm SHA256).Hash.ToLowerInvariant()
    payload_manifest_sha256=(Get-FileHash -LiteralPath $PayloadManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    compiler_sha256=(Get-FileHash -LiteralPath $CompilerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    launcher_sha256=$layoutReceipt.launcher.sha256
    installed_payload_logical_bytes=$layoutReceipt.logical_installed_payload_bytes
    supplied_payload_copied_unchanged=$true;installer_or_launcher_executed=$false
    redist_bundled=$false;redist_downloaded_or_executed=$false;native_install_validation='NOT TESTED'
    distribution_authorized=$false
}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'candidate-receipt.json') -Encoding utf8
$receipt | ConvertTo-Json
