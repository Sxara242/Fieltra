from __future__ import annotations

from datetime import datetime
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

from .app_logging import get_logger


logger = get_logger(__name__)


REQUIRED_TABLES = {
    "producer",
    "fields",
    "production",
    "income",
    "expenses",
}


class BackupError(RuntimeError):
    @classmethod
    def from_template(cls, template: str, **values) -> BackupError:
        """Retain the legacy exception text while exposing owned UI boundaries."""
        values = {key: str(value) for key, value in values.items()}
        error = cls(template.format(**values))
        error.ui_template = template
        error.ui_values = values
        return error


class BackupManager:
    AUTO_PREFIX = "auto_daily"
    AUTO_KEEP = 30
    PRE_RESTORE_PREFIX = "pre_restore"
    PRE_RESTORE_KEEP = 10

    def __init__(
        self,
        database_path: Path,
        backup_dir: Path,
        *,
        auto_keep: int | None = None,
        pre_restore_keep: int | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.backup_dir = Path(backup_dir)
        self.auto_keep = max(
            0,
            int(self.AUTO_KEEP if auto_keep is None else auto_keep),
        )
        self.pre_restore_keep = max(
            0,
            int(
                self.PRE_RESTORE_KEEP
                if pre_restore_keep is None
                else pre_restore_keep
            ),
        )
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def list_backups(self) -> list[Path]:
        backups = [
            path
            for path in self.backup_dir.glob("*.db")
            if path.is_file()
        ]
        return sorted(
            backups,
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def list_auto_backups(self) -> list[Path]:
        return self._matching_backups(self.AUTO_PREFIX)

    def create_backup(self, prefix: str = "fieltra") -> Path:
        """Create a timestamped manual/safety backup."""
        self._ensure_source_exists()

        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Reserve a distinct path even for concurrent/same-second safety snapshots.
        with tempfile.NamedTemporaryFile(
            prefix=f"{prefix}_{stamp}_", suffix=".db", dir=self.backup_dir, delete=False
        ) as reserved:
            target = Path(reserved.name)
        try:
            self._backup_to(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        logger.info("Backup created (kind=%s)", prefix)
        return target

    def create_or_update_daily_backup(self) -> Path:
        """
        Keep one automatic backup per calendar day.

        The same day's file is refreshed when the app starts and again when it
        closes, so it represents the latest clean state for that day.
        """
        self._ensure_source_exists()

        day = datetime.now().strftime("%Y-%m-%d")
        target = self.backup_dir / f"{self.AUTO_PREFIX}_{day}.db"

        self._backup_to(target)
        self.cleanup_automatic_backups()
        logger.info("Automatic daily backup updated")
        return target

    def cleanup_automatic_backups(self) -> int:
        """Keep only the newest AUTO_KEEP automatic daily backups."""
        return self._cleanup_prefix(
            prefix=self.AUTO_PREFIX,
            keep=self.auto_keep,
        )

    def cleanup_pre_restore_backups(self) -> int:
        """Keep only the newest PRE_RESTORE_KEEP pre-restore safety backups."""
        return self._cleanup_prefix(
            prefix=self.PRE_RESTORE_PREFIX,
            keep=self.pre_restore_keep,
        )

    def restore_backup(self, source_path: Path) -> tuple[Path, Path]:
        source_path = Path(source_path)
        logger.info("Backup restore started")

        if not source_path.exists():
            raise BackupError.from_template(
                "Δεν βρέθηκε το αρχείο backup:\n{path}", path=source_path
            )

        # Never restore an invalid or unrelated SQLite file.
        self._validate_database(source_path)

        # Safety snapshot of the current live database before any restore.
        safety_backup = self.create_backup(prefix=self.PRE_RESTORE_PREFIX)

        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Windows may keep the live DB file open. Copy through SQLite's
            # own backup API instead of replacing the file itself.
            self._sqlite_copy(
                source_path=source_path,
                destination_path=self.database_path,
            )

            self._validate_database(self.database_path)

        except Exception as exc:
            logger.exception("Backup restore failed")
            # Best-effort rollback using the same SQLite-safe method.
            try:
                self._sqlite_copy(
                    source_path=safety_backup,
                    destination_path=self.database_path,
                )
            except Exception:
                logger.exception("Backup restore recovery failed; safety snapshot retained")

            raise BackupError.from_template(
                "Η επαναφορά απέτυχε.\n\n{detail}\n\n"
                "Δημιουργήθηκε αντίγραφο ασφαλείας πριν την επαναφορά:\n"
                "{path}", detail=exc, path=safety_backup
            ) from exc

        # Retention must not destroy the input or recovery snapshot mid-restore.
        self._cleanup_prefix(
            self.PRE_RESTORE_PREFIX, self.pre_restore_keep,
            protected=(source_path, safety_backup),
        )
        logger.info("Backup restore completed")
        return source_path, safety_backup

    def _ensure_source_exists(self) -> None:
        if not self.database_path.exists():
            raise BackupError.from_template(
                "Δεν βρέθηκε η βάση δεδομένων:\n{path}", path=self.database_path
            )
        self._validate_database(self.database_path)

    def _backup_to(self, target: Path) -> None:
        """
        Create/update a consistent snapshot using SQLite's backup API.

        It is safe to update an existing daily backup file.
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            with closing(sqlite3.connect(
                self.database_path.resolve().as_uri() + "?mode=ro",
                uri=True,
                timeout=30,
            )) as source, closing(sqlite3.connect(
                target,
                timeout=30,
            )) as destination:
                source.execute("PRAGMA busy_timeout = 30000")
                destination.execute("PRAGMA busy_timeout = 30000")
                source.backup(destination, pages=256, sleep=0.05)
                destination.commit()

        except Exception as exc:
            raise BackupError.from_template(
                "Αποτυχία δημιουργίας backup:\n{detail}", detail=exc
            ) from exc

        self._validate_database(target)

    def _matching_backups(self, prefix: str) -> list[Path]:
        backups = [
            path
            for path in self.backup_dir.glob(f"{prefix}_*.db")
            if path.is_file()
        ]
        return sorted(
            backups,
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _cleanup_prefix(self, prefix: str, keep: int, *, protected: tuple[Path, ...] = ()) -> int:
        if keep < 0:
            keep = 0

        backups = self._matching_backups(prefix)
        deleted = 0

        protected_paths = {path.resolve() for path in protected}
        for path in backups[keep:]:
            if path.resolve() in protected_paths:
                continue
            try:
                path.unlink()
                deleted += 1
            except OSError:
                # Cleanup must never break normal app startup/closing.
                continue

        if deleted:
            logger.info("Expired backups removed (count=%s)", deleted)

        return deleted

    @staticmethod
    def _sqlite_copy(
        source_path: Path,
        destination_path: Path,
    ) -> None:
        """Copy one SQLite database into another without replacing the file."""
        source_path = Path(source_path)
        destination_path = Path(destination_path)

        with closing(sqlite3.connect(
            source_path.resolve().as_uri() + "?mode=ro",
            uri=True,
            timeout=30,
        )) as source, closing(sqlite3.connect(
            destination_path,
            timeout=30,
        )) as destination:
            destination.execute("PRAGMA busy_timeout = 30000")
            source.execute("PRAGMA busy_timeout = 30000")
            source.backup(destination, pages=256, sleep=0.05)
            destination.commit()

    @staticmethod
    def _validate_database(path: Path) -> None:
        con: sqlite3.Connection | None = None
        try:
            con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)

            integrity_row = con.execute("PRAGMA integrity_check").fetchone()
            integrity = integrity_row[0] if integrity_row else ""
            if str(integrity).lower() != "ok":
                raise BackupError.from_template(
                    "Η βάση δεδομένων απέτυχε στον έλεγχο ακεραιότητας:\n"
                    "{path}\n\nΑποτέλεσμα: {detail}", path=path, detail=integrity
                )

            rows = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            tables = {row[0] for row in rows}

            missing = REQUIRED_TABLES - tables
            if missing:
                missing_text = ", ".join(sorted(missing))
                raise BackupError.from_template(
                    "Το αρχείο SQLite δεν φαίνεται να είναι backup του "
                    "Fieltra.\n\n"
                    "Λείπουν πίνακες: {tables}", tables=missing_text
                )
        except BackupError:
            raise
        except sqlite3.Error as exc:
            raise BackupError.from_template(
                "Το αρχείο δεν είναι έγκυρη βάση SQLite:\n{path}\n\n{detail}", path=path, detail=exc
            ) from exc
        finally:
            if con is not None:
                con.close()
