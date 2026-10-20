# B02 review/hardening — final owner-review checkpoint, 2026-10-20

**Source review and bounded corrections saved. ALL TESTS / COMPILATION / LINT /
BUILDS / CI / GUI / GPS: NOT RUN. No production activation.**

Authority: owner's LARGE AUTONOMOUS SOURCE REVIEW, HARDENING & CI READINESS.
Branch `develop/v1.0.1`; HEAD
`ce76cc08c8ad8a2551b5f2ef2e32c91472ed89f1` unchanged; index/refs untouched.
This review edited20 pre-existing package files +four canonical docs and created
six files (30 total); accumulated isolated source now42 untracked files.
Both unrelated dirty master-source documents and all nine B02.1 files retain
entry SHA256s. Existing tracked app source/dependencies/workflows/manifest/
Gradle/signing/package/DB15/backup19/forms/map/GPS/release remain unchanged.

[Exact changed/new manifest, findings, test classification and future commands](CODEX_PROJECT_CONTEXT.md#b02-source-review-and-hardening--final-owner-checkpoint-2026-10-20).
Context/master ledgers remain ignored; do not force-add or publish private
master-source documents. Proposed future public whitelist has44 explicit paths.

Corrections: independent-commit permit bypass and missing-fence detection;
shared binary UTF8/raw-byte source/input fingerprints and four golden vectors;
full captured-input/count validation before overlay publication; stale-job
supersession/idempotent selection; stricter SQL/FKs/mappings; bounded ZIP/read/
union processing; Android API26-compatible URL encoding; WMS response/URL/XML/
coalescing checks; reviewed optional offline SHA256 and inherited feed license.

B02.1 SOURCE COMPLETE (unchanged isolated contracts). B02.2/B02.3/B02.4 PARTIAL.
B02.5 Windows/Android, WMS and generic INSPIRE/offline SOURCE COMPLETE means
unverified isolated source only. TEE provider BLOCKED: manual portal evidence
does not establish an authorized geometry API. No live provider probes.

Production gates remain: real legacy identities/payloads/jobs, every writer and
old-file restore protection, activation/recovery, verified Android regional PRJ/
format/heap use, cross-platform geometry, WMS HTTP/API28+ restriction, actual
Atom feed/terms, TEE service metadata, GUI/GPS, backup/ZIP compatibility.
No feature PASS or112-F-ID/26-gap reassignment. Native owner acceptance pending.

Next: owner review, then separately authorized focused hosted verification.
Existing scope=maps omits B02; current push triggers full verify. The smallest
proposed batch is seven Python modules plus standalone JVM contracts; focused
scope/class filtering requires separate workflow authorization. No commit,
push, PR, merge, tag, dispatch, install, build or local test occurred.
B02.6/B02.7 readiness is the recommended later package; do not begin without
new owner authorization. Historical dated checkpoints below remain preserved.

---

# Autonomous cadastral package — final owner-review checkpoint, 2026-10-20

**Bounded source implementation finished for review; B02 end-to-end remains incomplete.
ALL TESTS / COMPILATION / BUILDS / CI / GUI / GPS: NOT RUN.**

Owner's LARGE AUTONOMOUS IMPLEMENTATION PACKAGE supersedes only the historical
per-stage STOP gates below. Branch `develop/v1.0.1`,
HEAD `ce76cc08c8ad8a2551b5f2ef2e32c91472ed89f1` unchanged.
27 additive source/test/schema files and four canonical docs; complete grouped
manifest, API guarantees, deviations, risks and next steps:
[final source checkpoint](CODEX_PROJECT_CONTEXT.md#b022b025-wms-and-inspire--final-source-checkpoint-2026-10-20).

| Workstream | Final category |
| --- | --- |
| B02.2 synthetic storage/migration | PARTIAL; production activation BLOCKED |
| B02.3 repository/legacy compatibility | PARTIAL; primary editing/provider selection not integrated |
| B02.4 regional dataset foundations | PARTIAL; real Android PRJ/format/acquisition unverified |
| B02.5 Windows | SOURCE COMPLETE, isolated/unexecuted |
| B02.5 Android | SOURCE COMPLETE, isolated/uncompiled; JTS1.20.0 already declared |
| WMS | SOURCE COMPLETE foundation; live endpoint/capabilities/HTTP unverified |
| INSPIRE/Offline | SOURCE COMPLETE foundation; LIVE ATOM ENDPOINT NOT VERIFIED |

Default-deny target fences are not proof of complete old-writer safety. Existing
startup/restore/business paths and legacy-store fencing/activation remain unchanged
and must be integrated/audited before any real migration. Android has synthetic row
import/receipts but no filesystem-copy orchestration. Ambiguous UUID/legacy values
remain unresolved; no default-country inference. True unsnapped unions are written,
with complete-input checks and revision CAS; no geometry/engine execution occurred.
Secure local parsers, explicit download APIs and offline reuse do not establish
official provenance or licenses. Android cleartext policy was not relaxed.

11 pre-existing B02.1/master-source hashes unchanged; pre-existing documentation
content retained. All112 feature IDs and26 baseline assignments retained, no PASS.
No actual profile/database/cache/personal data, original Android installation,
main/Stable/tag/installer, dependencies/configuration, GPS/main form, Git index/refs,
remote or release was changed. No live cadastral/WMS/Atom acquisition was attempted.
Only public technical standards/API/license documentation was read online.

Next safe owner gate: review this source, then authorize one focused public
standard-hosted compile/test package separately. Existing verify.yml/runtime
workflows can execute after a focused filter is separately prepared/approved;
no workflow changes, commit/push or dispatch occurred here. B02.6/B02.7, production
activation, background overlays and owner GPS acceptance remain future packages.
See MASTER_PROGRESS for A–N source support; none has acceptance PASS.

Historical notes below retain their original dated scope.

---


# B02.1 isolated implementation checkpoint — 2026-10-20

**B02.1 COMPLETE AS SOURCE / STATICALLY REVIEWED / AUTOMATED TESTS NOT RUN.
B02.2 NOT STARTED. WAITING FOR OWNER APPROVAL.**
Authority: complete “FIELTRA — B02 IMPLEMENTATION MASTER INSTRUCTION”, owner
authorization2026-10-20. Canonical docs were read in full. Earlier not-authorized
statements below retain their historical scope; only B02.1 was authorized now.
Branch develop/v1.0.1 / HEAD ce76cc08c8ad8a2551b5f2ef2e32c91472ed89f1 unchanged.

Nine additive files: Python `app/country_extensions.py`,
`app/gis/cadastral_protocol.py`, `tests/test_country_extensions.py`,
`tests/test_cadastral_m2m.py`; Android prefix
`android/app/src/main/java/gr/mastixa/manager/`: CountryExtensions.java and
CadastralProtocol.java; androidTest equivalent CountryExtensionsTest.java and
CadastralM2MTest.java; shared/fixtures/cadastral_b021.json.
Exact contracts, test specifications and next-stage paths are recorded in
[current decisions](CODEX_PROJECT_CONTEXT.md#b021-isolated-foundation--owner-authorized-2026-10-20).
[Current stage TODO](MASTER_PROGRESS.md#b021--core-contracts-and-isolated-foundation)
retains the single ARCH-CAD-INTL-01 and all112 features/26 baseline gap assignments.

Pure registry supplies GR only and generic unsupported-country fallback. Greek
adapter preserves existing exact 12-ASCII-digit semantics/raw strings/leading0.
Immutable farm-scoped field/alias/parcel/link/legacy/config/revision DTOs and
repository interfaces permit one field/five parcels and inverse sharing. Farm
scope preserves opaque default/legacy/hex profile IDs; canonical UUIDs apply to
field/parcel identities only. No identity mapping or actual store is activated.
No existing application source is modified, so Greek forms/F-012/provider/cache/
GPS and ordinary startup behavior remain unchanged. Country persistence, SQL,
migration helpers, writer fencing, retrieval, union, backup/ZIP and UI are deferred
to their own gates. No product capability or complete F-ID received PASS.

Seven Python/six Android synthetic test methods are PREPARED, NOT RUN. Fixture
contains five invented rectangles and independent agricultural totals; union
metrics are future expectations only. Source/JSON/whitespace review is distinct
from tests. Python launcher has no registered interpreter; no tool installation,
Python app/test execution, Java compilation, build or local automated test occurred.
No dependency/manifest/Gradle/workflow/permission/version change. No network, real
dataset acquisition, real DB/profile/cache/credential access, migration, Android
installation, Git index/ref change, commit/push/dispatch/PR or release occurred.

Only the four canonical docs were modified in this stage; context/master remain
locally excluded by existing Git rules. Both pre-existing dirty master-source docs
retain their entry SHA256. main/Stable/original applications/installers untouched.
Current state is CODE WRITTEN + STATICALLY REVIEWED, not AUTOMATED TESTED,
OWNER GUI ACCEPTED or RELEASE READY. Existing acceptance evidence remains closed.

Next proposed approval is B02.2 SYNTHETIC-ONLY storage/migration/write-fence helper
and failure-injection test source, chiefly new cadastral_migration.py and Android
CadastralMigration.java plus their test modules. Preserve original schema/IDs/raw
values, reject identity conflicts, prove old-writer/old-restore protection before
any activation. All proofs remain NOT RUN until separately authorized hosted CI.
No real-user migration/startup activation or automatic next-stage continuation.
**STOP. B02.2 NOT STARTED. WAITING FOR OWNER APPROVAL.**

---

# Final cadastral decisions approved / B02 detailed design — 2026-10-20

**OWNER ARCHITECTURE APPROVED; DOCUMENTATION/DESIGN COMPLETE.
B02 IMPLEMENTATION NOT STARTED / NOT AUTHORIZED. STOP.**
The complete final owner attachment was read. Current authority:
[decisions, schema, interfaces and migration/union design](CODEX_PROJECT_CONTEXT.md#final-approved-cadastral-architecture-and-b02-design--2026-10-20),
[single ARCH-CAD-INTL-01 task, A–N tests and exact proposed file manifest](MASTER_PROGRESS.md#arch-cad-intl-01--p0-prerequisite-before-b02).
Older default-country/cardinality/title proposals and requests for architecture
approval below are superseded; only explicit implementation authorization remains.

- Fieltra is agricultural management. No ownership, titles, deeds or notarial
  functionality. Country of cultivation is explicitly stored per farm/profile,
  default GR, independent of language/GPS/IP/locale. Extension registry supports
  reviewed executable adapters, with Greece-only implementation scope and a
  generic unsupported-country farming fallback.
- Cultivated field UUID/history and official parcel identity are separate with
  mandatory M:N links. One field/crop/five adjoining KAEKs remains one cultivated
  field and one set of production/work/cost records; one parcel can serve two
  fields. Existing field IDs/UUID aliases and raw KAEKs remain unchanged.
- Default cadastral overlay is true union/dissolve of all linked selected source
  polygons, without internal seams; genuine holes/gaps/components remain. Default
  cadastral markers show exterior-ring vertices only. Preserve every original
  polygon/vertex/provenance and independent cultivated/GPS/point/track data. Never
  overwrite cultivated area or agricultural totals. Partial/stale/error results
  cannot be presented as complete/legal boundaries.
- Existing Greek main forms/validation/layout/controls/behavior remain exactly
  as currently implemented. Additional links use secondary Linked KAEKs via field
  context actions. Preserve regional Greek provider/cache/retry/attribution and
  known `510201507004`; no nationwide claim, removed provider or old ArcGIS
  endpoint activation. Android retrieval remains message-only in current source.

Detailed proposal: profile-scoped country config, stable identity aliases, unique
scoped cadastral parcels, M:N links/primary legacy-slot projection, immutable
source snapshots, per-parcel jobs/state and fingerprinted derived overlay cache.
Windows Shapely2.1.2 / Android JTS1.20.0 topology services operate on copies in an
explicit GR working CRS, without automatic snap/repair. Missing/invalid sources
have truthful counts/status. Background calculation never runs in paint/GPS
callbacks and must preserve viewport, follow state and foreground track lifecycle.

Migration design is additive, atomic/idempotent inside the prepared new database,
with validated backup, independent platform transition, preserved legacy tables/
payloads and unresolved-value bindings. A versioned live-store resolver plus
legacy write fencing protects against unmodified old writers/file-level restore;
multi-file activation is recoverable, not falsely described as one atomic SQL
transaction. Proposed DB16/backup20, portablev2/reference-aware GIS/lookup contracts
are reserved design values, not applied versions. No real database was opened,
copied, migrated, normalized or changed.

The ledger specifies all A–N stored-data/render cases, including one crop/five
adjoining parcels, inverse shared parcel, overlaps, gaps, multipart/holes, failure,
link invalidation, migration/backup/ZIP/country/GPS and zero agricultural duplication.
Exact expected future production paths are listed there; no app/test/fixture/
workflow files were created or edited. Android still needs a bounded audited
reader for the existing regional SHP/DBF dataset; JTS alone is not that reader.
Storage-fence coverage, conflicting legacy source selection, measured geometry
budgets and version negotiation remain engineering risks, not unresolved product
scope/cardinality decisions. Existing accepted tests were not rerun.

Working branch/HEAD remain `develop/v1.0.1` /
`ce76cc08c8ad8a2551b5f2ef2e32c91472ed89f1`. Only the same four canonical documents
were updated: this file, CODEX_PROJECT_CONTEXT.md, MASTER_PROGRESS.md and
android/WINDOWS_PARITY_PLAN.md. Context/master ledger remain locally excluded from
Git; exclusions and both original dirty master-source documents are preserved.
112 feature IDs / 26 baseline gap assignments remain intact. Design completion
is not app/GUI PASS; earlier installation/GNSS blockers remain unchanged.

No application tests, CI, builds, installs, migrations, source changes, Git index/
ref changes, commits, pushes, releases or main/Stable artifact changes.
Future automated tests remain public free-standard GitHub-hosted only; manual
emulator/GNSS/Sandbox acceptance stays separate. **NO APPLICATION CODE CHANGED;
NO COMMIT/PUSH/RELEASE. STOP for explicit owner B02 implementation approval.**

---

# B01 owner amendment — international cadastral architecture — 2026-10-20

**Historical checkpoint: superseded by the final approved decisions/design above
where it calls country/cardinality/title choices or architecture approval pending.**

**CURRENT P0: ARCH-CAD-INTL-01; architecture approval required BEFORE B02.**
The complete owner amendment was read and incorporated into the existing
[decisions/design](CODEX_PROJECT_CONTEXT.md#international-cadastral-identifier-architecture--owner-amendment-2026-10-20)
and [single TODO/source-audit ledger](MASTER_PROGRESS.md#arch-cad-intl-01--p0-prerequisite-before-b02).
Fieltra is international: independent field UUID, optional string reference,
explicit ISO alpha-2 country/system/authority/jurisdiction, typed title vs parcel
identity, system-specific validation. No country inference from language/GPS/locale;
unsupported-country field creation works without integration. Greek 12-digit KAEK
is preserved as a Greek-specific rule, never generic validation. Existing Greek
values/leading zeros, lookup/cache/jobs/attribution, geometry separation and owner
locality choices must survive a separately approved future implementation.

Read-only amendment audit covers UI/validation/schema/UUID-FKs, ZIP matching/export,
backup/migrations, providers/jobs/cache, GIS contracts/conflicts, tests/docs and
country/localization fallback. Exact production files/methods/columns, risks,
affected F-IDs, proposed additive model, old/new format strategy and focused
acceptance matrix are in the linked canonical files. No real databases/records
were opened, counted, rewritten, migrated or normalized; actual user-data UUID
coverage remains UNVERIFIED. No international provider was researched as an
approved integration, invented or implemented.

**Supersedes the pre-amendment global F-012 fix proposal below.** The Android
missing guard is a Greek-specific source difference, not a request to enforce
12 digits in generic CRUD. F-012 is now DECISION_REQUIRED pending approved system
architecture; legacy-value preservation/validation UX remains an explicit choice.
The 112 IDs and exact 26 baseline gaps stay intact; ARCH-CAD-INTL-01 is a prerequisite
task linked under those IDs, not a duplicate feature or automatic next batch.

Branch/HEAD and installation blockers below are unchanged. This batch modifies
only `docs/CODEX_HANDOFF.md`, `docs/CODEX_PROJECT_CONTEXT.md`,
`docs/MASTER_PROGRESS.md`, `android/WINDOWS_PARITY_PLAN.md`; two original dirty
master-source files remain byte-for-byte untouched. Documentation integrity checks
only; no app tests, migrations, builds, package changes, GUI input or CI execution.

The existing context and master ledger are local-only files already excluded by
`.git/info/exclude`; their durable local updates therefore do not appear in normal
Git diff/status. Those exclusions were preserved. The links above resolve in the
local checkout; they do not claim those files are published on GitHub. No competing
public ledger or private historical document was added to the tracked source.

B01 audit/documentation is complete; architecture and owner GUI acceptance remain
pending. First optional owner GUI action remains the read-only checks package
metadata command below. **STOP for owner architecture approval; do not start B02
or the earlier proposed F-012 fix. NO APPLICATION CODE CHANGED;
NO COMMIT/PUSH/RELEASE.**

---

# Fieltra Android parity B01 checkpoint — 2026-10-20 (pre-amendment findings)

**B01 documentation/source audit COMPLETE; owner GUI acceptance PENDING. STOP.**
Only local documentation was authorized. **NO-PRODUCTION-EDIT / NO-PUBLISH.**
No application, Gradle, test, dependency or workflow change; no build, install,
test execution, CI dispatch, commit, push, PR, tag or release in this batch.

The owner-approved `Fieltra_Android_Parity_Codex_Batches_and_Rules_2026-10-20.txt`
was read completely (Parts 1–7). Durable authority is now recorded in the existing
[decisions/context](CODEX_PROJECT_CONTEXT.md#android-parity-owner-decisions--2026-10-20)
and [master TODO/evidence ledger](MASTER_PROGRESS.md#android-parity-b01--2026-10-20).
The ledger contains all 112 stable IDs, 13 categories and the exact 26 baseline
gaps assigned once to B02–B08 (7 P0 / 10 P1 / 9 P2). B02–B10 are not authorized.
Historical September checkboxes and PASS labels retain their dated scope.

Working checkout: `develop/v1.0.1`, HEAD and inventory baseline both
`ce76cc08c8ad8a2551b5f2ef2e32c91472ed89f1`; no source/workflow differences.
Pre-existing dirty files, preserved without edits: `docs/master-source/README.md`
(462 additions / 45 deletions) and `docs/master-source/RECIPIENT_GUIDE.md`
(0 additions / 11 deletions). B01 changes only this handoff,
`docs/CODEX_PROJECT_CONTEXT.md`, `docs/MASTER_PROGRESS.md` and
`android/WINDOWS_PARITY_PLAN.md`. No index or ref changes.

Identity evidence: Gradle namespace/applicationId `gr.mastixa.manager`, checks
suffix `.checks`, default versionCode `3`, versionName `0.40.0-alpha.2` (overridable
by Gradle property). Existing checks APK output metadata also says
`gr.mastixa.manager.checks`, code `3`, name `0.40.0-alpha.2`; manifest label is
`Mastixa Manager`, launcher `WelcomeActivity`. This metadata does not bind the APK
to current HEAD. Owner-reported assembleChecks success, adb install Success and
monkey Events injected: 1 establish build/install/launch-attempt evidence only.
Installed version and actual foreground package are **BLOCKED_EXTERNAL** here:
ADB is not on PATH, SDK variables/local.properties are absent, the documented
default ADB executable is absent, and no accessible adb/emulator process was found.
No installation, launch, profile inspection or emulator changes were attempted.

Source audit: profiles/session/Quick Access/dashboard, parcel CRUD, cultivated
polygon/vertex switches, geometry import/manual/export, OSM/neutral map, GPS
point/track lifecycle, Windows ZIP preview/import, logical backup and year-lock
paths exist. This is **CODE_PRESENT_UNVERIFIED**, not owner acceptance.
**F-012 FAIL (source contract):** normal parcel save has no nonblank 12-digit KAEK
guard in `MainActivity.editField` or `FarmStore.saveField`; only cadastral-reference
import applies that guard. The complete reproduction, bounded fix proposal and
approval gate are in the master ledger. No fix was made. F-016's vertex control
currently draws cultivated vertices only; separate cadastral vertices are not
demonstrated. Cadastre retrieval remains message-only; automatic KAEK sync false.
Search/data quality/audit/declaration/general export remain construction entries.

Oct-17 focused Android acceptance is retained from `android/README.md`: initial
14/15 passed, repaired/new 2/2 passed, 16 unique passing cases. Relevant source
and method names were inspected; raw XML/reports are absent from this checkout,
and the original execution SHA is not recorded. Do not rerun or invent a current
automated/physical-GPS PASS. Database schema 15 and logical backup schema 19
(35 listed tables) agree with source; the known deferred activity-identity backup
tables are still outside that list, and advanced Windows crop rules remain a
linked limitation under F-048/F-100, not silently certified parity.

All seven local workflows use only `ubuntu-latest`/`windows-latest`; no paid,
larger or self-hosted label was found. Public visibility and retained Oct-18 CI
run successes were checked by read-only GitHub GETs. Standard public runner
minutes meet [GitHub's free-runner policy](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
No runner-policy workflow edit is needed. A later approved focused Android fix
may need an instrumentation class/method input; current runtime dispatch runs the
whole instrumentation suite. No CI was triggered. Future automated tests use
public standard GitHub-hosted runners only; older local connected-test commands
are historical, not renewed authorization. Host emulator and Windows Sandbox are
owner manual acceptance only. See the ledger's seven-workflow inventory.

Remote `main` and `v1.0.0` both resolve to released public
`6dd72e1e07a51173b15b5b72ac709e1c7141da5c` (read-only verification). Local `main`
is a distinct retained `973497ad6362a093eba18bc9283dbcc4c4b8c7ea`; no local
`v1.0.0` tag exists. Do not repair/fetch/switch these as part of B01.
Stable/main/release/installer, seven CLOSED recovery outcomes, licenses and
prior accepted Windows GUI/provider checks remain untouched.

**First owner action only:** in the owner's existing SDK terminal, run
`adb -e shell dumpsys package gr.mastixa.manager.checks` and report only its
versionName/versionCode lines (or package-not-found). This reads package metadata.
Do not create a profile until the exact checks installation/foreground identity
is confirmed. Later small GUI chunks are prepared in the master ledger; they
must be handed to the owner one chunk at a time. Never clear storage or use the
original package. Owner approval is required for the proposed F-012 fix or any
next implementation batch. **NO APPLICATION CODE CHANGED; NO COMMIT/PUSH/RELEASE.**

---

# Fieltra v1.0.1 development handoff — 2026-10-18

- Public development branch: `develop/v1.0.1`, based directly on public main
  `6dd72e1e07a51173b15b5b72ac709e1c7141da5c`.
- Public main and the published v1.0.0 tag/release remain unchanged.
- Source identity: Fieltra `1.0.1-alpha.1`, alpha channel. No development installer,
  release or tag is authorized or produced by this branch setup.
- Existing local development files were preserved during branch setup. Private
  historical workstation documents remain local and are excluded from publication;
  the original full handoff is retained outside the public repository.

## Current development scope

Windows/Android maps, KAEK, independent cultivated/cadastral geometry,
coordinates, polygon/vertex controls, locality suggestions and keyboard/navigation
remain. Windows offers No basemap, OpenStreetMap and optional CDSE. The existing
ArcGIS entry remains disabled under its existing licensing/account gates.
GeoNames CC BY 4.0 provenance, attribution and shipping license remain intact.

Owner decision, 2026-10-18: permanently remove Protomaps/PMTiles and
OpenAerialMap. Removed both provider entries, Download Chios/Open PMTiles actions,
downloader, local archive reader/writer, vector renderer, provider-only statuses,
translations and tests. The unused vendored dependency and its exclusive legal
manifest/notice entries were removed; retained component notices are unchanged.
No replacement provider or provider improvement is part of this change.

Old removed identities (including obsolete in-memory provider objects) resolve
to No basemap. Ambiguous legacy numeric slots other than 0/1 also resolve to No
basemap; CDSE remains selectable by its stable sentinel identity. Startup ignores
the old offline-maps/last-map.json pointer. It does not open, rewrite or delete
that metadata or user-owned map files. Regression checks retain complete parcel
DB snapshots and verify map/metadata bytes survive opening and reopening.

English tabs remain Field / Map; Greek captions and literal-ampersand/keyboard
navigation checks are preserved. The old 23-test offline-provider batch is
superseded by provider removal; its archive-specific checks are retired. The
remaining native module no longer needs a map dataset and remains owner-run in
the already-open Sandbox. Visual/native acceptance of this removal is NOT RUN.
Earlier accepted GUI/recovery outcomes remain closed.

## Hosted CI

Reuse .github/workflows/verify.yml. Ordinary pushes/PRs and default manual runs
retain the complete Windows/Android suite and source/privacy/Gitleaks checks.
No development installer or release is published.

Pre-removal source: 8c2db7faa91e5fdfb4e746a598d8c81c4a79404f.
https://github.com/Sxara242/Fieltra/actions/runs/39122298896
- Source/privacy/Gitleaks PASS; Android unit/lint/debug/test-APK compilation PASS.
- Windows PASS: 154/154 modules, 1,200 tests; development packaging/legal
  contracts PASS. This closes the diagnosed earlier development CI failures.
- Fixes included one-time KAEK identity migration (read-only snapshots retained),
  restored area-unit tooltip, current UI/schema expectations and English catalog.
  The release builder still rejects alpha metadata with the retained Stable
  installer configuration. This result predates provider removal.

For the owner-requested focused removal checks, the same workflow accepts a
manual scope=maps choice: map/provider/UI/geometry regressions, retained-license
contracts and source/privacy/Gitleaks only. Android is not rerun for this
Windows-only removal. Full verification remains the default. The removal commit
uses [skip ci] to avoid an unrelated full automatic rerun, followed by this
explicit focused dispatch.

Removal source: 328db9615d2fbe29657297e698430fa3afeb6949.
https://github.com/Sxara242/Fieltra/actions/runs/39133240354
- Source/privacy/Gitleaks PASS (992 source files).
- Focused Windows PASS: 10/10 modules, 60 tests, including 23 map UI tests.
- Development packaging/legal contracts PASS: 2 tests.
- Android intentionally NOT RUN for this Windows-only change; its pre-removal
  full run above passed. No unrelated full rerun or installer build occurred.
- This handoff-only result update changes no tested application source and uses
  [skip ci]. Native Sandbox/visual inspection remains owner-run and NOT RUN.

## Publication boundary

Keep databases, profiles, credentials, signing material, API keys, PMTiles/MBTiles
and raw map data, generated outputs, local Sandbox files and historical recovery
records outside Git publication. Binary test inputs retain their reviewed hash
allowlist. Required source/licenses/attribution remain present. No private Git
ancestry is copied or merged. No main merge, tag/release creation or installer
publication occurs.


B02.2 checkpoint (2026-10-20, autonomous package authority): isolated schema at
shared/fixtures/cadastral_schema_v2.sql; Python app/gis/cadastral_migration.py;
Android CadastralMigration.java; tests/test_cadastral_migration.py. Transactional
schema, default-deny DML guards, immutable snapshots, synthetic staging and pure
activation-marker refusal/recovery are implemented. PARTIAL: Android staging
orchestration and legacy extraction; production activation BLOCKED until startup,
restore/profile/import/background/business writers and legacy-path fence are
integrated. No global multi-file atomicity claim. Source reviewed; tests/builds/CI
NOT RUN. Existing B02.1 and master-source bytes preserved. Current authorization
supersedes historical per-stage STOP only for B02.2–B02.5/WMS/INSPIRE; no GUI,
real profiles/downloads, dependency change, Git mutation or dispatch. Continue
B02.3 repository automatically. All 112 IDs / 26 gap assignments and A–N retained.


B02.3 checkpoint (2026-10-20): app/gis/cadastral_store.py and Android
CadastralParcelRepository.java implement scoped parcel/UUID-alias dedup, exact
spellings, idempotent M:N links, reverse sharing, tombstones/revision CAS, immutable
source records, conflict-preserving selection, deduplicated jobs, immutable input
snapshots and shared-field invalidation/stale union publication refusal. Primary
projection is checked against unchanged fields.kaek; removing/changing the primary
slot is explicitly refused until the later confirmed compatibility/UI flow.
No business field/area/crop/finance writes. Python synthetic migration now records
classification and validates source tables; completed identical retry is a no-op,
incomplete targets retained/refused. Android API26 uses INSERT/UPDATE rather than
SQLite UPSERT. Test source tests/test_cadastral_store.py; NOT RUN/NOT COMPILED.
State PARTIAL pending primary-edit/legacy-payload extraction and lookup completion
integration; continue B02.4. No production callers, dependency or config edits.


B02.4 checkpoint (2026-10-20): Python app/gis/greek_cadastre.py reuses the
existing NorthAegeanProvider parser once per explicit local ZIP/multiple KAEKs;
no existing cache/provider/request behavior changed. Android GreekCadastreDataset,
GreekCadastreProvider and CadastralLookupWorker implement local ZIP/SHP type5/SHX,
dBASE III KAEK+bLfSpnVr character fields and UTF-8 CPG. Flat five-member archive,
path/CRC/ratio/count/size/offset/record/finite-coordinate/ring/topology/cancellation
checks; 32MiB compressed, 64MiB expanded (Android deliberately below Windows128MiB),
48MiB entry, 500000 rows, 20000 points/parcel and 100000 selected points. PRJ is
accepted ONLY by caller-supplied independently verified EPSG:2100 SHA256 hashes;
no live PRJ hash is bundled, so real Android regional compatibility is PARTIAL /
BLOCKED on verified PRJ evidence. Local archive provenance never becomes official
merely by import. Worker returns results only; transactional completion next.
No nationwide claim, hidden network, permission or current-map change. Tests to
be extended with generated synthetic ZIP source; all automated execution NOT RUN.

B02.5 checkpoint (2026-10-20): Python cadastral_union.py uses union_all(grid_size=0),
Android CadastralUnion.java uses existing JTS1.20.0 UnaryUnionNG FLOATING, without
snap/repair fallback. Dependency declarations and android/THIRD_PARTY_NOTICES.md
already cover JTS EPL2/EDL1 and Proj4J; requirements-windows-rc pins Shapely2.1.2.
No dependency/configuration change. Both implement all nine states, completeness,
100000/16MiB budgets, EPSG2100 / Greek-bounded EPSG4326 copies, holes/multipart,
exterior-only vertices, explicit executor/cancellation and stale publication CAS.
Native engine calls cannot be preempted mid-call; cooperative 30s checks only.
Test source tests/test_cadastral_union.py covers five/overlap/gaps/holes/multipart/
point-touch/invalid/missing/CRS/engine/stale cases. SOURCE WRITTEN, NOT RUN/COMPILED;
Android cross-platform geometric equivalence remains unverified. Continue WMS.


WMS checkpoint (2026-10-20): app/gis/provider_io.py + cadastre_wms.py and Android
CadastralProviderIO.java + GreekCadastreWms.java implement secure bounded XML,
GetCapabilities discovery/inheritance, advertised layer/style/format checks,
WMS1.1.1 SRS vs1.3 CRS axes (EPSG4326 lat/lon only in1.3), finite/dimension-bounded
GetMap, explicit executor/timeout/cancellation, duplicate in-flight coalescing,
service/image error detection and original response metadata. Published HTTP
endpoint retained exactly; HTTPS not assumed. Android respects existing cleartext
policy and returns explicit transport failure; no manifest/security change.
No live capabilities/layer/transport claim. Disk caching disabled pending reviewed
provider terms. Viewer is a source/terms reference, not a verified offline license.
Tests in tests/test_cadastre_providers.py are synthetic and NOT RUN. Continue INSPIRE.

INSPIRE checkpoint (2026-10-20): app/gis/inspire_offline.py and Android
InspireOffline.java parse bounded Atom/INSPIRE identifiers, versions/dates/coverage,
relative download links and rights/provenance. Explicit user-selected ZIP retrieval,
size/time/cancellation/CRC/traversal/bomb checks, SHA256 immutable exclusive file
publication and separate transactional index. No extraction API. Index commit and
blob publication are recoverable steps (verified orphan possible, never partial
AVAILABLE); no automatic cleanup. Fresh-only downloads; resume predicate validates
206/Content-Range/strong ETag but downloader never appends. Local reader validation
callback enables B02.4-compatible archives, without guessing all INSPIRE formats.
LIVE ATOM ENDPOINT NOT VERIFIED. No replacement URL invented, live dataset fetched,
orthophoto/vector confusion or WMS bulk download. Source written, test sources
prepared NOT RUN; official format/provenance/terms/live verification pending.
Next: complete focused Android synthetic tests and static cross-contract review.


## Source hardening review — inventory checkpoint, 2026-10-20

New owner SOURCE REVIEW, HARDENING & CI READINESS package authorized; no local
execution, workflow edits, remote mutations, live provider probes or activation.
Verified develop/v1.0.1 / ce76cc08c8ad8a2551b5f2ef2e32c91472ed89f1, unchanged.
Inventory matches the previous manifest: B02.1 nine files (four application,
four test sources, one JSON fixture), later27 files (16 application modules,
ten test/helper sources, one shared SQL schema). All36 remain untracked; four
canonical documents contain checkpoints (context/master are locally ignored).
Two unrelated dirty master-source documents remain protected; no existing live
application source is modified. Current hashes/lengths captured in tool state,
not duplicated on disk. All previous runtime/compile/test claims remain NOT RUN.
Next: inspect architecture/contracts, then storage/repositories, parsers/union,
WMS/Atom/TEE feasibility and prepare exact hosted commands without execution.


### Hardening checkpoints A–C — 2026-10-20 (source only, NOT RUN)

A: country/UUID/GR default contracts reviewed; settings remain unpersisted in live
farms and no language/GPS inference found. HIGH cross-platform defect corrected:
Python JSON/hex vs Java JSON/text source/input hashes now use versioned signed-int32
length framing of strict UTF8/raw bytes/null. Added cadastral_fingerprint.py and
CadastralFingerprint.java; Android source payload now immutable bytes with existing
text constructors retained. This is an isolated internal contract, not schema1 sync.

B: HIGH independent-commit bypass corrected before commit: Python requires owned
connect_synthetic/GuardedConnection and rejects transaction SQL/cursor/executescript
through an authorizer; Android uses SQLiteTransactionListener to veto premature
commit/yield and checks balanced completion. Exact fence definitions are checked,
not just names; missing/altered fences refuse writes. Shared SQL now rejects null
text PKs, duplicate request tokens, cross-provider snapshot selections and invalid
link timestamps/counts. Production activation remains BLOCKED: no legacy-store
fence, resolver/file activation, restore/profile/import/business integration exists.
These helpers are not a hostile arbitrary-SQL/filesystem security guarantee.

C: HIGH forged/truncated input snapshots could reuse the correct fingerprint and
publish a partial COMPLETE result; publication now compares the entire immutable
capture and result counts. Stale active lookup jobs are superseded rather than
returned forever; reselecting an identical current snapshot is idempotent. Primary
GUI edits and overall multi-provider conflict decisions remain isolated/deferred.
All fixes UNVERIFIED; focused guard/hash/CAS regression sources are being extended.
Next: dataset/union/WMS/offline boundary review, then TEE/hosted readiness.


### Hardening checkpoints D–H — 2026-10-20 (NOT RUN)

D: regional inputs remain local-only, actual official Android PRJ/DBF/SHP variant
UNKNOWN beyond existing Windows parser contracts. Added ZIP member/CRC checks to
new Windows adapter without altering the old provider, aggregate100000/16MiB output
bounds, strict supported jurisdiction, streamed Android ZIP hashes and mutation
checks, no duplicate-shell collapse, exact-size entry reads avoiding BAOS copies.
No official dataset was fetched/read. Android64MiB expanded bound still needs
hosted/device memory measurements; no universal official archive compatibility.

E: both true-unsnapped union APIs retained. Corrected cross-platform state priority,
coordinate-loop cancellation, finite transformed measurements, explicit transform
failures and derived output vertex bound. No native-call hard-preemption claim.
F: API33 URL encode/decode overloads replaced by API1 UTF8 forms for minSdk26;
reserved WMS query keys cleared, injected-transport size/cancellation validated.
Manifest has no cleartext exception/network config; target36 defaults to denied
HTTP on API28+, subject to actual OS policy. No endpoint/HTTPS probe or manifest edit.

G: offline root/index link refusal, dedicated index validation, optional reviewed
SHA256 verification (no invented feed checksum namespace), hash-preserving source
bytes, broken-link corruption handling and shared versioned dataset keys added.
Mixed XML rights text order retained; XML depth/attribute/URL boundaries aligned.
Missing Atom endpoint remains unverified; downloads stay explicit/fresh-only, no
resume append, extraction or WMS bulk acquisition. File/index publication remains
recoverable separate steps, with possible verified orphans after interruption.

H TEE: owner-observed parcel display/search/popup is evidence of portal behavior,
not an independently reusable API. geocode.arcgis.com is search/geocoding;
utility.arcgisonline.com is transformation; services-eu1.arcgis.com/query alone
lacks service/layer/field metadata, and returnGeometry=false proves no coordinates.
The TEE proxy.php observation is an internal portal route, not an approved direct
provider URL. Implementation BLOCKED pending exact officially documented feature
service/layer, KAEK field/type, geometry-returning capability, CRS/pagination/errors,
auth/access/license/attribution/rate conditions and direct-vs-proxy authorization.
A future adapter can reuse GR scoped identities/repository snapshots/jobs, remain
disabled and preserve competing sources. No TEE code, scraping, credentials or
network probes; imagery rendering was not established by the owner's screenshot.
Next: focused regression sources and exact hosted CI/Git proposal, no execution.
