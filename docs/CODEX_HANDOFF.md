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

Windows/Android maps, cadastral presentation, independent cultivated/cadastral
geometry, PMTiles reader/overview, explicit bounded download/local-file opening,
locality suggestions, keyboard/navigation corrections and related regressions.
GeoNames is public CC BY 4.0 data with hash/provenance/attribution and shipping
license. Vendored PMTiles source is BSD-3-Clause with full notices; map datasets
and local Sandbox artifacts are excluded. ArcGIS integration remains disabled
pending the documented provider/account/distribution requirements; no key is
included. No new provider-license clearance is claimed by a source CI pass.

The existing English translation of Αγροτεμάχιο is Field. The native tab test
now expects `['Field', 'Map']`; Greek labels, exact ampersand-free captions and
left/right keyboard navigation assertions are unchanged. Owner reported the
provider Sandbox batch at 22 PASS / 1 FAIL before this expectation correction;
the corrected 23-test batch and its visual inspection remain pending owner-run
execution in the already-open Sandbox. Earlier accepted GUI/recovery outcomes
remain closed and are not rerun by hosted source CI.

## Hosted CI

Reuse `.github/workflows/verify.yml`: pushes (including develop/v1.0.1), pull
requests and manual dispatch run source/privacy audit on ubuntu-latest, Windows
source tests on windows-latest, and Android unit tests/lint/debug and test-APK
compilation on ubuntu-latest. Hosted workflows publish no development installer.
Existing Android instrumentation/QA and Windows packaging workflows remain manual.
The guest-only native provider module remains outside ordinary source discovery.

Existing Stable run:
https://github.com/Sxara242/Fieltra/actions/runs/38777169557
- source-audit PASS; Android PASS; Windows FAIL (133/141 modules passed).
- Diagnosed failures: obsolete newer-version/channel and RC expectations,
  stale Fieltra file-dialog branding expectations, smoke-runner fixture version
  identity, and missing English navigation accessibility translation.
- Current development changes contain matching fixtures/translations without
  removing assertions or skipping failing modules. The Field correction is included.
- Packaging metadata intentionally remains the accepted Stable configuration;
  existing development tests require exactly the version/channel refusal and
  reject any additional legal/configuration error. CI runs these explicit
  development contracts; the actual release validator remains fail-closed.

Development branch publication and hosted results: pending focused publication
checks and push. Results will be recorded after the actual hosted run.

## Publication boundary

Keep databases, profiles, credentials, signing material, API keys, PMTiles/MBTiles
and raw map data, generated outputs, local Sandbox files and historical recovery
records outside Git publication. Binary test inputs retain their reviewed hash
allowlist. Required source/licenses/attribution remain present. No private Git
ancestry is copied or merged. No main merge, tag/release creation or installer
publication occurs.
