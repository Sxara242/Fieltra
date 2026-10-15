from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from .database import Database


ACTIVE_WORKING_YEAR_KEY: Final[str] = "active_working_year"
MIN_YEAR: Final[int] = 1000
MAX_YEAR: Final[int] = 9999


@dataclass(frozen=True)
class YearCorrectionState:
    year: int
    active_year: int
    reason: str


_CORRECTIONS: dict[str, YearCorrectionState] = {}


def _db_key(db: Database) -> str:
    try:
        return str(Path(db.path).resolve())
    except (OSError, RuntimeError):
        return str(db.path)


def _validate_year(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Το έτος πρέπει να είναι ακέραιος αριθμός.")
    try:
        year = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Το έτος πρέπει να είναι ακέραιος αριθμός.") from exc
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"Το έτος πρέπει να είναι μεταξύ {MIN_YEAR} και {MAX_YEAR}.")
    return year


def _ensure_year_lock_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS year_locks (
            year INTEGER PRIMARY KEY,
            is_locked INTEGER NOT NULL DEFAULT 0,
            locked_at TEXT,
            unlocked_at TEXT,
            reason TEXT NOT NULL DEFAULT ''
        )
        """
    )


def _audit(db: Database, year: int, details: str) -> None:
    exists = db.query_one(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_events'"
    )
    if exists is None:
        return
    db.execute(
        """
        INSERT INTO audit_events(event_time,table_name,action,record_id,details)
        VALUES(datetime('now','localtime'),'year_context','UPDATE',?,?)
        """,
        (str(year), str(details)),
    )


def active_working_year(db: Database) -> int:
    current = QDate.currentDate().year()
    raw = db.get_app_setting(ACTIVE_WORKING_YEAR_KEY, "").strip()
    if not raw:
        db.set_app_setting(ACTIVE_WORKING_YEAR_KEY, str(current))
        return current
    try:
        return _validate_year(raw)
    except ValueError:
        db.set_app_setting(ACTIVE_WORKING_YEAR_KEY, str(current))
        return current


def set_active_working_year(
    db: Database,
    year: int,
    *,
    audit: bool = True,
) -> int:
    value = _validate_year(year)
    previous = active_working_year(db)
    db.set_app_setting(ACTIVE_WORKING_YEAR_KEY, str(value))
    if audit and previous != value:
        _audit(
            db,
            value,
            f"Αλλαγή ενεργού έτους εργασίας: {previous} -> {value}",
        )
    sync_application_year_context(db)
    return value


def correction_state(db: Database) -> YearCorrectionState | None:
    return _CORRECTIONS.get(_db_key(db))


def is_correction_year(db: Database, year: int) -> bool:
    state = correction_state(db)
    return state is not None and state.year == int(year)


def is_year_physically_locked(db: Database, year: int) -> bool:
    # A read/validation must not migrate the database. Lock writers create the
    # table explicitly; a legacy database without it has no physical locks.
    if db.query_one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='year_locks'") is None:
        return False
    row = db.query_one(
        "SELECT is_locked FROM year_locks WHERE year=?",
        (int(year),),
    )
    return bool(row and int(row["is_locked"] or 0) == 1)


def is_year_write_blocked(db: Database, year: int) -> bool:
    """Return the effective write lock while preserving the physical lock row.

    A correction session makes exactly one physically locked year writable for
    the lifetime of the current process. The year_locks row remains locked, so
    a crash/restart returns to the safe locked state automatically.
    """

    value = int(year)
    return is_year_physically_locked(db, value) and not is_correction_year(db, value)


def require_writable_years(db: Database, years) -> None:
    """Store-level guard for annual workflows without a page save guard."""
    from .localized_messages import _text
    for year in sorted(set(int(value) for value in years)):
        if is_year_write_blocked(db, year):
            raise ValueError(_text(
                "Το έτος {year} είναι κλειδωμένο — Μόνο προβολή.\n\n"
                "Για αλλαγές: Ασφάλεια → Κλείδωμα Έτους → Προσωρινή διόρθωση.", year=year))


def begin_year_correction(db: Database, year: int, reason: str) -> YearCorrectionState:
    value = _validate_year(year)
    note = str(reason or "").strip()
    if not note:
        raise ValueError("Χρειάζεται αιτιολογία για την προσωρινή διόρθωση.")
    if not is_year_physically_locked(db, value):
        raise ValueError("Η προσωρινή διόρθωση επιτρέπεται μόνο σε κλειδωμένο έτος.")

    key = _db_key(db)
    existing = _CORRECTIONS.get(key)
    if existing is not None and existing.year != value:
        raise ValueError(
            f"Υπάρχει ήδη προσωρινή επεξεργασία για το έτος {existing.year}."
        )
    if existing is not None:
        return existing

    state = YearCorrectionState(
        year=value,
        active_year=active_working_year(db),
        reason=note,
    )
    _CORRECTIONS[key] = state
    _audit(
        db,
        value,
        f"Έναρξη προσωρινής διόρθωσης κλειδωμένου έτους {value} | Αιτιολογία: {note}",
    )
    sync_application_year_context(db)
    return state


def finish_year_correction(
    db: Database,
    *,
    outcome: str = "Ολοκλήρωση διορθώσεων & επανακλείδωμα",
    stay_on_year: bool = False,
) -> YearCorrectionState | None:
    key = _db_key(db)
    state = _CORRECTIONS.pop(key, None)
    if state is None:
        sync_application_year_context(db)
        return None
    _audit(
        db,
        state.year,
        f"{outcome}: έτος {state.year} | Αιτιολογία: {state.reason}",
    )
    if stay_on_year:
        set_active_working_year(db, state.year)
    sync_application_year_context(db)
    return state


def audit_correction_action(db: Database, action_text: str) -> None:
    state = correction_state(db)
    if state is None:
        return
    label = str(action_text or "").strip() or "Ενέργεια"
    _audit(
        db,
        state.year,
        f"Επιβεβαίωση ενέργειας σε προσωρινή διόρθωση: {label} | "
        f"Αιτιολογία: {state.reason}",
    )


def effective_working_year(db: Database) -> int:
    state = correction_state(db)
    return state.year if state is not None else active_working_year(db)


def sync_application_year_context(db: Database) -> None:
    app = QApplication.instance()
    if app is None:
        return
    active = active_working_year(db)
    state = correction_state(db)
    app.setProperty("mastixaActiveWorkingYear", active)
    app.setProperty("mastixaEffectiveWorkingYear", state.year if state else active)
    app.setProperty("mastixaCorrectionYear", state.year if state else -1)
    app.setProperty("mastixaCorrectionReason", state.reason if state else "")


def initialize_year_context(db: Database, *, reset_temporary: bool = True) -> int:
    if reset_temporary:
        _CORRECTIONS.pop(_db_key(db), None)
    year = active_working_year(db)
    sync_application_year_context(db)
    return year


def qdate_in_year(year: int, source: QDate | None = None) -> QDate:
    value = _validate_year(year)
    base = source if source is not None and source.isValid() else QDate.currentDate()
    month = base.month()
    day = base.day()
    first = QDate(value, month, 1)
    if not first.isValid():
        return QDate(value, 1, 1)
    return QDate(value, month, min(day, first.daysInMonth()))


def working_context_date(db: Database | None = None) -> QDate:
    if db is not None:
        return qdate_in_year(effective_working_year(db))
    app = QApplication.instance()
    if app is None:
        return QDate.currentDate()
    raw = app.property("mastixaEffectiveWorkingYear")
    try:
        year = _validate_year(raw)
    except ValueError:
        year = QDate.currentDate().year()
    return qdate_in_year(year, QDate.currentDate())


def permanently_unlock_year(db: Database, year: int, reason: str) -> bool:
    """Require an auditable reason; never confuse this with session correction."""
    value = _validate_year(year)
    note = str(reason or "")
    if not note.strip():
        raise ValueError("Συμπλήρωσε αιτία ενέργειας.")
    if correction_state(db) is not None:
        raise ValueError("Ολοκλήρωσε πρώτα την προσωρινή διόρθωση πριν κάνεις μόνιμο ξεκλείδωμα.")
    if not is_year_physically_locked(db, value):
        return False
    with db.transaction() as tx:
        tx.execute("UPDATE year_locks SET is_locked=0, unlocked_at=CURRENT_TIMESTAMP WHERE year=?", (value,))
        _audit(tx, value, f"Μόνιμο ξεκλείδωμα έτους {value} | Αιτιολογία: {note}")
    return True
