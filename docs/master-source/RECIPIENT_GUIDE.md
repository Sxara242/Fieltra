> Current source publication candidate (2026-10-15): a NEW builder is integrated
> alongside the retained application source associated with owner-accepted Setup
> `9457f1f4a8223de76caa49c1ba88a6dddd3e5176868dc25eb88a93eb9293875f`.
> Its historical 3,008-byte build script was not recovered; the owner closed that
> search. No historical source equivalence or acceptance transfer is claimed.
> See [PUBLICATION_CANDIDATE.md](../PUBLICATION_CANDIDATE.md) for the current scope,
> dependencies, hash-map payload manifest and future guest-only build route.
> The historical guide below documents a DIFFERENT Phase 2D/2E acceptance-polish
> delivery. Its pins, file counts and examples do not verify this Git source tree.
> All seven recovery tests remain SUCCESS; SmokeTest CLOSED. RELEASE NO-GO.

# Recipient verification and reconstruction — tools 1.0.0-phase2e1

**Preparation; RELEASE NO-GO.** Integrity PASS is not approval of distribution,
legal sufficiency, a build or a native Windows acceptance test. No source host or
download route has been qualified yet. A publisher must supply the complete source
view and independent trust pins before asking an external recipient to use it.

## Delivery contract and independent trust

Receive two sibling directories; their names may change:

```text
source-delivery/                 original pinned Phase 2D view, read-only
  MASTER_SOURCE_MATERIALIZATION.json
  MASTER_SOURCE_RELEASE.json
  MASTER_SOURCE_PUBLICATION_SELECTION.json
  application/source/           editable frozen application source, 869 members
  dependencies/                 all 35 intact supplier source archives
  materials/                    source controls, patches and replacement references
  legal/                        full selected license/notice/attribution payload
  BUILD_INSTRUCTIONS.md, DEPENDENCY_SOURCES.md, LIBRARY_REPLACEMENT.md
recipient-verifier/              independent tools; do not insert into source-delivery
  master_source.py, audit_public_source.py
  LICENSE, RECIPIENT_GUIDE.md, TOOL_MANIFEST.json
```

The complete source view contains 1,197 files / 924,800,158 logical bytes. Its
receipt SHA-256 is
`b3f514fed24d716246a4fd2c577e94d1d671cd1cdc62ff899800996c91b002e8`.
This expected digest must also be obtained through an authenticated independent
publisher channel. A digest computed from a received receipt is not a trust anchor.
Similarly obtain the expected TOOL_MANIFEST digest independently, before running
received code. The separate tool manifest hashes four payload files, never itself;
the source receipt does not hash or authorize the verification tools. The maintained
Master Source remains the source authority, not this small tool-delivery receipt.

No private developer paths, root maps, Git checkout/history, local environment or
evidence archives are required for verification. Python 3.11+ with its standard
library is required; isolated automated qualification used x64 CPython 3.12.14.
No PySide, pip packages, virtual environment, compiler or Git is needed to verify.

Before execution, use trusted system checksum tools to verify the tool manifest
and all four fixed payload names. For PowerShell, from the verifier directory:

```powershell
# Enter the digest supplied independently by the publisher; do not derive it here.
$expectedToolDigest = '<independently supplied TOOL_MANIFEST SHA-256>'
$ancestor = Get-Item -LiteralPath '.'
while ($ancestor) {
    if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Tool ancestor link refused' }
    $ancestor = $ancestor.Parent
}
$allowed = @('master_source.py','audit_public_source.py','LICENSE','RECIPIENT_GUIDE.md','TOOL_MANIFEST.json')
foreach ($entry in (Get-ChildItem -LiteralPath '.' -Force)) {
    if ($entry.PSIsContainer -or $entry.Name -notin $allowed -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected tool file or link' }
}
if ((Get-FileHash -LiteralPath './TOOL_MANIFEST.json' -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedToolDigest) { throw 'Tool manifest mismatch' }
$tool = Get-Content -LiteralPath './TOOL_MANIFEST.json' -Raw -Encoding UTF8 | ConvertFrom-Json
if ($tool.schema -ne 1 -or $tool.kind -ne 'master-source-recipient-tools' -or $tool.tool_version -ne '1.0.0-phase2e1') { throw 'Unsupported tool manifest' }
$names = @('master_source.py','audit_public_source.py','LICENSE','RECIPIENT_GUIDE.md')
$actualNames = ($tool.files.PSObject.Properties.Name | Sort-Object) -join ','
$expectedNames = ($names | Sort-Object) -join ','
if ($actualNames -ne $expectedNames) { throw 'Unexpected tool membership' }
foreach ($name in $names) {
    $file = Get-Item -LiteralPath (Join-Path '.' $name) -ErrorAction Stop
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Tool link refused' }
    $row = $tool.files.$name
    if ($file.Length -ne $row.size -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256) { throw 'Tool payload mismatch' }
}
```

Use fresh ordinary local directories, without links/junctions in their ancestors,
and coherent files with no concurrent writer. Obtain the Python interpreter through
a trusted authorized route. The checksum/bootstrap commands require a trusted OS,
PowerShell and independently obtained pins; they are not protection against a
privileged process changing files during verification. Do not run extra received
scripts. Run the pinned tool from any working directory:

```powershell
# Set these three paths to the recipient's own existing interpreter/directories.
$python = '<trusted Python executable>'
$tools = '<recipient-verifier directory>'
$source = '<source-delivery directory>'
& $python -X utf8 -I -S -B (Join-Path $tools 'master_source.py') --version
& $python -X utf8 -I -S -B (Join-Path $tools 'master_source.py') verify-recipient --output $source --receipt-sha256 b3f514fed24d716246a4fd2c577e94d1d671cd1cdc62ff899800996c91b002e8
if ($LASTEXITCODE) { throw 'Recipient integrity verification failed; preserve and inspect' }
```

`-I -S -B` ignores environment/site imports and avoids bytecode writes. The explicit
source directory must be absolute. The tool reads that supplied tree only, checks
the pinned receipt, exact manifest/policy, all expected hashes/sizes/membership,
supplier/legal/build references, historical identity and publication selection.
Missing/altered/extra files, traversal, links/reparse paths and hard links fail.
It never downloads, builds, installs, repairs or changes supplied source.
Diagnostics suppress untrusted values. Deterministic JSON results retain NO-GO.
Never replace a failed expected pin with the computed received digest to get PASS.

Selected Setup identity is
`64ff65ac8b4e3761486b4ee22d7d0fdc68148bbc02c914fd11c0941e1215f820`;
original private source ZIP identity is
`adce76181906a205b345df271cf2a94f715dbb3060f9bd474a34fe5784dd0bee`.
The private ZIP is not required by a recipient. Its 873-member policy explicitly
omits four internal administrative documents and preserves 869 exact source files.
Derived tree fingerprint is
`e7defdcdc56b1df08eab4e898684bebb13f7725a25ddbd0a1d4336edacceeb9e`.
Current Sidebar Option A is absent from this frozen installer/source selection.

## Application reconstruction and prerequisites

**Procedures below have not been executed as a clean recipient build.** Verification
alone cannot prove usable binaries or reproduction of byte-identical publisher
output. No installer build is authorized in Phase 2E-1 or by reading this guide.

Copy the verified editable tree into a new writable workspace, retaining the
received view unchanged. This is a recipient working copy, not a new source authority:

```text
work/MastixaSource/              contents of source-delivery/application/source/
work/WindowsReleaseSuppliers/psf-python-3.14.8/
work/WindowsReleaseSuppliers/firedaemon-openssl-3.5.9/x64/bin/
work/WindowsReleaseSuppliers/build-venv/
work/output/                    every build output fresh
```

The frozen source's `packaging/windows-tls-inputs.json` deliberately resolves
these declared sibling supplier roots. Provision them; an unrelated Python/venv
or hidden developer cache cannot substitute. Required binary tools/suppliers are
not bundled with corresponding source:

- Windows x64 and separately installed Microsoft VC++ x64 runtime
  **>=14.51.36247.0**. The Microsoft redistributable and app-local CRT are not supplied.
- PSF full runtime **3.14.8**, archive hash
  `4873947a8afc037846b180312b83c744a4146a851cfd316a75c3125a4d8299da`;
  FireDaemon OpenSSL **3.5.9** supplier ZIP hash
  `76da391395be029b44794857b9ff380255e02a0960a98314cd3f6a6816d82696`.
  Acquisition locations and 28 selected supplier file hashes are in the included
  `BUILD_INSTRUCTIONS.md` and source TLS lock. Availability is NOT VERIFIED here.
- Source `requirements-windows-rc-hashed.txt`: exact **23-wheel** lock, including
  PySide6/Shiboken **6.11.2**, NumPy **2.5.3**, Shapely **2.1.2**, pyproj **3.8.0**
  and PyInstaller **6.22.3**. Install with `--require-hashes --only-binary=:all:`
  after authorized acquisition into the declared supplier environment. No acquisition
  or dependency installation occurred during this phase.
- Launcher: entitled compatible x64 MSVC/Windows SDK. The archived launcher script
  accepts explicit `-VCToolsDir`, `-WindowsSdkDir` and `-WindowsSdkVersion`; select
  the intended tool versions rather than relying on latest local discovery.
- Optional installer: qualified Inno Setup **6.7.3**, ISCC hash
  `0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7`.
  Its required resources must also match the controlling archived inputs. Another
  executable with the same version string is insufficient. No guard is waived.

From `work/MastixaSource/`, after independent provisioning, the application route is:

```powershell
$buildPython = '../WindowsReleaseSuppliers/build-venv/Scripts/python.exe'
& $buildPython -m pip install --require-hashes --only-binary=:all: -r requirements-windows-rc-hashed.txt
powershell -NoProfile -File packaging/build_release.ps1 -SkipInstaller -PythonPath $buildPython -PyInstallerWorkPath ../output/app-work -PyInstallerDistPath ../output/app-dist
```

Create the venv with the pinned supplier interpreter as described in
`BUILD_INSTRUCTIONS.md`; its `sys.base_prefix` must match the supplier root. The
retained broad build instructions contain an earlier bundled-installer command:
the `-SkipInstaller` application route above and external launcher/candidate route
below supersede it. Dated private evidence references are historical information,
never provisioning requirements. Verification is independent of Git; retention
utilities using `git ls-files` are not needed to reconstruct this received tree.

For an independently authorized later package reconstruction, use the selected
source's `build_windows_launcher.ps1` into a fresh output, enumerate the fresh app
payload with `safe_files` in `external_vc_layout.py`, then call
`build_external_vc_candidate.ps1` with explicit `-PayloadDir`, `-PayloadManifest`,
`-LauncherPath`, `-CompilerPath`, `-PythonPath` and new `-OutputDir`. The payload
manifest is a generated mapping of relative path to SHA-256, not a private receipt.
The snapshot includes its exact installer/launcher/layout/identity scripts and
legacy ancestor map. Existing supplier/CRT/TLS/EPSG/legal guards remain intact.
A newly generated binary has a new identity; it is not the accepted frozen Setup.

## Covered-library reconstruction and replacement

Keep all source archives, notices and material recipes. For full details use the
included build/replacement guide and source `docs/WINDOWS_DEPENDENCY_REBUILD.md`,
`docs/WINDOWS_QTPDF_REBUILD.md`, and `docs/WINDOWS_LIBRARY_REPLACEMENT.md`.
These are supplied documents; optional private producer logs are unnecessary.

Qt/PySide: full producer sources are in `dependencies/`, including Qtbase and
qtsvg pinned commits and pyside-setup **6.11.2**. Build a coherent compatible
development SDK and binding set using included configure/CMake/setup/typesystem
and generation scripts. Runtime wheels alone lack development headers, import
libraries and tools. Qt SDK correspondence records MSVC **19.44.35227.0**,
CMake **3.30.5**, Ninja **1.10.2**; functional QtPdf guidance uses Windows SDK
**10.0.26100.0**, Python **3.8+** with html5lib. Matching libclang and build
requirements must come from the archived PySide instructions. Those separate
general-purpose tools are not an offline build kit and were not provisioned here.

QtPdf/PDFium: retain the complete **580,351,104-byte**
`dependencies/qtwebengine-everywhere-src-6.11.2.tar.xz`, hash
`6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163`,
including Chromium/PDFium, GN/CMake controls and third-party notices. Its integrated
delta is already applied; `materials/pdfium/pdfium-source-delta.patch` is a comparison
reference, not a second patch application. There is no proven smaller source closure.
Build the archived `Pdf` and `QPdfPlugin` targets with the documented QtPdf settings.

OpenSSL: preserve both `openssl-3.5.9-source.tar.gz` and
`psf-openssl-3.5.9.tar.gz`, their controlling recipes in `materials/WindowsReleaseSuppliers/`
and CPython PCbuild inputs. Distinct Python and Qt consumers/envelopes are not
interchangeable. PROJ **9.8.1** / pyproj **3.8.0** retain the editable overlay,
EPSG/IOGP credits/disclaimers, IGNF/IAU terms and source provenance controls.
GEOS **3.13.1** / Shapely **2.1.2** need coherent repaired-wheel DLL names/imports
(delvewheel **1.11.1** recipe), not renaming a lone DLL. Other 35-archive supplier
obligations and full NOTICE/copyright texts remain in their original archives/legal set.

To exercise the documented dynamic-library route, close the application and make
a new writable copy of the complete onedir program. Use a synthetic data home.
Replace compatible Qt/PySide files under `_internal/PySide6`, Shiboken under
`_internal/shiboken6`, the coherent `Qt6Pdf.dll` and `plugins/imageformats/qpdf.dll`
pair, or Shapely/GEOS loader and `Shapely.libs` set as applicable. Keep x64/Qt6.11
and Python limited-API compatibility, required exports and dependent libraries.
Verify actual loaded paths/hashes plus startup, input, PDF export/preview and GIS
operations. Update/repair overwrites program files; preserve/reapply a compatible
modified set or use a separate versioned copy. No automatic installed-library hash
guard was found in the reviewed source; this is static evidence, not a new native test.

Historical resource-marked QtPdf loading is narrow prior evidence, not a source
rebuild. `materials/replacement-reference/` scripts refer to its old retained PYZ
and layout; do not run them as portable current-candidate acceptance commands.
The usable shared-library route is not yet independently qualified for this exact
candidate. If that route fails, corresponding application/object relinking material
and any necessary Installation Information must be assessed and supplied under
the applicable alternative; neither existence of DLLs nor this guide proves it.

## License, Installation Information and limitations

The application and these first-party tools retain **AGPL-3.0-only**; keep `LICENSE`,
selected `legal/THIRD_PARTY_NOTICES.md`, source notices and every license/attribution
payload. LGPL modification/replacement/debugging rights remain. No license is changed.

The owner specifies standalone software downloads for recipients' existing PCs,
not transfer of a PC/device with the program. No qualifying User Product transfer
has been identified in that model. Applicability of the specific Installation
Information duty remains **CONDITIONAL**, with no blanket exemption based on
Windows or professional application use. A consumer PC can be a User Product;
device bundles, preinstallation, fixed-term device transfers or locked channels
must be reassessed. See [AGPLv3 section 6](https://www.gnu.org/licenses/agpl-3.0.html)
and [LGPLv3 section 4](https://www.gnu.org/licenses/lgpl-3.0.html).

If applicable, provide sufficient install/run procedures, required authorization
or signing information and replacement/relink steps for modified versions, including
actual platform/channel constraints. The current source declares an unsigned RC
and no publisher installed-DLL signature gate; new native testing must confirm
actual Windows policy behavior. No publisher signing key is identified as required
by this source. A future enforced signing/locked device route needs its own analysis.
Source and LGPL replacement duties persist independently of this conditional trigger.

Unqualified items: actual clean recipient app/library/package builds, substantive
modified-library loading, tool/supplier acquisition, supported anonymous source
retrieval/retention, applicable installation constraints, native/security/owner
acceptance and independent restore. Historical bundled Microsoft Community 2026
section 8(b)(ii) stays separately BLOCKED. This external-runtime view does not bundle
that redistributable. Full private CI logs and bit-identical producer reconstruction
are not automatically corresponding-source requirements. Known missing necessary
source would fail the contract rather than be waived as optional evidence.
