"""Offline name suggestions: geographic context, never official parcel names."""
from __future__ import annotations

from functools import lru_cache
import json
import math
from pathlib import Path
import time
import unicodedata

from shapely.geometry import Point, shape
from shapely.ops import transform

from .geometry import normalize, transformer
from .kaek_lookup import LookupStore, StaleLookup
from .sync_contract import fingerprint

GAZETTEER_PATH = Path(__file__).resolve().parents[1] / "assets" / "geonames_gr.json"
SOURCE = "https://download.geonames.org/export/dump/GR.zip"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
COLUMNS = ["id", "name", "original_name", "feature", "longitude", "latitude", "modified"]
RURAL_FEATURES = {"L.LCTY", "L.AGRR", "L.FRM", "L.FMS", "L.FMLD", "L.PST", "L.OCH", "L.VIN"}


def feature_group(feature):
    if feature in RURAL_FEATURES:
        return "rural"
    if feature.startswith("P."):
        return "settlement"
    return "natural"


class Gazetteer:
    def __init__(self, document):
        if (document.get("schema") != 1 or document.get("columns") != COLUMNS
                or document.get("source") != SOURCE or document.get("license") != LICENSE):
            raise ValueError("Unsupported offline gazetteer")
        self.metadata = {key: document[key] for key in (
            "source", "license", "attribution", "acquired_at", "source_sha256")}
        self.rows = tuple(tuple(row) for row in document["features"])
        if any(len(row) != len(COLUMNS) for row in self.rows):
            raise ValueError("Malformed gazetteer row")

    def suggestions(self, geometry, radius_m=3000, limit=5):
        if not 0 < radius_m <= 3000 or not 0 < limit <= 5:
            raise ValueError("Local bounded search required")
        west, south, east, north = geometry.bbox
        pad_lat = radius_m / 110000
        pad_lon = radius_m / (110000 * math.cos(math.radians(max(abs(south), abs(north)))))
        parcel = transform(transformer("EPSG:4326", "EPSG:2100").transform, shape(geometry.wgs84))
        project = transformer("EPSG:4326", "EPSG:2100").transform
        candidates = []
        for source_id, name, original, feature, lon, lat, modified in self.rows:
            if not (west-pad_lon <= lon <= east+pad_lon and south-pad_lat <= lat <= north+pad_lat):
                continue
            distance = parcel.distance(Point(*project(lon, lat)))
            if distance > radius_m:
                continue
            group = feature_group(feature)
            candidate = dict(
                geonames_id=source_id, name=name, original_name=original, feature=feature,
                feature_group=group, longitude=lon, latitude=lat, modified=modified,
                distance_m=round(distance, 2), confidence="unconfirmed",
                spatial_relation="mapped_point_within_parcel" if distance < 0.01 else "nearby_point",
                **self.metadata,
            )
            # A village point is context, not a better agricultural locality just
            # because it is marginally nearer. Distances are to the actual parcel
            # (including holes/multipart geometry), not merely to its centroid.
            penalty = {"rural": 0, "natural": 400, "settlement": 2000}[group]
            candidates.append((distance + penalty, distance, source_id, candidate))
        candidates.sort(key=lambda entry: entry[:3])
        return [entry[3] for entry in candidates[:limit]]


@lru_cache(maxsize=1)
def gazetteer():
    return Gazetteer(json.loads(GAZETTEER_PATH.read_text(encoding="utf-8")))


class ToponymStore:
    """Explicit user decisions, isolated from fields and official attributes."""
    def __init__(self, db, clock=None):
        self.db = db
        self.clock = clock or (lambda: time.time_ns() // 1_000_000)

    def context(self, field_id):
        payload = LookupStore(self.db).geometry(field_id)
        if payload is None:
            return None
        return dict(field_uuid=payload["field_id"], kaek=payload["kaek"],
                    result_hash=fingerprint(payload),
                    geometry=normalize(payload["geometry"], payload["source_crs"]))

    def load(self, field_id):
        row = self.db.query_one("""SELECT t.* FROM agricultural_toponyms t
            JOIN kaek_field_identity i USING(field_uuid) JOIN fields f ON f.id=i.field_id
            WHERE i.field_id=? AND f.kaek=t.kaek""", (field_id,))
        return (dict(confirmed_name=row["confirmed_name"], decision=row["decision"],
                     candidate=json.loads(row["candidate_json"]), updated_at=row["updated_at"])
                if row else dict(confirmed_name="", decision="unspecified", candidate={}, updated_at=None))

    def save(self, field_id, context, *, decision, name="", candidate=None):
        if decision not in {"confirmed", "rejected", "unspecified"}:
            raise ValueError("Unknown toponym decision")
        name = unicodedata.normalize("NFC", name.strip())
        if (len(name) > 200 or any(unicodedata.category(c).startswith("C") for c in name)
                or (decision == "confirmed" and not name)):
            raise ValueError("Invalid confirmed locality")
        if decision != "confirmed":
            name = ""
        candidate = candidate or {}
        if decision == "unspecified":
            candidate = {}
        if candidate and (
                candidate.get("source") != SOURCE or candidate.get("license") != LICENSE
                or type(candidate.get("geonames_id")) is not int
                or not isinstance(candidate.get("name"), str)
                or candidate.get("confidence") != "unconfirmed"):
            raise ValueError("Invalid suggestion provenance")
        encoded = json.dumps(candidate, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 8192:
            raise ValueError("Suggestion too large")
        with self.db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("""SELECT i.field_uuid,f.kaek,g.result_hash FROM fields f
                JOIN kaek_field_identity i ON i.field_id=f.id
                JOIN cadastral_geometry g ON g.field_uuid=i.field_uuid AND g.kaek=f.kaek
                WHERE f.id=?""", (field_id,)).fetchone()
            if (context is None or row is None or any(row[key] != context[key]
                    for key in ("field_uuid", "kaek", "result_hash"))):
                raise StaleLookup("Field, KAEK or cadastral geometry changed")
            con.execute("""INSERT INTO agricultural_toponyms
                (field_uuid,kaek,candidate_json,confirmed_name,decision,updated_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(field_uuid) DO UPDATE SET kaek=excluded.kaek,
                candidate_json=excluded.candidate_json,confirmed_name=excluded.confirmed_name,
                decision=excluded.decision,updated_at=excluded.updated_at""",
                (context["field_uuid"], context["kaek"], encoded, name, decision, self.clock()))
