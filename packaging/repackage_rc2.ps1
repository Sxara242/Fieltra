[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [Parameter(Mandatory=$true)][string]$OriginalRecipientManifest,
    [Parameter(Mandatory=$true)][string]$VcRedistPath,
    [Parameter(Mandatory=$true)][string]$CompilerPath,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$OutputBaseName = 'MastixaManager-1.0.0-rc.2-Setup-repack'
)
$ErrorActionPreference = 'Stop'
# This helper describes the retained historical bundled candidate, whose source
# and artifacts stay immutable. It must not accidentally become an active build
# route against the revised installer. A future bundled mode needs new approval.
throw 'Historical bundled-runtime helper is inactive. Use build_external_vc_candidate.ps1; Microsoft clarification is unresolved.'
$repoRoot = Split-Path -Parent $PSScriptRoot
$lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'vc-redist-lock.json') -Raw | ConvertFrom-Json
function Get-Sha([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
$redist = Get-Item -LiteralPath $VcRedistPath
$signature = Get-AuthenticodeSignature -LiteralPath $redist.FullName
if ($redist.Length -ne $lock.size -or (Get-Sha $redist.FullName) -ne $lock.sha256 -or
    $redist.VersionInfo.FileVersion -ne $lock.version -or $signature.Status -ne 'Valid' -or
    $signature.SignerCertificate.Subject -notmatch '(^|, )O=Microsoft Corporation(,|$)') {
    throw 'Microsoft redist identity/version/signature mismatch'
}
if ((Get-Sha $OriginalRecipientManifest) -ne '8bf76c7093c3b842e8adbb35b2ba1dc6266ce1023f552c242bdb24eae8bf4b0d') {
    throw 'Original recipient manifest identity mismatch'
}
$manifest = Get-Content -LiteralPath $OriginalRecipientManifest -Raw | ConvertFrom-Json
$payload = [IO.Path]::GetFullPath($PayloadDir)
$expected = @{}
foreach ($entry in $manifest.binary_identity.members_sha256.PSObject.Properties) {
    if ($entry.Name.StartsWith('MastixaManager/')) {
        $expected[$entry.Name.Substring(15)] = $entry.Value
    }
}
function Assert-Payload {
    $actual = @(Get-ChildItem -LiteralPath $payload -File -Recurse)
    if ($expected.Count -ne 559 -or $actual.Count -ne 559) { throw 'Payload member count mismatch' }
    foreach ($item in $actual) {
        $relative = $item.FullName.Substring($payload.Length+1).Replace('\','/')
        if (-not $expected.ContainsKey($relative) -or (Get-Sha $item.FullName) -ne $expected[$relative]) {
            throw "Unchanged payload verification failed: $relative"
        }
    }
}
Assert-Payload
$output = [IO.Path]::GetFullPath($OutputDir)
if (-not (Test-Path -LiteralPath $output)) { New-Item -ItemType Directory -Path $output | Out-Null }
if (@(Get-ChildItem -LiteralPath $output -Force).Count -ne 0) { throw 'Fresh empty output directory required; no retries or overwrite' }
$compiler = Get-Item -LiteralPath $CompilerPath
if ((Get-Sha $compiler.FullName) -ne '0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7') {
    throw 'Retained Inno compiler identity mismatch'
}
$setup = Join-Path $output "$OutputBaseName.exe"
$started = [ordered]@{compiler_sha256=(Get-Sha $compiler.FullName);redist_sha256=$lock.sha256;payload_files=559;output=$setup;max_attempts=1;exclusions_created=$false;installer_executed=$false}
$started | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'compile-started.json') -Encoding utf8
& $compiler.FullName "/O$output" "/F$OutputBaseName" "/DMyAppSourceDir=$payload" "/DMyVcRedistPath=$($redist.FullName)" (Join-Path $repoRoot 'installer/MastixaManager.iss') *> (Join-Path $output 'compiler.log')
$code = $LASTEXITCODE
Assert-Payload
$receipt = [ordered]@{exit_code=$code;payload_files_unchanged=559;installer_executed=$false;exclusions_created=$false;artifact=$null}
if (Test-Path -LiteralPath $setup) {
    $receipt.artifact = @{name=[IO.Path]::GetFileName($setup);size=(Get-Item -LiteralPath $setup).Length;sha256=(Get-Sha $setup)}
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output 'compile-result.json') -Encoding utf8
if ($code -ne 0 -or $null -eq $receipt.artifact) { throw "Inno failed ($code); attempt consumed. Preserve diagnostics and do not retry automatically." }
$receipt | ConvertTo-Json -Depth 5
