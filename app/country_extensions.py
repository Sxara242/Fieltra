"""Pure country contracts (B02.1); no settings, provider or startup activation.

SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol

DEFAULT_CULTIVATION_COUNTRY = "GR"
GREEK_SYSTEM = "kaek"
GREEK_AUTHORITY = "hellenic-cadastre"


def country_code(value: str) -> str:
    """Require an explicit alpha-2 shaped code, without inferring/normalizing it.

    This is syntax validation, not an ISO membership catalogue. Future Settings
    must offer reviewed ISO data. Unknown codes resolve to unavailable fallback.
    """
    if not isinstance(value, str) or len(value) != 2 or any(c < "A" or c > "Z" for c in value):
        raise ValueError("Explicit uppercase alpha-2 country code required")
    return value


class ValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class IdentifierScope:
    country_code: str
    system_id: str
    authority_id: str
    jurisdiction_key: str = ""

    def __post_init__(self):
        country_code(self.country_code)
        for value in (self.system_id, self.authority_id):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Explicit system and authority required")
        if not isinstance(self.jurisdiction_key, str):
            raise ValueError("Jurisdiction must be an explicit string")


@dataclass(frozen=True)
class IdentifierValidation:
    scope: IdentifierScope
    raw: str
    state: ValidationState
    comparison_key: str | None
    validator_version: str

    def __post_init__(self):
        if not isinstance(self.scope, IdentifierScope) or not isinstance(self.raw, str):
            raise ValueError("Scoped raw identifier string required")
        if (not isinstance(self.state, ValidationState) or not isinstance(self.validator_version, str)
                or not self.validator_version):
            raise ValueError("Versioned validation state required")
        if self.state is ValidationState.VALID:
            if not isinstance(self.comparison_key, str) or not self.comparison_key:
                raise ValueError("Valid identity requires a comparison key")
        elif self.comparison_key is not None:
            raise ValueError("Unverified identity cannot acquire a comparison key")


class IdentifierAdapter(Protocol):
    def validate(self, raw: str, scope: IdentifierScope) -> IdentifierValidation: ...


class GreekIdentifierAdapter:
    """Same exact 12-ASCII-digit rule as kaek_lookup.valid_kaek and CadastralStore.

    Kept isolated until the legacy adapter stage. No trimming, numeric conversion,
    provenance classification, coverage promise or existing-form behavior change.
    """
    def validate(self, raw: str, scope: IdentifierScope) -> IdentifierValidation:
        if not isinstance(raw, str) or not isinstance(scope, IdentifierScope):
            raise ValueError("Scoped raw identifier string required")
        if (scope.country_code, scope.system_id, scope.authority_id) != (
            "GR", GREEK_SYSTEM, GREEK_AUTHORITY
        ):
            return IdentifierValidation(scope, raw, ValidationState.UNSUPPORTED, None, "gr-kaek-ascii12-v1")
        valid = len(raw) == 12 and raw.isascii() and raw.isdigit()
        return IdentifierValidation(scope, raw, ValidationState.VALID if valid else ValidationState.INVALID,
                                    raw if valid else None, "gr-kaek-ascii12-v1")


@dataclass(frozen=True)
class CountryDescriptor:
    code: str
    label: str
    version: str
    form_configuration: str
    identifier_systems: tuple[str, ...] = ()
    provider_ids: tuple[str, ...] = ()
    supported_crs: tuple[str, ...] = ()
    coverage: str = "No country-specific cadastral integration"
    attribution_reference: str = ""

    def __post_init__(self):
        country_code(self.code)
        if any(not isinstance(v, str) or not v for v in (self.label, self.version, self.form_configuration)):
            raise ValueError("Versioned country descriptor required")
        if not isinstance(self.coverage, str) or not isinstance(self.attribution_reference, str):
            raise ValueError("Coverage and attribution reference must be strings")
        for name in ("identifier_systems", "provider_ids", "supported_crs"):
            values = tuple(getattr(self, name))
            if any(not isinstance(v, str) or not v for v in values):
                raise ValueError("Descriptor capabilities must be strings")
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class CountryExtension:
    descriptor: CountryDescriptor
    identifier_adapter: IdentifierAdapter | None = None

    def __post_init__(self):
        if not isinstance(self.descriptor, CountryDescriptor):
            raise ValueError("Country descriptor required")

    def validate(self, raw: str, scope: IdentifierScope) -> IdentifierValidation:
        if not isinstance(raw, str) or not isinstance(scope, IdentifierScope):
            raise ValueError("Scoped raw identifier string required")
        if self.identifier_adapter is None or scope.country_code != self.descriptor.code:
            return IdentifierValidation(scope, raw, ValidationState.UNSUPPORTED, None, "unsupported-v1")
        return self.identifier_adapter.validate(raw, scope)


def greece_extension() -> CountryExtension:
    return CountryExtension(CountryDescriptor(
        "GR", "Greece", "1", "existing-gr-main-form", (GREEK_SYSTEM,),
        ("hellenic-cadastre-north-aegean",), ("EPSG:2100", "EPSG:4326"),
        "North Aegean regional dataset only; retrieval is not connected",
        "app/gis/kaek_provider.py: NorthAegeanProvider attribution/terms",
    ), GreekIdentifierAdapter())


class CountryRegistry:
    """Reviewed source extensions only. No executable plugin loading or I/O."""
    def __init__(self, extensions: Iterable[CountryExtension] | None = None):
        self._extensions: dict[str, CountryExtension] = {}
        for extension in (greece_extension(),) if extensions is None else extensions:
            code = extension.descriptor.code
            if code in self._extensions:
                raise ValueError("Duplicate country extension")
            self._extensions[code] = extension

    def get(self, code: str) -> CountryExtension:
        code = country_code(code)
        if code in self._extensions:
            return self._extensions[code]
        return CountryExtension(CountryDescriptor(code, "Generic farming", "1", "generic-farming"))
