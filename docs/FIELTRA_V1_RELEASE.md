# Fieltra v1.0.0 Stable — release and corresponding source

Fieltra — Farm Management is free, open-source, offline-first software for Windows.
The official [v1.0.0 Release](https://github.com/Sxara242/Fieltra/releases/tag/v1.0.0)
provides the Windows installer and the source materials listed below.
Android remains in development. First-party material is **AGPL-3.0-only**;
historical contributor copyrights and third-party terms are preserved.

## Accepted Windows installer

| Item | Value |
| --- | --- |
| Installer | `Fieltra-1.0.0-Setup.exe` |
| Bytes | 54,347,611 |
| SHA-256 | `b4f0efebb54dac65735761d5dbf0197e5529252be13a1f279d95c26178cfee56` |
| Product / version / channel | Fieltra — Farm Management / 1.0.0 / stable |
| Windows version / executable | 1.0.0.0 / `Fieltra.exe` |
| Installation | `%LOCALAPPDATA%\Programs\Fieltra` |
| Data and settings | `%LOCALAPPDATA%\Fieltra` |
| AppId | `{8A6CE872-CC79-4605-9084-893E304E38AD}` |

Windows Sandbox installation, startup, Dashboard, branding/version and final Open
Source presentation are owner-accepted PASS. Export to host and installer SHA-256
are verified. This accepted installer is preserved unchanged. It requires the
independently obtained Microsoft VC++ x64 runtime 14.51.36247.0 or newer.

## Demonstrated source correspondence — PASS

The [v1.0.0 tag](https://github.com/Sxara242/Fieltra/tree/v1.0.0) points to the final
source commit, whose exact SHA is stated in the Release notes. It descends from
public parent `e5b56568f8396f3b0547d8f151e7904314ff3225`. The binary was built from
retained source before this publication commit; the correspondence below is
content-based, not an invented build-time commit receipt.

- **116 first-party Python modules MATCH:** CPython 3.14.8 code-object comparison,
  normalizing only `co_filename`; 114 match optimization 0, while `app.crop_program`
  and `app.plant_tracking` match optimization 1.
- **76 packaged resources/documents MATCH** the retained build-source bytes.
  Publication-only updates to `source-artifacts.json`, `DISTRIBUTION_SOURCE.md`
  and `SOURCE_DELIVERY_PLAN.md` are documented in the source index, with their
  original embedded hashes. Git text normalization can change CRLF to LF.
- **Installer source correspondence PASS:** reconstructing the canonical
  `installer_identity.py` input object from 560 payload files, six exact installer
  source inputs, compiler inputs and predecessor ID reproduces embedded build ID
  `8987dad40ab05f9c6fcbef93d96165a3e018d884961ef974a5c310909f40de24`.
- **Native launcher correspondence PASS:** one authorized Sandbox compilation
  using retained MSVC 14.51.36231 / SDK 10.0.26100.0 produced matching executable
  code, all five resource payloads and all remaining data. The only differences
  are COFF and debug-directory timestamps at file offsets `0xE0` and `0x24CC`.
  Masking only these two timestamp fields in memory makes the complete files
  byte-identical. All ten recorded native source/build/policy pins match.

| Launcher comparison | SHA-256 |
| --- | --- |
| Distributed launcher | `b6d70e934a5fbd1a9bd692182acfff6ebfde46f58d7afa0948a9d8ac342290a4` |
| Single guest reconstruction | `04b86cfe20dad3043f09734f46fa0dadb5b4f5cc89e2a9d0dda8042d682cd72b` |
| Both files with only the two timestamps masked | `2579c0f3454caf5a103a0f8b11e1425827d8c1be2acce5e3da52ec88a4b3aef8` |

The original exported `RELEASE_BUILD.json` is retained unchanged, including its
null source commit and pre-install cutoff. Later owner acceptance and the content
comparisons above close those later scenarios; no new commit is inserted into an
old receipt. Bit-for-bit reproducibility is not claimed or required by this
correspondence result. The native-launcher provenance issue is CLOSED.

## Source downloads

Use the tagged application source plus **both** unchanged companion archives:

| Download | Bytes | SHA-256 |
| --- | ---: | --- |
| [Dependency sources and materials](https://github.com/Sxara242/Fieltra/releases/download/v1.0.0/MastixaManager-1.0.0-rc.2-repack-source.zip) | 336,765,013 | `e6aed5b7eab77185b34f2ea0033dab422106519721969b157d9dcbf72bb91700` |
| [Complete QtPdf/PDFium carrier](https://github.com/Sxara242/Fieltra/releases/download/v1.0.0/qtwebengine-everywhere-src-6.11.2.tar.xz) | 580,351,104 | `6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163` |

The main archive contains 34 dependency source archives: PySide6/Shiboken 6.11.2,
matching QtBase/QtSvg/QtImageformats/QtTranslations, CPython 3.14.8 and its source
dependencies, NumPy/OpenBLAS, Shapely/GEOS, pyproj/PROJ, OpenSSL 3.5.9 and other
pinned Python components. It includes selected producer scripts/configuration,
PDFium patch references, full legal texts and replacement recipes. The separate
intact QtWebEngine carrier supplies QtPdf, nested Chromium/PDFium sources,
CMake/GN controls and notices. Its Qt changes are already incorporated; do not
apply the reference PDFium delta a second time.

The old carrier's `application/` ZIPs and build/status records describe historical
Mastixa RC2. Use the **Fieltra source tag** for application, launcher and installer
source. The two carriers are reused for unchanged dependencies/materials; they
are not substituted for current application source. No Microsoft runtime binary,
private profile, recovery collection or raw audit archive is a Release asset.
Retain source access while binaries are distributed and for at least five years
after last distribution under existing project policy.

## Build controls and replacement

Verify the archive hashes. Extract the main archive and place the intact Qt archive
at `dependencies/qtwebengine-everywhere-src-6.11.2.tar.xz`. Its existing
`verify_package.py` checks the historical carrier with Python 3.11+; it does not
by itself establish the Fieltra application binding.

Follow its `BUILD_INSTRUCTIONS.md` for pinned supplier retrieval/hashes and the
sibling `WindowsReleaseSuppliers` layout, replacing the old application ZIP step
with the Fieltra tagged checkout. Preserve the CPython 3.14.8 supplier selection,
build-wheel hash lock, TLS/CRT/EPSG/Mesa controls, source archives and legal terms.
See [BUILDING.md](BUILDING.md), [dependency rebuilding](WINDOWS_DEPENDENCY_REBUILD.md)
and [QtPdf instructions](WINDOWS_QTPDF_REBUILD.md).

The final controls are `packaging/build_fieltra_sandbox.ps1`, `build_release.ps1`,
`MastixaManager.spec`, `build_windows_launcher.ps1`, `installer_identity.py`,
`windows-prerequisite.json` and `installer/MastixaManager.iss` with its includes.
The Sandbox wrapper requires independently provisioned suppliers and explicit
MSVC/SDK paths for a new launcher. The final branding correction reused the
already built Fieltra launcher through `ReuseLauncherPath` and `PredecessorIdentity`.
A recipient can build its own launcher without the publisher's original receipt.
Use Inno Setup 6.7.3 with its original companion `.issig` files from the
[official distribution](https://github.com/jrsoftware/issrc/releases/tag/is-6_7_3).
General-purpose compiler/runtime binaries are obtained separately under supplier terms.

Close Fieltra and back up a writable application copy before replacing libraries.
Compatible x64 DLLs/plugins live under `engine/_internal/PySide6`,
`engine/_internal/shiboken6`, `engine/_internal/Shapely.libs` and
`engine/_internal/pyproj.libs`; the PDF plugin is
`PySide6/plugins/imageformats/qpdf.dll`. Preserve ABI, exports, dependencies and
filenames. Use synthetic data for experiments. Follow the existing
[library replacement instructions](WINDOWS_LIBRARY_REPLACEMENT.md), prepending
`engine/` to older onedir paths. Applicable modification/debugging rights remain;
build-time input hash checks do not prevent runtime library replacement. Repair
or updates can overwrite modified libraries; retain your sources and copies.

## Repository identity

The public repository was renamed from `Sxara242/Mastixa-Manager-Source` to
[Sxara242/Fieltra](https://github.com/Sxara242/Fieltra) without rewriting history.
The accepted binary retains its old Source Code URL; GitHub's repository redirect
preserves that destination. Internal identifiers and legitimate historical
copyrights are retained. No production-user migration is required.
