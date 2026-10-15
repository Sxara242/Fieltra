# Building Fieltra v1.0.0 Stable

Use the existing qualified CPython 3.14.8 environment, locked wheels, TLS/CRT/EPSG/
Mesa controls and Inno Setup 6.7.3 with all 16 accepted signatures. No third-party
library rebuild is needed. Internal recipe filenames remain unchanged.

The final Windows recipe is `packaging/build_fieltra_sandbox.ps1`; it reuses an
existing build venv and produces one application package, one native launcher and
one `Fieltra-1.0.0-Setup.exe`. Run only inside an authorized Windows Sandbox.
See [source and build controls](FIELTRA_V1_RELEASE.md). The accepted final installer has already been built and owner-accepted.
These controls are supplied for recipient modification and reconstruction;
publication preparation does not require another build.

The accepted installation, startup and branding/version results remain closed.
Do not rebuild or repeat these checks to publish the existing source.
Older exhaustive qualification lists below are historical, not additional tasks
for this finalization. Source development instructions and Android information
remain available below.

Native launcher source correspondence is PASS; the guest comparison found only
two linker timestamps. Use the [v1.0.0 source tag](https://github.com/Sxara242/Fieltra/tree/v1.0.0)
and both companion archives. No new build is needed to distribute the accepted installer.

---

Historical records and retained technical instructions follow. Earlier status statements
do not override the Fieltra v1.0.0 preparation status above.

# Development, CI and packaging

Windows source development uses Python 3.14/PySide6. Android uses JDK 21,
Gradle 8.13, AGP 8.13.2 and SDK 36. Windows is the current release target;
Android debug builds do not qualify a public Android release.

Run Windows tests from the root with `QT_QPA_PLATFORM=offscreen`, `PYTHONUTF8=1`
and `MASTIXA_DATA_HOME` pointing to a new disposable directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c requirements-windows-rc.txt
.\.venv\Scripts\python.exe tools/run_windows_tests.py --jobs 2 --timeout 120 --module-timeout tests.test_stabilization=360
.\.venv\Scripts\python.exe tools/audit_public_source.py
.\.venv\Scripts\python.exe packaging/validate_windows_release.py
```

`requirements-dev.txt` includes Pillow for the optional image-fixture tools.
It is a development dependency, not a new Windows shipping input. Its original
MIT-CMU terms remain applicable; see [Pillow](https://pypi.org/project/pillow/).

Use synthetic fixtures and temporary profiles. Shared changes require
Windows/Android parity consideration. Android commands are in
[INSTALLATION.md](INSTALLATION.md). Instrumentation uses the `.checks` app.
The runner executes every `test_*.py` module in a fresh process and bounds each
module to 120 seconds, with an explicit 360-second stabilization override. That
legacy module constructs the complete window for 23 tests; measured assertions
completed in 284 seconds before fixture-controller cleanup. The override preserves
every assertion and still fails on timeout, failure or unsuccessful process exit.
Timeout diagnostics capture a Python stack before process-tree cleanup. This avoids
carrying Qt objects/timers from deleted
fixtures across modules. A failed module or timeout fails the run; no tests are
silently skipped. Both unittest classes and the existing plain test functions
are executed. Direct unittest discovery remains available for diagnosis but does
not discover those plain functions.

The hosted command also names three measured slow-module bounds: activity-expense
sync 240 seconds, composed UI localization 180 seconds, sale sources 360 seconds.
Each made assertion progress up to the original hosted bound and passes locally.
These explicit limits preserve all cases and fail on unsuccessful process exit;
they are not skip/xfail policies. Hosted CI must pass the complete corpus.

## Hosted CI

`verify.yml` runs Windows tests/packaging contracts on `windows-latest` and source
audit/Android build/lint/test-APK compilation on `ubuntu-latest`.
`windows-release-gate.yml` is a manual packaging check, without installers.
`android-runtime.yml` manually runs Linux emulator instrumentation.
`android-update-gate.yml` manually builds QA APKs with optional upload.
All workflows have read-only repository permissions, bounded runtimes and
nonpersistent checkout credentials. They require no production secrets.
Regular CI uploads no artifacts; optional manual artifacts expire after one day.
No dependency caches are created. Temporary artifacts cannot be the only
corresponding-source delivery mechanism for distributed binaries.

## Qualified Windows packaging

The actual recipe is `packaging/build_release.ps1` / `MastixaManager.spec` with
TLS/CRT/EPSG/Mesa guards. It uses locked PSF CPython 3.14.8 and FireDaemon
OpenSSL 3.5.9, wheel hashes in `requirements-windows-rc-hashed.txt` and supplier
identities in `packaging/windows-tls-inputs.json`. Preserve all locks.
Stock setup-python is for source tests, not qualified binary packaging.

Supplier roots/build venv must be independently provisioned at the relative
locations in the TLS lock. Supplier binaries and matching dependency-source
archives are not bundled in this snapshot. Public automated supplier bootstrap
and hosted frozen/installer qualification are still pending. Do not relax hashes,
copy ambient PATH DLLs or use an unqualified runtime to get a green result.

After prerequisites and owner authorization, invoke the existing build script
with distinct work/dist/installer paths. Before any binary upload, verify the
actual bundle, CRT/TLS/Mesa, real EXE smoke (`smoke_test_packaged.ps1`), installation,
upgrade/repair/uninstall/data preservation, EPSG/PDF/GIS/native routes and owner
acceptance. Bind source/SBOM/checksums to that exact artifact. Deliver required
covered source, patches, controlling build scripts and replacement instructions
with durable equivalent access. Source tests alone cannot approve publication.

Retained details: [distribution source](DISTRIBUTION_SOURCE.md),
[source delivery](SOURCE_DELIVERY_PLAN.md), [replacement](WINDOWS_LIBRARY_REPLACEMENT.md),
[CRT](WINDOWS_CRT_NORMALIZATION.md), [EPSG remedy](WINDOWS_EPSG_REMEDIATION.md).
Historical local archive paths are evidence references, not public downloads.
Use [RELEASE_STATUS.md](RELEASE_STATUS.md) for the current decision.

## External VC++ launch mode — 2026-10-12

The only active prerequisite mode is `external-launch`, configured in
`packaging/windows-prerequisite.json`. Its x64 minimum remains 14.51.36247.0.
The application bundle continues to exclude all Microsoft CRT copies under the
existing locked B2 policy. Setup includes neither the redistributable package
nor download/execution/consent logic; detection happens at launch.

Full `build_release.ps1` builds the native launcher before compiling Setup and
passes `MyLauncherPath` plus the frozen `MyAppSourceDir`. `-SkipInstaller` still
returns the bare frozen payload for its existing qualification checks; it is not
the user-facing installed launch layout. Inno places the launcher at the root
and the unchanged frozen payload under `engine/`.

`build_windows_launcher.ps1 -OutputDir <fresh-path>` requires installed entitled
MSVC x64 tools and Windows SDK; it does not install them. Discovery uses vswhere
or explicit tool/SDK parameters. C11, `/W4 /WX /GS /Zl` and `/NODEFAULTLIB` keep
first-party guard support and reject any CRT-library dependency. The native
front end links only Windows SDK import libraries, with ASLR/NX, random stack
cookie, asInvoker/DPI manifest and System32-only dependent-load policy.
`launcher_audit.py` inspects actual PE imports/delay imports and hardening.

To package an already-qualified frozen application without rebuilding it,
use `build_external_vc_candidate.ps1` with explicit payload, its exact member-hash
manifest, native launcher, qualified compiler/Python and fresh output paths.
`external_vc_layout.py` verifies B2 locks and preserves every payload byte.
One compile attempt is made per invocation; failed diagnostics are retained.
Installer read-back/extraction, member comparison and native qualification are
separate mandatory steps. Never execute a candidate on the owner's live PC.

With `-BuildSyntheticTests`, the native builder also emits private headless
policy/argument/owned-fixture-child tests and a console-only runtime probe.
The latter uses the production detector, reads only HKLM runtime metadata and
System32 files, prints a status and exits; it never launches the GUI/payload or
writes registry/data. Neither diagnostic executable is installed with Mastixa.

`vc_redist_prerequisite.iss` and its lock remain engineering references. The
historical `repackage_rc2.ps1` now refuses use against the revised installer.
Future separately approved bundling can reuse that reference and the mode/hook
boundary while keeping the native launcher and frozen payload; it needs
Microsoft clarification, reviewed delivery terms, new build and qualification.
The current JSON/ISPP guards reject bundled mode and expose no user option.

Native C/header/resource/manifest files are included by the source snapshot
allowlist. Deliver those source/build inputs, generated-policy derivation and the
exact original frozen source plus installer/launcher overlay and required full
supplier/Qt/PDFium materials. A new code-only ZIP is not complete corresponding
source or legal clearance. No archive consolidation or workspace cleanup is part
of this change.
