from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .runtime_paths import BASE_DIR


DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "mastixa_manager.db"

DEFAULT_APP_SETTINGS = {
    "default_sale_source": "pooled",
    "farm_name": "",
    "auto_backup_enabled": "1",
    "auto_backup_keep": "30",
    "pre_restore_keep": "10",
    "backup_dir": "",
}


class _ClosingConnection(sqlite3.Connection):
    """Commit/rollback like sqlite3, then release the Windows file handle."""

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class _Transaction:
    """Explicit connection-bound queries/writes; no commit or nested transaction API."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        return int(self._connection.execute(sql, tuple(params)).lastrowid)

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self._connection.execute(sql, tuple(params)).fetchall())

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self._connection.execute(sql, tuple(params)).fetchone()


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self, *, _read_only_query: bool = False) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, factory=_ClosingConnection)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            if _read_only_query:
                connection.execute('PRAGMA query_only = ON')
            if not _read_only_query and not getattr(self, '_initializing', False):
                from .year_write_policy import install_write_policy
                install_write_policy(connection, self.path)
        except BaseException:
            connection.close()
            raise
        return connection

    @contextmanager
    def transaction(self):
        """One deferred transaction; normal exit commits, any exception rolls back.

        Pass the yielded helper explicitly to subordinate writers. It deliberately
        has no connect/commit/transaction methods; independent Database.execute
        calls keep their existing semantics. _ClosingConnection closes on all exits.
        """
        with self.connect() as connection:
            connection.execute("BEGIN")
            yield _Transaction(connection)

    def initialize(self) -> None:
        self._initializing = True
        try:
            self._initialize_schema()
        finally:
            self._initializing = False

    def _initialize_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS producer (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT NOT NULL DEFAULT '',
            tax_id TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        );

        INSERT OR IGNORE INTO producer(id) VALUES (1);

        CREATE TABLE IF NOT EXISTS fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kaek TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            area_stremma REAL NOT NULL DEFAULT 0,
            productive_trees INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS production (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            field_id INTEGER,
            product TEXT NOT NULL,
            product_id INTEGER,
            quantity_kg REAL NOT NULL CHECK(quantity_kg >= 0),
            notes TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            field_id INTEGER,
            description TEXT NOT NULL,
            partner TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL CHECK(amount >= 0),
            notes TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            field_id INTEGER,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            supplier TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL CHECK(amount >= 0),
            notes TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'kg',
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
        CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

        CREATE TABLE IF NOT EXISTS product_fields (
            product_id INTEGER NOT NULL,
            field_id INTEGER NOT NULL,
            variety TEXT NOT NULL DEFAULT '',
            planting_date TEXT NOT NULL DEFAULT '',
            cultivation_status TEXT NOT NULL DEFAULT 'active'
                CHECK(cultivation_status IN ('active','inactive')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(product_id, field_id),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_product_fields_field
        ON product_fields(field_id);

        CREATE TABLE IF NOT EXISTS migration_flags (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS year_locks (
            year INTEGER PRIMARY KEY,
            is_locked INTEGER NOT NULL DEFAULT 0,
            locked_at TEXT,
            unlocked_at TEXT,
            reason TEXT NOT NULL DEFAULT ''
        );
        """
        with self.connect() as con:
            con.executescript(schema)
            from .gis.store import migrate as migrate_gis
            migrate_gis(con)
            from .gis.sync_repository import migrate as migrate_gis_sync
            migrate_gis_sync(con)
            from .gis.kaek_lookup import migrate as migrate_kaek
            migrate_kaek(con)
            self._remove_connection_and_queue_schema(con)
            self._import_legacy_products(con)
            self._seed_app_settings(con)
            from .sale_source_schema import migrate_sale_sources
            migrate_sale_sources(con)
            con.execute(
                "INSERT OR IGNORE INTO migration_flags(name) VALUES(?)",
                ("app_settings_v1",),
            )
            link_columns = {
                row["name"]
                for row in con.execute("PRAGMA table_info(product_fields)")
            }
            for name, definition in {
                "variety": "TEXT NOT NULL DEFAULT ''",
                "planting_date": "TEXT NOT NULL DEFAULT ''",
                "cultivation_status": "TEXT NOT NULL DEFAULT 'active'",
                # SQLite ALTER TABLE only accepts a constant default.
                "updated_at": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in link_columns:
                    con.execute(
                        f"ALTER TABLE product_fields ADD COLUMN {name} {definition}"
                    )
            columns = {
                row["name"] for row in con.execute("PRAGMA table_info(production)")
            }
            if "product_id" not in columns:
                con.execute("ALTER TABLE production ADD COLUMN product_id INTEGER")
            products = {
                str(row["name"]).strip().casefold(): int(row["id"])
                for row in con.execute("SELECT id,name FROM products")
            }
            for row in con.execute(
                "SELECT id,product,product_id FROM production "
                "WHERE TRIM(COALESCE(product,''))<>''"
            ):
                if (
                    row["product_id"] is not None
                    and con.execute(
                        "SELECT id FROM products WHERE id=?", (row["product_id"],)
                    ).fetchone() is not None
                ):
                    continue
                product_id = products.get(str(row["product"]).strip().casefold())
                if product_id is not None and row["product_id"] != product_id:
                    con.execute(
                        "UPDATE production SET product_id=? WHERE id=?",
                        (product_id, row["id"]),
                    )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_production_product_id "
                "ON production(product_id)"
            )
            migration_name = "product_fields_from_production_v1"
            applied = con.execute(
                "SELECT 1 FROM migration_flags WHERE name=?", (migration_name,)
            ).fetchone()
            if applied is None:
                con.execute(
                    """INSERT OR IGNORE INTO product_fields(product_id,field_id)
                       SELECT DISTINCT product_id,field_id
                       FROM production
                       WHERE product_id IS NOT NULL AND field_id IS NOT NULL
                         AND EXISTS(SELECT 1 FROM products pr WHERE pr.id=production.product_id)
                         AND EXISTS(SELECT 1 FROM fields f WHERE f.id=production.field_id)"""
                )
                con.execute(
                    "INSERT INTO migration_flags(name) VALUES(?)",
                    (migration_name,),
                )

    @staticmethod
    def _import_legacy_products(con: sqlite3.Connection) -> None:
        """Import legacy production names into the product registry."""
        existing = list(con.execute("SELECT id,name FROM products ORDER BY id"))
        names = {
            str(row["name"] or "").strip().casefold()
            for row in existing
            if str(row["name"] or "").strip()
        }
        legacy = list(
            con.execute(
                """SELECT DISTINCT TRIM(product) AS name
                   FROM production
                   WHERE TRIM(COALESCE(product,''))<>''"""
            )
        )
        for row in legacy:
            name = str(row["name"]).strip()
            key = name.casefold()
            if key not in names:
                con.execute(
                    "INSERT INTO products(name,unit,is_active) VALUES(?,?,1)",
                    (name, "kg"),
                )
                names.add(key)

    @staticmethod
    def _remove_connection_and_queue_schema(con: sqlite3.Connection) -> None:
        """Remove the retired product connection and delivery subsystems."""
        con.executescript(
            """
            DROP TRIGGER IF EXISTS product_queue_schedule_after_product;
            DROP TRIGGER IF EXISTS product_connection_settings_after_product;
            DROP TRIGGER IF EXISTS trg_products_create_settings;
            DROP TABLE IF EXISTS product_delivery_queue_events;
            DROP TABLE IF EXISTS product_delivery_queue;
            DROP TABLE IF EXISTS product_sync_items;
            DROP TABLE IF EXISTS product_delivery_history;
            DROP TABLE IF EXISTS product_queue_schedules;
            DROP TABLE IF EXISTS product_send_history;
            DROP TABLE IF EXISTS product_connection_settings;
            DROP TABLE IF EXISTS product_settings;
            DELETE FROM migration_flags
             WHERE name IN ('product_settings_v1',
                            'product_settings_connection_test_v1');
            """
        )

    @staticmethod
    def _seed_app_settings(con: sqlite3.Connection) -> None:
        """Create safe defaults for application-wide settings."""
        con.executemany(
            "INSERT OR IGNORE INTO app_settings(key,value) VALUES(?,?)",
            list(DEFAULT_APP_SETTINGS.items()),
        )

    def get_app_setting(self, key: str, default: str = "") -> str:
        row = self.query_one(
            "SELECT value FROM app_settings WHERE key=?",
            (str(key),),
        )
        if row is None:
            return str(default)
        return str(row["value"] if row["value"] is not None else default)

    def get_app_setting_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get_app_setting(key, "1" if default else "0").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def get_app_setting_int(
        self,
        key: str,
        default: int,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        try:
            value = int(self.get_app_setting(key, str(default)).strip())
        except (TypeError, ValueError):
            value = int(default)
        if minimum is not None:
            value = max(int(minimum), value)
        if maximum is not None:
            value = min(int(maximum), value)
        return value

    def set_app_setting(self, key: str, value: object) -> None:
        self.execute(
            """INSERT INTO app_settings(key,value) VALUES(?,?)
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,
                   updated_at=CURRENT_TIMESTAMP""",
            (str(key), str(value)),
        )

    def save_app_settings(self, values: dict[str, object]) -> None:
        if not values:
            return
        with self.connect() as con:
            con.executemany(
                """INSERT INTO app_settings(key,value) VALUES(?,?)
                   ON CONFLICT(key) DO UPDATE SET
                       value=excluded.value,
                       updated_at=CURRENT_TIMESTAMP""",
                [(str(key), str(value)) for key, value in values.items()],
            )

    def reset_app_settings(self) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM app_settings")
            self._seed_app_settings(con)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self.connect() as con:
            cursor = con.execute(sql, tuple(params))
            con.commit()
            return int(cursor.lastrowid)

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect(_read_only_query=True) as con:
            return list(con.execute(sql, tuple(params)).fetchall())

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connect(_read_only_query=True) as con:
            return con.execute(sql, tuple(params)).fetchone()
