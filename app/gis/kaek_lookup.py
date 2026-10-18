"""Local KAEK queue and transport-neutral wire format. No device transport."""
from __future__ import annotations

import json
import time
import uuid
from datetime import date
from urllib.parse import urlsplit

from .geometry import normalize
from .sync_contract import canonical, fingerprint

ANDROID_KAEK_SYNC_ENABLED = False
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024
MAX_ATTEMPTS = 6  # Legacy limit; retained only to recognize old persisted jobs.
LEASE_MS = 300_000
MAX_BACKOFF_MS = 3_600_000
REQUEST_KEYS = {"schema", "kind", "dataset_id", "field_id", "job_id", "request_id", "kaek", "requested_at"}
RESULT_KEYS = (REQUEST_KEYS - {"kind"}) | {
    "kind", "geometry", "source_crs", "provider", "source_url", "terms_url",
    "attribution", "source_date", "retrieved_at",
}


class StaleLookup(ValueError):
    pass


class LookupConflict(ValueError):
    pass


def valid_kaek(value):
    return isinstance(value, str) and len(value) == 12 and value.isascii() and value.isdigit()


def validate_payload(value):
    # Copy through the established canonical format; reject NaN/oversized input.
    encoded = canonical(value)
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("KAEK payload exceeds 4 MB")
    value = json.loads(encoded)
    if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1:
        raise ValueError("Unknown KAEK schema")
    kind = value.get("kind")
    keys = REQUEST_KEYS if kind == "kaek-request" else RESULT_KEYS if kind == "kaek-result" else set()
    if not keys or set(value) != keys:
        raise ValueError("Unknown KAEK payload fields/kind")
    for key in ("dataset_id", "field_id", "job_id", "request_id"):
        if not isinstance(value[key], str) or str(uuid.UUID(value[key])) != value[key]:
            raise ValueError("Canonical UUID required")
    if not valid_kaek(value["kaek"]):
        raise ValueError("12 ASCII digit KAEK required")
    if type(value["requested_at"]) is not int or value["requested_at"] < 0:
        raise ValueError("Invalid request time")
    if kind == "kaek-result":
        if (type(value["retrieved_at"]) is not int
                or value["retrieved_at"] < value["requested_at"]):
            raise ValueError("Invalid retrieval time")
        for key in ("provider", "attribution"):
            if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 1000:
                raise ValueError("Missing provenance")
        for key in ("source_url", "terms_url"):
            if not isinstance(value[key], str):
                raise ValueError("HTTPS provenance URL required")
            url = urlsplit(value[key])
            if url.scheme != "https" or not url.hostname or url.username or url.password or len(value[key]) > 2048:
                raise ValueError("HTTPS provenance URL required")
        if not isinstance(value["source_date"], str):
            raise ValueError("Invalid source date")
        if value['source_date']:
            date.fromisoformat(value['source_date'])
        if value["source_crs"] not in ("EPSG:2100", "EPSG:4326"):
            raise ValueError("Unsupported cadastral CRS")
        geometry = normalize(value["geometry"], value["source_crs"])
        west, south, east, north = geometry.bbox
        if not (19 <= west <= east <= 30 and 34 <= south <= north <= 42.5 and geometry.area_m2 < 1e9):
            raise ValueError("Cadastral geometry outside supported Greek extent/size")
    return value


def serialize(value):
    return canonical(validate_payload(value))


def deserialize(text):
    if not isinstance(text, (str, bytes)) or len(text.encode("utf-8") if isinstance(text, str) else text) > MAX_PAYLOAD_BYTES:
        raise ValueError("Invalid KAEK payload size")

    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out

    return validate_payload(json.loads(text, object_pairs_hook=unique))


def apply_device_result(*args, **kwargs):
    # Future authenticated transport must be implemented before opening this boundary.
    raise PermissionError("Windows–Android KAEK sync is disabled in v1.0.1")


def migrate(con):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS kaek_field_identity(
            field_id INTEGER PRIMARY KEY REFERENCES fields(id) ON DELETE CASCADE,
            field_uuid TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS kaek_lookup_jobs(
            job_id TEXT PRIMARY KEY, field_uuid TEXT NOT NULL UNIQUE
                REFERENCES kaek_field_identity(field_uuid) ON DELETE CASCADE,
            kaek TEXT NOT NULL, provider TEXT NOT NULL, status TEXT NOT NULL,
            requested_at INTEGER NOT NULL, request_id TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, next_attempt INTEGER NOT NULL DEFAULT 0,
            lease_until INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '',
            result_hash TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS cadastral_geometry(
            field_uuid TEXT PRIMARY KEY REFERENCES kaek_field_identity(field_uuid) ON DELETE CASCADE,
            kaek TEXT NOT NULL, job_id TEXT NOT NULL, result_json TEXT NOT NULL,
            result_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cadastral_details(
            field_uuid TEXT PRIMARY KEY REFERENCES kaek_field_identity(field_uuid) ON DELETE CASCADE,
            result_hash TEXT NOT NULL, details_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agricultural_toponyms(
            field_uuid TEXT PRIMARY KEY REFERENCES kaek_field_identity(field_uuid) ON DELETE CASCADE,
            kaek TEXT NOT NULL, candidate_json TEXT NOT NULL DEFAULT '{}',
            confirmed_name TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT 'unspecified',
            updated_at INTEGER NOT NULL);
        CREATE TRIGGER IF NOT EXISTS kaek_invalidate_changed_identifier
        AFTER UPDATE OF kaek ON fields WHEN NEW.kaek IS NOT OLD.kaek
        BEGIN
            DELETE FROM kaek_lookup_jobs WHERE field_uuid IN
                (SELECT field_uuid FROM kaek_field_identity WHERE field_id=NEW.id);
        END;
        INSERT OR IGNORE INTO migration_flags(name) VALUES('kaek_lookup_v1');
    """)
    con.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('kaek_dataset_uuid',?)", (str(uuid.uuid4()),))
    for row in con.execute("SELECT id FROM fields WHERE id NOT IN (SELECT field_id FROM kaek_field_identity)").fetchall():
        con.execute("INSERT INTO kaek_field_identity VALUES(?,?)", (row[0], str(uuid.uuid4())))


class LookupStore:
    def __init__(self, db, clock=None):
        self.db = db
        self.clock = clock or (lambda: time.time_ns() // 1_000_000)

    def enqueue(self, field_id, provider):
        """Idempotent per current field/KAEK; only the caller's local field is used."""
        with self.db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT kaek FROM fields WHERE id=?", (field_id,)).fetchone()
            if row is None:
                raise StaleLookup("Field was deleted")
            con.execute("INSERT OR IGNORE INTO kaek_field_identity VALUES(?,?)", (field_id, str(uuid.uuid4())))
            identity = con.execute("SELECT field_uuid FROM kaek_field_identity WHERE field_id=?", (field_id,)).fetchone()[0]
            if not valid_kaek(row["kaek"]):
                con.execute("DELETE FROM kaek_lookup_jobs WHERE field_uuid=?", (identity,))
                return None
            existing = con.execute("SELECT * FROM kaek_lookup_jobs WHERE field_uuid=?", (identity,)).fetchone()
            if existing and existing["kaek"] == row["kaek"]:
                return dict(existing)
            supported = provider is not None and provider.supports(row["kaek"])
            status = "pending" if supported else "unavailable"
            reason = "" if supported else "unsupported_region" if provider is not None else "provider_unavailable"
            con.execute("INSERT INTO kaek_lookup_jobs(job_id,field_uuid,kaek,provider,status,requested_at,request_id,reason) VALUES(?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), identity, row["kaek"], provider.identity if provider else "", status, self.clock(), str(uuid.uuid4()), reason))
            return dict(con.execute("SELECT * FROM kaek_lookup_jobs WHERE field_uuid=?", (identity,)).fetchone())

    def job(self, field_id):
        row = self.db.query_one("SELECT j.* FROM kaek_lookup_jobs j JOIN kaek_field_identity f USING(field_uuid) WHERE f.field_id=?", (field_id,))
        return dict(row) if row else None

    def request(self, job):
        dataset = self.db.query_one("SELECT value FROM app_settings WHERE key='kaek_dataset_uuid'")[0]
        return validate_payload(dict(schema=1, kind="kaek-request", dataset_id=dataset,
                                     field_id=job["field_uuid"], job_id=job["job_id"],
                                     request_id=job["request_id"], kaek=job["kaek"], requested_at=job["requested_at"]))

    def claim(self, provider):
        if provider is None:
            return None
        now = self.clock()
        with self.db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            # Upgrade stranded legacy outage jobs without changing permanent
            # unsupported/not-in-snapshot decisions or resetting attempt history.
            con.execute("UPDATE kaek_lookup_jobs SET status='temporary_failure',reason='offline_or_timeout',lease_until=0 WHERE status='unavailable' AND reason='retry_limit'")
            row = con.execute("""SELECT j.* FROM kaek_lookup_jobs j
                JOIN kaek_field_identity i USING(field_uuid) JOIN fields f ON f.id=i.field_id
                WHERE j.provider=? AND j.kaek=f.kaek
                  AND ((j.status IN ('pending','temporary_failure') AND j.next_attempt<=?)
                    OR (j.status='retrieving' AND j.lease_until<=?))
                ORDER BY j.next_attempt,j.requested_at,j.job_id LIMIT 1""", (provider.identity, now, now)).fetchone()
            if row is None:
                return None
            con.execute("UPDATE kaek_lookup_jobs SET status='retrieving',attempts=attempts+1,lease_until=?,request_id=?,reason='' WHERE job_id=?",
                        (now + LEASE_MS, str(uuid.uuid4()), row["job_id"]))
            job = dict(con.execute("SELECT * FROM kaek_lookup_jobs WHERE job_id=?", (row["job_id"],)).fetchone())
        return self.request(job)

    def fail(self, request, reason, temporary=True):
        now = self.clock()
        with self.db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            job = con.execute("SELECT * FROM kaek_lookup_jobs WHERE job_id=? AND request_id=? AND status='retrieving'",
                              (request["job_id"], request["request_id"])).fetchone()
            if job is None:
                return
            retry = temporary
            delay = min(30_000 * 2 ** min(max(job['attempts']-1, 0), 7), MAX_BACKOFF_MS)
            con.execute("UPDATE kaek_lookup_jobs SET status=?,reason=?,next_attempt=?,lease_until=0 WHERE job_id=?",
                        ("temporary_failure" if retry else "unavailable", reason, now + delay, request["job_id"]))

    def connectivity_restored(self):
        """OS connectivity signal can expedite only temporary outage jobs."""
        self.db.execute("""UPDATE kaek_lookup_jobs SET next_attempt=?
            WHERE status='temporary_failure' AND reason IN
            ('offline_or_timeout','provider_http_error','not_in_cached_snapshot')""", (self.clock(),))

    def retry(self, field_id, provider):
        job = self.enqueue(field_id, provider)
        if job and provider is not None and provider.supports(job["kaek"]):
            self.db.execute("UPDATE kaek_lookup_jobs SET status='pending',attempts=0,next_attempt=0,lease_until=0,request_id=?,reason='',provider=? WHERE job_id=?",
                            (str(uuid.uuid4()), provider.identity, job["job_id"]))

    def complete(self, payload, provider, snapshot=None):
        value = validate_payload(payload)
        if value["kind"] != "kaek-result":
            raise ValueError("Result required")
        if (provider is None or value["provider"] != provider.identity
                or value["source_url"] != provider.source_url or value["terms_url"] != provider.terms_url
                or value["attribution"] != provider.attribution):
            raise ValueError("Unexpected provider provenance")
        if value["retrieved_at"] > self.clock() + 300_000:
            raise ValueError("Future retrieval time")
        digest = fingerprint(value)
        with self.db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            dataset = con.execute("SELECT value FROM app_settings WHERE key='kaek_dataset_uuid'").fetchone()[0]
            row = con.execute("""SELECT j.*,f.kaek AS current_kaek FROM kaek_lookup_jobs j
                JOIN kaek_field_identity i USING(field_uuid) JOIN fields f ON f.id=i.field_id
                WHERE j.job_id=?""", (value["job_id"],)).fetchone()
            if (row is None or dataset != value["dataset_id"] or row["field_uuid"] != value["field_id"]
                    or row["kaek"] != value["kaek"] or row["current_kaek"] != value["kaek"]
                    or row["request_id"] != value["request_id"] or row["requested_at"] != value["requested_at"]
                    or row["provider"] != value["provider"]):
                raise StaleLookup("Field, KAEK or request changed")
            if row["status"] == "retrieved":
                if row["result_hash"] == digest:
                    return False
                raise LookupConflict("Different result for completed request")
            if row["status"] != "retrieving":
                raise StaleLookup("Request is no longer active")
            con.execute("""INSERT INTO cadastral_geometry VALUES(?,?,?,?,?)
                ON CONFLICT(field_uuid) DO UPDATE SET kaek=excluded.kaek,job_id=excluded.job_id,
                result_json=excluded.result_json,result_hash=excluded.result_hash""",
                        (value["field_id"], value["kaek"], value["job_id"], canonical(value), digest))
            con.execute("UPDATE kaek_lookup_jobs SET status='retrieved',reason='',result_hash=?,lease_until=0 WHERE job_id=?", (digest, value["job_id"]))
            if snapshot is not None:
                # Local cache provenance is bound to this exact result hash. Keep
                # the already accepted version-1 transport contract unchanged.
                clean = {key: snapshot[key] for key in ('downloaded_at', 'checked_at', 'refresh_error')
                         if key in snapshot}
                con.execute("""INSERT INTO cadastral_details VALUES(?,?,?) ON CONFLICT(field_uuid)
                    DO UPDATE SET result_hash=excluded.result_hash,details_json=excluded.details_json""",
                    (value['field_id'], digest, canonical({'snapshot': clean})))
        return True

    def details(self, field_id):
        row = self.db.query_one("""SELECT d.details_json FROM cadastral_details d
            JOIN cadastral_geometry g USING(field_uuid,result_hash)
            JOIN kaek_field_identity i USING(field_uuid) JOIN fields f ON f.id=i.field_id
            WHERE i.field_id=? AND f.kaek=g.kaek""", (field_id,))
        return json.loads(row[0]) if row else {}

    def geometry(self, field_id):
        row = self.db.query_one("""SELECT g.result_json FROM cadastral_geometry g
            JOIN kaek_field_identity i USING(field_uuid) JOIN fields f ON f.id=i.field_id
            WHERE i.field_id=? AND f.kaek=g.kaek""", (field_id,))
        return deserialize(row[0]) if row else None
