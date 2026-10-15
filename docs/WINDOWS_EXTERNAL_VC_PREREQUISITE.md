# External Windows VC++ prerequisite — 2026-10-12

Latest checkpoint: the single controlled build **PASS**, 54,336,551 bytes, SHA
`9457f1f4a8223de76caa49c1ba88a6dddd3e5176868dc25eb88a93eb9293875f`.
Actual package integrity/extraction and all 560 member comparisons PASS;
no bundled redist/loose Microsoft CRT. The new method's runtime binary
nonredistribution gate PASS for that exact artifact only. Sharing error32 did not
recur under owner-reported temporary protection pause; causation is unproved.
See [current qualification](WINDOWS_EXTERNAL_VC_QUALIFICATION.md).
Native/security/source/notice/final owner gates remain OPEN; **RELEASE NO-GO**.

The implementation description and initial failed-build checkpoint below are
retained as historical evidence; its BLOCKED package result is superseded only
for the exact newly inspected artifact above. Old artifacts/receipts are unchanged.

Owner decision: the next candidate uses **external prerequisite detection at
launch**. **Microsoft Visual C++ Redistributable x64 is required to run Mastixa
Manager, but is not included in its installer.** Minimum remains
**14.51.36247.0**, x64. Obtain it directly from
[Microsoft](https://aka.ms/vc14/vc_redist.x64.exe), install it yourself under
Microsoft's terms, complete any requested restart, and recheck or reopen Mastixa.
[Microsoft's supported-runtime guidance](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
explains architecture and version compatibility. Mastixa remains AGPL-3.0-only;
other supplier and corresponding-source obligations remain independent.

**Implementation and staged-layout checks PASS. Completed installer build FAIL;
actual installer inspection/native qualification NOT TESTED. RELEASE NO-GO.**
No new public binary, source publication, owner acceptance or Microsoft approval
is implied. Earlier bundled RC2 documentation/artifacts retain their own scope.

## Why a native launcher is necessary

Inspection of the accepted frozen payload found `python314.dll` importing
`VCRUNTIME140.dll`; Qt6Core imports `MSVCP140.dll`, `MSVCP140_1.dll`,
`VCRUNTIME140.dll` and `VCRUNTIME140_1.dll`. QtCore.pyd depends on that native chain.
Although the PyInstaller entry EXE imports OS libraries only, it must load Python
before Python/PySide can display the requested warning. Therefore a Python/Qt
warning cannot reliably handle an absent CRT. A generic bootloader error is not
the requested Greek prerequisite workflow.

`packaging/windows_launcher/` implements a small first-party Windows x64 front
end. C11, `/W4 /WX /GS /Zl` and `/NODEFAULTLIB` exclude CRT objects/libraries.
First-party stack-cookie support uses Windows BCrypt randomness and fail-fast
handling, including termination on exceptional unwinding; no Microsoft CRT
implementation is copied. Actual PE inspection verifies six OS-only imports:
advapi32, bcrypt, kernel32, shell32, user32, version. ASLR/NX, cookie load config,
asInvoker and PerMonitorV2 manifests, and System32-dependent-load flags are
verified. [Microsoft documents the dependency search flag](https://learn.microsoft.com/en-us/cpp/build/reference/dependentloadflag?view=msvc-170).
Custom entry/guard code and actual missing-runtime behavior still require native
and security review; dependency inspection alone is not full security clearance.

## Detection and launch behavior

The detector reads the HKLM `VisualStudio\14.0\VC\Runtimes\x64` subkey in
explicit 64- and 32-bit views. Installed must be a valid DWORD equal to one;
typed Major/Minor/Bld/Rbld fields must meet the four-part minimum in either view.
It also reads the PE machine and file version of canonical System32
`msvcp140.dll`, `msvcp140_1.dll`, `msvcp140_2.dll`, `vcruntime140.dll` and
`vcruntime140_1.dll`. All five must be valid AMD64 images meeting the minimum.
Missing, outdated, wrong-architecture and unverified/error states stop before
Python/Qt loading. It neither loads those CRT files during probing nor writes
registry, preferences or application data. A valid view can satisfy the registry
requirement despite an invalid other view; file checks remain mandatory.

The Greek dialog explains that Mastixa is installed, identifies x64/minimum,
and offers **Λήψη από Microsoft / Έλεγχος ξανά / Ακύρωση**, plus the visible
official URL. Only an explicit download-button click opens the URL through the
browser. No package fetch, execution, administrator elevation or silent consent
occurs. Recheck reruns detection; successful detection opens Mastixa. Cancel or
window close leaves Mastixa installed. Offline users obtain Microsoft's package
separately on a connected device. An adequate runtime skips the warning.

The root `MastixaManager.exe` launcher starts the absolute sibling
`engine\MastixaManager.exe`, quotes and forwards arguments, inherits environment
(including synthetic data-home overrides), uses the engine working directory,
and forwards its exit status. An owned Windows Job holds the exact new suspended
child before resuming it. Forced parent termination stops that engine; normal
engine exit clears kill-on-close so separately requested updater descendants may
continue. No global process-name/PID killing is introduced.

Current scope is native Windows x64. ARM64/ARM64X is NOT QUALIFIED: strict AMD64
image checks may reject hybrid ARM64X runtime files. The existing installer
`x64compatible` declaration is unchanged and is not proof of ARM support.

## Installer and compatibility

Setup no longer includes the bundled prerequisite script or a runtime package,
page, consent, detection, execution or prerequisite restart callback. Its
PrepareToInstall return does not depend on VC++ state. Only external-launch mode
is accepted by ISPP/configuration. No end-user mode toggle exists.

Start Menu, Desktop and post-install launch all use `{app}\MastixaManager.exe`.
The accepted frozen application is copied unchanged under `{app}\engine`.
AppId, install path, upgrade/repair detection, `/NOICONS`, data/preference
identities, installation-year marker and explicit `/PURGEDATA` semantics are
preserved. The offline staging updater remains inactive as a public release feed.
Actual update-helper/Job interactions and upgrade/rollback must be guest-tested.
The root native EXE retains the application name/icon and version metadata.

An upgrade can leave old `_internal/` program files. No destructive migration
cleanup was added; this can increase the upgrade footprint beyond the fresh
layout figure below. Inno's normal/full-purge uninstall code remains unchanged,
but its new root/engine layout is not natively qualified. The accepted installer
is retained for rollback evidence, not automatically requalified for this mode.

`vc_redist_prerequisite.iss` and the existing redist lock are retained engineering
references, excluded from the active installer. The historical repackager refuses
use against the changed script. Any future bundled mode requires separate owner
approval, authoritative clarification/review, package build and full-path
qualification. Community 2026 §8(b)(ii) for bundled delivery is still unresolved.

## Measured outputs and identities

Base checkout: `main`, HEAD `973497ad6362a093eba18bc9283dbcc4c4b8c7ea`;
inherited uncommitted work preserved. Private evidence directory:
`RC2ExternalVc_20261012/` outside the public repository.

| Item | Bytes | SHA-256 / status |
| --- | ---: | --- |
| Accepted year-display RC2 Setup | 72,587,698 | `865d2068ac03f4d18a7553a40b6dfea94c4cfac47f3491c22944665bcf9a7edc` |
| Accepted frozen application EXE | 10,757,055 | `b7b474aa65093b7fc147e3f7c9bd38a181a1935888233b14f92bc43d2dcdb573` |
| Accepted code source archive | 23,989,689 | `c15a2d59b4da4edf3879463c262ac96238ca896996ff0ee8713ba93923ebc1d8` |
| Staged native launcher, native-06 | 286,720 | `e6b85f013d27ed08680ab0a165e7d25d258574d47781ae387d0cbead284cba87` |
| Original 559-member frozen payload | 168,781,801 | Every retained member SHA-256 matches |
| New 560-member staged install payload | 169,068,521 | All 559 engine members unchanged; one launcher added |
| New completed Setup | — | FAIL/BLOCKED; no completed artifact/hash/size |

The logical fresh installed-payload increase is **286,720 bytes / 280 KiB**.
These figures exclude generated uninstaller, filesystem allocation, user data and
the separately installed system runtime. Actual installed allocation and package
size delta cannot be reported until Setup builds and is installed in a guest.
No compression-ratio estimate is substituted for measured package bytes.

Verified staging is in `dist/1.0.0-rc.2-external-vc-20261012-final/install-layout/`;
the adjacent `layout-receipt.json` records all 560 hashes. The earlier attempt is
also retained. Initial Pascal-comment compile error was corrected. Subsequent
compiler attempts, including the same layout compiled as an ordinary user
outside the tool sandbox into a fresh destination, failed after compression with
Windows sharing error **32**, compiler exit **2**. No completed installer remains.
Owner reports a Bitdefender **Potentially unwanted app detected** notification
for the candidate basename. Blocking/quarantine/action is not yet confirmed;
this is a possible cause, not established root cause. Read-only ordinary-user
Windows event checks found no Bitdefender event-log channel or matching recent
Application event. No ISCC process remains. Current output paths contain no Setup.
The accessible Desktop Events store contains only a wlan directory; quarantine
metadata does not independently identify this candidate. No quarantine contents
were extracted/restored. Handle CLI is unavailable; openfiles cannot identify
local locks because its tracking flag is disabled/access is denied. That flag was
not enabled. Historical locks and actual installer integrity are **NOT VERIFIED**.
Detailed Bitdefender notification time/path/detection/action must be read manually
by the owner. No AV exclusions or security changes were made. Failed diagnostics
are retained; no unchanged retry loop is authorized by this report.

The native-07 diagnostic build also retains identical production source with a
console-only production detector probe; its timestamped launcher hash differs
and it is not substituted for native-06 in this layout. Synthetic tests and the
probe are not shipped. Source snapshots now include `.c`, `.h`, `.rc` and
`.manifest`; the exact native source, generated configuration and tool/build
receipts are retained. The accepted code ZIP plus a new launcher/installer
overlay and full supplier materials need final corresponding-source binding;
no existing code ZIP alone certifies this revised candidate's full source.

## Focused validation and release gates

| Check | Result | Scope |
| --- | --- | --- |
| Python packaging/regression tests | PASS | 85 tests, nine modules, isolated workspace TEMP/TMP; no production profile launch |
| Native synthetic tests | PASS | 74 assertions: policy boundaries, Windows argument round trips, owned fixture child lifetimes |
| Actual native launcher PE/dependency/hardening inspection | PASS | Windows system imports only, no CRT libraries; GUI not executed on owner PC |
| Production detector, present host runtime | PASS, bounded | Console-only read-only probe returns READY/0; does not launch app/dialog |
| Exact frozen payload and staged layout | PASS | 559 preserved members, B2 locked importers, no CRT/redist members |
| General frozen bundle legal/feed preflight against current source | FAIL, existing notice drift | THIRD_PARTY_NOTICES.md differs: accepted frozen file predates source-only Microsoft audit headers; preserved, not silently replaced |
| Actual completed Setup build | FAIL | Sharing error 32; no resulting installer |
| Completed installer unpacking and runtime-absence inspection | NOT TESTED/BLOCKED | Inspection cannot run on a nonexistent package |
| Launcher/dialog when runtime absent/outdated and application launch when present | NOT TESTED | No accessible disposable Windows guest; no host runtime manipulation |
| Native shortcuts/post-install, upgrade/repair/rollback/uninstall/data preservation | NOT TESTED | Contracts pass; actual revised installation must be guest-tested |
| Light/Dark, Greek layout, DPI/accessibility/browser/reboot paths | NOT TESTED | Embedded DPI manifest is not a visual acceptance result |
| Complete suite/hosted CI for this dirty checkpoint | NOT RUN | Historical passes are not reassigned to this source |
| New route's Microsoft nonredistribution gate | PENDING | Layout passes, but actual complete package inspection is required |
| Historical bundled §8(b)(ii) | UNRESOLVED | No Microsoft clarification or recipient/distributor agreement clearance |
| Other supplier/source/native/security/final-owner gates | OPEN | Existing independent obligations retained; RELEASE NO-GO |

Initial TEMP-access harness errors and stale English test expectations were
diagnosed and corrected without production data changes or weakened assertions.
An intermediate process-name cleanup idea failed the existing packaging contract
and was replaced by exact owned child handles/Job; the contract remains intact.

## Owner handoff

1. Investigate sharing error 32 using retained compiler logs and the owner-reported
   PUA alert. Read its timestamp, full path, detection and action/status without
   Restore/Allow/exclusions. Do not disable protection or add exclusions without
   explicit approval. Detection alone does not establish malware or a false positive.
   Build one fresh candidate only after a concrete cause/remedy is identified.
2. Read back/unpack that exact completed Setup without executing it, record its
   SHA-256/size, compare all engine/launcher members to the staged manifest and
   reject bundled redist/CRT copies. Only then reassess nonredistribution.
3. Use a disposable snapshot-capable Windows x64 guest with synthetic data. Check
   missing runtime, old runtime, x86-only, malformed/access-denied registry and
   damaged/missing/wrong-machine System32 files **inside the guest only**. Check
   adequate/newer runtime, Recheck after manual Microsoft install, Cancel/close,
   official browser link/offline behavior and reboot-required handling.
4. Verify all three launch entry points, `/NOICONS`, Greek dialog at Windows DPI
   scales including 100/125/150/200%, Light/Dark/accessibility, actual frozen
   functionality/PDF/native paths, exit/forced-stop/updater behavior, clean
   install, accepted-RC2 upgrade/repair/rollback, normal uninstall preserving
   profiles/preferences and explicit full purge of synthetic data. Measure fresh
   and upgrade allocation separately; never infer these results from static tests.
5. Complete security review, exact source/supplier/access binding and final owner
   acceptance before any publication decision. This report authorizes none.

The next separately authorized phase remains **Unified, optimized Master Source
→ verified GitHub/Proton Drive backups → approved workspace cleanup**. Existing
Scenario B inventories predate these new files/outputs and need refreshing in
that phase. No restructuring, backup, upload or cleanup was performed here.
