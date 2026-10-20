"""Synthetic-only staged storage and fencing. Never imported by startup.

No filesystem activation is implemented: resolving production/restore paths is a
separate audited integration. A SQLite trigger cannot prevent full-file restore.
SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

from contextlib import contextmanager, closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import NAMESPACE_URL, uuid5, uuid4

from .cadastral_protocol import canonical_uuid, farm_scope

SCHEMA = Path(__file__).resolve().parents[2] / "shared/fixtures/cadastral_schema_v2.sql"
SCHEMA_VERSION = 2


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class StorageRefused(ValueError):
    pass


class GuardedConnection(sqlite3.Connection):
    """Owned isolated connection; no unknown authorizer is replaced. Not a live DB.
    SQL-level authorizer also catches commits via cursors/executescript.
    """
    _guard_active = False
    _guard_internal = False

    def set_authorizer(self, callback):
        raise StorageRefused('The isolated connection owns its authorizer')

    def close(self):
        if self._guard_active:
            raise StorageRefused('Cannot close a guarded transaction')
        super().close()


def connect_synthetic(database, **kwargs):
    if 'factory' in kwargs:
        raise StorageRefused('Isolated connection factory is fixed')
    return sqlite3.connect(database, factory=GuardedConnection, **kwargs)


def validate_store(db: sqlite3.Connection):
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise StorageRefused("Target integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise StorageRefused("Target foreign key check failed")


def create_schema(db: sqlite3.Connection, scope: str, activation: str, source_hash: str):
    """Caller-owned empty synthetic target with a fields(id) fixture table."""
    farm_scope(scope)
    canonical_uuid(activation)
    if db.in_transaction:
        raise StorageRefused("Schema requires an idle isolated connection")
    db.execute("PRAGMA foreign_keys=ON")
    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise StorageRefused("Foreign keys unavailable")
    try:
        db.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA.read_text(encoding="utf-8").replace(
                "FIELD_REFERENCE", "field_identity(field_uuid)").split(";"):
            if statement.strip():
                db.execute(statement)
        db.execute("INSERT INTO farm_configuration VALUES(1,'GR',1,0,0)")
        db.execute("INSERT INTO cadastral_storage_state VALUES(1,2,2,?,?,'PREPARED',0,?,'')",
                   (scope, activation, source_hash))
        install_fence(db)
        db.commit()
    except BaseException:
        db.rollback()
        raise


def _fences(db):
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        if table.startswith('sqlite_') or table == 'cadastral_storage_state':
            continue
        quoted = '"' + table.replace('"', '""') + '"'
        for operation in ('INSERT', 'UPDATE', 'DELETE'):
            name = 'cad_fence_' + digest((table + operation).encode())[:20]
            yield name, (f'CREATE TRIGGER {name} BEFORE {operation} ON {quoted} '
                "WHEN COALESCE((SELECT permit FROM cadastral_storage_state WHERE id=1),0)!=1 "
                "BEGIN SELECT RAISE(ABORT,'cadastral_upgrade_required'); END")
    for operation in ('UPDATE', 'DELETE'):
        name = 'cad_snapshot_' + operation
        yield name, (f'CREATE TRIGGER {name} BEFORE {operation} ON cadastral_snapshots '
                     "BEGIN SELECT RAISE(ABORT,'immutable_source'); END")


def verify_fence(db):
    actual = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
    if any(actual.get(name) != sql for name, sql in _fences(db)):
        raise StorageRefused('Missing or altered write fence requires recovery')


def install_fence(db: sqlite3.Connection):
    """Fence DML on every current table, including copied business tables.

    DDL/raw file replacement are outside this helper's guarantee. The state table
    is controlled only by the supported writer; this is compatibility, not a
    security boundary against arbitrary SQL. Future tables require re-audit.
    """
    actual = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
    for name, sql in _fences(db):
        if name in actual:
            if actual[name] != sql:
                raise StorageRefused('Conflicting write-fence definition')
        else:
            db.execute(sql)


@contextmanager
def guarded_write(db: sqlite3.Connection, scope: str, activation: str):
    """No nesting, no internal commits. Crash rolls back data and temporary permit."""
    if not isinstance(db, GuardedConnection):
        raise StorageRefused('Use an owned connect_synthetic connection')
    if db.in_transaction:
        raise StorageRefused("Nested or independently committing writer")
    db.execute("BEGIN IMMEDIATE")
    try:
        verify_fence(db)
        row = db.execute("SELECT farm_scope,activation_id,schema_version,min_writer,permit FROM cadastral_storage_state WHERE id=1").fetchone()
        if row != (scope, activation, SCHEMA_VERSION, SCHEMA_VERSION, 0):
            raise StorageRefused("Store identity/version/permit mismatch")
        db.execute("UPDATE cadastral_storage_state SET permit=1 WHERE id=1")
        def authorize(operation, first, second, database, trigger):
            if not db._guard_internal and (operation in (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT)
                    or first == 'cadastral_storage_state' and (operation in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_DELETE)
                        or operation == sqlite3.SQLITE_UPDATE and second != 'receipt_hash')):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        # Setting an authorizer invalidates prepared statements, including COMMIT.
        sqlite3.Connection.set_authorizer(db, authorize)
        db._guard_active = True
        yield
        if not db.in_transaction:
            raise StorageRefused("Writer committed independently")
        verify_fence(db)
        db._guard_internal = True
        db.execute("UPDATE cadastral_storage_state SET permit=0 WHERE id=1")
        db.commit()
    except BaseException:
        db._guard_internal = True
        db.rollback()
        raise
    finally:
        db._guard_active = False
        db._guard_internal = False
        sqlite3.Connection.set_authorizer(db, None)


def resolve_activation(expected: dict, legacy_marker: dict | None, target_state: dict | None) -> str:
    """Pure recoverable marker protocol, no fallback and no filesystem mutation."""
    if not target_state:
        return "RECOVERY_REQUIRED"
    if (target_state.get('phase') not in ('PREPARED', 'ACTIVE') or target_state.get('min_writer') != 2
            or target_state.get('schema_version') != 2 or target_state.get('permit') != 0):
        return 'RECOVERY_REQUIRED'
    keys = ("activation_id", "farm_scope", "source_hash", "receipt_hash")
    if any(not expected.get(k) or target_state.get(k) != expected.get(k) for k in keys):
        return "RECOVERY_REQUIRED"
    if not legacy_marker:
        return "PREPARED_REQUIRES_SOURCE_LOCK" if target_state.get("phase") == "PREPARED" else "RESTORE_DETECTED"
    if any(legacy_marker.get(k) != expected.get(k) for k in keys):
        return "RESTORE_DETECTED"
    return "ACTIVE" if target_state.get("phase") == "ACTIVE" else "RECOVER_ACTIVATION"


@dataclass(frozen=True)
class SyntheticField:
    local_id: int
    field_uuid: str
    raw_kaek: str
    aliases: tuple[tuple[str, str, str], ...] = ()
    confirmed_greek: bool = False

    def __post_init__(self):
        canonical_uuid(self.field_uuid)
        if type(self.local_id) is not int or self.local_id < 1 or not isinstance(self.raw_kaek, str) or type(self.confirmed_greek) is not bool:
            raise ValueError('Exact synthetic field key/raw string/confirmation required')
        aliases = tuple(sorted(tuple(a) for a in self.aliases))
        for namespace, dataset, alias in aliases:
            if not isinstance(namespace, str) or not namespace or not isinstance(dataset, str) or not dataset:
                raise ValueError('Explicit alias namespace/dataset required')
            canonical_uuid(alias)
        object.__setattr__(self, 'aliases', aliases)


def prepare_synthetic(source: Path, target: Path, scope: str, fields: tuple[SyntheticField, ...]) -> dict:
    """Copy only a deliberately marked synthetic DB. Existing target is retained.

    Real legacy extraction/classification is deliberately absent. Caller supplies
    verified mappings; incompatible aliases abort the target transaction. No live
    profile discovery, source writes, cleanup, rename or activation occurs.
    """
    from ..country_extensions import IdentifierScope
    from .cadastral_protocol import CadastralParcel, ScopedParcelIdentity, RecordVersion, CultivatedFieldRef, FieldCadastralLink
    from .cadastral_store import CadastralRepository
    farm_scope(scope)
    fields = tuple(sorted(fields, key=lambda f: f.local_id))
    if len({f.local_id for f in fields}) != len(fields) or len({f.field_uuid for f in fields}) != len(fields):
        raise StorageRefused('Duplicate/conflicting synthetic field mapping')
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise StorageRefused("Source and target must be distinct")
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        if src.execute("SELECT farm_scope FROM cadastral_synthetic_input").fetchall() != [(scope,)]:
            raise StorageRefused("Explicit synthetic input marker required")
        src.execute("BEGIN")
        validate_store(src)
        source_hash = digest("\n".join(src.iterdump()).encode())
        plan_hash = digest(canonical([vars(f) for f in fields]).encode())
        activation = str(uuid5(NAMESPACE_URL, scope + source_hash + plan_hash))
        receipt = dict(activation_id=activation, farm_scope=scope, source_hash=source_hash,
                       plan_hash=plan_hash, fields=len(fields), schema_version=2)
        if target.exists():
            # Completed retry is a no-op. Partial stages are retained and refused;
            # explicit recovery must choose another stage rather than overwrite.
            with closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)) as existing:
                validate_store(existing)
                receipt['target_state_hash'] = _migration_state_hash(existing)
                receipt['receipt_hash'] = digest(canonical(receipt).encode())
                row = existing.execute('SELECT farm_scope,activation_id,source_hash,receipt_hash,permit,phase '
                                       'FROM cadastral_storage_state WHERE id=1').fetchone()
                if row != (scope, activation, source_hash, receipt['receipt_hash'], 0, 'PREPARED'):
                    raise StorageRefused('Incomplete or different stage requires explicit recovery')
                _compare_source_tables(src, existing)
                return receipt
        # Exclusive creation protects any pre-existing stage, including a race.
        with target.open("xb"):
            pass
        with closing(connect_synthetic(target)) as dst:
            src.backup(dst)
            create_schema(dst, scope, activation, source_hash)
            repo = CadastralRepository(dst, scope, activation)
            with guarded_write(dst, scope, activation):
                for f in fields:
                    canonical_uuid(f.field_uuid)
                    if dst.execute("SELECT kaek FROM fields WHERE id=?", (f.local_id,)).fetchone() != (f.raw_kaek,):
                        raise StorageRefused("Synthetic field mapping differs from source")
                    dst.execute("INSERT INTO field_identity VALUES(?,?,?,NULL)", (f.field_uuid, f.local_id, str(f.local_id)))
                    for namespace, dataset, alias in f.aliases:
                        canonical_uuid(alias)
                        dst.execute("INSERT INTO field_identity_aliases VALUES(?,?,?,?)", (namespace, dataset, alias, f.field_uuid))
                    raw_payload = canonical(vars(f)).encode()
                    dst.execute("INSERT INTO cadastral_legacy_bindings VALUES('fields',?,?,?, ?,NULL,NULL,'unclassified','synthetic',?)",
                                (str(f.local_id), digest(raw_payload), f.field_uuid, f.raw_kaek, raw_payload))
                # Repository writes own transactions; imported identity preparation
                # finishes first. A failed stage remains PREPARED and is never active.
            for f in fields:
                if not f.confirmed_greek:
                    continue
                from ..country_extensions import GreekIdentifierAdapter, ValidationState
                validation = GreekIdentifierAdapter().validate(f.raw_kaek, IdentifierScope('GR', 'kaek', 'hellenic-cadastre'))
                if validation.state != ValidationState.VALID:
                    with guarded_write(dst, scope, activation):
                        dst.execute("UPDATE cadastral_legacy_bindings SET classification='invalid' WHERE field_uuid=?", (f.field_uuid,))
                    continue
                parcel = CadastralParcel(scope, str(uuid4()),
                    ScopedParcelIdentity(IdentifierScope('GR', 'kaek', 'hellenic-cadastre'), f.raw_kaek),
                    f.raw_kaek, 'gr-kaek-ascii12-v1', RecordVersion(1, 0, 0))
                parcel = repo.ensure_parcel(parcel)
                repo.link(FieldCadastralLink(CultivatedFieldRef(scope, f.field_uuid), parcel.parcel_uuid,
                                            RecordVersion(1, 0, 0), True, False), 0)
                with guarded_write(dst, scope, activation):
                    dst.execute("UPDATE cadastral_legacy_bindings SET classification='confirmed_greek',parcel_uuid=? WHERE field_uuid=?",
                                (parcel.parcel_uuid, f.field_uuid))
            _compare_source_tables(src, dst)
            receipt['target_state_hash'] = _migration_state_hash(dst)
            receipt['receipt_hash'] = digest(canonical(receipt).encode())
            with guarded_write(dst, scope, activation):
                dst.execute("UPDATE cadastral_storage_state SET receipt_hash=? WHERE id=1", (receipt['receipt_hash'],))
            validate_store(dst)
            return receipt


def _compare_source_tables(source, target):
    for (table,) in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        quoted = '"' + table.replace('"', '""') + '"'
        if sorted(source.execute('SELECT * FROM ' + quoted).fetchall(), key=repr) != sorted(
                target.execute('SELECT * FROM ' + quoted).fetchall(), key=repr):
            raise StorageRefused('Source table differs in staged store')


def _migration_state_hash(db):
    tables = ('farm_configuration', 'field_identity', 'field_identity_aliases',
              'cadastral_parcels', 'cadastral_parcel_aliases', 'cadastral_identifier_spellings',
              'field_cadastral_links', 'cadastral_snapshots', 'cadastral_parcel_state',
              'cadastral_legacy_bindings')
    contents = {}
    for table in tables:
        rows = db.execute('SELECT * FROM ' + table).fetchall()
        contents[table] = [[{'bytes': v.hex()} if isinstance(v, bytes) else v for v in row]
                           for row in sorted(rows, key=repr)]
    return digest(canonical(contents).encode())
