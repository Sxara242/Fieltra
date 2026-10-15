# Fieltra

**Farm Management** · **Version 1.0.0 Stable**

Fieltra is free, open-source, offline-first farm management software for Windows.
It helps farmers and farm managers organize fields, production, inventory,
income and expenses while keeping operational data on their own computer.
No cloud account is required. Optional online maps require your selection.

**[Download Fieltra v1.0.0 for Windows](https://github.com/Sxara242/Fieltra/releases/tag/v1.0.0)**

## What you can do

- Organize farm profiles and fields, with GIS tools and optional map access.
- Record production, sales, income and expenses.
- Track inventory and equipment records.
- Create reports and export PDF or spreadsheet files.
- Keep local backups and transfer profile packages.

Your farm records are stored locally. You control your data and backups.
Android is under development and is not part of this Windows v1.0.0 release.

## Install on Windows

Requirements: **Windows 10 or Windows 11, x64**, and the Microsoft Visual C++
Redistributable **x64 14.51.36247.0 or newer**. Obtain the runtime independently
from [Microsoft](https://aka.ms/vc14/vc_redist.x64.exe); Fieltra does not bundle it.
An internet connection is needed to download these files and for optional online
maps; ordinary farm-record management works offline.

1. Download [Fieltra-1.0.0-Setup.exe](https://github.com/Sxara242/Fieltra/releases/download/v1.0.0/Fieltra-1.0.0-Setup.exe)
   from the official Release and verify its checksum below.
2. Install Microsoft's x64 runtime if needed, then run Fieltra Setup.
3. Open **Fieltra** from the Start Menu or optional desktop shortcut. If the
   runtime is missing or too old, the launcher offers Download, Recheck and Cancel.

The installer is **54,347,611 bytes**, with SHA-256:

```text
b4f0efebb54dac65735761d5dbf0197e5529252be13a1f279d95c26178cfee56
```

Fieltra installs per user and stores data/settings in `%LOCALAPPDATA%\Fieltra`.
Normal uninstall preserves your data; full removal requires an explicit purge
choice. See [installation details](docs/INSTALLATION.md).

## Free and open-source

First-party code is licensed under **AGPL-3.0-only**. See [LICENSE](LICENSE),
[licensing scope](docs/LICENSING.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
Historical Mastixa Manager copyright and all third-party attributions are retained.

The [v1.0.0 source tag](https://github.com/Sxara242/Fieltra/tree/v1.0.0) identifies
the corresponding application, native-launcher and installer source. The Release
also supplies **both** required dependency/source companion archives:

- [Dependency sources, selected build materials and notices](https://github.com/Sxara242/Fieltra/releases/download/v1.0.0/MastixaManager-1.0.0-rc.2-repack-source.zip).
- [Complete QtPdf/PDFium source carrier](https://github.com/Sxara242/Fieltra/releases/download/v1.0.0/qtwebengine-everywhere-src-6.11.2.tar.xz).

The companion's historical filename is retained to preserve its verified identity.
Use the Fieltra source tag for application code; the older application ZIPs inside
the companion describe historical builds. [Release/source materials](docs/FIELTRA_V1_RELEASE.md)
provide all archive hashes, source correspondence and library replacement guidance.

## Build from source

For Python source development, use Python 3.14 in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c requirements-windows-rc.txt
.\.venv\Scripts\python.exe main.py
```

[BUILDING.md](docs/BUILDING.md) documents the pinned release inputs and native
build controls. Release reconstruction uses the qualified CPython 3.14.8 suppliers
and locked dependencies; it is distinct from a development environment.
The internal `MASTIXA_DATA_HOME` override can select a synthetic development
profile. Internal module and recipe names may retain historical identifiers.

## Contribute

Bug reports and discussion are welcome. Use synthetic examples and exclude
personal records, credentials and private exports. External code contributions
require an executed rights grant before merge; see [CONTRIBUTING.md](CONTRIBUTING.md).
