from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat
import tempfile
from uuid import uuid4
import zipfile

from .invoice_storage import (
    ATTACHMENT_MAX_BYTES, contained_file, managed_name, owned_file, owned_root,
    referenced_names, resolve_file,
)


class ProfileError(RuntimeError):
    pass


@dataclass(frozen=True)
class UserProfile:
    id: str
    name: str
    database_path: Path
    backup_dir: Path
    created_at: str
    color: str = "#3F765B"
    language: str = "el"
    avatar_path: Path | None = None
    has_pin: bool = False
    is_active: bool = False


class ProfileManager:
    """Registry for fully isolated Mastixa data profiles."""

    VERSION = 3
    PACKAGE_VERSION = 2
    DEFAULT_ID = "default"
    DEFAULT_COLORS = (
        "#3F765B", "#476A8A", "#8A5D47", "#73598C", "#8A783F", "#39777A"
    )
    PIN_ROUNDS = 210_000
    PROFILE_DB_MAX_BYTES = 2 * 1024**3
    PROFILE_AVATAR_MAX_BYTES = 20 * 1024**2
    PROFILE_MANIFEST_MAX_BYTES = 64 * 1024
    PROFILE_TOTAL_MAX_BYTES = PROFILE_DB_MAX_BYTES + PROFILE_AVATAR_MAX_BYTES + PROFILE_MANIFEST_MAX_BYTES
    PROFILE_MAX_RATIO = 1000
    PROFILE_RATIO_MIN_BYTES = 1024**2
    # Keep the existing overall archive budget. Attachments additionally have
    # an avatar-sized per-file cap and a finite 256 MiB / 1024-file sub-budget.
    PROFILE_ATTACHMENT_MAX_BYTES = ATTACHMENT_MAX_BYTES
    PROFILE_ATTACHMENTS_MAX_BYTES = 256 * 1024**2
    PROFILE_ATTACHMENT_MAX_COUNT = 1024

    @staticmethod
    def _copy_profile_member(source, output, limit: int) -> int:
        total = 0
        while chunk := source.read(min(65536, limit - total + 1)):
            total += len(chunk)
            if total > limit:
                raise ProfileError("Το περιεχόμενο του πακέτου υπερβαίνει το επιτρεπτό μέγεθος.")
            output.write(chunk)
        return total

    def _validate_profile_archive(self, package) -> None:
        members = package.infolist()
        names = [item.filename for item in members]
        if not 2 <= len(members) <= 3 + self.PROFILE_ATTACHMENT_MAX_COUNT or len({name.casefold() for name in names}) != len(names):
            raise ProfileError("Μη έγκυρος αριθμός ή διπλά αρχεία στο πακέτο.")
        if "manifest.json" not in names or "profile.db" not in names:
            raise ProfileError("Λείπουν απαιτούμενα αρχεία προφίλ.")
        total = attachment_total = attachment_count = avatar_count = 0
        for item in members:
            name = item.filename
            mode = stat.S_IFMT(item.external_attr >> 16)
            attachment = name.startswith("invoice_documents/")
            if attachment:
                try:
                    managed_name(name.removeprefix("invoice_documents/"))
                except ValueError as exc:
                    raise ProfileError("Μη ασφαλές όνομα συνημμένου στο πακέτο.") from exc
                attachment_count += 1
                attachment_total += item.file_size
            avatar = bool(re.fullmatch(r"avatar\.(png|jpg|jpeg|webp|bmp)", name, re.I))
            avatar_count += int(avatar)
            if (name not in {"manifest.json", "profile.db"}
                    and not avatar and not attachment):
                raise ProfileError("Μη αναμενόμενο όνομα αρχείου στο πακέτο.")
            if (mode not in (0, stat.S_IFREG) or item.flag_bits & 1
                    or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ProfileError("Μη υποστηριζόμενο ZIP: απαιτούνται απλά αρχεία με Store/Deflate.")
            limit = (self.PROFILE_MANIFEST_MAX_BYTES if name == "manifest.json" else
                     self.PROFILE_DB_MAX_BYTES if name == "profile.db" else
                     self.PROFILE_ATTACHMENT_MAX_BYTES if attachment else self.PROFILE_AVATAR_MAX_BYTES)
            total += item.file_size
            if (item.file_size > limit or total > self.PROFILE_TOTAL_MAX_BYTES
                    or (item.file_size > self.PROFILE_RATIO_MIN_BYTES
                        and item.file_size > max(1, item.compress_size) * self.PROFILE_MAX_RATIO)):
                raise ProfileError("Το μέγεθος ή η συμπίεση του πακέτου υπερβαίνει τα όρια.")
        if (avatar_count > 1 or attachment_count > self.PROFILE_ATTACHMENT_MAX_COUNT
                or attachment_total > self.PROFILE_ATTACHMENTS_MAX_BYTES):
            raise ProfileError("Υπέρβαση ορίων συνημμένων ή πολλαπλές εικόνες προφίλ.")

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.data_dir = self.base_dir / "data"
        self.profiles_dir = self.data_dir / "profiles"
        self.assets_dir = self.data_dir / "profile_assets"
        self.trash_dir = self.data_dir / "profile_trash"
        self.registry_path = self.data_dir / "profiles.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_registry()

    def profiles(self) -> list[UserProfile]:
        data = self._load()
        active_id = str(data["active_profile_id"])
        result = [
            self._profile_from_record(record, active_id)
            for record in data["profiles"]
        ]
        return sorted(
            result,
            key=lambda profile: (
                not profile.is_active,
                profile.name.casefold(),
                profile.id,
            ),
        )

    @property
    def active_profile(self) -> UserProfile:
        for profile in self.profiles():
            if profile.is_active:
                return profile
        raise ProfileError("Δεν βρέθηκε ενεργό προφίλ.")

    @property
    def ask_on_startup(self) -> bool:
        return bool(self._load().get("ask_on_startup", True))

    def set_ask_on_startup(self, enabled: bool) -> None:
        data = self._load()
        data["ask_on_startup"] = bool(enabled)
        self._save(data)

    def set_language(self, profile_id: str, language: str) -> UserProfile:
        clean_language = self._validate_language(language)
        data = self._load()
        self._record(data, profile_id)["language"] = clean_language
        self._save(data)
        return self.get(profile_id)

    def get(self, profile_id: str) -> UserProfile:
        for profile in self.profiles():
            if profile.id == profile_id:
                return profile
        raise ProfileError("Το επιλεγμένο προφίλ δεν υπάρχει πλέον.")

    def create(self, name: str) -> UserProfile:
        clean_name = self._validate_name(name)
        data = self._load()
        self._assert_unique_name(data, clean_name)
        profile_id = uuid4().hex
        relative_db = Path("profiles") / profile_id / "mastixa_manager.db"
        database_path = self._resolve_data_path(relative_db)
        database_path.parent.mkdir(parents=True, exist_ok=False)
        from .database import Database
        try:
            Database(database_path)
        except Exception as exc:
            shutil.rmtree(database_path.parent, ignore_errors=True)
            raise ProfileError(
                f"Δεν ήταν δυνατή η δημιουργία της βάσης του προφίλ.\n\n{exc}"
            ) from exc
        data["profiles"].append(
            self._new_record(profile_id, clean_name, relative_db, len(data["profiles"]))
        )
        self._save(data)
        return self.get(profile_id)

    def rename(self, profile_id: str, name: str) -> UserProfile:
        clean_name = self._validate_name(name)
        data = self._load()
        self._assert_unique_name(data, clean_name, exclude_id=profile_id)
        self._record(data, profile_id)["name"] = clean_name
        self._save(data)
        return self.get(profile_id)

    def set_active(self, profile_id: str) -> UserProfile:
        data = self._load()
        self._record(data, profile_id)
        data["active_profile_id"] = profile_id
        self._save(data)
        return self.get(profile_id)

    def has_pin(self, profile_id: str) -> bool:
        data = self._load()
        return bool(self._record(data, profile_id).get("pin_hash"))

    def verify_pin(self, profile_id: str, pin: str) -> bool:
        data = self._load()
        record = self._record(data, profile_id)
        stored = str(record.get("pin_hash", ""))
        salt_text = str(record.get("pin_salt", ""))
        if not stored:
            return True
        try:
            salt = bytes.fromhex(salt_text)
        except ValueError:
            return False
        try:
            rounds = int(record.get("pin_rounds", self.PIN_ROUNDS))
        except (TypeError, ValueError):
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256", str(pin).encode("utf-8"), salt, rounds
        ).hex()
        return hmac.compare_digest(stored, computed)

    def set_pin(self, profile_id: str, pin: str) -> UserProfile:
        clean_pin = str(pin).strip()
        if not re.fullmatch(r"\d{4,8}", clean_pin):
            raise ProfileError("Το PIN πρέπει να έχει από 4 έως 8 ψηφία.")
        data = self._load()
        record = self._record(data, profile_id)
        salt = secrets.token_bytes(16)
        record["pin_salt"] = salt.hex()
        record["pin_rounds"] = self.PIN_ROUNDS
        record["pin_hash"] = hashlib.pbkdf2_hmac(
            "sha256", clean_pin.encode("utf-8"), salt, self.PIN_ROUNDS
        ).hex()
        self._save(data)
        return self.get(profile_id)

    def clear_pin(self, profile_id: str) -> UserProfile:
        data = self._load()
        record = self._record(data, profile_id)
        record.pop("pin_salt", None)
        record.pop("pin_hash", None)
        record.pop("pin_rounds", None)
        self._save(data)
        return self.get(profile_id)

    def set_color(self, profile_id: str, color: str) -> UserProfile:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color)):
            raise ProfileError("Μη έγκυρο χρώμα προφίλ.")
        data = self._load()
        self._record(data, profile_id)["color"] = str(color).upper()
        self._save(data)
        return self.get(profile_id)

    def set_avatar(self, profile_id: str, source: Path | None) -> UserProfile:
        data = self._load()
        record = self._record(data, profile_id)
        previous = self._avatar_from_record(record)
        if source is None:
            record.pop("avatar", None)
            self._save(data)
            if previous:
                previous.unlink(missing_ok=True)
            return self.get(profile_id)
        source = Path(source).resolve()
        allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        if not source.is_file() or source.suffix.casefold() not in allowed:
            raise ProfileError("Επίλεξε εικόνα PNG, JPG, WEBP ή BMP.")
        target = self.assets_dir / f"{profile_id}{source.suffix.casefold()}"
        if source != target.resolve():
            shutil.copy2(source, target)
        record["avatar"] = target.relative_to(self.data_dir).as_posix()
        self._save(data)
        if previous and previous != target:
            previous.unlink(missing_ok=True)
        return self.get(profile_id)

    def archive(self, profile_id: str) -> Path:
        """Remove a non-active profile and keep its files recoverable."""
        data = self._load()
        if profile_id == data["active_profile_id"]:
            raise ProfileError("Δεν μπορεί να διαγραφεί το ενεργό προφίλ.")
        record = self._record(data, profile_id)
        if profile_id == self.DEFAULT_ID:
            raise ProfileError("Το κύριο προφίλ δεν μπορεί να διαγραφεί.")
        database_path = self._resolve_data_path(record["database"])
        profile_dir = database_path.parent.resolve()
        if profile_dir.parent != self.profiles_dir.resolve():
            raise ProfileError("Μη ασφαλής διαδρομή αρχείων προφίλ.")
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.trash_dir / f"{profile_id}_{stamp}"
        if profile_dir.exists():
            shutil.move(str(profile_dir), str(target))
        else:
            target.mkdir(parents=True, exist_ok=False)
        avatar = self._avatar_from_record(record)
        if avatar and avatar.exists():
            shutil.move(str(avatar), str(target / avatar.name))
        data["profiles"] = [item for item in data["profiles"] if item["id"] != profile_id]
        self._save(data)
        return target

    def export_profile(self, profile_id: str, destination: Path) -> Path:
        profile = self.get(profile_id)
        destination = Path(destination)
        if destination.suffix.casefold() != ".fieltraprofile":
            destination = destination.with_suffix(".fieltraprofile")
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = self._load()
        record = self._record(data, profile_id)
        manifest = {
            "format": "mastixa-profile",
            "version": self.PACKAGE_VERSION,
            "name": profile.name,
            "created_at": profile.created_at,
            "color": profile.color,
            "language": profile.language,
            "pin_salt": record.get("pin_salt", ""),
            "pin_hash": record.get("pin_hash", ""),
            "pin_rounds": record.get("pin_rounds", self.PIN_ROUNDS),
            "has_avatar": bool(profile.avatar_path),
        }
        staging = None
        try:
            with tempfile.TemporaryDirectory(prefix="mastixa_profile_") as folder:
                snapshot = Path(folder) / "profile.db"
                with closing(sqlite3.connect(str(profile.database_path), timeout=20)) as source, closing(sqlite3.connect(str(snapshot))) as target:
                    source.backup(target)
                references = referenced_names(snapshot)
                if len(references) > self.PROFILE_ATTACHMENT_MAX_COUNT:
                    raise ProfileError("Υπέρβαση ορίου συνημμένων προφίλ.")
                with tempfile.NamedTemporaryFile(
                    prefix=".mastixa-profile-", suffix=".tmp", dir=destination.parent,
                    delete=False,
                ) as prepared:
                    staging = Path(prepared.name)
                with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as package:
                    package.writestr(
                        "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
                    )
                    package.write(snapshot, "profile.db")
                    if profile.avatar_path and profile.avatar_path.is_file():
                        package.write(
                            profile.avatar_path,
                            "avatar" + profile.avatar_path.suffix.casefold(),
                        )
                    attachment_bytes = 0
                    for name in sorted(references):
                        path = resolve_file(profile.database_path, name, self.data_dir / "invoice_documents")
                        if not path.is_file():
                            raise ProfileError(f"Λείπει συνημμένο τιμολογίου: {name}")
                        with path.open("rb") as source, package.open("invoice_documents/" + name, "w") as output:
                            attachment_bytes += self._copy_profile_member(
                                source, output, min(self.PROFILE_ATTACHMENT_MAX_BYTES,
                                    self.PROFILE_ATTACHMENTS_MAX_BYTES - attachment_bytes))
                # Apply the same bounds to exports before replacing a good archive.
                with zipfile.ZipFile(staging) as package:
                    self._validate_profile_archive(package)
                if staging.stat().st_size > self.PROFILE_TOTAL_MAX_BYTES + 1024**2:
                    raise ProfileError("Το αρχείο πακέτου υπερβαίνει το επιτρεπτό μέγεθος.")
                os.replace(staging, destination)
                staging = None
        except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as exc:
            raise ProfileError(f"Η εξαγωγή του προφίλ απέτυχε.\n\n{exc}") from exc
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
        return destination.resolve()

    def import_profile(self, package_path: Path) -> UserProfile:
        package_path = Path(package_path)
        if not package_path.is_file():
            raise ProfileError("Το αρχείο προφίλ δεν βρέθηκε.")
        if package_path.stat().st_size > self.PROFILE_TOTAL_MAX_BYTES + 1024**2:
            raise ProfileError("Το αρχείο πακέτου υπερβαίνει το επιτρεπτό μέγεθος.")
        profile_id = uuid4().hex
        profile_dir = self.profiles_dir / profile_id
        profile_dir_created = False
        avatar_target: Path | None = None
        try:
            with zipfile.ZipFile(package_path, "r") as package:
                self._validate_profile_archive(package)
                names = set(package.namelist())
                if "manifest.json" not in names or "profile.db" not in names:
                    raise ProfileError("Το πακέτο προφίλ δεν είναι έγκυρο.")
                if package.getinfo("manifest.json").file_size > 64 * 1024:
                    raise ProfileError("Το πακέτο προφίλ δεν είναι έγκυρο.")
                manifest_bytes = io.BytesIO()
                with package.open("manifest.json") as source:
                    copied_bytes = self._copy_profile_member(source, manifest_bytes, self.PROFILE_MANIFEST_MAX_BYTES)
                manifest = json.loads(manifest_bytes.getvalue())
                if not isinstance(manifest, dict):
                    raise ProfileError("Το manifest του πακέτου πρέπει να είναι αντικείμενο JSON.")
                try:
                    package_version = int(manifest.get("version", 0))
                    pin_rounds = int(manifest.get("pin_rounds", self.PIN_ROUNDS))
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ProfileError("Μη έγκυρη έκδοση ή παράμετροι PIN στο πακέτο.") from exc
                if (
                    manifest.get("format") != "mastixa-profile"
                    or package_version not in (1, self.PACKAGE_VERSION)
                ):
                    raise ProfileError("Μη υποστηριζόμενη έκδοση πακέτου προφίλ.")
                name = self._validate_name(str(manifest.get("name", "")))
                color = str(manifest.get("color", self.DEFAULT_COLORS[0]))
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                    color = self.DEFAULT_COLORS[0]
                try:
                    language = self._validate_language(
                        str(manifest.get("language", "el"))
                    )
                except ProfileError:
                    language = "el"
                pin_salt = str(manifest.get("pin_salt", ""))
                pin_hash = str(manifest.get("pin_hash", ""))
                if bool(pin_salt) != bool(pin_hash) or (
                    pin_hash and not re.fullmatch(r"[0-9a-f]{64}", pin_hash)
                ) or (pin_salt and not re.fullmatch(r"[0-9a-f]{32}", pin_salt)) or (
                    pin_hash and not 100_000 <= pin_rounds <= 2_000_000
                ):
                    raise ProfileError("Το PIN του πακέτου δεν είναι έγκυρο.")
                profile_dir.mkdir(parents=True, exist_ok=False)
                profile_dir_created = True
                database_path = profile_dir / "mastixa_manager.db"
                with package.open("profile.db") as source, database_path.open("wb") as output:
                    copied_bytes += self._copy_profile_member(source, output,
                        min(self.PROFILE_DB_MAX_BYTES, self.PROFILE_TOTAL_MAX_BYTES - copied_bytes))
                self._validate_sqlite(database_path)
                references = referenced_names(database_path)
                if len(references) > self.PROFILE_ATTACHMENT_MAX_COUNT:
                    raise ProfileError("Υπέρβαση ορίου συνημμένων προφίλ.")
                attachments = {item.removeprefix("invoice_documents/") for item in names
                               if item.startswith("invoice_documents/")}
                if ((package_version == 1 and attachments)
                        or (package_version == 2 and attachments != references)):
                    raise ProfileError("Τα συνημμένα δεν αντιστοιχούν στις αναφορές της βάσης προφίλ.")
                owned_root(database_path).mkdir(parents=True, exist_ok=True)
                attachment_bytes = 0
                for filename in sorted(references):
                    if package_version == 1:
                        legacy = contained_file(self.data_dir / "invoice_documents", filename)
                        if not legacy.is_file():
                            raise ProfileError(f"Λείπει παλαιό συνημμένο τιμολογίου: {filename}")
                        source_context = legacy.open("rb")
                    else:
                        source_context = package.open("invoice_documents/" + filename)
                    with source_context as source, owned_file(database_path, filename).open("xb") as output:
                        size = self._copy_profile_member(source, output, min(
                            self.PROFILE_ATTACHMENT_MAX_BYTES,
                            self.PROFILE_ATTACHMENTS_MAX_BYTES - attachment_bytes,
                            self.PROFILE_TOTAL_MAX_BYTES - copied_bytes))
                        attachment_bytes += size
                        copied_bytes += size
                avatar_name = next(
                    (item for item in names if re.fullmatch(
                        r"avatar\.(png|jpg|jpeg|webp|bmp)", item, re.I
                    )), None
                )
                avatar_relative = ""
                if avatar_name:
                    avatar_target = self.assets_dir / f"{profile_id}{Path(avatar_name).suffix.casefold()}"
                    with package.open(avatar_name) as source, avatar_target.open("wb") as output:
                        copied_bytes += self._copy_profile_member(source, output,
                            min(self.PROFILE_AVATAR_MAX_BYTES, self.PROFILE_TOTAL_MAX_BYTES - copied_bytes))
                    avatar_relative = avatar_target.relative_to(self.data_dir).as_posix()
        except BaseException as exc:
            if profile_dir_created:
                shutil.rmtree(profile_dir, ignore_errors=True)
            if avatar_target:
                avatar_target.unlink(missing_ok=True)
            if isinstance(exc, (OSError, ValueError, zipfile.BadZipFile, sqlite3.Error)):
                raise ProfileError(f"Η εισαγωγή του προφίλ απέτυχε.\n\n{exc}") from exc
            raise
        try:
            data = self._load()
            unique_name = self._unique_import_name(data, name)
            record = self._new_record(
                profile_id,
                unique_name,
                Path("profiles") / profile_id / "mastixa_manager.db",
                len(data["profiles"]),
            )
            record["color"] = color.upper()
            record["language"] = language
            if pin_hash:
                record["pin_salt"] = pin_salt
                record["pin_hash"] = pin_hash
                record["pin_rounds"] = pin_rounds
            if avatar_relative:
                record["avatar"] = avatar_relative
            data["profiles"].append(record)
            self._save(data)
        except BaseException:
            shutil.rmtree(profile_dir, ignore_errors=True)
            if avatar_target:
                avatar_target.unlink(missing_ok=True)
            raise
        return self.get(profile_id)

    def default_backup_dir(self, profile_id: str | None = None) -> Path:
        profile = self.get(profile_id) if profile_id else self.active_profile
        return profile.backup_dir

    @property
    def initial_installation_year(self) -> int | None:
        """Stable installation metadata, shared by profiles and retained on reinstall.

        Unknown legacy dates stay unknown; transaction dates and file timestamps
        are not evidence of when the application was first installed.
        """
        value = self._load().get('initial_installation_year')
        return value if type(value) is int and 1000 <= value <= 9999 else None

    def _installer_year_metadata(self) -> tuple[int | None, str] | None:
        marker = self.data_dir / 'installation-year.json'
        if not marker.exists():
            return None
        try:
            data = json.loads(marker.read_text(encoding='utf-8-sig'))
            year = data['year']
            if data['schema'] == 1 and type(year) is int and 1000 <= year <= 9999:
                return year, 'installer-first-install'
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None, 'unknown-invalid-install-marker'

    @staticmethod
    def _legacy_installation_year(data: dict) -> int | None:
        default = next((record for record in data['profiles']
                        if record['id'] == ProfileManager.DEFAULT_ID), None)
        if default is None:
            return None
        try:
            year = datetime.fromisoformat(default.get('created_at', '')).year
            return year if 1000 <= year <= 9999 else None
        except (ValueError, TypeError):
            return None

    def _ensure_registry(self) -> None:
        if self.registry_path.exists():
            data = self._load()
            changed = data.get("version") != self.VERSION or "ask_on_startup" not in data
            data["version"] = self.VERSION
            data.setdefault("ask_on_startup", True)
            if 'initial_installation_year' not in data:
                marker = self._installer_year_metadata()
                if marker is not None:
                    data['initial_installation_year'], data['initial_installation_year_source'] = marker
                else:
                    data['initial_installation_year'] = self._legacy_installation_year(data)
                    data['initial_installation_year_source'] = (
                        'default-profile-created-at' if data['initial_installation_year'] is not None
                        else 'unknown-legacy')
                changed = True
            for index, record in enumerate(data["profiles"]):
                if "color" not in record:
                    record["color"] = self.DEFAULT_COLORS[index % len(self.DEFAULT_COLORS)]
                    changed = True
                if "language" not in record:
                    record["language"] = "el"
                    changed = True
            if changed:
                self._save(data)
            return
        existing_database = (self.data_dir / 'mastixa_manager.db').exists() or any(self.profiles_dir.rglob('*.db'))
        data = {
            "version": self.VERSION,
            "active_profile_id": self.DEFAULT_ID,
            "ask_on_startup": True,
            "profiles": [self._new_record(
                self.DEFAULT_ID, "Κύριο προφίλ", Path("mastixa_manager.db"), 0
            )],
        }
        marker = self._installer_year_metadata()
        if marker is not None:
            data['initial_installation_year'], data['initial_installation_year_source'] = marker
        else:
            data['initial_installation_year'] = None if existing_database else datetime.now().year
            data['initial_installation_year_source'] = 'unknown-legacy' if existing_database else 'first-application-start'
        self._save(data)

    def _load(self) -> dict:
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"Δεν ήταν δυνατή η ανάγνωση των προφίλ.\n\n{exc}") from exc
        self._validate_registry(data)
        return data

    def _save(self, data: dict) -> None:
        self._validate_registry(data)
        temporary = self.registry_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.registry_path)

    def _validate_registry(self, data: object) -> None:
        if not isinstance(data, dict):
            raise ProfileError("Το αρχείο προφίλ δεν έχει έγκυρη μορφή.")
        profiles = data.get("profiles")
        active_id = data.get("active_profile_id")
        if not isinstance(profiles, list) or not profiles:
            raise ProfileError("Το αρχείο προφίλ δεν περιέχει προφίλ.")
        ids: set[str] = set()
        names: set[str] = set()
        for record in profiles:
            if not isinstance(record, dict):
                raise ProfileError("Βρέθηκε μη έγκυρη εγγραφή προφίλ.")
            profile_id = str(record.get("id", ""))
            name = self._validate_name(str(record.get("name", "")))
            if not re.fullmatch(r"[a-z0-9_-]{1,64}", profile_id):
                raise ProfileError("Βρέθηκε μη έγκυρο αναγνωριστικό προφίλ.")
            if profile_id in ids or name.casefold() in names:
                raise ProfileError("Βρέθηκε διπλό προφίλ.")
            ids.add(profile_id)
            names.add(name.casefold())
            self._resolve_data_path(str(record.get("database", "")))
        if active_id not in ids:
            raise ProfileError("Το ενεργό προφίλ δεν υπάρχει στη λίστα.")

    def _profile_from_record(self, record: dict, active_id: str) -> UserProfile:
        database_path = self._resolve_data_path(record["database"])
        backup_dir = (
            self.base_dir / "backups"
            if record["id"] == self.DEFAULT_ID
            else database_path.parent / "backups"
        )
        return UserProfile(
            id=str(record["id"]),
            name=str(record["name"]),
            database_path=database_path,
            backup_dir=backup_dir,
            created_at=str(record.get("created_at", "")),
            color=str(record.get("color", self.DEFAULT_COLORS[0])),
            language=self._validate_language(str(record.get("language", "el"))),
            avatar_path=self._avatar_from_record(record),
            has_pin=bool(record.get("pin_hash")),
            is_active=str(record["id"]) == active_id,
        )

    def _avatar_from_record(self, record: dict) -> Path | None:
        relative = str(record.get("avatar", "")).strip()
        if not relative:
            return None
        candidate = (self.data_dir / relative).resolve()
        try:
            candidate.relative_to(self.assets_dir.resolve())
        except ValueError as exc:
            raise ProfileError("Μη ασφαλής διαδρομή εικόνας προφίλ.") from exc
        return candidate

    def _resolve_data_path(self, relative: str | Path) -> Path:
        candidate = (self.data_dir / Path(relative)).resolve()
        try:
            candidate.relative_to(self.data_dir.resolve())
        except ValueError as exc:
            raise ProfileError("Μη ασφαλής διαδρομή βάσης προφίλ.") from exc
        if candidate.suffix.casefold() != ".db":
            raise ProfileError("Η βάση του προφίλ πρέπει να είναι αρχείο .db.")
        return candidate

    @staticmethod
    def _validate_name(name: str) -> str:
        clean = " ".join(str(name).split())
        if not clean:
            raise ProfileError("Το όνομα προφίλ δεν μπορεί να είναι κενό.")
        if len(clean) > 60:
            raise ProfileError("Το όνομα προφίλ μπορεί να έχει έως 60 χαρακτήρες.")
        return clean

    @staticmethod
    def _validate_language(language: str) -> str:
        clean = str(language).strip().casefold()
        if not re.fullmatch(r"[a-z]{2,8}", clean):
            raise ProfileError("Μη έγκυρος κωδικός γλώσσας.")
        return clean

    @staticmethod
    def _record(data: dict, profile_id: str) -> dict:
        for record in data["profiles"]:
            if record["id"] == profile_id:
                return record
        raise ProfileError("Το επιλεγμένο προφίλ δεν υπάρχει πλέον.")

    def _new_record(
        self, profile_id: str, name: str, relative_db: Path, color_index: int
    ) -> dict:
        return {
            "id": profile_id,
            "name": name,
            "database": relative_db.as_posix(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "color": self.DEFAULT_COLORS[color_index % len(self.DEFAULT_COLORS)],
            "language": "el",
        }

    @staticmethod
    def _assert_unique_name(
        data: dict, name: str, exclude_id: str | None = None
    ) -> None:
        key = name.casefold()
        for record in data["profiles"]:
            if record["id"] != exclude_id and str(record["name"]).casefold() == key:
                raise ProfileError("Υπάρχει ήδη προφίλ με αυτό το όνομα.")

    def _unique_import_name(self, data: dict, name: str) -> str:
        existing = {str(item["name"]).casefold() for item in data["profiles"]}
        if name.casefold() not in existing:
            return name
        base = self._validate_name(f"{name} (εισαγωγή)")
        candidate = base
        number = 2
        while candidate.casefold() in existing:
            suffix = f" ({number})"
            candidate = base[: 60 - len(suffix)].rstrip() + suffix
            number += 1
        return candidate

    @staticmethod
    def _validate_sqlite(path: Path) -> None:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or str(result[0]).casefold() != "ok":
                raise ProfileError("Η βάση δεδομένων του πακέτου είναι κατεστραμμένη.")
            table_count = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            if table_count < 1:
                raise ProfileError("Το πακέτο δεν περιέχει βάση Fieltra.")
        finally:
            connection.close()
