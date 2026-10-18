from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from .version import APP_VERSION, RELEASE_CHANNEL, is_newer_version, parse_version


UPDATE_FEED_URL = (
    "https://raw.githubusercontent.com/Sxara242/"
    f"Fieltra/main/updates/{RELEASE_CHANNEL}.json"
)
# Staging is deliberately offline until a reviewed production feed is published.
UPDATE_FEED_MODE = "staging"
STAGING_FEED = Path(__file__).resolve().parents[1] / "updates" / "staging" / f"{RELEASE_CHANNEL}.json"
USER_AGENT = f"Fieltra/{APP_VERSION}"


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateAsset:
    filename: str
    url: str | None
    sha256: str | None


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    channel: str
    release_url: str
    notes: str
    windows: UpdateAsset | None
    android: UpdateAsset | None

    @property
    def is_newer(self) -> bool:
        return is_newer_version(self.version, APP_VERSION)


def _asset(value: Any) -> UpdateAsset | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise UpdateError("Invalid update asset metadata")
    filename = str(value.get("filename") or "").strip()
    if not filename:
        raise UpdateError("Update asset filename is missing")
    url = str(value.get("url") or "").strip() or None
    sha256 = str(value.get("sha256") or "").strip().lower() or None
    if url and not url.startswith("https://"):
        raise UpdateError("Update downloads must use HTTPS")
    if sha256 and (len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256)):
        raise UpdateError("Invalid SHA-256 in update feed")
    if url and not sha256:
        raise UpdateError("A downloadable update must include a SHA-256 checksum")
    return UpdateAsset(filename=filename, url=url, sha256=sha256)


def parse_manifest(payload: bytes | str, *, expected_channel: str | None = None) -> UpdateInfo:
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("The update feed is not valid JSON") from exc

    if not isinstance(data, dict) or data.get("schema") != 1:
        raise UpdateError("Unsupported update feed schema")
    if data.get("product") != "Fieltra":
        raise UpdateError("Update feed belongs to a different product")

    version = str(data.get("version") or "").strip()
    channel = str(data.get("channel") or "").strip().lower()
    release_url = str(data.get("release_url") or "").strip()
    notes = str(data.get("notes") or "").strip()
    if not version or channel not in {"alpha", "beta", "rc", "stable"}:
        raise UpdateError("Update feed version/channel is invalid")
    try:
        parsed = parse_version(version)
    except ValueError as exc:
        raise UpdateError(str(exc)) from exc
    if parsed.channel_rank != {"alpha": 0, "beta": 1, "rc": 2, "stable": 3}[channel]:
        raise UpdateError("Update feed version does not match its channel")
    if expected_channel is not None and channel != expected_channel:
        raise UpdateError("Update feed belongs to a different channel")
    if not release_url.startswith("https://"):
        raise UpdateError("Release page must use HTTPS")

    return UpdateInfo(
        version=version,
        channel=channel,
        release_url=release_url,
        notes=notes,
        windows=_asset(data.get("windows")),
        android=_asset(data.get("android")),
    )


def _project_artifact(info: UpdateInfo) -> UpdateInfo:
    if info.windows and info.windows.url:
        try:
            url = urlsplit(info.windows.url)
            allowed = (url.scheme == "https" and url.hostname == "github.com"
                       and any(url.path.startswith(f"/Sxara242/{repository}/releases/download/")
                               for repository in ("Fieltra", "Mastixa-Manager-Source"))
                       and not url.username and not url.password and url.port in (None, 443))
        except ValueError:
            allowed = False
        if not allowed:
            raise UpdateError("Windows artifacts must use the project GitHub Releases")
    return info


def fetch_update_info(
    feed_url: str | None = None,
    *,
    timeout: float = 8.0,
    opener: Callable[..., Any] = urlopen,
    expected_channel: str | None = None,
) -> UpdateInfo:
    if feed_url is None:
        if UPDATE_FEED_MODE == "staging":
            try:
                return _project_artifact(parse_manifest(STAGING_FEED.read_bytes(), expected_channel=RELEASE_CHANNEL))
            except OSError as exc:
                raise UpdateError(f"Could not read the staging update feed: {exc}") from exc
        feed_url = UPDATE_FEED_URL
        expected_channel = RELEASE_CHANNEL
    if not feed_url.startswith("https://"):
        raise UpdateError("Update feed must use HTTPS")
    request = Request(feed_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener(request, timeout=timeout) as response:
            payload = response.read()
    except Exception as exc:
        raise UpdateError(f"Could not check for updates: {exc}") from exc
    info = parse_manifest(payload, expected_channel=expected_channel)
    return _project_artifact(info) if expected_channel is not None else info


def download_windows_update(
    info: UpdateInfo,
    *,
    destination_dir: Path | None = None,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urlopen,
) -> Path:
    asset = info.windows
    if asset is None or asset.url is None or asset.sha256 is None:
        raise UpdateError("This release does not provide a direct Windows installer download")
    # Validate Windows names even when source verification runs on another OS.
    device = asset.filename.split(".", 1)[0].rstrip(" ").upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³")
    if (Path(asset.filename).name != asset.filename
            or not asset.filename.lower().endswith(".exe")
            or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in asset.filename)
            or device in reserved):
        raise UpdateError("Unsafe Windows installer filename in update feed")

    root = destination_dir or (Path(tempfile.gettempdir()) / "Fieltra-updates")
    root.mkdir(parents=True, exist_ok=True)
    target = root / asset.filename
    partial = target.with_suffix(target.suffix + ".part")

    request = Request(asset.url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    try:
        with opener(request, timeout=timeout) as response, partial.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"Could not download the update: {exc}") from exc

    actual = digest.hexdigest().lower()
    if actual != asset.sha256.lower():
        partial.unlink(missing_ok=True)
        raise UpdateError("Downloaded installer failed SHA-256 verification")

    partial.replace(target)
    return target


def launch_windows_installer(installer: Path) -> None:
    installer = installer.resolve()
    if not installer.is_file() or installer.suffix.lower() != ".exe":
        raise UpdateError("Installer file is missing or invalid")
    try:
        subprocess.Popen([str(installer)], close_fds=True)
    except OSError as exc:
        raise UpdateError(f"Could not launch the installer: {exc}") from exc
