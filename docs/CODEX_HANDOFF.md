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
