[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [string]$VCToolsDir = '',
    [string]$WindowsSdkDir = '',
    [string]$WindowsSdkVersion = '',
    [switch]$BuildSyntheticTests
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $PSScriptRoot 'windows_launcher'
$output = [IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $output) { throw 'Fresh launcher output directory required; never overwrite or retry automatically.' }
$ancestor = Split-Path -Parent $output
while ($ancestor) {
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse output ancestor refused'
    }
    $ancestor = Split-Path -Parent $ancestor
}
$policy = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'windows-prerequisite.json') -Raw | ConvertFrom-Json
if ($policy.mode -ne 'external-launch' -or $policy.architecture -ne 'x64' -or
    $policy.download_url -ne 'https://aka.ms/vc14/vc_redist.x64.exe' -or
    $policy.payload_directory -ne 'engine' -or $policy.executable -ne 'MastixaManager.exe') {
    throw 'Only the reviewed external-launch policy is active'
}
$crtPolicy = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'windows-crt-policy.json') -Raw | ConvertFrom-Json
if ($policy.minimum_version -ne $crtPolicy.minimum_version) { throw 'Runtime minimum disagrees with qualified CRT policy' }
$parts = $policy.minimum_version.Split('.')
if ($parts.Count -ne 4 -or @($parts | Where-Object { $_ -notmatch '^\d{1,5}$' -or [int]$_ -gt 65535 }).Count) {
    throw 'Invalid runtime version tuple'
}
$expectedDlls = @('msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','vcruntime140.dll','vcruntime140_1.dll')
if (($policy.canonical_files -join ',') -cne ($expectedDlls -join ',')) { throw 'Canonical DLL list changed' }
if (-not $VCToolsDir) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Pass -VCToolsDir or install entitled MSVC build tools separately' }
    $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
    if (-not $vsRoot) { throw 'MSVC x64 build tools not found' }
    $VCToolsDir = (Get-ChildItem -LiteralPath (Join-Path $vsRoot 'VC\Tools\MSVC') -Directory |
        Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1).FullName
}
if (-not $WindowsSdkDir) { $WindowsSdkDir = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10' }
if (-not $WindowsSdkVersion) {
    $WindowsSdkVersion = (Get-ChildItem -LiteralPath (Join-Path $WindowsSdkDir 'Include') -Directory |
        Where-Object { $_.Name -match '^10\.0\.\d+\.0$' } |
        Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1).Name
}
$cl = Join-Path $VCToolsDir 'bin\Hostx64\x64\cl.exe'
$link = Join-Path $VCToolsDir 'bin\Hostx64\x64\link.exe'
$rc = Join-Path $WindowsSdkDir "bin\$WindowsSdkVersion\x64\rc.exe"
foreach ($tool in @($cl,$link,$rc)) { if (-not (Test-Path -LiteralPath $tool)) { throw "Missing build tool: $tool" } }
New-Item -ItemType Directory -Path $output | Out-Null
$dllLiteral = ($expectedDlls | ForEach-Object { 'L"' + $_ + '"' }) -join ', '
$header = @"
#define MASTIXA_MIN_MAJOR $($parts[0])
#define MASTIXA_MIN_MINOR $($parts[1])
#define MASTIXA_MIN_BUILD $($parts[2])
#define MASTIXA_MIN_REVISION $($parts[3])
#define MASTIXA_MIN_TEXT L"$($policy.minimum_version)"
#define MASTIXA_DLL_COUNT 5
#define MASTIXA_DLL_LIST $dllLiteral
#define MASTIXA_DOWNLOAD_URL L"$($policy.download_url)"
#define MASTIXA_PAYLOAD_DIRECTORY L"engine"
"@
Set-Content -LiteralPath (Join-Path $output 'policy_config.h') -Value $header -Encoding utf8
$includes = @($output, $source, (Join-Path $VCToolsDir 'include'))
foreach ($section in @('ucrt','shared','um')) { $includes += Join-Path $WindowsSdkDir "Include\$WindowsSdkVersion\$section" }
$flags = @('/nologo','/c','/TC','/std:c11','/utf-8','/W4','/WX','/O1','/GS','/Zl','/DUNICODE','/D_UNICODE','/D_WIN32_WINNT=0x0A00')
foreach ($include in $includes) { $flags += "/I$include" }
foreach ($name in @('guard','launcher')) {
    & $cl @flags "/Fo$(Join-Path $output ($name + '.obj'))" (Join-Path $source ($name + '.c')) *> (Join-Path $output ($name + '-compile.log'))
    if ($LASTEXITCODE -ne 0) { throw "Native $name compilation failed; preserve log and stop" }
}
Push-Location $source
try {
    & $rc /nologo "/I$output" "/I$(Join-Path $WindowsSdkDir "Include\$WindowsSdkVersion\um")" "/I$(Join-Path $WindowsSdkDir "Include\$WindowsSdkVersion\shared")" "/fo$(Join-Path $output 'launcher.res')" 'launcher.rc' *> (Join-Path $output 'resource-compile.log')
    if ($LASTEXITCODE -ne 0) { throw 'Resource compilation failed; preserve log and stop' }
} finally { Pop-Location }
$umLib = Join-Path $WindowsSdkDir "Lib\$WindowsSdkVersion\um\x64"
$linkFlags = @('/NOLOGO','/NODEFAULTLIB','/MACHINE:X64','/DYNAMICBASE','/HIGHENTROPYVA','/NXCOMPAT','/DEPENDENTLOADFLAG:0x800',"/LIBPATH:$umLib")
$objects = @((Join-Path $output 'launcher.obj'),(Join-Path $output 'guard.obj'),(Join-Path $output 'launcher.res'))
& $link @linkFlags /SUBSYSTEM:WINDOWS,6.02 /ENTRY:MastixaLauncherEntry "/OUT:$(Join-Path $output 'MastixaManager.exe')" "/MAP:$(Join-Path $output 'launcher.map')" @objects kernel32.lib user32.lib shell32.lib advapi32.lib version.lib bcrypt.lib *> (Join-Path $output 'launcher-link.log')
if ($LASTEXITCODE -ne 0) { throw 'Launcher link failed; never add CRT libraries to fix the build' }
if ($BuildSyntheticTests) {
    & $cl @flags "/Fo$(Join-Path $output 'native-tests.obj')" (Join-Path $repoRoot 'tests\native\test_windows_launcher.c') *> (Join-Path $output 'native-tests-compile.log')
    if ($LASTEXITCODE -ne 0) { throw 'Native synthetic test compilation failed' }
    & $link @linkFlags /SUBSYSTEM:CONSOLE,6.02 /ENTRY:MastixaTestEntry "/OUT:$(Join-Path $output 'launcher-policy-tests.exe')" (Join-Path $output 'native-tests.obj') (Join-Path $output 'guard.obj') kernel32.lib shell32.lib bcrypt.lib *> (Join-Path $output 'native-tests-link.log')
    if ($LASTEXITCODE -ne 0) { throw 'Native test link failed' }
    & $cl @flags "/Fo$(Join-Path $output 'runtime-probe.obj')" (Join-Path $repoRoot 'tests\native\probe_windows_runtime.c') *> (Join-Path $output 'runtime-probe-compile.log')
    if ($LASTEXITCODE -ne 0) { throw 'Read-only diagnostic compilation failed' }
    & $link @linkFlags /SUBSYSTEM:CONSOLE,6.02 /ENTRY:MastixaRuntimeProbeEntry "/OUT:$(Join-Path $output 'runtime-probe.exe')" (Join-Path $output 'runtime-probe.obj') (Join-Path $output 'guard.obj') kernel32.lib user32.lib shell32.lib advapi32.lib version.lib bcrypt.lib *> (Join-Path $output 'runtime-probe-link.log')
    if ($LASTEXITCODE -ne 0) { throw 'Read-only diagnostic link failed' }
}
$receipt = [ordered]@{
    mode=$policy.mode;minimum=$policy.minimum_version;msvc_tools=$VCToolsDir;sdk=$WindowsSdkVersion
    cl_sha256=(Get-FileHash -LiteralPath $cl -Algorithm SHA256).Hash.ToLowerInvariant()
    link_sha256=(Get-FileHash -LiteralPath $link -Algorithm SHA256).Hash.ToLowerInvariant()
    launcher_sha256=(Get-FileHash -LiteralPath (Join-Path $output 'MastixaManager.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
    launcher_size=(Get-Item -LiteralPath (Join-Path $output 'MastixaManager.exe')).Length
    crt_libraries_linked=$false;runtime_downloaded=$false;launcher_executed=$false
}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'build-receipt.json') -Encoding utf8
$receipt | ConvertTo-Json
