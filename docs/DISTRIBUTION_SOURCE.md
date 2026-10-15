# Fieltra v1.0.0 — corresponding source and library replacement

Fieltra is free, open-source software under AGPL-3.0-only. Application, native
launcher and installer source correspond to the accepted Stable installer;
all source correspondence items PASS, including the timestamp-only launcher comparison.

Use the [tagged Fieltra source](https://github.com/Sxara242/Fieltra/tree/v1.0.0)
and both Release source companion archives. [FIELTRA_V1_RELEASE.md](FIELTRA_V1_RELEASE.md)
provides exact hashes, download links and the demonstrated source binding.
[source-artifacts.json](source-artifacts.json) retains dependency/source identities.
Historical application ZIPs in the companion do not replace Fieltra source.

For the external-launcher layout, covered libraries reside under `engine/_internal/`.
Close Fieltra and back up a writable application copy, replace compatible x64
libraries preserving ABI/exports/dependencies, and use synthetic data for experiments.
Build-input hash checks do not remove runtime modification or debugging rights.
Explicit repair/updates can overwrite replacements; keep your modified sources/copies.
See [replacement instructions](WINDOWS_LIBRARY_REPLACEMENT.md) and
[dependency build controls](WINDOWS_DEPENDENCY_REBUILD.md).

The historical records below retain their original dated scope. Their pending
or blocked statuses do not override the current Fieltra release correspondence.


---

Historical records and retained technical instructions follow. Earlier status statements
do not override the Fieltra v1.0.0 preparation status above.

> Retained historical engineering record, sanitized for public review.
> Current status: [RELEASE_STATUS.md](RELEASE_STATUS.md). This record does not
> establish approval of the current source or a new binary release. Local-only
> receipt paths refer to privately retained evidence, absent from this snapshot.

> Current legal gate2026-10-08: B1-LEGAL/B4-LEGAL PASS; B1-AUDIT/B4-REPRO INCOMPLETE (non-blocking); B3-LEGAL BLOCKED.
> Prior private-CI/bit-identical/full-rebuild prerequisites are superseded by WINDOWS_RELEASE_GATE_POLICY.md.
> Required matching source/controlling scripts/replacement rights and future public source access remain mandatory.
> Exact review: WINDOWS_B3_LEGAL_CLOSURE.md. No RC build/preflight authorized by this note.

# Final narrow B1/B3/B4 closure — 2026-10-08

**BLOCKED BEFORE RC BUILD.** RELEASE-INFRA / DESKTOP, Windows x64. This section
supersedes older blocker wording. B2 and B5 are PASS RETAINED, without reruns or
input/policy changes. `native_notices_complete=false` and
`corresponding_source_ready=false` remain unchanged. RC may not be built.

| Gate | Status | Evidence | Remaining action |
| --- | --- | --- | --- |
| B1 | BLOCKED |39 exact shipping PE nodes +3 embedded nodes; exact absent-node decisions; pinned OpenBLAS publish run/x64 ILP64 job | Executed QtPdf GN/patch/compiler graph, binding generation/build correspondence and static GCC source/version/artifact receipts |
| B2 | PASS RETAINED | Zero Microsoft DLL/installer shipment; independent x64 VC Redist >=14.51.36247.0; canonical-import frozen receipts unchanged | none |
| B3 | BLOCKED | Unchanged proj.db; retained39-table/77707-row correspondence;4 Esri transform+usage input matches;6 NKG2008 parameter matches | Original Esri lookup state; LT ty difference/NKG2020; IGNF/ITRF/IAU/init terms; EPSG modification compliance |
| B4 | BLOCKED | Benign modified QtPdf DLL actually loaded by frozen Mastixa from documented path; startup/PDF/preview PASS; deterministic source mechanism retained | Missing matching producer/generator/build materials and complete rebuild instructions; later artifact/source delivery binding |
| B5 | PASS RETAINED | Qualified TLS3.5.9/Mesa exclusion receipts and inputs unchanged | none |


Recipient replacement instructions and explicit-update overwrite behavior are in the supplied SOURCE_DELIVERY_PLAN.md. Exact matching source/build material gaps remain; no public source or artifact binding is claimed.

---

# B2 canonical-import build delta — 2026-10-08

**B2 PASS; B4 remains BLOCKED.** Planned distribution has no Microsoft CRT DLLs
or runtime installer. Official x64 VC Redist >=14.51.36247.0 is an independently
installed recipient prerequisite. packaging/crt_policy.py plus its JSON lock
reproduce five third-party import-string/checksum transformations from the23
original locked wheels and remove13 former CRT entries at collection time.
The transformed NumPy/GEOS/PROJ files carry separate input/output hash receipts;
they are not claimed to be pristine wheel RECORD files or upstream rebuilds.
Original source/license/producer receipts are preserved. B4 source/replacement
gaps remain unchanged; this B2 patch is included by the existing source selector.
Historical source ZIP hashes describe prior bytes and were not refreshed or
claimed to match this checkpoint. See WINDOWS_CRT_NORMALIZATION.md.

---

# B2 Community installation re-evaluation — 2026-10-07

**B2 BLOCKED; B4 BLOCKED; B5 PASS RETAINED.** New legally installed Community2026
18.10.3 supplies a conditional grant for listed unmodified Microsoft release
CRT. It does not close exact older10 CRT code/origin correspondence,3 hashed
filename permissions, recipient protective assent or a qualified canonical
packaging route. Exact13-file mapping and terms are in
`WINDOWS_MICROSOFT_REDISTRIBUTION.md` and `windows-microsoft-runtime.json`.
Microsoft proprietary CRT is not offered as modifiable AGPL/LGPL application
source. Keep existing covered-library replacement rights intact.

No new release artifact/source binding is claimed. Previous deterministic
source-candidate ZIPs and receipts are retained unchanged as historical captures;
these new documentation bytes are outside those captures. Refresh source
candidate only after the selected CRT route and other required closure materials
are ready. B1/B3/B4 materials, B5 inputs and supplier binaries remain untouched.


---

# Current source and replacement delivery — 2026-10-07

**B4 BLOCKED; B5 retained PASS.** Full official QtWebEngine6.11.2 archive with
nested Chromium/PDFium is retained locally. Matching Qtbase ef55f427 and SVG
17ca512f producer sources/build configuration are now retained. QtImageformats
SDK lacks a pinned source revision; wheel QtPdf GN arguments/target attribution,
patches/toolchain and binding/GEOS/OpenBLAS build/source correspondence remain
incomplete. Source tag URLs alone are not an exact matching source commitment.

Use `packaging/source_snapshot.py` to assemble the reviewed dirty Windows source
inputs into a deterministic local prebuild ZIP/receipt outside the checkout.
It includes required untracked runtime/build/legal files, sorted names, fixed ZIP
timestamps/permissions, exact source SHA256s; excludes owner data/backups/logs,
credentials/signing material/Git/evidence directories. Final candidate hash and
source binding are pending because no release binary exists. Local retention is
not public delivery or a written source offer. Before actual distribution, make
matching sources/build instructions and covered notices available by a lawful
license route and preserve them while binaries are available and at least five
years after last distribution (project policy); retain archival copies thereafter.

Intended LGPL3 route: suitable dynamically linked Qt/PySide/shiboken/GEOS DLLs.
Allow compatible recipient replacement and reverse engineering for debugging
modifications as required.26 SDK DLL/plugins were replaced in an isolated copy:
startup/PDF/GIS PASS, no runtime signature enforcement. SDK code sections are
identical, so this demonstrates mechanism, not complete modified-library source
or replacement qualification. Full alternate QtPdf/bindings/GEOS builds remain
missing. Build-time release hash validation is not a runtime replacement ban.
No automatic object-file obligation is asserted for a usable dynamic route;
an alternative relinking/object route would be needed if that route is unusable.
Assess User Product installation-information requirements for the eventual
actual installer/product; it is unsigned and no final installer exists yet.
No online source mirror, source offer, signing key, real profile or public updater
feed is created. Readiness flags remain false. Full gate details in
WINDOWS_DISTRIBUTION_COMPLIANCE_MATRIX.md and SOURCE_DELIVERY_PLAN.md.

---

> Updated exact-source checkpoint — 2026-10-07: see the supplied
> [SOURCE_DELIVERY_PLAN.md](SOURCE_DELIVERY_PLAN.md) and
> [source-artifacts.json](source-artifacts.json) for component-specific routes,
> pinned source versions/hashes, QtPdf nested source identity and retention.
> Verified local archives now exist; full matching build/replacement materials
> and future dirty-application release source archive/access are incomplete.
> No publication or written source offer has occurred. Current status remains
> BLOCKED BEFORE RC BUILD; the general checklist below is retained.

# Corresponding source and library replacement

Public Mastixa code: **AGPL-3.0-only**. Public binary releases require concrete,
matching source delivery; a generic repository link is not sufficient evidence
that a binary built from this dirty Windows checkout has its corresponding
source available. Current status: **source delivery not yet implemented**.
No tag, release, source archive or production feed is published in this batch.

Planned distribution route: place the exact application corresponding-source
archive beside the installer on GitHub Releases, with clear download links in
release notes. Include preferred editable code, artwork/resources/locales,
schema/migrations, requirements with resolved versions, build/installer scripts,
configuration, license/notices and installation/build instructions. Include
every required file from this uncommitted checkout, not merely current HEAD.
Keep personal data, backups, private evidence, logs, secrets and output caches
out of that archive. The canonical project repository is
https://github.com/Sxara242/Mastixa-Manager-Source .

| Component / route | Concrete required delivery and verification |
| --- | --- |
| Mastixa AGPLv3 | Full `LICENSE`, appropriate visible notices/no-warranty/source access, exact preferred source and scripts. Use section 6(d) equivalent source access alongside downloadable binary, with exact version/hash linkage. Modified network-accessible versions must satisfy section 13 where applicable. Mastixa itself remains local-only. |
| PySide6 / shiboken / Qt under LGPLv3 | Full LGPLv3 + GPLv3 texts, prominent notice, exact module/version source and third-party texts. Record local modifications or explicit unmodified status and build parameters. Provide a verified shared-library replacement route or corresponding application code/relinking route under LGPL section 4. Do not add terms prohibiting library modification or reverse engineering for debugging. |
| GEOS under LGPLv2.1 | Preserve GEOS license/copyright and provide exact GEOS source/build/replacement materials under the chosen LGPL route. Shapely BSD terms remain separate. |
| QtPdf/PDFium/indirect plugins | Match the exact Qt native subset and third-party SBOM/source licenses. LGPL labels for the Python wheel do not cover all bundled native code. VirtualKeyboard is excluded, not relicensed. |
| Certifi MPL2 | Preserve the MPL text and make source for covered CA data/files available for the exact shipped release, including modifications if any. |
| Other Python/native permissive components | Preserve exact upstream copyright, permission/disclaimer and required NOTICE text; follow any native subcomponent/source conditions. CPython license chain and component exceptions remain separate. |
| Microsoft runtime DLLs | Verify permitted redistributable origin/version and applicable redistribution terms. Do not relicense these DLLs as AGPL or assume wheel presence proves entitlement. |

Implementation checklist before changing the preflight to ready:

1. Select and verify the exact target Python/wheels/compiler. Record wheel
   hashes, native DLL versions/origins, module SBOM and any modifications.
2. Assemble missing Qt/native notices and matching dependency source archives
   with hashes and source URLs; include license texts in `licenses/manifest.json`.
3. Prepare the exact Mastixa source archive and its version-to-binary manifest.
   Before public distribution, verify free anonymous source access alongside
   binary access and retain the materials for the license-required period.
4. Test replacing compatible Qt/PySide/shiboken and GEOS libraries in the onedir
   layout. Typical files are under `_internal/PySide6`, `_internal/shiboken6`
   and `_internal/Shapely.libs`; source/build instructions must resolve ABI and
   dependent DLLs. Onedir alone is not proof of compliant replacement.
5. Where a static/copied-code route requires object/application code or
   Installation Information, deliver it rather than assuming a shared DLL
   exemption. Record the chosen obligation route per component.
6. Validate legal files and source references in the fresh bundle/installer,
   then complete install/upgrade/KEEP DATA and updater artifact acceptance.

This is an implementation plan and blocked checklist, not a compliance claim
or a standalone written source offer. Do not enable release readiness flags
merely because this document exists.

Authoritative references: [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html),
[LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html),
[Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations),
[Qt 6.11 licensing / SBOM](https://doc.qt.io/qt-6.11/licensing.html),
[PyInstaller licensing](https://pyinstaller.org/en/v6.22.2/license.html).
