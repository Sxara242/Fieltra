[CmdletBinding()]
param(
    [string]$ExecutablePath = (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\Fieltra\Fieltra.exe"),
    [ValidateRange(5, 300)][int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$exe = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
if ((Split-Path -Leaf $exe) -cne "Fieltra.exe" -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Expected the packaged Fieltra.exe."
}
$bundle = Split-Path -Parent $exe
$resourceBundle = $bundle
# Installer entry is the independent launcher; its frozen resources live in engine.
# Keep FileName pointed at the launcher so this checks the actual launch path.
if (Test-Path -LiteralPath (Join-Path $bundle "engine\Fieltra.exe")) {
    $resourceBundle = Join-Path $bundle "engine"
}

# Never run against an installed application's legacy preferences/private data.
# Missing assets/locales can otherwise silently fall back to blank icons/Greek.
if (Test-Path -LiteralPath (Join-Path $resourceBundle "_internal\data")) {
    throw "Refusing a bundle containing legacy/private _internal/data."
}
foreach ($resource in @("assets", "locales")) {
    $sourceRoot = Join-Path $repoRoot "app\$resource"
    foreach ($source in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File) {
        $relative = $source.FullName.Substring($sourceRoot.Length + 1)
        $packaged = Join-Path $resourceBundle "_internal\app\$resource\$relative"
        if (-not (Test-Path -LiteralPath $packaged -PathType Leaf)) {
            throw "Missing packaged resource: app/$resource/$relative"
        }
        if ((Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $packaged -Algorithm SHA256).Hash) {
            throw "Packaged resource differs from this checkout: app/$resource/$relative"
        }
    }
}

$tempParent = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$tempParent = (Resolve-Path -LiteralPath $tempParent).Path
# A fresh GUID directory prevents profiles, absolute backup paths or PIN state
# from a previous run entering startup. No caller-supplied data root is reused.
$isolationRoot = Join-Path $tempParent ("MastixaManager-smoke-" + [guid]::NewGuid().ToString("N"))
if (Test-Path -LiteralPath $isolationRoot) { throw "Isolation directory already exists." }
$dataHome = Join-Path $isolationRoot "app-data"
$guestHome = Join-Path $isolationRoot "home"
$childTemp = Join-Path $isolationRoot "temp"
$localData = Join-Path $guestHome "AppData\Local"
$roamingData = Join-Path $guestHome "AppData\Roaming"
foreach ($directory in @($dataHome, $localData, $roamingData, $childTemp)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$appLog = Join-Path $dataHome "data\logs\mastixa_manager.log"
$stdoutPath = Join-Path $isolationRoot "stdout.txt"
$stderrPath = Join-Path $isolationRoot "stderr.txt"

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $exe
$startInfo.Arguments = "--smoke-test"
$startInfo.WorkingDirectory = $isolationRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
# These overrides affect only the new process. runtime_paths.py honors
# MASTIXA_DATA_HOME first; the remaining paths isolate fallback/Qt/temp storage.
$startInfo.EnvironmentVariables["MASTIXA_DATA_HOME"] = $dataHome
$startInfo.EnvironmentVariables["LOCALAPPDATA"] = $localData
$startInfo.EnvironmentVariables["APPDATA"] = $roamingData
$startInfo.EnvironmentVariables["USERPROFILE"] = $guestHome
$startInfo.EnvironmentVariables["HOME"] = $guestHome
$startInfo.EnvironmentVariables["HOMEDRIVE"] = [System.IO.Path]::GetPathRoot($guestHome).TrimEnd('\')
$startInfo.EnvironmentVariables["HOMEPATH"] = $guestHome.Substring([System.IO.Path]::GetPathRoot($guestHome).Length - 1)
$startInfo.EnvironmentVariables["TEMP"] = $childTemp
$startInfo.EnvironmentVariables["TMP"] = $childTemp
$startInfo.EnvironmentVariables["QT_QPA_PLATFORM"] = "offscreen"
foreach ($variable in @("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")) {
    $startInfo.EnvironmentVariables.Remove($variable)
}

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $startInfo
$started = $false
$stdoutTask = $null
$stderrTask = $null
$status = "FAIL"
$exitCode = $null
$failure = $null
try {
    $started = $process.Start()
    if (-not $started) { throw "Packaged process did not start." }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        throw "Packaged startup timed out after $TimeoutSeconds seconds."
    }
    $exitCode = $process.ExitCode
    if ($exitCode -ne 0) { throw "Packaged process exited with code $exitCode." }
    if (-not (Test-Path -LiteralPath $appLog)) { throw "Missing isolated application log." }
    $log = Get-Content -LiteralPath $appLog -Raw -Encoding UTF8
    # This existing marker is emitted only after controller.start() constructs
    # and shows the main window. The existing Qt timer then exits the event loop.
    if ($log -notmatch '\| INFO \| mastixa\.main_window \| Packaged smoke test started') {
        throw "Packaged application did not reach the startup marker."
    }
    if ($log -match '\| (ERROR|CRITICAL) \|') { throw "Application logged a runtime error." }
    if (-not (Test-Path -LiteralPath (Join-Path $dataHome "data\profiles.json")) -or
        -not (Test-Path -LiteralPath (Join-Path $dataHome "data\mastixa_manager.db"))) {
        throw "Fresh isolated profile/database was not initialized."
    }
    $status = "PASS"
}
catch {
    $failure = $_.Exception.Message
}
finally {
    # The existing smoke hook exits normally. On timeout/failure, use the exact
    # retained process instance; never enumerate or kill by application name.
    if ($started -and -not $process.HasExited) {
        try {
            # The native launcher owns a kill-on-close job for its exact child;
            # terminating this process instance also stops that engine.
            $process.Kill()
            if (-not $process.WaitForExit(5000)) { throw "Created process did not terminate." }
        }
        catch { $status = "FAIL"; $failure = "Cleanup failed: $($_.Exception.Message)" }
    }
    if ($started -and $process.HasExited) { $exitCode = $process.ExitCode }
    foreach ($capture in @(@($stdoutTask, $stdoutPath), @($stderrTask, $stderrPath))) {
        if ($null -ne $capture[0]) {
            if ($capture[0].Wait(1000)) {
                $text = $capture[0].Result
                Set-Content -LiteralPath $capture[1] -Value $text -Encoding UTF8
                if ($text -match '(?i)Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|Fatal Python error|Could not (find|load) the Qt platform plugin') {
                    $status = "FAIL"; $failure = "Packaged runtime error in captured output."
                }
            }
            else { $status = "FAIL"; $failure = "Output capture timed out." }
        }
    }
    $process.Dispose()
    [ordered]@{
        status = $status; executable = $exe; isolatedData = $dataHome
        timeoutSeconds = $TimeoutSeconds; exitCode = $exitCode; failure = $failure
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $isolationRoot "result.json") -Encoding UTF8
    Write-Host "Packaged smoke: $status; exit=$exitCode; timeout=${TimeoutSeconds}s"
    Write-Host "Executable: $exe"
    Write-Host "Isolated evidence: $isolationRoot"
    if ($status -ne "PASS") {
        foreach ($path in @($appLog, $stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $path) { Get-Content -LiteralPath $path -Tail 80 | Out-Host }
        }
    }
    # Keep only this synthetic run's evidence for diagnosis; no recursive delete.
}
if ($status -ne "PASS") { throw "Packaged startup smoke failed: $failure" }
