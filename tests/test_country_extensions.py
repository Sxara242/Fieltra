"""B02.1 synthetic contract tests; execution requires approved hosted CI.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from app.country_extensions import (
    CountryDescriptor, CountryExtension, CountryRegistry, GreekIdentifierAdapter,
    IdentifierScope, ValidationState, greece_extension,
)
from app.gis.kaek_lookup import valid_kaek
from app.gis.cadastral_protocol import FarmCountryConfiguration, RecordVersion

FIXTURE = Path(__file__).resolve().parents[1] / "shared/fixtures/cadastral_b021.json"
GR = IdentifierScope("GR", "kaek", "hellenic-cadastre")


class CountryExtensionsTests(unittest.TestCase):
    def test_greek_adapter_preserves_accepted_rule_and_raw_strings(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["identifier_cases"]
        for case in cases:
            with self.subTest(raw=case["raw"]):
                result = GreekIdentifierAdapter().validate(case["raw"], GR)
                self.assertEqual(case["valid"], valid_kaek(case["raw"]))
                self.assertEqual(case["valid"], result.state is ValidationState.VALID)
                self.assertEqual(case["raw"], result.raw)
                self.assertEqual(case["raw"] if case["valid"] else None, result.comparison_key)

    def test_explicit_country_default_and_generic_fallback(self):
        config = FarmCountryConfiguration("default", RecordVersion(1, 0, 0))
        self.assertEqual("GR", config.cultivation_country)
        registry = CountryRegistry()
        # Language/GPS/locale have no input parameter or acquisition path in these APIs.
        selected = replace(config, cultivation_country="ES")
        fallback = registry.get(selected.cultivation_country)
        self.assertEqual("GR", config.cultivation_country)
        self.assertEqual("ES", fallback.descriptor.code)
        self.assertEqual((), fallback.descriptor.provider_ids)
        self.assertEqual("generic-farming", fallback.descriptor.form_configuration)
        result = fallback.validate("AB/00-1", IdentifierScope("ES", "synthetic", "fixture"))
        self.assertIs(ValidationState.UNSUPPORTED, result.state)
        self.assertIsNone(result.comparison_key)
        self.assertIs(ValidationState.UNSUPPORTED, registry.get("GR").validate(
            "510201507004", replace(GR, authority_id="synthetic-other-authority")).state)
        self.assertIs(ValidationState.UNSUPPORTED, registry.get("GR").validate(
            "510201507004", replace(GR, system_id="synthetic-other-system")).state)
        for code in ("gr", "", "GRC", "12"):
            with self.assertRaises(ValueError):
                registry.get(code)

    def test_reviewed_extension_can_be_added_without_business_records(self):
        # ZZ is a deliberately synthetic extension, not an official country module.
        descriptor = CountryDescriptor("ZZ", "Synthetic test only", "1", "generic-farming")
        registry = CountryRegistry((greece_extension(), CountryExtension(descriptor)))
        self.assertEqual(descriptor, registry.get("ZZ").descriptor)
        self.assertEqual("existing-gr-main-form", registry.get("GR").descriptor.form_configuration)
        with self.assertRaises(ValueError):
            CountryRegistry((greece_extension(), greece_extension()))
