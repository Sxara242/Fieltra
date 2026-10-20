"""Pure unsnapped derived geometry; source bytes and cultivated area stay separate.
SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time

import shapely
from shapely import union_all
from shapely.errors import GEOSException
from shapely.geometry import shape, mapping
from shapely.ops import transform
from pyproj.exceptions import ProjError

from .cadastral_migration import canonical
from .cadastral_store import InputSnapshot
from .geometry import transformer

STATES = frozenset(('NONE', 'PENDING', 'PARTIAL', 'COMPLETE_DERIVED', 'STALE',
                    'CONFLICT', 'INVALID_SOURCE', 'UNION_FAILED', 'TOO_LARGE'))
MAX_VERTICES = 100_000
MAX_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class OverlayResult:
    state: str
    fingerprint: str
    required_count: int
    usable_count: int
    geometry_json: str | None = None
    exterior_vertices: tuple = ()
    engine: str = 'Shapely/' + shapely.__version__ + '/GEOS/' + shapely.geos_version_string
    diagnostic: str = ''
    working_crs: str = 'EPSG:2100'
    precision_policy: str = 'unsnapped-floating'

    def __post_init__(self):
        if self.state not in STATES or not 0 <= self.usable_count <= self.required_count:
            raise ValueError('Invalid overlay state/counts')
        if self.state == 'COMPLETE_DERIVED' and (not self.required_count or self.usable_count != self.required_count or not self.geometry_json):
            raise ValueError('Complete result requires every source and derived geometry')
        if self.state != 'COMPLETE_DERIVED' and self.geometry_json is not None:
            raise ValueError('Incomplete output cannot masquerade as a complete outline')


def _coordinates(value):
    if not isinstance(value, dict) or value.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Only polygon sources supported')
    parts = [value['coordinates']] if value['type'] == 'Polygon' else value['coordinates']
    if not isinstance(parts, list) or not parts:
        raise ValueError('Empty source')
    for part in parts:
        if not isinstance(part, list) or not part:
            raise ValueError('Empty part')
        for ring in part:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('Unclosed ring')
            for xy in ring:
                if not isinstance(xy, list) or len(xy) != 2 or any(
                        type(v) not in (int, float) or not math.isfinite(v) for v in xy):
                    raise ValueError('Invalid finite XY')
                yield xy


def build_union(inputs: InputSnapshot, cancelled=lambda: False, *, seconds=30.0) -> OverlayResult:
    """Run in an explicit executor. Cancellation is cooperative around native GEOS;
    no claim of interrupting a single native operation. No automatic repair/grid.
    """
    required = len(inputs.inputs)
    deadline = time.monotonic() + seconds
    usable = 0

    def result(state, diagnostic='', geometry=None, vertices=()):
        return OverlayResult(state, inputs.fingerprint, required, usable, geometry, vertices, diagnostic=diagnostic)

    def check():
        if cancelled():
            raise InterruptedError('Cancelled')
        if time.monotonic() > deadline:
            raise TimeoutError('Worker time budget exceeded')

    if not required:
        return result('NONE')
    if any(i.state == 'CONFLICT' for i in inputs.inputs):
        return result('CONFLICT')
    if any(i.state == 'STALE' for i in inputs.inputs):
        return result('STALE')
    if any(i.state == 'INVALID_SOURCE' for i in inputs.inputs):
        return result('INVALID_SOURCE')
    geometries = []
    total = 0
    try:
        byte_count = 0
        for source in inputs.inputs:
            byte_count += len((source.geometry_json or '').encode('utf-8'))
            if byte_count > MAX_BYTES:
                return result('TOO_LARGE', 'geometry_byte_budget')
        for source in inputs.inputs:
            check()
            if source.state != 'READY' or not all((source.geometry_json, source.snapshot_uuid, source.content_hash)):
                continue
            if source.source_crs not in ('EPSG:2100', 'EPSG:4326'):
                return result('INVALID_SOURCE', 'unsupported_crs')
            value = json.loads(source.geometry_json)
            for x, y in _coordinates(value):
                total += 1
                if total % 1024 == 0:
                    check()
                if total > MAX_VERTICES:
                    return result('TOO_LARGE', 'source_vertex_budget')
                if source.source_crs == 'EPSG:4326' and not (19 <= x <= 30 and 34 <= y <= 42.5):
                    return result('INVALID_SOURCE', 'outside_supported_greek_extent')
            geometry = shape(value)
            if geometry.is_empty or not geometry.is_valid or geometry.area <= 0 or not math.isfinite(geometry.area) or not math.isfinite(geometry.length):
                return result('INVALID_SOURCE', 'invalid_source_topology')
            if source.source_crs != 'EPSG:2100':
                geometry = transform(transformer(source.source_crs, 'EPSG:2100').transform, geometry)
            if (geometry.is_empty or not geometry.is_valid or not all(math.isfinite(v) for v in geometry.bounds)
                    or not math.isfinite(geometry.area) or not math.isfinite(geometry.length)):
                return result('INVALID_SOURCE', 'invalid_transformed_source')
            geometries.append(geometry)
            usable += 1
        if usable != required:
            return result('PARTIAL' if usable else 'PENDING', 'missing_required_source')
        check()
        # Explicit 0 is double precision. None could inherit a precision model.
        combined = union_all(geometries, grid_size=0)
        check()
        if shapely.get_num_coordinates(combined) > MAX_VERTICES:
            return result('TOO_LARGE', 'derived_vertex_budget')
        if (combined.geom_type not in ('Polygon', 'MultiPolygon') or combined.is_empty or not combined.is_valid
                or not math.isfinite(combined.area) or not math.isfinite(combined.length)):
            return result('UNION_FAILED', 'invalid_derived_topology')
        derived = mapping(combined)
        rings = (combined,) if combined.geom_type == 'Polygon' else combined.geoms
        outer = tuple(tuple((float(x), float(y)) for x, y in p.exterior.coords[:-1]) for p in rings)
        return result('COMPLETE_DERIVED', geometry=canonical(derived), vertices=outer)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, ProjError):
        return result('INVALID_SOURCE', 'invalid_source_or_transform')
    except GEOSException:
        return result('UNION_FAILED', 'topology_engine_failure')
    except TimeoutError:
        return result('TOO_LARGE', 'worker_time_budget')


def submit_union(executor, inputs, cancelled=lambda: False):
    """Captured DTO is immutable. Caller publishes on its DB-owning thread via CAS."""
    return executor.submit(build_union, inputs, cancelled)
