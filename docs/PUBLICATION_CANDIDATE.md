# Windows source publication candidate — 2026-10-15

This is a **new source-only publication candidate**, using the retained application
source associated with the owner-accepted external-VC installer. No installer has
been built from this publication tree. RELEASE NO-GO.

The accepted reference Setup is
`9457f1f4a8223de76caa49c1ba88a6dddd3e5176868dc25eb88a93eb9293875f`.
Its historical `packaging/build_external_vc_candidate.ps1` (3,008 bytes, SHA-256
`ba81f3d9f07145bd007a6824678590f5b0300c2c2e37f3ccdab05c3e89de3c56`)
was not recovered. The owner closed that search and approved a new implementation.
**This publication does not establish historical source equivalence with that
Setup.** Its acceptance is not transferred to a future installer.

## Replacement and dependencies

The replacement builder is adapted from the retained newer 3,714-byte script,
SHA-256 `57fb14e0b2c1bf651db758cf26afc1176bcf108f120915d4c23ba5a06ed0b3be`.
The later installer-identity generator and predecessor option are omitted because
the retained installer does not implement that protocol. The installer AppId,
application source, data-preservation behavior and runtime policy are unchanged.
No later sidebar/development code is silently substituted.

The builder requires explicit existing paths for a fresh application payload,
its manifest, native launcher, compiler, Python and fresh output. It checks the
pinned compiler; validates legal/resources, TLS and CRT policy; audits the launcher;
copies/verifies the payload; invokes Inno once; and writes a new candidate receipt.
It performs no dependency download, installation, application launch, overwrite,
cleanup or automatic retry. Failed output is retained. Build receipts are evidence
of their stated operations, not distribution permission or historical equivalence.

- Use Windows x64 and the pinned CPython 3.14.8/wheels, including `pefile==2024.8.26`
  from `requirements-windows-rc-hashed.txt`. PyInstaller 6.22.3 is needed to build
  the application. The builder's Python helpers are included in `packaging/`.
- Use the retained Inno Setup 6.7.3 compiler with SHA-256
  `0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7`
  and its required resources/license. Inno is a separately supplied build tool;
  no tool binaries or supplier archives enter ordinary Git source history.
- The existing native launcher fallback is 286,720 bytes, SHA-256
  `e6b85f013d27ed08680ab0a165e7d25d258574d47781ae387d0cbead284cba87`.
  It is separately retained, outside the 121-file external-input collection.
  Launcher source and audit/build scripts are included. Compiling a replacement
  launcher requires separately entitled MSVC/Windows SDK tools and qualification;
  the reuse route does not require a new native toolchain.
- The Microsoft VC++ runtime remains externally installed by the recipient.
  This builder neither bundles nor downloads/installs Microsoft runtime files.
- First-party source remains AGPL-3.0-only. Preserve all third-party licenses,
  notices, exact dependency sources and necessary producer/replacement materials.
  The builder adds no new third-party runtime or binary redistribution payload.

## Future build route — separate guest-only authorization required

Use a fresh disposable Windows guest, a clean copy of the published source and
verified offline inputs. Pin the published commit and preserve a complete source
snapshot/inventory before construction. Configure the retained Python/TLS supplier
roots as documented in `packaging/windows-tls-inputs.json`; use a fresh venv and
`--no-index --find-links` with the offline wheels and `--require-hashes` lock.

1. Run `packaging/build_release.ps1 -SkipInstaller` with explicit guest Python,
   fresh PyInstaller work and dist paths. Do not reuse the historical frozen engine
   as proof that the new source built it. Do not use the script's default native
   launcher/installer build route for this candidate.
2. Record a nonempty JSON **object** mapping every case-sensitive payload-relative
   path (forward slashes) to its lowercase SHA-256. For example,
   `{"MastixaManager.exe":"<64 hex digits>","_internal/example":"<64 hex digits>"}`.
   This matches the retained `external_vc_layout.py` interface; an array of
   `path,size,sha256` rows is not that helper's manifest format.
3. Invoke `packaging/build_external_vc_candidate.ps1` with `-PayloadDir`,
   `-PayloadManifest`, `-LauncherPath`, `-CompilerPath`, `-PythonPath` and
   `-OutputDir`. Output must be a new path outside source/payload. The default
   Setup basename ends in `public-source`, distinguishing it from accepted output.
4. Bind the fresh installer and complete package to the exact published source
   and supplier identities, then qualify the new candidate's affected installer
   behavior before acceptance. No byte-identical reproduction claim is implied.

## Publication and distribution boundary

The historical builder hash is no longer a prerequisite for this explicitly NEW
source candidate. Static source preparation is not a completed installer rebuild.
The local retained source/material collection is not independently verified public
recipient access. Before binary distribution, establish the new artifact/source
binding and equivalent recipient access to required application/dependency source,
build controls and notices under the chosen license routes. Retained prebuild legal
flags describe their scoped material checks; they do not authorize distribution.

The seven existing public workflows remain unchanged. Only `verify.yml` has an
automatic push trigger; it includes source, Windows and Android jobs. This review
does not authorize CI, commit, push, release or cleanup. The proposed commit message
includes `[skip ci]` to preserve that CI boundary when commit/push are approved.

All seven accepted recovery tests remain **SUCCESS**; SmokeTest **CLOSED**.
The owner confirmed the independent Maxtor payload and metadata hash matches.
Those completed checks are not repeated or replaced by this source review.
