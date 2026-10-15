# Installer preference preservation

Ordinary uninstall and reinstall preserve the existing
`HKCU\Software\Mastixa\Mastixa Manager` key, including values and subkeys.
The obsolete `[Registry]` creation/deletion entries are removed: source contains
no application dependency on those entries, and its `QSettings` instances use
explicit INI files. Installation and repair neither create this namespace nor
overwrite existing preference values. Application production code is unchanged.

Full purge uses the existing `DeleteUserDataOnUninstall` decision. Explicit
`/PURGEDATA`, or an explicit Yes to the interactive full-removal prompt, deletes
both the preference key (including subkeys) and the existing filesystem user-data
root. Silent uninstall without `/PURGEDATA`, and No/default in the prompt, keep
both. Preference deletion occurs only at `usPostUninstall` in that opt-in branch.
Other Mastixa applications' keys are never recursively deleted. Failed purge
deletion is logged; complete purge is not guaranteed after an access failure.

The pre-fix RC.2 installer has an unconditional preference deletion flag. Its
SHA256 is `ace3c4dbf470e19edbeef0eab62a7121af6890b809b461fe3d5cd778ecf6821e`.
It remains defective and must not be used for preference-preservation validation.
Source changes do not repair that artifact. A separately authorized rebuild in a
new artifact location and subsequent native qualification are required.

`tools/installer_validate.py` replaces the historical private evidence harness.
The failed harness, BSOD evidence and existing artifacts remain unchanged.
The replacement has no registry mutation/rename or preference restoration.
It records read-only recursive snapshots of the existing real preference key,
then compares them before and after each stage and at completion. Differences
record both snapshots and block further stages without automatic restoration or
cleanup. Enumeration errors fail closed instead of looking like empty keys.
Snapshots cover existence, values, types and subkeys, not registry security ACLs.

The normal cycle retains custom `/DIR`, synthetic `MASTIXA_DATA_HOME`, `/NOICONS`,
and bounded TEMP/TMP directories. Existing shortcuts and the production install
are compared read-only. The Start Menu entry explicitly checks `not WizardNoIcons`,
with `AllowNoIcons=yes` so `/NOICONS` sets that state; the desktop shortcut remains
controlled by the separate unchecked `desktopicon` task. The harness records each
shortcut's existence, hash, size and modification timestamp before execution and
both snapshots for every comparison. Any creation/change is a hard stop without
automatic restoration, including when prior shortcut contents are unknown. The harness
requires a fresh evidence output directory outside public source,
no existing installer registration, ordinary-user execution,
an explicit execution opt-in, a reviewed new installer SHA256 and its payload
inventory report. It rejects the known defective installer before registry access
or report writes. Supplying a new expected hash is an identity check, not proof
of the candidate's source provenance; review rebuilt inputs separately. It also
rejects the known shortcut-defective installer SHA256
`50c2291c4d8765dbfb5479a3c17c2b8a909a763236cd45d799b29ebf1c988ce3`.
That artifact remains evidence only; this source fix requires another authorized
rebuild and native qualification.

This real-user preservation cycle never uses `/PURGEDATA`. Native purge testing
requires a separately authorized disposable Windows account/environment; a
post-execution comparison cannot undo destruction and is not permission to risk
existing user state. No execution is authorized by this document.

`tests/test_installer_preference_preservation.py` checks installer source contracts
and snapshot helpers against a synthetic read-only registry. It extracts only
those helper definitions via AST, never imports/runs the harness, accesses the
real registry, or starts installers/uninstallers. These source checks are not
native install/uninstall/reinstall qualification or owner acceptance.
