from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


APP_DATA_FOLDER = "Fieltra"
DATA_HOME_ENV = "MASTIXA_DATA_HOME"


def resolve_base_dir(
    *,
    frozen: bool | None = None,
    environ: Mapping[str, str] | None = None,
    module_file: str | Path = __file__,
) -> Path:
    """Return the writable root used for databases, profiles, backups and logs.

    Source and packaged builds use the clean Fieltra LocalAppData namespace.
    Developer Mastixa data is never discovered or migrated automatically.
    ``MASTIXA_DATA_HOME`` is an explicit override used by diagnostics and
    packaged smoke tests.
    """
    values = os.environ if environ is None else environ
    override = str(values.get(DATA_HOME_ENV, "")).strip()
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = str(values.get("LOCALAPPDATA", "")).strip()
    if local_app_data:
        return (Path(local_app_data) / APP_DATA_FOLDER).resolve()
    return (Path.home() / "AppData" / "Local" / APP_DATA_FOLDER).resolve()


BASE_DIR = resolve_base_dir()
