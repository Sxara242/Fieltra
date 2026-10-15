# Windows RC2 installer and split source delivery — 2026-10-11

This batch changes installer prerequisite handling and source delivery only.
The 559 frozen application files, including QtPdf/PDFium and PDF plugin, stay
byte-identical to controlled-3. Its four retained native PASS receipts qualify
that original installer, not this changed installer. Distribution remains NO-GO.

The bundled unmodified Microsoft x64 runtime is 14.51.36247.0, 18,731,856 bytes,
SHA-256 `843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c`.
Build preparation verifies its Valid Microsoft Authenticode signature, file
version, size and hash. The installer checks its extracted hash before execution.
The Microsoft bootstrapper is an x86 PE that installs the x64 runtime; that is
not an architecture mismatch. The unchanged canonical CRT minimum remains
14.51.36247.0; no app-local CRT is introduced.

Setup checks both registry views and five canonical System32 files. Adequate or
newer runtime skips execution. Otherwise the per-user Setup requests administrator
approval for the central prerequisite, waits for `/install /quiet /norestart`,
checks the exit code and rechecks actual readiness before installing app files.
Every installer recipient must accept the separate Microsoft terms, including
when existing runtime installation is skipped, because the installer contains
that executable. Unattended deployment must be elevated if installation is
needed and use `/ACCEPTVCRUNTIME` only after those terms have been accepted. Failure or
cancelled elevation stops before app installation. 1638/0x80070666 is accepted
only after readiness succeeds. 3010 marks restart required; if readiness is not
yet established it stops for reboot/retry. Unexpected 1641 stops for reboot.
Use `/NORESTART /RESTARTEXITCODE=3010` for unattended Mastixa Setup; never launch
the application before a required restart. Normal uninstall never removes the
shared Microsoft runtime. Runtime installer logs are in Setup's temporary
`mastixa-vc-redist.log`; retain them before closing failed test sessions.

Microsoft redistribution eligibility is conditional on the retained valid
Community entitlement and the listed unmodified release installer. The separate
prerequisite terms page and silent acceptance switch do not relicense Microsoft
code as AGPL or restrict Mastixa/Qt replacement rights. Publisher/distributor
protective assent, indemnity and other grant conditions require final channel
review before distribution. No unconditional legal clearance is claimed.
Primary sources: [Microsoft deployment and silent options](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files),
[2026 distributable list](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution),
[Community terms](https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/),
[runtime terms](https://aka.ms/VCRedistLicense).

Use `packaging/repackage_rc2.ps1` with the retained controlled-3 payload,
hash-pinned original recipient manifest, official runtime and retained Inno
compiler. It validates all 559 payload files before/after one compilation and
requires an empty output directory. It never runs the generated installer or
changes protection settings. No PyInstaller rebuild is needed for this batch.

The full Qt source archive remains unchanged, 580,351,104 bytes, SHA-256
`6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163`.
It is delivered separately as versioned `qtwebengine-everywhere-src-6.11.2.tar.xz`.
Its name denotes the source carrier for shipped QtPdf/PDFium, not a shipped
browser runtime. Do not trim it or apply the retained comparison patch twice.
The main source ZIP includes a mandatory asset index, complete unchanged build,
patch and license materials, exact old application source and a separate new
installer-source overlay. Apply that overlay to a fresh copy only when building
the repack installer. It does not change frozen application source provenance.

Extract the main source ZIP to a fresh directory and place the separate archive
either at `dependencies/qtwebengine-everywhere-src-6.11.2.tar.xz` or in a separate
asset directory. Run `python -B verify_package.py <source-root> --assets <asset-dir>`.
A missing/corrupt asset fails verification. Complete offline delivery consists
of both assets. Future publisher-controlled versioned download URLs and anonymous
access checks remain pending; manifest `public_urls` stays null. Retain sources
while binaries are available and at least five years after last distribution.

Isolated Windows tests must cover missing/older and adequate/newer runtime,
elevation cancellation, installer failure, duplicate-version race, reboot paths,
559 installed hashes, launch and PDF rendering using synthetic data. Owner-PC
installation/registry mutation is prohibited. Windows Sandbox launch is an owner
GUI step; merely finding WindowsSandbox.exe does not establish a usable clean VM.
No passed static test substitutes for those native checks.
