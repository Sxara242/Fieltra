> Current 2026-10-11 repack delivery uses a main source ZIP plus a mandatory
> separate full Qt6.11.2 source asset, with SHA-256
> `6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163`.
> [WINDOWS_RC2_REPACKAGING.md](WINDOWS_RC2_REPACKAGING.md) and
> [windows-rc2-repack-delivery.json](windows-rc2-repack-delivery.json) define the
> current layout. Original source materials remain unchanged; Qt source is not
> trimmed. Main ZIP alone is incomplete. Public URLs remain unpublished.

> Retained historical engineering record, sanitized for public review.
> Current status: [RELEASE_STATUS.md](RELEASE_STATUS.md). This record does not
> establish approval of the current source or a new binary release. Local-only
> receipt paths refer to privately retained evidence, absent from this snapshot.

# Current EPSG source delta — 2026-10-08

B4-LEGAL PASS retained; B4-REPRO INCOMPLETE remains non-blocking. EPSG/B3 prebuild
attribution PASS after the narrow provenance remedy described in
WINDOWS_EPSG_REMEDIATION.md. Older broader blocker statements below are historical.

The current source delta must be applied after every retained earlier source
supplement. It includes app/gis/geometry.py, packaging/MastixaManager.spec,
packaging/epsg_provenance.py, packaging/windows-epsg-provenance.json, the modified
release guard/configuration, focused tests and current attribution/legal metadata.
The current recipe derives the shipping proj.db from exact PROJ9.8.1 supplier
input, adding only three operation-provenance descriptions and independent
PROJ900913 alias identity/name/description/usage. It retains the2.0m ranking values,
all parameters/grids/interpolation context and genuine EPSG source references.
Do not ship the original unmarked database as the current binary input.

The source includes editable overlay statements and both source/output hashes.
Recipients may regenerate or modify this data through the documented recipe;
all inherited EPSG/IOGP/other-provider terms, credits and source rights remain.
Keep original dependency/application archives immutable and retain this exact
delta alongside them. Publish equivalent freely accessible matching source only
with a later authorized distribution, binding it to that actual artifact.
This local delta creates no written offer, public source access or binary approval.

---

## IAU exact collection source supplement

Retain licenses/CRS/IAU-collection/{naifcodes_radii_m_wAsteroids_IAU2015.csv,
LICENSE-LGPL-3.0.txt,AUTHORS.rst}, full GPLv3/LGPLv3 and the selected NOTICE.
Publish these with matching PROJ9.8.1 preferred SQL/generator source at any later
authorized distribution; existing exact PROJ source material supplies iau.sql and
build_db_from_iau.py. Keep covered collection contributions under their terms;
no upstream MIT software relicense is asserted. Recipients may modify the source
collection and regenerate the data through PROJ's documented database build route.
The exact source overlay is local and unpublished; no binary/source offer is made.

---

# Final narrow B3 decision — 2026-10-08

**BLOCKED BEFORE RC BUILD.** RELEASE-INFRA / DESKTOP. Current decision supersedes
the older three-topic blocker wording below. B1/B2/B4/B5 legal PASS retained;
B1 audit and B4 reproduction remain INCOMPLETE and non-blocking. B3 remains
BLOCKED solely on the named EPSG adaptation-attribution condition.

| B3 Topic | Status | Legal basis | RC blocking? |
| --- | --- | --- | --- |
| IGNF3.1.0 | PASS | French CRPA statutory public-information/database reuse; source/date/meaning preservation; inherited EPSG terms separately retained | no |
| IAU | PASS | Present LGPLv3 grant for the exactly matching consolidated collection; covered source/credits/terms retained; independent factual scientific parameters, not a paper reprint or government-work claim | no |
| EPSG | BLOCKED | Redistribution/notices basis established; clause6(vii) attribution for upstream accuracy/authority modifications remains material | yes |

Final pre-RC preflight: **NOT RUN**, because B3 is BLOCKED. RC may be built: **NO**.
The unchanged shipping proj.db SHA256 is528b9763b57e85ee78f6f30478ef0494902320f1d71d1564bf0d7ec4f30cc002.
Full earlier39-table/77707-row evidence and B2/B5 qualification are retained.
Only two authority subsets and the named EPSG records were queried read-only.
No full inventory/functional audit/source snapshot/native qualification was rerun.

The IAU NOTICE is now a selected recipient input; exact collection CSV, LGPL
license and AUTHORS are source-only inputs. Current source/legal hashes and
SBOM metadata are reconciled in the bounded delta supplement. Original source
base and all prior supplements remain immutable. Actual artifact/source access,
output notices/privacy and functional checks remain mandatory after a later build.

Legal detail and exact table/row/source map: WINDOWS_B3_LEGAL_CLOSURE.md,
windows-b3-legal-closure.json and sibling WindowsB3FinalEvidence/topic-map.json.
Publish-safety and preservation results: sibling WindowsB3FinalEvidence/final-report.json.

Forensic-only gaps: historical IGNF license page; IAU pre2022 license/correction
lineage; retained LT2008 causal history, B1 private producer correspondence and
B4 bit-identical reproduction. None independently blocks RC.

Exact next step: resolve EPSG clause6(vii) for operations1312/1462 accuracy and
authority attribution900913/7001, through applicable primary interpretation or
a qualified non-attribution remedy preserving CRS behavior. Then B3 and eligible
preflight; no database modification, RC build or external message in this batch.

Future Bitdefender rule retained: temporary Administrator PowerShell solely for
supported exclusion management of the exact actual PyInstaller/Inno build/work/
output directory; never create/rename PROSORINA, exclude repository/profile/drive,
disable protection globally or use undocumented registry hacks. Record the path,
remove exclusion after build and validation and verify removal. If manual action
is necessary, STOP before build, present the exact path and wait indefinitely for
explicit owner OK/Done/Continue; no countdown, timeout or automatic continuation.

All inherited dirty work is preserved; no commit/push/tag/publication/upload/RC.

---

# Final B3 legal closure and RC gate reclassification — 2026-10-08

**BLOCKED BEFORE RC BUILD.** RELEASE-INFRA / DESKTOP. This is the current
decision; contrary B1/B4/CI/LT gate wording below is historical and superseded.

| Gate | Legal status | Audit/Repro status | RC blocking? | Remaining action |
| --- | --- | --- | --- | --- |
| B1 | PASS | INCOMPLETE | no | Optional exact QtPdf producer/config/private CI/output correspondence |
| B2 | PASS RETAINED | COMPLETE | no | none |
| B3 | BLOCKED | INCOMPLETE | yes | IGNF3.1.0 collection rights; IAU2015 collection reuse; EPSG attributed metadata adaptations |
| B4 | PASS | INCOMPLETE | no | Optional full/bit-identical producer reproduction; mandatory final artifact/source access binding at later distribution |
| B5 | PASS RETAINED | COMPLETE | no | none |

B1-LEGAL and B4-LEGAL PASS are prebuild material/replacement decisions from
retained evidence. Required source/scripts, notices and replacement rights are
not waived. B1-AUDIT/B4-REPRO incompleteness cannot alone block RC. B3 still can.
Final pre-RC preflight **NOT RUN** because B3-LEGAL is BLOCKED. RC may be built:
**NO**. No RC, installer, commit, push, tag, publication or external upload.

LT2008:0.11549 ->0.115495, delta5 micrometres, upstream-only. PR2494 and public
review/history supply no causal explanation. No rounding/correction assertion.
CC-BY change indication/credit retained; exact causal history is audit-only.
IGNF ontology3.1/2019-02-13 Licence Ouverte is a distinct object from the shipped
IGNF registry3.1.0/2019-05-24, not a license substitution. ITRF2000/2008/2014
computed coefficients have a scoped factual-use/PROJ definition-file basis.
NKG inherited IERS/EUREF steps use EPSG7941/8366, not independently shipped
IERS/EPN datasets. IAU constants are facts, but the actual collection's reuse
basis remains unresolved. EPSG recipient terms/ownership/no-warranty are included;
permitted attributed upstream accuracy/interpolation metadata remains unresolved.

Details, evidence, limitations and issue classifications: WINDOWS_B3_LEGAL_CLOSURE.md
and windows-b3-legal-closure.json. Gate policy: WINDOWS_RELEASE_GATE_POLICY.md.
Only required legal/security gates drive packaging/windows-rc.json; audit scores
are informational. The guard fails closed on missing/non-PASS legal gates.
Retained B2/B5/runtime qualification and full functional audit are not rerun.

Next step: resolve only the three named B3 legal issues with applicable grants
or supported lawful-use/terms analysis; then eligible final preflight. Reusing
retained data/source evidence is required. No private CI hunting or full audit.
Future source/material delivery must bind to the actual authorized artifact and
provide equivalent freely accessible matching source alongside its distribution.

Future build Bitdefender rule: owner-authorized temporary Administrator PowerShell
access solely for documented exclusion management of the exact actual
PyInstaller/Inno build/work/output folder; never create/rename PROSORINA, exclude
repository/profile/drive, disable protection globally or use undocumented registry
hacks. Remove exclusion after artifact validation and verify removal. If manual,
STOP before build, show exact path and wait indefinitely for explicit owner
OK/Done/Continue; no countdown, timeout or automatic continuation.

---

> Current2026-10-08 upstream receipt review: B1/B4 BLOCKED for requested exact
> correspondence; unavailable CI logs are not an independent legal requirement.
> B3 rights/terms basis remains unresolved; B2/B5 PASS RETAINED.
> See WINDOWS_UPSTREAM_RECEIPT_CLOSURE.md, windows-upstream-receipt-closure.json,
> WINDOWS_DEPENDENCY_REBUILD.md and windows-release-retention-manifest.json.
> Older producer-log/full-rebuild blocker wording below is superseded.

# Final supplier/provider and rebuild evidence — 2026-10-08

**BLOCKED BEFORE RC BUILD.** RELEASE-INFRA / DESKTOP. This is the current
checkpoint; preceding narrow receipts and older sections below are retained
history. B2/B5 stay PASS RETAINED with unchanged inputs and no reruns.

| Gate | Status | Evidence | Remaining action |
| --- | --- | --- | --- |
| B1 | BLOCKED | PDFium baseline/final source delta;18 deterministic binding outputs; pinned Rtools GCC/gfortran10.3.0-9804 | Exact QtPdf executed GN/features/toolchain/job hash chain; binding producer outputs/options; OpenBLAS executed static-object/job mapping and9804 source patches |
| B2 | PASS RETAINED | Existing canonical CRT/import/prerequisite receipts unchanged | none |
| B3 | BLOCKED | Original four Esri lookup branches explained; six NKG2020 national parameter matches; ten init files individually identified | LT2008 reason; IGNF3.1.0/IGN-IERS/IAU independent grants; inherited NKG inputs; EPSG modified-attribution resolution |
| B4 | BLOCKED | Usable conditional functional QtPdf recipe; actual deterministic QPdfDocument MOC stage; practical replacement PASS retained | Missing exact producer/generator/GEOS materials; full functional DLL build/load not demonstrated; complete source retention remains open |
| B5 | PASS RETAINED | Existing TLS/Mesa/native qualification and policies unchanged | none |

New receipts: windows-producer-rebuild-receipts.json and sibling
WindowsProducerRebuildEvidence. Recipient commands and explicit prerequisites:
WINDOWS_QTPDF_REBUILD.md. PDFium upstream revision1afaa1a380fcd06cec420f3e5b6ec1d2ccb920dc
to final Qt treea73e60360d4a1b21df9b41b59d46db1ab489d42a has2880 identical,
54 changed and1620 omitted members. Final release sources already contain changes;
no extra patch application or producer execution is inferred from the delta.

Official Shiboken6.11.2 runs produced18 byte-identical C++/header outputs twice
(one timing log differs). Producer-generated C++ does not exist in the retained
source archive. Exact producer headers/options/output/binary receipt is still
missing. QPdfDocument MOC ran twice successfully with identical output SHA
deede3ee28fb8d3ea42feea2e1df06bd838d7f02ada47497a7de59d19b2f857d.
No Qt6Pdf DLL rebuild/load was performed. Full SDK import environment/VS2022
and exact producer config are not present as a qualified complete rebuild setup;
the batch stops at the meaningful generator stage instead of a blind large build.

Rtools2022-02-06 archive and executable/package receipts establish UCRT GCC and
gfortran10.3.0-9804. The earlier generic GCC8.3 assumption would be wrong for this
UCRT recipe. GNU10.3 source/runtime exception retained. No standalone GCC/runtime
DLL or proved libstdc++ node is introduced. Eligible static-runtime combination
does not itself impose a separate runtime-source delivery blocker. Missing exact
executed OpenBLAS/static-object and patched9804 toolchain correspondence remains
a provenance/build-material issue, not an invented standalone-runtime obligation.

Esri import parent2b73f93d6ea4a1a41773cface1c1ac9c8f13679e has EPSG9408/9409
target11134; current lookup has4258. Exact SELECT branches for108066/108067/108118/
108126 yield no original match, with positive target11134 controls. This closes
the four-record original lookup explanation without whole database regeneration.
Six NKG2020 national Helmert sets match Häkli2023 Table3 after ppb/mas conversion;
the primary paper grants CC-BY4.0 to the transformation and associated data.
LT2008: earliest NKG resource already0.11549 and first PROJ SQL already0.115495;
no authoritative reason proves rounding/correction/transcription. Do not edit data.

Named init resources CH/GL27/nad27/nad83/world/other.extra have explicit PROJ
source/data MIT definition-file coverage and original references; referenced grid
payloads do not ship. ITRF2000/2008/2014 name exact IGN/IERS parameter sources and
unit/sign changes; independent input grants remain unproved. ITRF2020 is generated
from EPSG. IGNF3.1.0 and IAU2015 constants likewise still lack exact input grants.
There is no generic unnamed init blocker. Additional inherited IERS/EUREF input
rights and EPSG-specific modification conditions remain separately named.

Mastixa ships the upstream wheel proj.db byte-for-byte, does not patch it at build
or runtime, and adds no EPSG rows. All observed data edits are upstream PROJ-only.
The upstream representation is modified, including alias900913 and accuracy1312/
1462 edits. Full EPSG terms, IOGP ownership and no-warranty notice remain required.
The terms contain no prescribed generic 'modified by' sentence; a truthful PROJ
modification disclosure is added. Such disclosure does not authorize impermissible
EPSG attribution. The two accuracy edits/alias need authoritative permitted-use
resolution; numerical source correspondence is not that legal permission.

Current active source candidate refresh includes the newly missing rebuild and
receipt documents. The original755 candidate and older745/741 captures remain
immutable. Deterministic hashes/file list are outside the checkout in the new
receipt, avoiding self-reference. Required producer inputs remain explicit BLOCKED
in the retention manifest. SBOM138 components/101 native/1216 pure/456 data and
189 dependency required legal entries +root LICENSE remain unchanged; no inventory
or qualification gate was rerun.

Final pre-RC preflight: **NOT RUN**, since B1/B3/B4 are BLOCKED. RC build allowed:
**NO**. Focused generation, source delta, four lookup controls, six national
parameters, attribution/retention consistency and preservation checks are recorded
in WindowsProducerRebuildEvidence/final-report.json. No app/UI/Android/native input,
installer/updater/guard, B2/B5 policy, staged entry, commit/push/tag/publication,
upload, final RC or antivirus setting was changed. The detailed future Bitdefender
rule below remains mandatory, including indefinite explicit owner confirmation
for manual exclusion management and removal verification.

Next owner action: obtain QtPdf/PySide/shiboken/OpenBLAS/Rtools9804/GEOS matching
executed build/config/generator/patch/output receipts and the named IGN/IERS/IAU/
LT2008/EPSG input explanations or grants. Nothing was sent to those providers.
Only after B1/B3/B4 PASS with B2/B5 retained PASS may final preflight run.

---

# Recipient library replacement — narrow evidence 2026-10-08

The owner-authorized benign identifiable QtPdf variant test PASSED. The isolated
recipient copy of the retained current-policy onedir package loaded modified
`_internal/PySide6/Qt6Pdf.dll` with a new RT_RCDATA resource62123. Original SHA256
`6fc87c84a723b05a0a3d7dce87083d25d23b1558e8806ff1cc7952bb9c5c9779`;
modified SHA256 `54a204d34beea013a62bed004cfe71f535eb671c774fbbdf4a1402f6270ebabf`.
The non-resource PE sections and export names were identical. This is a controlled
recipient modification, not a rebuilt library or producer/source correspondence
claim. Original wheel/supplier and retained diagnostic bytes remain unchanged.

The B4-only diagnostic executable reused the retained PYZ/bootstrap and current
main.py. No Analysis, full audit, B2/B5 test suite or final RC build was run.
Actual visible startup, report PDF export and invoice QPixmap/qpdf preview PASS.
GetModuleHandle/GetModuleFileName confirmed the exact changed QtPdf path/hash and
the bundle-local qpdf plugin. One printer CreateDC warning was recorded; PDF output
and preview still passed. Two initial harness API mistakes were corrected and
their failed evidence retained; no application change was necessary.

For an end user:

1. Close Mastixa. Copy the entire onedir application to a writable test directory;
   keep the original copy and your replacement libraries backed up. Use a new
   synthetic QA profile for checks, never your production database.
2. Replace compatible x64 Qt DLLs/plugins in `_internal/PySide6` (the PDF plugin is
   `plugins/imageformats/qpdf.dll`); PySide wrappers/runtime use this directory,
   Shiboken uses `_internal/shiboken6`. GEOS uses `_internal/Shapely.libs` with the
   exact wheel-mangled names and matching imports. Preserve Python limited-API,
   Qt6.11 ABI, all required exports and the coherent dependent set.
3. For the demonstrated variant, use the exact retained `prepare_replacement.py`
   recipe to add a harmless RT_RCDATA marker to a COPY of Qt6Pdf.dll with Win32
   BeginUpdateResource/UpdateResource/EndUpdateResource. This changes its bytes
   without changing compiled code/import/export sections. Rebuild from the exact
   upstream source/patch/config/toolchain set for substantive library changes;
   those full producer materials are still incomplete, so B4 remains BLOCKED.
4. Launch from the writable copy. Verify actual loaded DLL paths/hashes, visible
   startup, text input and the functions using the changed libraries: PDF export
   and invoice preview for QtPdf; GIS geometry/transforms for GEOS/PROJ. The
   retained narrow probe validates QtPdf only; it does not claim rebuilt binding
   or GEOS qualification. Remove the test copy or return to the original to undo.
5. Explicit repair/update installs overwrite matching program files: current Inno
   `[Files]` recursively copies with `ignoreversion`; the updater verifies the
   downloaded INSTALLER's SHA, not installed LGPL DLLs. Back up replacements,
   install an update explicitly, then reapply an ABI-compatible set for that new
   release, or keep a separate versioned writable copy. Do not apply stale DLLs
   blindly to a changed Qt/Python ABI. No automatic installed-library self-healing
   or runtime DLL hash/signature guard was found in the reviewed startup/updater.

Build-time trusted-supplier/TLS/CRT/Mesa/legal checks remain intact. They qualify
the publisher's inputs/output and are not normal recipient startup guards. No
production guard, installer, updater or native packaging path was changed here.
Recipient debugging/reverse engineering of covered-library modifications remains
permitted by the applicable LGPL route. Suitable dynamic linking avoids an
automatic blanket application-object-file obligation; complete corresponding
library source and necessary build/installation information remain required.

Raw experiment: `../WindowsNarrowClosureEvidence/variant.json`,
`replacement-result.json`, `replacement-launch.json`, `prepare_replacement.py`,
`replacement_driver.py`, `ReplacementProbe.spec`. These are internal evidence,
not public download links. The eventual source delivery must include the curated
recipe/probe and matching rebuild materials; do not ship private profile/log data.

Per-release required materials: windows-corresponding-source-package.json. B4 remains BLOCKED for matching producer/build/generator materials; benign replacement PASS does not change readiness flags.

---

# B2 transformation materials — 2026-10-08

B2 PASS applies only to canonical CRT deployment. The five modified third-party
PE import strings/checksums can be reproduced from the original hashed-wheel
inputs with packaging/crt_policy.py and windows-crt-policy.json; full upstream
and derived SHA256 mapping is in windows-crt-normalization.json. Preserve those
recipes alongside the retained original NumPy/GEOS/PROJ source/license materials
in the eventual source delivery. Microsoft code is neither modified nor shipped;
the official runtime is installed independently by recipients. No new dependency
version or broader source/replacement qualification is asserted. Existing B4
executed-build/replacement/artifact-binding gaps remain BLOCKED and unchanged.
Old source candidates retain their original identities; refresh/bind a source
candidate only in the later source/artifact batch.

---

# External rights / supplier evidence checkpoint — 2026-10-07

**BLOCKED BEFORE RC BUILD.** Authoritative current supplement, RELEASE-INFRA / DESKTOP. B5 PASS retained without changes or reruns. Full decisions/evidence: `WINDOWS_EXTERNAL_RIGHTS_CLOSURE.md`, `windows-external-rights-closure.json`, sibling `WindowsExternalRightsEvidence`. Previous sections below retain their historical checkpoints.

| Gate | Status | Evidence | Remaining action |
| --- | --- | --- | --- |
| B1 | BLOCKED | QtImageformats552 source hashes; exact OpenBLAS producer/source/recipe; binding identity | QtPdf GN/compiled graph; executed binding and GCC/toolchain producer receipts |
| B2 | BLOCKED | Microsoft primary license/docs, PSF Windows binary conditions, host probes |13-file applicable grants/downstream terms or qualified no-CRT/user-installed prerequisite route |
| B3 | BLOCKED | Unchanged proj.db and retained correspondence; targeted EPSG customization/input review | Esri/NKG exact derivation; IGNF/ITRF/IAU/init rights; EPSG modification compliance |
| B4 | BLOCKED | Added matching sources/build scripts/patch; no post-install DLL hash guard; SDK26 smoke retained | Full executed build/generator materials and usable recipient-built modified-library replacement |
| B5 | PASS RETAINED | TLS3.5.9 and Mesa exclusion evidence reused unchanged | none |

Closed: QtImageformats exact source commit/archive and552 supplier hash correspondence; actual8-file binding identity; OpenBLAS exact producer wheel/DLL, pinned source, patch/Windows recipe; static GCC presence; Microsoft own-license vs supplier-distributor distinction and original PSF Windows binary conditions; EPSG upstream modification classification; build-time vs installed-library guard review and explicit update/repair overwrite behavior.

Still blocked: exact QtPdf compiled GN/producer graph; executed binding/GCC toolchain and GEOS build/generator/replacement materials;13 CRT applicable grants/downstream terms or qualified no-CRT route; Esri/NKG exact derivation, IGNF/ITRF/IAU/init rights and complete EPSG modification compliance. Both readiness flags remain false. Final pre-RC preflight NOT RUN, because B1-B4 are not all PASS. RC may not be built.

Owner reports VS Code only; host probes discover no VS/Build Tools. Microsoft installer redistribution/chaining still needs rights; independent recipient download/install avoids Mastixa copying it, but3 hashed MSVCP imports prevent blind removal of13 app-local CRTs. No system installer executed or entitlement assumed.

New required legal/source records justify only a deterministic source-candidate refresh. Original741-file archive and all retained Qt26/database/TLS/Mesa/wheel/usage evidence remain unchanged. Focused validation and exact Git/preservation receipt are in `../WindowsExternalRightsEvidence/final-report.json` and `preservation-final.json`; no full audit or native qualification is repeated.

Exact next owner action: establish the chosen Microsoft distribution route and obtain the listed missing supplier/CRS/replacement receipts. Then close only those gaps; final preflight is permitted only after B1-B4 PASS. No commit/push/tag/publication/final RC build.

---

# Final Windows B1–B4 materials closure — 2026-10-07

**BLOCKED BEFORE RC BUILD.** Authoritative current section; older sections below
remain history. RELEASE-INFRA / DESKTOP, Windows x64,1.0.0-rc.1,rc,AGPL-3.0-only.
No final RC, installer, commit, push, tag, publication, upload or external message.

| Gate | Final status | Closed / exact remaining requirement |
| --- | --- | --- |
| B1 | BLOCKED | Qt Windows SDK SBOM/config/compiler receipts and matching PE sections for26 shipping files; exact Qtbase/SVG producer source retained. Missing complete QtPdf GN target attribution/build/patch graph, bindings receipt and OpenBLAS/GCC runtime closure; QtImageformats SDK source revision remains unpinned. |
| B2 | BLOCKED | Official signed x64 VC14.51.36247.0 installer and terms retained; root2 VCRUNTIME + pyproj MSVCP byte-identical to official container. All13 shipping CRTs still lack proven applicable redistribution grant/recipient eligibility; older8 PySide/shiboken + NumPy/Shapely provenance/repair rights still need supplier originals. |
| B3 | BLOCKED | PROJ9.8.1 SQL/database correspondence39 tables77707 rows PASS; pinned Esri3.6 Apache2 and NKG CC BY4 grants/legal texts retained. Exact Esri/NKG derivation statement, IGNF3.1.0/ITRF and IAU input rights, inherited init-data rights and full EPSG modification/numerical-equivalence conditions remain unresolved. |
| B4 | BLOCKED | Full official QtWebEngine6.11.2 nested source retained; local deterministic Windows application source candidate prepared.26-file SDK DLL substitution smoke PASS. Exact full QtPdf/bindings/GEOS/OpenBLAS build/patch/toolchain/source correspondence and complete usable modified-library replacement materials remain incomplete. |
| B5 | PASS (retained) | Qualified promoted TLS input and exact Mesa/LLVM exclusion reused byte-unchanged; no new qualification performed. |

`native_notices_complete=false`; `corresponding_source_ready=false`.
Final release preflight: **NOT RUN**, because B1–B4 are not all PASS. Focused
regression tests check expected fail-closed behavior; they are not a passed final
preflight. RC may not be built. B5/TLS/Mesa/wheel lock inputs remain unchanged.

Exact primary receipts: `docs/windows-qt-producer-receipts.json`,
`docs/windows-microsoft-runtime.json`, `docs/windows-crs-resources.json`,
`docs/windows-source-retention.json`, `docs/source-artifacts.json`,
`licenses/manifest.json`. Raw authoritative downloads/hash receipts, database
comparison, SDK comparison, build log/TOC, source snapshot and synthetic smoke
outputs are retained in sibling `WindowsFinalB1B4Evidence`.

Legal selection:172 full texts +38 attribution files,210 indexed paths including
root LICENSE.189 REQUIRED AND SHIPS,12 REQUIRED FOR SOURCE PACKAGE ONLY,
2 OPTIONAL/INFORMATIONAL,7 NOT APPLICABLE TO CURRENT SHIPPING SURFACE.
All current `licenses/` files are indexed and hash-checked; binary legal data
selects only REQUIRED AND SHIPS. Old Python/OpenSSL/Mesa/LLVM receipts remain
locally retained and do not re-enter the bundle. QtPdf candidate notices remain
conservatively delivered until compiled GN membership is proved; their inclusion
does not establish that the associated code ships. NotoSansCJK is source-only.

Validation:17 focused release/legal/source tests, isolated diagnostic main.py
startup/visible render/PDF export+invoice preview/PROJ+GEOS/legal selection, and
26-file official-SDK replacement smoke PASS;0 Qt messages. Native114 and pure1216
membership remain unchanged. Planned data455. Diagnostic executable/wrapper are
not release/SBOM members; this is a packaging smoke, not the retained99-scenario
usage audit, a release artifact qualification, or repeated B5 qualification.

Exact next owner action: obtain the original applicable Microsoft grant and
recipient entitlement for the13 CRTs, and supplier statements/materials for the
listed exact QtPdf/binding/GEOS/OpenBLAS build+patch+replacement and CRS/EPSG
derivation/rights gaps. Forbid enabling readiness flags based on URLs alone.
Then close only those material gaps against retained hashes; run final preflight
only after B1–B4 PASS. Build the final candidate only in a later authorized batch.

---

# Mesa/native B5 closure — 2026-10-07

**B5 PASS — FINAL B1–B4 CLOSURE REMAINS.** RELEASE-INFRA / DESKTOP.
Mesa11.2.2 and LLVM3.6.2 are now **EXCLUDE / SAFE TO EXCLUDE** for the current
raster Widgets application. Only `_internal/PySide6/opengl32sw.dll` is removed;
SHA25634b444c016289b560662ff896deceb7f4b2c0723aed3d319ae167c9186ce42b3.
No separate LLVM DLL ships. Exact wheel/RECORD/frozen hash match and Qt supplier
PE-section correspondence prove PySide6 Essentials6.11.2 / Qt llvmpipe origin.
This DLL was automatically collected by PyInstaller, not tooling/PATH leakage.

Normal main.py startup, report PDF export, invoice QPixmap preview, themes and
updater never load it. An added software OpenGL context does load it in the
baseline. Without it, required raster routes pass even with all OpenGL creation
deliberately unavailable. Exact-name binary/data exclusion, post-Analysis and
post-COLLECT/validator guards reject wheel/tool copies and known renamed bytes.
No current supported Mastixa feature needs this optional compatibility fallback.
Legacy supplier maintenance/static build/security remains unqualified; exclusion
removes its shipped code rather than claiming it is patched or vulnerability-free.
Retained Mesa/LLVM legal/source receipts remain historical/reference material.

Focused tests9/9 PASS (0 failures/errors/skips/Qt messages/ResourceWarnings),
isolated and production-policy frozen validation PASS, actual loaded-module
snapshots, raster/no-GL/theme/PDF/input/updater checks, 114 unchanged retained
native hashes, one-file/one-component metadata delta, CycloneDX1.6 schema,
independent deterministic metadata and git diff --check PASS. Expected OpenGL
warnings occur only after an explicit diagnostic context/failure injection.
Installed Bitdefender injection is recorded separately from bundle/system DLLs.
No GPU/VM fleet certification or public updater/installer E2E is claimed.

Current planned membership:114 native /1216 pure /465 data /17 package families /
7 Qt modules /21 plugins; SBOM150 components, embedded coverage still incomplete.
OpenSSL pins/lock/report/evidence and wheel lock are byte-unchanged and reused;
no TLS advisory review, supplier search, promotion or qualification repeated.
B1 producer Qt/PDFium/native notices/build receipts; B2 Microsoft rights and
release-status evidence; B3 remaining CRS/EPSG correspondence; B4 matching
nested source/build/replacement/application archive remain BLOCKED. Both
native_notices_complete and corresponding_source_ready remain false.

Approved worktree Mastixa-Icon-Diagnosis / icon-runtime-qa-final / unchanged
HEAD0a0031cf8ea20b2956944bf8468da9d647701237. Protected MastixaManager and all
unrelated dirty work preserved; no staged changes. Exact Git counts/content
preservation are in sibling WindowsMesaNativeEvidence/preservation-final.json.
Full qualification: docs/WINDOWS_MESA_NATIVE_QUALIFICATION.md. Raw evidence:
WindowsMesaNativeEvidence; prior checkpoint bytes remain below as history.

**Exact next step:** separately authorized final B1–B4 materials closure, reusing
qualified wheel/TLS/Mesa evidence unless inputs change. B5 is complete. Do not
build final RC yet. No final RC, installer, reset, clean, revert, discard,
commit, push, tag, publication or external upload occurred in this batch.

---

# Promoted TLS/runtime source delta — 2026-10-07

**BLOCKED BEFORE RC BUILD. B5 BLOCKED solely for the retained Mesa/native maintenance/security/build qualification gap. The OpenSSL supplier/promotion/frozen subgate is PASS.** B1-B4 statuses remain blocked; only the two CRT input records in B2 change; neither native notices nor corresponding-source readiness is true. RELEASE-INFRA / DESKTOP, Windows x64. No final RC, installer, commit, push, tag, upload or publication.

| Stack | Before -> promoted release input | Result |
| --- | --- | --- |
| Python | CPython 3.14.6 / OpenSSL 3.5.7 -> complete PSF CPython 3.14.8 / OpenSSL 3.5.9 | ACCEPTABLE FOR RC for OpenSSL; coherent runtime + unchanged 23-wheel lock qualified |
| Qt | Qt/PySide6 6.11.2 + accidental Poppler OpenSSL 3.6.4 -> same Qt/PySide + FireDaemon OpenSSL 3.5.9 LTS | ACCEPTABLE FOR RC for OpenSSL; 305 exported resolver symbols and frozen runtime qualified |

The supported patched3.5.9 LTS replacement fixes the reviewed3.6.4 issues; semantic minor numbering is not a Qt dependency. No Qt/PySide update, Qt rebuild or commercial Qt is required for this TLS change. Mesa remains a separate existing blocker; this batch does not transfer it to another gate or certify it.

Retain exact PSF3.14.8 full runtime and Python source; PSF openssl3.5.9 source-deps archive; FireDaemon original signed ZIP, upstream3.5.9 source/tag commit and pinned mkopenssl.zip recipe; PSF SPDX and Expat 2.8.5 source/COPYING. Hashes and actual binary linkage in windows-tls-promotion.json/source-artifacts.json/windows-source-retention.json. OpenSSL Apache2.0 and PSF/Expat permissive duties remain distinct from B4 copyleft delivery. Project retention: while binary available and at least five years after last distribution, indefinitely in archive. No source offer/publication. Retained old source receipts remain historical; do not select3.14.6/3.5.7/3.6.4 sources for the promoted files.

---

# Windows source delivery plan — 2026-10-07

## B4 closure continuation — authoritative

**B4 BLOCKED.** `windows-source-retention.json` now verifies the local hashes
of the retained source archive/tree receipts and maps relevant copyleft/MPL
components to exact shipping paths and binary hashes. It distinguishes the
AGPL application, Qt modules, bindings/shiboken, QtPdf nested sources, GEOS,
Certifi, conditional Qt PSL and NumPy/GCC exception. No generic latest-source
URL is substituted. Qt/GIS source candidates and the wheel members match their
named versions; binary-specific supplier configuration/patches remain missing.

The selected route remains equivalent source access alongside downloads and
mirrored exact copyleft sources. Links to versioned third-party sources are
useful receipts; this project does not treat link-only as complete release
delivery. Retain original source archives, patches or an evidenced unmodified
statement, dependency sources, build/spec/installer/loading scripts, compiler/
SDK configuration, wheel hashes, legal material and binary-to-source mapping.
For translations retain the editable .ts files. Certifi's immutable exact
covered-file source is identified and retained; public access must accompany
future binary distribution. Microsoft proprietary CRT has separate rights.

No GPL-only Qt module is present in the retained shipping set; VirtualKeyboard,
WebEngine/QML/Quick and QtPdfWidgets remain absent. GPL/AGPL terms still govern
the chosen application and the relevant alternative/source texts. Emitted
PyInstaller/runtime hooks use the documented bootloader exception; that does
not remove independent LGPL dependencies' duties. GCC runtime exception does
not impose blanket GPL application-source delivery; exact covered runtime
build/modification applicability remains unresolved.

Practical replacement: close the app; copy the onedir install to a writable
directory; rebuild ABI-compatible x64 Qt 6.11.2 modules/plugins, limited-API
PySide6/shiboken and GEOS 3.13.1 using the supplier recipe. Preserve dependent
DLL names/exports and wheel-mangled GEOS names (or reproduce the loading/rename
recipe from the exact Shapely source). Replace a coherent dependent set in
`_internal/PySide6`, `_internal/shiboken6`, `_internal/Shapely.libs`; run native
load, startup/input and PDF/GIS tests. Keep the editable packaging/loader code
available and permit reverse engineering for library-modification debugging.
The existing installer/update checksum does not hash-enforce installed libraries.
No compatible alternate build was supplied or tested here. Directory layout
and re-copying identical libraries are not replacement proof.

Object/application relinking files are not automatically required if LGPLv3
4(d)(1)/LGPLv2.1 6(b) suitable shared-library routes work. If they do not, retain
the appropriate Minimal Corresponding Source / Corresponding Application Code
or object/relinking material and any applicable Installation Information.
Do not claim an unconditional object-file exemption. Per-release retention is
while binaries remain available and at least five years after last distribution
as project policy; no written source offer is created by this manifest.

Exact missing B4 materials: full pinned QtPdf nested source including GN inputs,
supplier Qt/PySide/GEOS patch/configuration/compiler/build receipts, NumPy native
OpenBLAS/GCC mapping and exception evidence, alternate compatible replacement
validation, and reviewed dirty Mastixa preferred-source archive/build instructions.
The latter must include necessary untracked app files; HEAD alone is insufficient.
Binary/source final hash linkage and anonymous publication happen only in a later
authorized distribution action. Keep `corresponding_source_ready=false` now.

The following detailed original component plan remains applicable except for
wheel qualification and EPSG retrieval, which were advanced in this continuation.

---

Status: **BLOCKED BEFORE RC BUILD**. This is a delivery plan and verified local
source receipt index, not a written source offer or public-source availability
claim. No source, binary, feed or evidence was uploaded. Application decisions
remain AGPL-3.0-only, 1.0.0-rc.1, rc, UNSIGNED.

`source-artifacts.json` records exact URLs and archive SHA-256 values. PyPI
sdists were checked against PyPI's published hashes. Six CPython external source
archives were checked against the exact 3.14.6 `Misc/externals.spdx.json` hashes.
Qt, CPython, PROJ, GEOS and OpenSSL archives were downloaded from upstream
HTTPS origins and hashed locally; that does not prove a supplier's Windows
build flags or absence of patches. Do not substitute an archive for a different
version, or treat a generic latest-source URL as delivery.

## Component-specific routes

| Shipped work | Exact source identity | Required delivery / replacement / outstanding work |
| --- | --- | --- |
| Mastixa application and assets/locales | Current dirty 1.0.0-rc.1 sources, including all necessary untracked app modules; HEAD alone is insufficient | AGPLv3 section 6(d): exact preferred editable source, schema/migrations, resources, locked dependencies, build/spec/installer scripts and instructions, freely accessible alongside binary. Preserve license/notices/no-warranty. Section 13 applies if a modified version is made network-accessible; current app is local-only. Application source archive and binary-to-source hash mapping remain unassembled. |
| Qt Core/Gui/Widgets/Network/PrintSupport; base plugins | qtbase 6.11.2, locally retained archive hash in index | LGPLv3/GPLv3 texts, prominent Qt notice, complete matching library source including patches, configuration and scripts. Choose LGPLv3 section 4(d)(1) suitable shared-library mechanism. Need supplier feature/build receipt and source correspondence. |
| Qt SVG and SVG/icon plugins | qtsvg 6.11.2 archive | Same LGPL route. Preserve XSVG copyright/license. Match build flags and plugin/base Qt ABI. |
| Qt image-format plugins | qtimageformats 6.11.2 archive | Same LGPL route plus TIFF/WebP and relevant codec notices. Exact codec candidates in qt-third-party.json must be reconciled to wheel build, not blindly inferred from a documentation list. |
| Qt translations | qttranslations 6.11.2 archive; emitted .qm hashes in shipping manifest | Corresponding editable .ts source and relevant licenses; preserve module notices. No QML source tree ships in current preview. |
| PySide6 bindings and shiboken6 | official pyside-setup-everywhere-src-6.11.2.tar.xz | LGPLv3 route; include complete sources, patches/build scripts, Python limited-API/MSVC/x64 build requirements and module selection. Include bindings, not just Qt C++ source. Source downloaded, supplier matching build recipe still required. |
| QtPdf / PDFium / native stock fonts | qtwebengine a33fa2a897e5ee58e385b3f88dc247d99fca56db; nested qtwebengine-chromium 5170777d28bee1ce92cc693a0dbf2ad01492e5cf; PDFium source tree a73e60360d4a1b21df9b41b59d46db1ab489d42a | LGPLv3 for Qt wrapper; preserve separate PDFium/Chromium/codec/font permission and copyright notices. Full corresponding QtPdf source must include the pinned nested subtree and GN/toolchain/build/config/patches, not a Qt wrapper archive that omits its gitlink. Individual legal files and font payload correspondence collected; full nested source bundle and compiled feature receipt missing. PDFium permissive code alone does not impose a standalone copyleft source offer. |
| GEOS | 3.13.1 exact source archive, matched runtime version | LGPLv2.1 shared-library mechanism under section 6(b), plus source provision for redistributed library under section 4. Supply source and build instructions/patches, preserving licenses/copyrights. Shapely 2.1.2 source and delvewheel DLL-renaming/loading recipe needed for practical replacement. |
| Certifi CA bundle | certifi 2026.7.22 PyPI sdist, published SHA-256 verified | MPL2 section 3.2: inform recipients how to get exact covered-file source. Preserve MPL and covered notices. Index gives immutable version/hash access; retain a project mirror to keep access working. This is public CA data, not an owner signing secret. |
| Qt Public Suffix List if compiled in Network | qtbase pinned PSL source 2026-05-14 and libpsl revision in qt-third-party.json | MPL covered data: exact source and notice/access information if included. Feature/SBOM closure must confirm the compiled subset. No application-wide MPL relicensing. |
| NumPy/OpenBLAS/GCC runtimes | NumPy 2.5.3 sdist; scipy-openblas build identity 0.3.34.106.0; exact underlying OpenBLAS/GCC build receipt still missing | Preserve NumPy's full composite notices and GCC exception. Eligible compilation under GCC Runtime Library Exception normally permits independent application distribution; do not impose a blanket GPL application-source obligation. Confirm compiler/runtime modifications and exception applicability; modified covered runtime/source conditions remain separate. |
| Other permissive native/Python code | Pinned source URLs/hashes and per-file versions in manifests | Usually no source-distribution duty; preserve required copyright/permission/disclaimer and NOTICE. Apache NOTICE must be retained where upstream supplies one; a generic Apache LICENSE is insufficient by itself. CPython's historical chain and all compiled extension terms remain included. |
| Microsoft CRT | Exact filenames/PE versions/RECORD origin in shipping manifest | Proprietary redistributable terms, not AGPL source. Obtain eligible redist origin and applicable terms/entitlement for each runtime variant. UCRT/API sets are OS-provided on supported Windows and excluded. No Microsoft source/object-file offer is promised. |

## Practical DLL / binding replacement

Close Mastixa, copy the onedir installation to a user-writable test directory,
and replace compatible x64 libraries while keeping expected filenames/import
dependencies. Qt lives in `_internal/PySide6`, bindings in that directory and
`_internal/shiboken6`; GEOS lives in `_internal/Shapely.libs` with wheel-mangled
names. Rebuild/rename the complete dependent set as required, using the pinned
source, Python ABI and compiler recipe. The qpdf image plugin and Qt6Pdf must
remain compatible with QtCore/Gui. Supply editable packaging/loading scripts.
Do not add runtime DLL hash enforcement or terms preventing library modification
or reverse engineering for debugging. Updater installer-SHA verification does
not prevent modifying installed libraries.

The diagnostic bundle passed startup, text input, report export and invoice PDF
preview with excluded modules absent. It demonstrates the dynamic layout; it
does **not** prove successful replacement with a differently built compatible
Qt/GEOS library. An ABI-compatible alternate build and practical replacement
test remain required by the project's release gate. Object files are not
automatically required when the suitable shared-library route works. If that
route fails, use the relevant LGPL application-code/relinking route and provide
all necessary object/application code and Installation Information, rather than
claiming onedir alone satisfies the license.

## Per-release source package and retention

For the chosen download route, put a reviewed `MastixaManager-1.0.0-rc.1-Source`
archive and matching copyleft dependency source/materials beside the installer
on GitHub Releases. Include a machine-readable release manifest with final
binary/source hashes, exact wheel URLs/hashes, native/subcomponent identities,
compiler/OS/build configurations, modifications, full legal files and replacement
instructions. Offer free anonymous equivalent access and clear links from
notices/release notes. If using another source server, project responsibility
for continuing source access remains; hosting every permissive source is not a
blanket legal requirement. This project chooses mirrored copyleft materials to
avoid reliance on mutable or disappearing external pages.

Retain exact source/build/legal materials while binaries remain available and
indefinitely in the release archive as project policy (at least five years after
last distribution). This policy is distinct from a written-offer route's legal
minimum periods; no section 6(b) written offer is made here. Keep internal RC
inputs locally; public source access becomes mandatory when binary distribution
under the chosen route begins, not merely because this internal audit exists.

Review the dirty application source scope for private data, credentials, owner
profiles, QA copies, logs, backups and sensitive historical evidence before
archiving or publication. Never include the external audit evidence wholesale.
No network publication is authorized by this plan.

## Closure checklist

1. Obtain exact Windows wheel/build SBOM/configuration/patch receipts for Qt,
   QtPdf and native software OpenGL; reconcile conditional components and NOTICE.
2. Complete EPSG/other CRS data terms and MSVC redistributable origin/terms.
3. Assemble the pinned QtPdf nested source/toolchain and build/replacement
   materials, finish NumPy native build mapping, and test compatible replacement.
4. Qualify exact interpreter/wheel/ambient OpenSSL inputs and known security
   updates; preserve metadata unless a verified blocker requires revision.
5. Run readiness preflight. Keep `native_notices_complete=false` and
   `corresponding_source_ready=false` until the receipts/materials are verified.
   Stop before RC build in this audit. Public-source delivery and actual
   installer/updater acceptance are subsequent authorized release actions.

References: [LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html),
[LGPLv2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html),
[AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html),
[Qt obligations](https://www.qt.io/development/open-source-lgpl-obligations).
