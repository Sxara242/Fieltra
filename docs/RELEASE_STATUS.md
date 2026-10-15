# Fieltra v1.0.0 Stable

Fieltra — Farm Management is the first official free, open-source Windows release.
[Official Release and downloads](https://github.com/Sxara242/Fieltra/releases/tag/v1.0.0).

Installer: `Fieltra-1.0.0-Setup.exe`, 54,347,611 bytes; SHA-256:
`b4f0efebb54dac65735761d5dbf0197e5529252be13a1f279d95c26178cfee56`.
Owner acceptance: Sandbox installation, startup, Dashboard, branding/version and
Open Source presentation PASS. Python, resource, installer and native-launcher
source correspondence PASS. The launcher differences are only two linker timestamps;
the provenance issue is CLOSED. The accepted installer remains unchanged.

The `v1.0.0` tag identifies the exact published source commit. Both source companion
archives, licenses and build/replacement controls accompany this release. See
[FIELTRA_V1_RELEASE.md](FIELTRA_V1_RELEASE.md) for identities and links.
AGPL-3.0-only licensing and historical attributions remain. Android is in development.
The seven accepted recovery tests remain CLOSED. Development after this release targets v1.1.


---

Historical records and retained technical instructions follow. Earlier status statements
do not override the Fieltra v1.0.0 preparation status above.

# Current release status — 2026-10-15

**New Windows RC2: build and SHA-256 PASS; owner Sandbox installation and Dashboard
launch PASS / ACCEPTED. All seven recovery tests remain SUCCESS / CLOSED.**
Accepted installer SHA-256:
`8c4b003646ca8c4f0174a7a72e31079fbd6c6d7d471375a82459bfe74cade303`;
source commit `e5b56568f8396f3b0547d8f151e7904314ff3225`.

The owner also confirms a clean Bitdefender scan of this exact file; the normal
scan item is CLOSED. Public binary distribution awaits only recipient access to
the matching source/material companion and owner publication approval. The
accepted export records external-runtime mode with no bundled VC Redist/CRT;
the historical bundled Microsoft agreement gap does not block this route.
The artifact identifies as `1.0.0-rc.2`; stable embedded metadata is optional,
not a licensing prerequisite. Do not silently relabel or rebuild it. See the current
[project handoff](CODEX_HANDOFF.md) for the scope and shortest resolution.
Finish Windows v1.0 before v1.1. No tests or builds are requested by this status.

---
The dated records below retain their original scope and do not reopen accepted
tests or override the current accepted artifact and remaining work above.

# Historical release status — 2026-10-12

Latest focused qualification: **external-runtime Setup build and actual package
inspection PASS**. Candidate SHA
`9457f1f4a8223de76caa49c1ba88a6dddd3e5176868dc25eb88a93eb9293875f`,
54,336,551 bytes; 18,251,147 bytes/25.14% smaller than accepted RC2 Setup.
All560readback application members match staged hashes, including559accepted
engine members. No redist/loose Microsoft CRT; new runtime nonredistribution gate
PASS for this artifact only. One controlled compile under owner-reported pause
did not reproduce sharingerror32; previous cause is still NOT VERIFIED.
No code changes/repeat85Python tests/74native assertions. Native installation,
missing-runtime GUI, upgrade/uninstall, security recheck and final owner acceptance
remain unqualified. Source/notice/supplier/access binding remains OPEN.
See [exact candidate qualification](WINDOWS_EXTERNAL_VC_QUALIFICATION.md).
Bundled §8(b)(ii) unresolved; **RELEASE NO-GO**. No publish/commit/cleanup.

Initial external implementation checkpoint below is retained for its failed
outputs; the new exact artifact supersedes its compile/inspection blocker only:

Latest owner decision: **external x64 VC++ prerequisite, checked at launch** for
the next candidate. Setup installs without checking/bundling/downloading/running
VC Redist; the native Greek launcher offers Microsoft download/Recheck/Cancel.
Implementation/staged layout PASS, 85 focused Python tests and 74 native synthetic
assertions PASS. Read-only production detector returns READY; actual missing-runtime
dialog/application launch and revised installation/upgrade/uninstall are NOT TESTED.
Completed Setup build FAIL (Windows sharing error 32, also outside tool sandbox);
actual package inspection and installer size are BLOCKED. Native launcher is
286,720 bytes; staged logical payload grows from 168,781,801 to 169,068,521 bytes.
The general bundle preflight also reports a notices mismatch against current source:
the accepted frozen notices predate the later source-only Microsoft headers.
Retained bytes are preserved; final notice/source/artifact binding is still OPEN.
See [external prerequisite implementation and handoff](WINDOWS_EXTERNAL_VC_PREREQUISITE.md).
The new mode's nonredistribution gate is PENDING until completed-package inspection.
Bundled Community §8(b)(ii), remaining supplier/source/native/security/owner gates
stay unresolved/open. **RELEASE NO-GO.** No commit/push/publication or cleanup.

The following checkpoint describes the unchanged accepted bundled candidate:

Current local checkpoint: owner confirms the latest year-display RC2 installer
passed Windows Sandbox; installer UX/compact editable selector are ACCEPTED and
four-digit clipping is resolved. See CODEX_HANDOFF.md for that exact candidate and
scoped owner result. Previous native receipts retain their own hashes/scopes.
Community 2026 individual eligibility and the listed unmodified runtime grant
are established conditionally; fresh official DOCX-byte verification PASS after
approved retrieval, matching the retained originals. Bundled binary distribution
remains BLOCKED by unproved protective recipient/distributor agreement.
See WINDOWS_RC2_MICROSOFT_COMPLIANCE.md.
Accepted installer flow and all binaries are unchanged. Matching covered source/
access, native fault/PDF/cleanup, security and final release acceptance remain open.
Distribution stays NO-GO. No native/full-suite/hosted CI rerun or publication.

**Public AGPL development snapshot: PUBLISHED; hosted CI PASS.**
**Windows public binary release: NO-GO. Android: IN DEVELOPMENT.**

Windows x64 is the current release target. Current source metadata is
`1.0.0-rc.2`, channel `rc`, first-party license `AGPL-3.0-only`, unsigned intent,
offline staging updater. No release feed is activated by this snapshot.

| Gate | Current status | Scope and remaining work |
| --- | --- | --- |
| Windows rc.1 candidate build and artifact validation | PASS, retained historical evidence | rc.1 was built, installed and tested; it is not the owner-accepted final candidate |
| rc.1 owner acceptance | BLOCKED / superseded by source fixes | Owner found defects, including locked-year/correction behavior |
| FIX 1–11 source batch | PASS, retained evidence | 168 focused tests and six native source routes recorded; fixes require a new candidate |
| Windows rc.2 current year-display candidate | BUILT; owner Sandbox/UX PASS; broader qualification PARTIAL | Installer/selector accepted and clipping resolved; no additional native fault/reboot/PDF/DPI scenarios inferred |
| B1–B5 legal/material preparation and scoped EPSG remedy | PASS in current retained release configuration | Preserve exact locked inputs and notices; B1 audit/B4 reproduction gaps are separately labelled, not waived legal inputs |
| Corresponding source for a new public binary | PENDING | Publish matching covered source/build/patch/replacement materials with final artifact binding and equivalent access |
| Public hosted CI | PASS, runners verified | Corrected commit 23c98fa passes source audit, Windows tests/preflight and Android build/lint on standard hosted runners; no stored artifacts |
| Retained full Windows source suite at the published snapshot | PASS historically | 133 modules / 994 cases passed before the local UX changes; current scoped checks pass 161 cases / 16 modules, while a new full-suite/hosted run is NOT RUN |
| Android | IN DEVELOPMENT | Build/lint and instrumentation do not qualify a public Android release; complete binary notices/native and CRS rights review remains required |

The rc.1 application SHA-256 recorded in retained evidence is
`edfe925e40d648ee1e95a51421b52dc1a10b84b4ec234b313fb9429a0e6c0619`;
installer SHA-256 is
`f96b20fbad16aad79f50398b000fe9e7dd6c0ac1715332bee54e55e44ba9bc47`.
Those hashes describe historical binaries and do not bind this current source.

Public development CI uses Windows source tests and Linux Android build/lint.
Packaging contracts and release preflight run without producing installers.
Actual release builds remain a deliberate maintainer step using qualified,
hash-locked suppliers. A hosted runner's Python install is not a substitute for
the qualified PSF/FireDaemon packaging inputs. See [BUILDING.md](BUILDING.md).

Historical audit documents preserve earlier decisions and local receipt paths.
Use this page for the current release conclusion. Local evidence directories,
private Git history, production profiles and candidate binaries are absent from
the public snapshot. No private repository mutation or publication is implied.
The public repository is now the primary active development repository after
the audited source push and actual hosted-runner verification. Phase 5 and all
rc.2 work use its public checkout. Windows source failures block rc.2 build,
not this explicitly authorized development-source publication. Corrected source,
tests and workflows at `23c98fa8da4286a7c26e9062e67c90dd6df58a23` passed
[hosted run 37973487436](https://github.com/Sxara242/Mastixa-Manager-Source/actions/runs/37973487436)
before advancing public main. Subsequent status-only documentation updates do not
change those validated inputs. See [Phase 5 diagnosis and validation](PHASE5_WINDOWS_BLOCKERS.md).
