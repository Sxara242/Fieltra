[CmdletBinding()]
param(
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonPath) {
    if (-not $env:LOCALAPPDATA) {
        throw "LOCALAPPDATA is required when PythonPath is not supplied."
    }
    $PythonPath = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Build Python was not found: $PythonPath"
}
if (-not $env:RUNNER_TEMP) {
    throw "RUNNER_TEMP is required for the Windows release gate."
}

$runId = if ($env:GITHUB_RUN_ID) { $env:GITHUB_RUN_ID } else { "local" }
$runAttempt = if ($env:GITHUB_RUN_ATTEMPT) { $env:GITHUB_RUN_ATTEMPT } else { "1" }
$outputDir = Join-Path $env:RUNNER_TEMP "MastixaManager-release-$runId-$runAttempt"
$monitorLog = Join-Path $env:RUNNER_TEMP "MastixaManager-locks-$runId-$runAttempt.log"

function Prepare-LockDiagnostics {
    try {
        $zip = Join-Path $env:RUNNER_TEMP "Handle.zip"
        $dir = Join-Path $env:RUNNER_TEMP "Sysinternals-Handle"

        Invoke-WebRequest -Uri "https://download.sysinternals.com/files/Handle.zip" -OutFile $zip
        if (Test-Path -LiteralPath $dir) {
            Remove-Item -LiteralPath $dir -Recurse -Force
        }
        Expand-Archive -LiteralPath $zip -DestinationPath $dir

        $handle = Join-Path $dir "handle64.exe"
        $signature = Get-AuthenticodeSignature -LiteralPath $handle
        if (
            $signature.Status -ne "Valid" -or
            $signature.SignerCertificate.Subject -notmatch "Microsoft"
        ) {
            throw (
                "Sysinternals Handle signature verification failed: " +
                "$($signature.Status) / $($signature.SignerCertificate.Subject)"
            )
        }

        Write-Host "Lock diagnostics prepared: $handle"
        return $handle
    }
    catch {
        Write-Warning "Lock diagnostics are unavailable: $($_.Exception.Message)"
        return $null
    }
}

$handleExe = Prepare-LockDiagnostics
$monitor = $null
Write-Host "Starting Windows release build: $outputDir"

if ($handleExe) {
    $monitor = Start-Job -ArgumentList $handleExe, $outputDir, $monitorLog -ScriptBlock {
        param($HandleExe, $OutputDir, $MonitorLog)

        while ($true) {
            if (Test-Path -LiteralPath $OutputDir) {
                Get-ChildItem -LiteralPath $OutputDir -Filter "*.exe" -File -ErrorAction SilentlyContinue |
                    ForEach-Object {
                        $handleOutput = (& $HandleExe -accepteula -nobanner $_.FullName 2>&1 | Out-String)
                        if ($handleOutput -match "pid:") {
                            Add-Content -LiteralPath $MonitorLog -Value (
                                "[$(Get-Date -Format o)] $($_.FullName)`n$handleOutput"
                            )
                        }
                    }
            }
            Start-Sleep -Milliseconds 500
        }
    }
}

$exitCode = 1
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_release.ps1") `
        -PythonPath $PythonPath `
        -InstallerOutputDir $outputDir `
        -InstallerBuildAttempts 1
    $exitCode = $LASTEXITCODE
    Write-Host "Windows release build exit code: $exitCode"
}
finally {
    if ($monitor) {
        Start-Sleep -Seconds 1
        Stop-Job -Job $monitor -ErrorAction SilentlyContinue
        Receive-Job -Job $monitor -ErrorAction SilentlyContinue | Out-Host
        Remove-Job -Job $monitor -ErrorAction SilentlyContinue
    }

    if (Test-Path -LiteralPath $monitorLog) {
        Write-Host "=== Observed installer file locks ==="
        Get-Content -LiteralPath $monitorLog
        Write-Host "=== End installer file locks ==="
    }
}

if ($exitCode -ne 0) {
    exit $exitCode
}
