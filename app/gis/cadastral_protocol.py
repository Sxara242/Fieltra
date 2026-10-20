"""Isolated farm-scoped cadastral DTOs/interfaces; no SQL, wire format or I/O.

These are not GIS schema-1 entities and never create cultivated business fields.
SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ..country_extensions import DEFAULT_CULTIVATION_COUNTRY, IdentifierScope, country_code

MAX_INTEGER = (1 << 63) - 1  # Same positive revision/time range as SQLite and Java long.


def canonical_uuid(value: str) -> str:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Canonical UUID required")
    return value


def farm_scope(value: str) -> str:
    """Opaque caller-selected profile/store identity, including default/legacy IDs."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Explicit farm/profile store scope required")
    return value


@dataclass(frozen=True)
class RecordVersion:
    revision: int
    created_at: int
    updated_at: int
    deleted_at: int | None = None

    def __post_init__(self):
        if type(self.revision) is not int or not 1 <= self.revision <= MAX_INTEGER:
            raise ValueError("Positive revision required")
        if any(type(t) is not int or not 0 <= t <= MAX_INTEGER for t in (self.created_at, self.updated_at)):
            raise ValueError("Nonnegative UTC millisecond timestamps required")
        if self.updated_at < self.created_at:
            raise ValueError("Update predates creation")
        if self.deleted_at is not None and (
            type(self.deleted_at) is not int or not self.created_at <= self.deleted_at <= self.updated_at
        ):
            raise ValueError("Invalid tombstone timestamp")


@dataclass(frozen=True)
class FarmCountryConfiguration:
    """Value to be explicitly persisted later; constructing it writes nothing."""
    farm_scope: str
    version: RecordVersion
    cultivation_country: str = DEFAULT_CULTIVATION_COUNTRY

    def __post_init__(self):
        farm_scope(self.farm_scope)
        country_code(self.cultivation_country)
        if not isinstance(self.version, RecordVersion) or self.version.deleted_at is not None:
            raise ValueError("Active configuration version required")


@dataclass(frozen=True)
class CultivatedFieldRef:
    farm_scope: str
    field_uuid: str

    def __post_init__(self):
        farm_scope(self.farm_scope)
        canonical_uuid(self.field_uuid)


@dataclass(frozen=True)
class FieldIdentityAlias:
    """Existing namespace/dataset identity; no remapping/allocation is performed."""
    field: CultivatedFieldRef
    namespace: str
    dataset: str
    alias_uuid: str

    def __post_init__(self):
        if (not isinstance(self.field, CultivatedFieldRef)
                or any(not isinstance(v, str) or not v for v in (self.namespace, self.dataset))):
            raise ValueError("Explicit field alias scope required")
        canonical_uuid(self.alias_uuid)


@dataclass(frozen=True)
class ScopedParcelIdentity:
    scope: IdentifierScope
    comparison_key: str

    def __post_init__(self):
        if not isinstance(self.scope, IdentifierScope) or not isinstance(self.comparison_key, str) or not self.comparison_key:
            raise ValueError("Verified scoped comparison key required")


@dataclass(frozen=True)
class CadastralParcel:
    farm_scope: str
    parcel_uuid: str
    identity: ScopedParcelIdentity
    identifier_raw: str
    validator_version: str
    version: RecordVersion

    def __post_init__(self):
        farm_scope(self.farm_scope)
        canonical_uuid(self.parcel_uuid)
        if not isinstance(self.identity, ScopedParcelIdentity) or not isinstance(self.identifier_raw, str):
            raise ValueError("Scoped parcel and exact raw string required")
        if (not isinstance(self.validator_version, str) or not self.validator_version
                or not isinstance(self.version, RecordVersion)):
            raise ValueError("Versioned parcel required")


@dataclass(frozen=True)
class FieldCadastralLink:
    field: CultivatedFieldRef
    parcel_uuid: str
    version: RecordVersion
    legacy_slot: bool = False
    manual_link: bool = True

    def __post_init__(self):
        if not isinstance(self.field, CultivatedFieldRef) or not isinstance(self.version, RecordVersion):
            raise ValueError("Field and link version required")
        canonical_uuid(self.parcel_uuid)
        if type(self.legacy_slot) is not bool or type(self.manual_link) is not bool:
            raise ValueError("Boolean link origins required")
        if self.version.deleted_at is None and not (self.legacy_slot or self.manual_link):
            raise ValueError("Active link requires an origin")

    @property
    def association_key(self) -> tuple[str, str, str]:
        return self.field.farm_scope, self.field.field_uuid, self.parcel_uuid


@dataclass(frozen=True)
class LegacyCadastralValue:
    """Unclassified value. Default GR is never evidence for classifying it."""
    field: CultivatedFieldRef
    raw: str

    def __post_init__(self):
        if not isinstance(self.field, CultivatedFieldRef) or not isinstance(self.raw, str):
            raise ValueError("Legacy field and raw string required")


class ParcelRepository(Protocol):
    """Future implementations must enforce these transaction invariants:

    Scope every operation to the supplied farm. Ensure deduplicates only the full
    scoped identity, preserving UUID aliases/raw spellings; conflicts fail closed.
    Links require existing same-farm field/parcel records. Duplicate pairs are
    idempotent, inverse M:N is allowed, active legacy slots are unique per field.
    expected_revision=0 means absent; otherwise compare-and-swap, never overwrite
    a concurrent revision. Unlink tombstones only the association, retains shared
    parcels/snapshots, and cannot silently clear the legacy main-form value.
    No operation creates fields/crops/history, writes business totals/area, calls
    providers or mutates fields.kaek. Storage/legacy projection are later stages.
    """
    def ensure_parcel(self, candidate: CadastralParcel) -> CadastralParcel: ...
    def link(self, association: FieldCadastralLink, expected_revision: int) -> FieldCadastralLink: ...
    def unlink(self, field: CultivatedFieldRef, parcel_uuid: str, expected_revision: int) -> FieldCadastralLink: ...
    def list_links(self, field: CultivatedFieldRef, *, include_deleted: bool = False) -> tuple[FieldCadastralLink, ...]: ...
