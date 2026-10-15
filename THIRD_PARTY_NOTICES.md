# Fieltra — Farm Management: third-party notices

Fieltra v1.0.0 Stable continues the Mastixa Manager application under
**AGPL-3.0-only**, with the full license in `LICENSE`. Historical Mastixa Manager
copyright and contributor notices remain in force. Third-party copyrights,
licenses, required attributions and component terms below remain unchanged.
The Fieltra installer uses an independent external VC++ prerequisite; it conveys
neither VC Redist nor loose Microsoft CRT DLLs. See `docs/FIELTRA_V1_RELEASE.md`
for the matching source companion and actual publication status.

Historical first-party copyright attribution, preserved verbatim:

> Copyright: Mastixa Manager contributors.

---

Historical records and retained technical instructions follow. Earlier status statements
do not override the Fieltra v1.0.0 preparation status above.

> Next candidate — owner decision 2026-10-12: external runtime detection at launch.
> Microsoft Visual C++ Redistributable x64 >=14.51.36247.0 is required, but is not
> included in the revised installer. Obtain it separately from
> [Microsoft](https://aka.ms/vc14/vc_redist.x64.exe) under Microsoft's own terms.
> Mastixa's AGPL and all supplier license/source/replacement obligations persist.
> Completed package inspection and native qualification are pending; NO-GO.
> See [external prerequisite report](docs/WINDOWS_EXTERNAL_VC_PREREQUISITE.md).
> Retained frozen notices are unchanged; new source/artifact binding is still required.

> Historical bundled installer surface — 2026-10-12: accepted RC2 candidates embed the
> unchanged Microsoft Visual C++ v14 Redistributable x64 14.51.36247.0, separate
> from the frozen application's zero app-local Microsoft CRT policy. Microsoft
> retains its component rights and notices; it is not licensed under Mastixa AGPL.
> [Runtime terms](https://visualstudio.microsoft.com/license-terms/vs2026-ga-visualcpp-v14-redist-runtime/) and [conditional Community redistribution grant](https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/)
> apply to Microsoft code. Preserve AGPL and covered-library replacement rights.
> Distribution remains BLOCKED pending protective recipient/distributor agreement;
> see [current compliance report](docs/WINDOWS_RC2_MICROSOFT_COMPLIANCE.md).
> This source notice does not change or retroactively qualify retained binaries.

# Current Windows EPSG data provenance — 2026-10-08

The EPSG Dataset is owned by IOGP. Its complete Terms of Use and AS-IS/liability
disclaimers are supplied in licenses/EPSG/TERMS-OF-USE-2016.html. Mastixa includes
PROJ9.8.1-derived CRS data, not the official EPSG Dataset. Consult
[epsg.org](https://epsg.org/) for official current definitions and values.

PROJ supplies the2.0m operation-ranking accuracy for original operations1312 and
1462; the imported EPSG v12.029 values were1.0m. Those modified fields are PROJ
metadata and are not attributed to the EPSG Dataset. Their WKT/PROJJSON remarks
carry this field-specific distinction; genuine EPSG operation references remain.
PROJ added the interpolation-CRS association for operation7001; the genuine
Amersfoort EPSG4289 CRS identifier does not attribute that addition to EPSG.
900913 is an unofficial PROJ/Google legacy alias of official EPSG3857, with a
PROJ deprecation flag. The supplied alias is identified as PROJ900913, and Mastixa
canonicalizes historical EPSG900913 inputs to official EPSG3857.

Mastixa adds only provenance descriptions for the three named operations and
independent PROJ identification/name/usage for the alias in a derived build copy.
It does not change operation accuracy, parameters, grids or interpolation context.
Original supplier packages remain unchanged. Complete upstream notices, terms and
source/replacement rights remain applicable. Source includes the exact overlay
recipe/lock and compatibility handling.

EPSG/B3 prebuild attribution PASS follows the documented scoped terms assessment;
it is not provider approval or acceptance of an unbuilt artifact. The dated
checkpoints below describe earlier inputs/assessments; their unchanged-database
and BLOCKED statements are superseded by this current distribution representation.

---

> Final narrow B3 decision2026-10-08: IGNF and IAU scoped legal PASS; EPSG
> adaptation-attribution remains BLOCKED. Historical three-topic blocker wording
> below is superseded. IGN France IGNF3.1.0, source update2019-05-24: statutory
> public-information reuse under French CRPA L321-1/L321-3/L322-1, with source/date
> and meaning preservation; PROJ XML-to-SQL translation. No ontology-license or
> current-version/retroactive Etalab substitution is made.
> IAU collection: detailed credits/terms in licenses/CRS/IAU-collection/NOTICE.txt;
> exact PlanetMap csvForWKT input/contributor license/source preserved. Full LGPLv3
> and incorporated GPLv3 apply to covered collection contributions; independently
> authored PROJ code retains MIT. Mixed authorship is credited, not public domain.
> EPSG Dataset owned by IOGP: full terms/no-warranty remain in licenses/EPSG.
> Upstream accuracy1312/1462=2.0 and interpolation7001/alias900913 are PROJ changes;
> Mastixa adds no edits. Generic disclosure alone does not clear clause6(vii).

---

> Current legal review2026-10-08: B1-LEGAL/B4-LEGAL PASS for prebuild materials;
> B3-LEGAL BLOCKED, so distribution is not cleared. Older CI/LT blocker wording
> below is superseded. EPSG Dataset owned by IOGP; full terms/no-warranty supplied
> in licenses/EPSG/TERMS-OF-USE-2016.html. Upstream PROJ adapts EPSG aliases,
> interpolation metadata and accuracy; Mastixa ships proj.db byte-for-byte.
> NKG: Nordic Geodetic Commission, NordicTransformations, CC-BY4.0; Häkli et al.
> 2023 DOI10.1515/jogs-2022-0155; upstream PROJ unit/SQL adaptations include
> LT2008 ty0.11549 to0.115495 (cause unproved). IGN Product Centre: published
> ITRF.TP/ITRF2005, Transfo-ITRF2008_ITRFs.txt and Transfo-ITRF2014_ITRFs.txt;
> PROJ converts units/signs into init definitions. IERS and EUREF frame references
> remain separately credited via NKG/EPSG; EPN data is not included. IAU:
> Archinal et al., WGCCRE2015 report, Celestial Mechanics130:22(2018),
> DOI10.1007/s10569-017-9805-5; PROJ constructs planetary CRS/projections from
> radii/axes/conventions. IGN registry3.1.0 dated2019-05-24 is imported by PROJ.
> These factual credits do not grant unresolved IGNF/IAU collection permissions
> or close EPSG permitted-attribution compliance. See docs/WINDOWS_B3_LEGAL_CLOSURE.md.

> Upstream receipt review2026-10-08: underlying CRS rights/terms basis remains
> unresolved (B3); exact internal producer logs are audit evidence, not a license
> requirement. Existing complete license texts/credits remain unchanged.
> Source/rebuild supplement: docs/WINDOWS_DEPENDENCY_REBUILD.md.
> Current decision: docs/WINDOWS_UPSTREAM_RECEIPT_CLOSURE.md.

> Final2026-10-08 supplier/rebuild checkpoint: B1/B3/B4 BLOCKED; B2/B5 PASS RETAINED.
> EPSG Dataset ownership: IOGP. The shipped PROJ representation includes upstream
> PROJ adaptations (alias900913, unit/interpolation metadata and accuracy1312/1462);
> Mastixa makes no further database edits. Full EPSG terms/no-warranty are included.
> This disclosure does not close unresolved permitted-attribution compliance.
> NKG2020 national parameters: Häkli et al2023, DOI10.1515/jogs-2022-0155,
> CC-BY4.0; PROJ converts ppb/mas to ppm/arcseconds. Full existing CC license retained.
> Exact recipient rebuild instructions: docs/WINDOWS_QTPDF_REBUILD.md.

---

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


The EPSG Dataset is owned by IOGP; its complete terms/no-warranty/disclaimer remain
in licenses/EPSG. Esri retains Apache2 copyright/license and PROJ transformation
notice; NKG retains CC BY4 attribution and modification notice. No Mastixa data
edits were made. Exact unresolved input rights/EPSG compliance still block B3.
The supplied SOURCE_DELIVERY_PLAN.md now documents proven benign QtPdf recipient
replacement and explicit-update overwrite/backup/reapply behavior. Required
189 dependency legal-material classifications plus root LICENSE (190 required
ledger entries) are unchanged; native notice completeness and
corresponding-source readiness remain false. Older contrary gate/CRT/source-pin
statements below are historical.

---

> Current B2 disposition — 2026-10-08: **B2 PASS; BLOCKED BEFORE RC BUILD**.
> B1/B3/B4 BLOCKED and B5 PASS are retained. Microsoft CRT DLLs/installer are
> not included; recipients independently install official x64 VC Redist
> >=14.51.36247.0 under Microsoft terms. Five third-party NumPy/GEOS/PROJ
> import strings/checksums are normalized reproducibly; their original licenses
> and source/replacement duties remain. Older blanket B2/13-file statements
> below are historical for the retired shipping surface.

---

> External rights continuation2026-10-07: B1-B4 BLOCKED; B5 PASS retained.
> QtImageformats exact producer source47b6139d pinned by552 supplier source hashes.
> OpenBLAS/GCC actually ships inside the exact NumPy DLL; producer source/Windows
> recipe retained, executed GCC/static-runtime receipt remains incomplete.
> Official PSF Windows binary Microsoft conditions are included in
> licenses/CPython-3.14.8-WINDOWS-BINARY-LICENSE.txt; they remain independent
> of AGPL/PSF software licensing and do not supply a blanket13-file grant.
> Source/replacement and CRS/EPSG gaps remain; see supplied SOURCE_DELIVERY_PLAN.md.

> Current Windows legal disposition — 2026-10-07: **BLOCKED BEFORE RC BUILD**.
> B5 retained PASS; B1–B4 BLOCKED. Binary notices are selected explicitly by
> licenses/manifest.json; historical/source-only texts remain in source retention.
>26 matching Qt SDK PE-section receipts and producer SBOM/configs establish
> partial native notice membership. Complete QtPdf target/build closure remains
> incomplete; conservative candidate notices do not imply compiled inclusion.
> The EPSG Dataset is owned by IOGP. Its full terms apply independently of PROJ
> software MIT. Esri data: copyright Esri, Apache2 at pinned3.6.0 input; transformed
> by PROJ. NKG definitions: Nordic Geodetic Commission (NKG), NordicTransformations,
> CC BY4.0; PROJ hand-written SQL transformation; pinned attribution/full license
> in licenses/CRS. No Mastixa edits to proj.db. Remaining exact derivation and
> IGNF/ITRF/IAU/EPSG input rights remain unresolved; no blanket MIT conclusion.
> LGPL3 suitable dynamic DLL route is intended; source/build and usable compatible
> modified-library replacement materials remain incomplete. See SOURCE_DELIVERY_PLAN.md.

> Current B1β€“B5 continuation β€” 2026-10-07: **BLOCKED BEFORE RC BUILD**.
> All retained shipping wheels are independently archive-qualified; original
> Exact compiled native/build/source closure remains
> blocked. EPSG's full official terms are now in
> `licenses/EPSG/TERMS-OF-USE-2016.html`. The EPSG Dataset is owned by IOGP;
> redistribution and modifications remain subject to those terms, separately
> from PROJ's software license. See `docs/WINDOWS_CRS_ATTRIBUTION.md` for the
> other actually shipped registry resources and unresolved rights.
> Mesa 11.2.2/LLVM 3.6.2 code is excluded after raster/no-OpenGL qualification.
> Its retained versioned legal texts are historical/reference material only.
> The older preparation rows below are retained history, not current membership.

> Current Windows distribution audit β€” 2026-10-07: **BLOCKED BEFORE RC BUILD**.
> Exact planned membership and component obligations are in
> `docs/WINDOWS_DISTRIBUTION_COMPLIANCE_MATRIX.md` and
> `docs/windows-distribution-manifest.json`. The onedir bundle supplies
> `SOURCE_DELIVERY_PLAN.md` and `source-artifacts.json` alongside this index.
> Native notice/build/source/redist and CRS dataset closure remains incomplete;
> the original retained-snapshot rows below are extended by this authoritative
> audit, not evidence of public-distribution clearance.

## Audited native and source notice additions

This program uses Qt/PySide/shiboken shared libraries under the selected LGPLv3
route. Full GPLv3/LGPLv3 and relevant upstream copyright/permission texts are
provided in `licenses/`. Recipients may modify/replace the libraries and reverse
engineer for debugging such modifications; see the supplied source delivery plan
for exact sources and the still-unverified compatible replacement procedure.
No commercial Qt grant is asserted.

The observed Windows native Qt modules are Core, Gui, Widgets, Network,
PrintSupport, SVG and PDF. Qt Quick/QML/OpenGL module DLLs and VirtualKeyboard
are excluded; the optional Mesa/LLVM software OpenGL DLL is now also excluded.
QtGui and operating-system OpenGL remain available. QtPdf/qpdf is required by
invoice QPixmap preview, and includes PDFium. Exact pinned QtWebEngine/Chromium/
PDFium source identities and source/notice hashes are in source-artifacts.json
and licenses/manifest.json. Source attributions are preserved separately from
license texts; feature-dependent Nth-party applicability remains unresolved.

| Additional actual native/data identity | Included legal material / action |
| --- | --- |
| CPython 3.14.8 native extensions: bzip2 1.0.8, libffi 3.4.4, mpdecimal 4.0.0, XZ 5.2.5, zlib-ng 2.2.4, zstd 1.5.7, Expat 2.8.5 | Exact source-dependency legal texts in licenses/CPython-native; source hashes checked against CPython externals SBOM. SQLite 3.50.4 is public domain; _sqlite3 keeps CPython terms. |
| Qt 6.11.2 third-party code | Verbatim texts/copyrights and source attribution metadata under licenses/Qt-6.11.2, including relevant permissive/custom/Unicode/MPL materials. Not all source candidates are claimed compiled. Exact wheel build/SBOM/NOTICE receipt remains a blocker. |
| PDFium and Chromium plus Abseil/FreeType/ICU/JPEG/PNG/zlib/fast_float/OpenJPEG/Little CMS and conditional candidates | Exact pinned source license files under licenses/QtPdf-6.11.2; versions/conditional feature gap in compliance matrix. Preserve any additional upstream NOTICE and embedded copyrights after build closure. |
| Sixteen embedded PDFium/Foxit stock fonts | Full PDFium BSD-style LICENSE plus verbatim 2014 PDFium Authors / original 2014 Foxit Software copyright headers. Every generated font payload byte-matches Qt6Pdf.dll; names/hashes in embedded-font-provenance.json. |
| PROJ 9.8.1 / GEOS 3.13.1 | Exact upstream COPYING retained in version-named directories; source archive receipts in supplied source index. GEOS LGPL library source/replacement duties remain; PROJ software license does not settle every CRS dataset term. |
| GIS native curl 8.19.0 / TIFF 4.7.1 / libjpeg-turbo 3.1.4.1 / XZ 5.8.3 / zlib 1.3.1 | Exact version legal material in licenses/GIS-native; GPL utility licenses in XZ source are not assigned to the shipped liblzma library. pyproj SQLite 3.53.0 is public domain. |
| Python and Qt OpenSSL 3.5.9 | Exact Apache-2.0 license supplied in licenses/openssl-3.5.9/LICENSE.txt; PSF and FireDaemon distinct builds/source/archive hashes pinned. TLS supplier/security/frozen qualification PASS. Older legal texts retained as history. |
| Emitted hooks-contrib pyproj runtime hook 2026.7 | Exact source license in licenses/pyinstaller-hooks-contrib-2026.7; whole developer hook package is not redistributed. |
| Excluded opengl32sw: Mesa 11.2.2 / LLVM 3.6.2 | Code does not ship. Retained upstream texts/source receipts are reference material; supplier/static closure is not claimed. See WINDOWS_MESA_NATIVE_QUALIFICATION.md. |
| MSVC runtime variants | Exact filenames/PE versions and wheel/interpreter origins in manifest; Microsoft permitted redist terms/entitlement receipts still missing. UCRT/API-set files are OS-provided and excluded for Windows 10+. |
| proj.db CRS data: EPSG v12.029 and other registries | Version/source metadata/hash mapped, but authoritative full data redistribution/attribution closure missing. No blanket MIT data-license claim. |

The NotoSansCJK test font is marked Shipped:no upstream and is not bundled;
its source-audit license is marked nonshipping and excluded by packaging.
No standalone Windows font files, basemap/offline tile packs, external OCR
program or updater helper is included. Required project artwork is covered by
the 41-file owner-attested asset ledger, separately from dependency fonts/code.

Collected texts/duplicate-byte context do not establish notice completeness.
Keep native/source readiness flags false until the component-specific blockers
close. The current SBOM is explicitly incomplete for unverified embedded native
subcomponents, even though its JSON validates against the CycloneDX 1.6 schema.

---

# Mastixa Manager β€” Windows third-party notices

Mastixa public application code: **AGPL-3.0-only**, full text in `LICENSE`.
Dependencies keep their own copyright and licenses. This application uses
**PySide6 / shiboken6 / Qt**, with LGPLv3 terms for the applicable libraries and
separate licenses for their bundled third-party code. Full GPLv3 and LGPLv3
texts are in `licenses/`. See `DISTRIBUTION_SOURCE.md` in the bundle (or
`docs/DISTRIBUTION_SOURCE.md` in source) for source/replacement delivery.

**Preparation status: incomplete; not cleared for RC packaging.** This index
covers components demonstrated in the retained Windows bundle/PYZ, not every
package installed in the development environment. Versions below are the
retained build snapshot; the exact future candidate must reconcile wheel
hashes, native versions, notices and source access before building. No old
artifact is claimed to be the `1.0.0-rc.1` candidate.

| Distributed component | Retained version | License / full text | Required attribution / source / outstanding action |
| --- | --- | --- | --- |
| PySide6 Essentials / shiboken6 | 6.11.2 | LGPL-3.0-only route; `licenses/LGPL-3.0-only.txt`, `GPL-3.0-only.txt` | Qt Company/upstream copyrights and exact source/replacement materials; full exact native and upstream copyright inventory pending. No commercial entitlement is claimed. |
| Qt Core, Gui, Widgets, Network, PrintSupport, OpenGL, SVG, QML/Quick and plugins | Qt 6.11.2 snapshot; verify native match | Per-module Qt terms and third-party sublicenses | Libraries/plugins shown by historical membership, including indirect modules. Match the exact module/source SBOM and preserve all embedded third-party notices. |
| QtPdf / PDFium and `qpdf` plugin | Exact PDFium revision pending | Qt terms plus PDFium/Chromium third-party terms | Shipping in old bundle even without direct import; full revision-specific third-party notice/source mapping missing. RELEASE BLOCKER. |
| Qt image-format/TLS/platform/input/style/generic plugins | Exact internal versions pending | Qt plus image codec/OpenSSL and other upstream terms as applicable | Retain exact plugin/native notices and copyrights. No blanket LGPL clearance. VirtualKeyboard DLL/plugin/QML resources are explicitly excluded. |
| CPython runtime / standard library | Promoted PSF3.14.8 full runtime, pinned supplier | PSF and historical license chain, `licenses/CPython-3.14.8-LICENSE.txt` | Preserve full license chain; disclose modifications if made. Match bundled OpenSSL, SQLite, libffi, Expat, zstd, bzip2, lzma and other embedded code to exact upstream terms. Native closure pending. |
| NumPy / emitted OpenBLAS and compiler runtime | 2.5.3 | BSD and bundled subcomponent terms, full `licenses/numpy/` tree | Preserve all supplied notices/exceptions, including applicable BLAS/compiler licenses. Match exact DLL runtime/source duties rather than assuming everything BSD. |
| pyproj / PROJ | 3.8.0; QA-only 3.7.2 does not define candidate | MIT-style texts, `licenses/pyproj/` | Preserve pyproj/PROJ copyrights. Resolve exact curl/TIFF/JPEG/zlib/lzma/SQLite/runtime and CRS/EPSG data notices for the emitted wheel. |
| Shapely / GEOS | 2.1.2; exact GEOS native version pending | BSD-3-Clause / LGPL-2.1, full `licenses/shapely/` | Preserve Windows notice and full GEOS terms; exact source and library replacement route required. |
| pyshp | 2.4.2 | MIT, `licenses/pyshp/` | Retain copyright/license/disclaimer. |
| ezdxf | 1.4.4 | MIT, `licenses/ezdxf/` | Retain copyright/license/disclaimer. |
| fontTools | 4.65.0 | MIT, `licenses/fonttools/` | Retain both upstream license files. This is a library, not a bundled font pack. |
| pyparsing | 3.3.3 | MIT, `licenses/pyparsing/` | Retain copyright/license/disclaimer. |
| defusedxml | 0.7.1 | PSF, `licenses/defusedxml/` | Preserve upstream license and authorship notices. |
| openpyxl | 3.1.5 | MIT, `licenses/openpyxl/LICENCE.rst` | Verbatim text extracted from exact PyPI sdist, verified against its published SHA-256. |
| et_xmlfile | 2.0.0 | MIT, `licenses/et_xmlfile/LICENCE.rst` | Verbatim text extracted from exact PyPI sdist, verified against its published SHA-256. |
| typing_extensions | 4.16.0 | PSF, `licenses/typing_extensions/` | Preserve the full upstream license chain. |
| Certifi CA data | 2026.7.22 | MPL-2.0, `licenses/certifi/` | Preserve license and provide exact covered-file source access. Public CA certificates are dependency data, not signing secrets. |
| PyInstaller emitted bootloader/runtime hooks/utilities | 6.22.3 | GPLv2 with bootloader exception / Apache-2.0, `licenses/PyInstaller-6.22.3-COPYING.txt` | Full upstream combined license text includes exception and Apache terms. Preserve actual emitted hook/utilities copyrights; do not attribute build-only altgraph/pefile/packages as shipped without membership. |
| Inno Setup installer/uninstaller runtime | Build config 6.7.3; verify actual compiler | Inno Setup license, `licenses/Inno-Setup-LICENSE.txt` | Upstream copyright/website notices must remain. Tool itself is not redistributed. License downloaded from official site; match compiler version before acceptance. |
| MSVC/UCRT/API-set runtime DLLs | Exact version/origin pending | Microsoft redistribution terms | Present in historical bundle, including wheel-vendored variants. Verify original permitted redistributable source and terms. RELEASE BLOCKER until native closure. |

`licenses/manifest.json` records full-text origin, component/version where known
and SHA-256. Installed wheel license files are copied without editing; commercial
Qt license-reference files are not presented as grants. GNU texts are upstream
Qt copies; the full unmodified FSF AGPL text comes from the SPDX license mirror.

No fonts, icon packs, GIS bulk tiles, third-party PDF templates or external OCR
executables are in the current Windows resource inputs. Project artwork is
covered separately by `docs/ASSET_PROVENANCE.md`. Tesseract is an optional external
installation, not shipped. When the user explicitly enables OpenStreetMap,
existing map-provider attribution applies to visible tiles; no tile pack is
included. Windows system fonts are not redistributed as font files.

Packaging includes `LICENSE`, this index, `licenses/`, source-delivery information
and offline staging feeds. Installer displays the application AGPL; Settings
provides legal/source links. The preflight and postbuild verifier block incomplete
source/legal closure and check byte-identical legal files. Actual artifact-level
inclusion, Qt replacement and exact native compliance remain unverified.
