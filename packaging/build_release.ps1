[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [string]$PythonPath = "",
    [string]$PyInstallerWorkPath = "",
    [string]$PyInstallerDistPath = "",
    [string]$InstallerOutputDir = "",
    [int]$InstallerBuildAttempts = 3
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$tlsLock = Get-Content -LiteralPath (Join-Path $PSScriptRoot "windows-tls-inputs.json") -Raw | ConvertFrom-Json
$venvPython = Join-Path (Join-Path $repoRoot $tlsLock.python.build_venv) "Scripts\python.exe"
$spec = Join-Path $PSScriptRoot "MastixaManager.spec"
$releaseConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot "windows-rc.json") -Raw | ConvertFrom-Json
$releaseVersion = $releaseConfig.version
if ($releaseVersion -notmatch '^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$') {
    throw "Unsafe release output version: $releaseVersion"
}
# A candidate invocation supplies separate paths; existing CI defaults stay usable.
$releaseWork = if ($PyInstallerWorkPath) { [IO.Path]::GetFullPath($PyInstallerWorkPath) } else { Join-Path $repoRoot "build" }
$releaseDist = if ($PyInstallerDistPath) { [IO.Path]::GetFullPath($PyInstallerDistPath) } else { Join-Path $repoRoot "dist" }

function Get-BundleRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$ChildPath
    )

    $baseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\') + '\'
    $childFull = [System.IO.Path]::GetFullPath($ChildPath)
    if (-not $childFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the release bundle: $childFull"
    }
    return $childFull.Substring($baseFull.Length).Replace("\", "/")
}

if ($InstallerBuildAttempts -lt 1) {
    throw "InstallerBuildAttempts must be at least 1."
}

if ($PythonPath) {
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        throw "Build Python was not found: $PythonPath"
    }
    $python = (Resolve-Path -LiteralPath $PythonPath).Path
}
elseif (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
}
else {
    throw "Missing build Python. Create .venv or pass -PythonPath <python.exe>."
}

Push-Location $repoRoot
try {
    & $python (Join-Path $PSScriptRoot "validate_windows_release.py")
    if ($LASTEXITCODE -ne 0) {
        throw "BLOCKED BEFORE RC BUILD: close the release preflight findings before packaging."
    }
    & $python -m PyInstaller --noconfirm --clean --workpath $releaseWork --distpath $releaseDist $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $bundle = Join-Path $releaseDist "MastixaManager"
    $exe = Join-Path $bundle "MastixaManager.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Packaged executable was not created: $exe"
    }
    & $python (Join-Path $PSScriptRoot "crt_policy.py") --bundle $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "B2 BLOCKED: central-runtime CRT packaging policy failed."
    }
    & $python (Join-Path $PSScriptRoot "validate_windows_release.py") --bundle $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged legal/resource/VirtualKeyboard/privacy validation failed."
    }
    & $python (Join-Path $PSScriptRoot "tls_inputs.py") --bundle $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "B5 BLOCKED: frozen TLS files do not match qualified supplier inputs."
    }

    $bundledDataDir = Join-Path $bundle "_internal\data"
    if (Test-Path -LiteralPath $bundledDataDir) {
        $bundledDataItems = @(Get-ChildItem -LiteralPath $bundledDataDir -Force)
        if ($bundledDataItems.Count -ne 0) {
            throw "Private application data unexpectedly entered the build."
        }
        Remove-Item -LiteralPath $bundledDataDir -Force
    }

    # Dependency packages may legitimately ship read-only SQLite data. In
    # particular pyproj/PROJ requires proj.db for CRS transformations. Keep
    # the privacy gate strict for every other SQLite database so user/profile
    # databases can never be bundled accidentally.
    $databaseFiles = @(Get-ChildItem -LiteralPath $bundle -Recurse -File -Filter "*.db")
    $unexpectedDatabaseFiles = @(
        foreach ($databaseFile in $databaseFiles) {
            $relativePath = Get-BundleRelativePath -BasePath $bundle -ChildPath $databaseFile.FullName
            $isProjDependency = (
                $databaseFile.Name -ieq "proj.db" -and
                $relativePath -match "(^|/)pyproj(/|$)"
            )
            if ($isProjDependency) {
                Write-Host "Allowed dependency database: $relativePath"
                continue
            }
            $databaseFile
        }
    )
    if ($unexpectedDatabaseFiles.Count -ne 0) {
        $unexpectedPaths = $unexpectedDatabaseFiles |
            ForEach-Object {
                Get-BundleRelativePath -BasePath $bundle -ChildPath $_.FullName
            }
        throw (
            "Unexpected SQLite database files entered the release bundle: " +
            ($unexpectedPaths -join ", ")
        )
    }

    if ($SkipInstaller) {
        Write-Host "Bundle:    $bundle"
        return
    }

    $compilerCandidates = @(
        (Join-Path $repoRoot ".tools\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    if ($env:LOCALAPPDATA) {
        $compilerCandidates += Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    }
    $compiler = $compilerCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
    if (-not $compiler) {
        throw "Inno Setup 6 was not found. Install it or use -SkipInstaller."
    }

    $installerScript = Join-Path $repoRoot "installer\MastixaManager.iss"
    # Frozen Python/Qt cannot reliably show a prerequisite warning without CRT.
    # Build a CRT-independent front end; keep the frozen payload unchanged.
    $launcherOutput = Join-Path $releaseWork "windows-launcher"
    & (Join-Path $PSScriptRoot "build_windows_launcher.ps1") -OutputDir $launcherOutput
    $launcher = Join-Path $launcherOutput "MastixaManager.exe"
    & $python -B (Join-Path $PSScriptRoot "launcher_audit.py") $launcher
    if ($LASTEXITCODE -ne 0) { throw "Independent launcher dependency/hardening validation failed." }
    $installerText = Get-Content -LiteralPath $installerScript -Raw
    $versionMatch = [regex]::Match(
        $installerText,
        '#define\s+MyAppVersion\s+"([^"]+)"'
    )
    if (-not $versionMatch.Success) {
        throw "Could not read MyAppVersion from $installerScript"
    }
    $version = $versionMatch.Groups[1].Value
    if ($version -ne $releaseVersion) {
        throw "Installer version does not match release metadata: $version / $releaseVersion"
    }

    if ($InstallerOutputDir) {
        $installerOutput = [System.IO.Path]::GetFullPath($InstallerOutputDir)
    }
    else {
        $installerOutput = Join-Path $releaseDist "installer"
    }
    New-Item -ItemType Directory -Force -Path $installerOutput | Out-Null

    $setup = Join-Path $installerOutput "MastixaManager-$version-Setup.exe"
    $outputArg = "/O$installerOutput"
    $compilerExitCode = $null
    $successfulAttemptSetup = $null

    # Antivirus/indexing on Windows can briefly lock a freshly generated EXE.
    # Each compiler retry therefore uses a fresh output filename so a lock on
    # a failed attempt cannot poison the next attempt. Only a successful build
    # is promoted to the stable release filename expected by verification and
    # artifact upload.
    for ($attempt = 1; $attempt -le $InstallerBuildAttempts; $attempt++) {
        $attemptBaseName = "MastixaManager-$version-Setup-attempt-$attempt"
        $attemptSetup = Join-Path $installerOutput "$attemptBaseName.exe"
        $filenameArg = "/F$attemptBaseName"

        if (Test-Path -LiteralPath $attemptSetup) {
            for ($removeAttempt = 1; $removeAttempt -le 10; $removeAttempt++) {
                try {
                    Remove-Item -LiteralPath $attemptSetup -Force -ErrorAction Stop
                    break
                }
                catch {
                    if ($removeAttempt -eq 10) {
                        Write-Warning "Installer attempt output is still locked: $attemptSetup"
                        break
                    }
                    Start-Sleep -Seconds 1
                }
            }
        }

        & $compiler $outputArg $filenameArg "/DMyAppSourceDir=$bundle" "/DMyLauncherPath=$launcher" "/DMyPrerequisiteMode=external-launch" $installerScript
        $compilerExitCode = $LASTEXITCODE
        if ($compilerExitCode -eq 0) {
            $successfulAttemptSetup = $attemptSetup
            break
        }

        if ($attempt -lt $InstallerBuildAttempts) {
            $delaySeconds = 5 * $attempt
            Write-Warning (
                "Inno Setup attempt $attempt failed with exit code " +
                "$compilerExitCode. Retrying in $delaySeconds seconds."
            )
            Start-Sleep -Seconds $delaySeconds
        }
    }

    if ($compilerExitCode -ne 0) {
        throw (
            "Inno Setup failed with exit code $compilerExitCode after " +
            "$InstallerBuildAttempts attempt(s)"
        )
    }

    if (-not $successfulAttemptSetup -or -not (Test-Path -LiteralPath $successfulAttemptSetup)) {
        throw "Successful installer attempt output was not created."
    }

    $promoted = $false
    for ($promoteAttempt = 1; $promoteAttempt -le 15; $promoteAttempt++) {
        try {
            Copy-Item -LiteralPath $successfulAttemptSetup -Destination $setup -Force -ErrorAction Stop
            $promoted = $true
            break
        }
        catch {
            if ($promoteAttempt -eq 15) {
                throw "Installer was built but could not be promoted to the release filename: $setup"
            }
            Start-Sleep -Seconds 1
        }
    }

    if (-not $promoted -or -not (Test-Path -LiteralPath $setup)) {
        throw "Installer was not created: $setup"
    }

    $hash = $null
    for ($hashAttempt = 1; $hashAttempt -le 10; $hashAttempt++) {
        try {
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $setup).Hash.ToLowerInvariant()
            break
        }
        catch {
            if ($hashAttempt -eq 10) {
                throw
            }
            Start-Sleep -Seconds 1
        }
    }

    Set-Content -LiteralPath "$setup.sha256" -Encoding ascii -Value "$hash  $(Split-Path -Leaf $setup)"
    Write-Host "Installer: $setup"
    Write-Host "SHA256:    $hash"
}
finally {
    Pop-Location
}
