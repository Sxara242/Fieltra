# Mastixa Manager public development

- This repository, Sxara242/Mastixa-Manager-Source, is the primary active source
  repository for rc.2 and later. Make future source/tests/docs/PR/CI changes here.
- The private Mastixa-Manager repository and existing private local checkouts are
  protected archives. Never alter their work or history, copy/merge private Git
  ancestry, import private refs, or use them for normal development without an
  explicit owner request.
- Preserve uncommitted work. Do not reset, clean, discard, force-push or rewrite.
- Use terminal/CLI/direct files only on the owner's PC. Do not invoke computer
  control, visual automation or virtual mouse/keyboard input. Required GUI steps
  must be performed manually by the owner.
- Windows x64 is the current release target. Android remains in development.
  rc.1 is immutable historical evidence. rc.2 is unbuilt/unqualified until its
  actual candidate passes release gates and explicit owner acceptance.
- Keep profiles, databases, backups, logs, dumps, local configuration, credentials,
  keys and private artifacts out of public source. Use synthetic fixtures. Run
  tools/audit_public_source.py and secret scanning before publication; reviewed
  binary inputs must match docs/public-binary-inputs.json.
- First-party material is AGPL-3.0-only. Preserve third-party notices, EPSG/PROJ
  terms and covered-source/replacement requirements. Follow CONTRIBUTING.md and
  docs/CONTRIBUTION_RIGHTS.md; do not merge external contributions without an
  executed grant supporting AGPL and separate commercial licensing.
- CI must use only ubuntu-latest/windows-latest. Normal push/PR runs do not
  generate installers. Optional manual artifacts have one-day retention.
- Diagnose failures in isolated processes and run affected tests plus appropriate
  complete validation. Do not conceal failures with skips, xfails or weaker
  assertions. Validate diffs and report evidence-based release conclusions.

## Windows validation safety — live user state

- Validation, packaging, installer, migration and recovery tests must not rename,
  move, delete, overwrite or otherwise mutate the owner's real Mastixa preferences
  or registry state merely to isolate a test.
- Do not use RegRenameKey, NtRenameKey, `reg rename`, ctypes registry rename calls
  or equivalent live-profile rename workarounds.
- Prefer synthetic data homes (`MASTIXA_DATA_HOME`), temporary test registry
  namespaces, isolated directories or read-only before/after snapshots.
- Normal uninstall must preserve preferences and user data. Destructive cleanup
  requires the explicit project purge mechanism (`/PURGEDATA` or explicit Yes to
  full removal), with dedicated tests; it must never be a test-isolation shortcut.
- If safe isolation requires mutating real user state, STOP and report the blocker.
  Do not invent a mutation-based workaround.
- Never intentionally reproduce a known BSOD-triggering validation path.
- Known-defective installer artifacts with identified hashes must not be reused
  for qualification; preserve them only as evidence.
