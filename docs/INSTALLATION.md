# Fieltra v1.0.0 — Windows installation

The final installer is `Fieltra-1.0.0-Setup.exe`; it installs per user into
`%LOCALAPPDATA%\Programs\Fieltra`, with Start Menu and optional desktop shortcuts
opening `Fieltra.exe`. Windows Installed Apps and the uninstaller identify Fieltra.
The first production release does not migrate Mastixa pre-release installations.

Install the official Microsoft Visual C++ Redistributable **x64 14.51.36247.0 or
newer** separately: [Microsoft download](https://aka.ms/vc14/vc_redist.x64.exe).
Fieltra Setup neither bundles nor executes that package. The native launcher
checks it before Python/Qt and offers Download / Recheck / Cancel when necessary.
Offline operation needs no account; obtain the runtime beforehand if needed.

Data, profiles, backups and appearance settings use `%LOCALAPPDATA%\Fieltra`.
Source runs also default to this clean namespace. The existing internal
`MASTIXA_DATA_HOME` diagnostic override selects an explicit alternative.
Normal uninstall keeps Fieltra data. `/PURGEDATA` or an explicit Yes to full
removal removes Fieltra data only, not Mastixa developer data or backups.

The final Fieltra installer passed owner-observed Sandbox installation, startup
and branding/version acceptance. [Release/source status](FIELTRA_V1_RELEASE.md)
records its exact hash, source correspondence and official downloads.
The old installation identities below describe historical RC2 only.


[Download the official Windows installer](https://github.com/Sxara242/Fieltra/releases/download/v1.0.0/Fieltra-1.0.0-Setup.exe).
Supported platform: Windows 10 or Windows 11, x64.

---

Historical records and retained technical instructions follow. Earlier status statements
do not override the Fieltra v1.0.0 preparation status above.

# Installation and local data

Windows x64 is the current release target. No public rc.2 installer is approved;
the older rc.1 candidate is historical and lacks subsequent fixes.
Android remains in development. Download binary releases only after the
[release status](RELEASE_STATUS.md) and published checksums explicitly qualify them.

For Windows source development, install Python 3.14 and create a virtual
environment. The first install downloads dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c requirements-windows-rc.txt
.\.venv\Scripts\python.exe main.py
```

Normal application data lives under `%LOCALAPPDATA%\MastixaManager`, separate
from program files. Set `MASTIXA_DATA_HOME` to a new disposable directory before
development launches. Keep databases, backups and profile exports outside the
source tree. Back up real data before installation, upgrade or uninstall.

## Windows application prerequisite — next candidate

**Microsoft Visual C++ Redistributable x64 is required to run Mastixa Manager,
but is not included in its installer.** Obtain **x64 version 14.51.36247.0 or
newer** from [Microsoft](https://aka.ms/vc14/vc_redist.x64.exe) and install it
separately under Microsoft's own terms. x86 alone is insufficient. Microsoft
maintains the [supported version/architecture guidance](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

Mastixa Setup finishes regardless of VC++ presence. It does not contain, download,
run or request consent to install the Microsoft package. On application launch,
a small native Windows front end checks the x64 runtime registry entries and the
architecture/version of five canonical System32 runtime files before loading
Python/Qt. Missing/outdated runtime produces a friendly Greek warning with
**Λήψη από Microsoft**, **Έλεγχος ξανά** and **Ακύρωση**. Detection/access failures
are reported safely rather than bypassing the check. The link opens only after
your explicit click; Mastixa never runs the downloaded package for you.

Run the official Microsoft installer yourself, accept Microsoft's terms and any
required administrator prompt, then choose **Έλεγχος ξανά** or reopen Mastixa.
If Microsoft requests a restart, restart Windows first. Cancel leaves the Mastixa
installation and data intact. An adequate runtime proceeds without this warning.

For offline installation, save the official x64 package on a connected device
and transfer it separately. Mastixa installs offline, but cannot run until its
runtime is installed. No rehosting/proxy download or substitute CRT DLL is used.
Mastixa's AGPL rights and third-party/source replacement obligations are unchanged.

Start Menu, Desktop and post-install launch use the same root executable. The
unchanged frozen application lives in the installation's `engine/` directory.
Keep that entire directory; use the root launcher for normal opening.
Existing AppId, data path, preference identity and normal-uninstall preservation
stay the same. An upgrade may retain old program `_internal/` files; no new
destructive migration/cleanup rule was added. Native upgrade/rollback and actual
installed footprint require disposable Windows qualification.

The current target is native Windows x64. ARM64/ARM64X compatibility is not
qualified; the unchanged installer `x64compatible` declaration is not an ARM
acceptance result. The detector requires AMD64 canonical runtime images.

Earlier accepted RC2 artifacts used a bundled runtime and keep their original
hashes/documentation. A new external-runtime Setup has built and passed actual
package inspection; native installation/security qualification remains pending.
See [candidate qualification](WINDOWS_EXTERNAL_VC_QUALIFICATION.md).
No public release or final owner acceptance is implied.
See [implementation/validation](WINDOWS_EXTERNAL_VC_PREREQUISITE.md) and
[release status](RELEASE_STATUS.md). Source CI alone does not establish readiness.

For Android install JDK 21 and Android SDK platform 36, set `JAVA_HOME` and
`ANDROID_HOME`, and run from `android/`:

```powershell
.\gradlew.bat --no-daemon testDebugUnitTest lintDebug assembleDebug assembleChecksAndroidTest
```

On Linux use `bash ./gradlew` with the same tasks. Debug APKs are development
outputs. `connectedChecksAndroidTest` requires an emulator/device and uses a
separate `.checks` application. JVM unit tasks presently have no test sources;
they do not substitute for instrumentation. Do not provide production signing
keys for CI. See [Android documentation](../android/README.md).
