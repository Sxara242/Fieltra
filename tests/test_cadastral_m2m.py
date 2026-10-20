"""Pure DTO/cardinality specifications, not storage or business-integration proof.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest

from app.country_extensions import IdentifierScope
from app.gis.cadastral_protocol import (
    CadastralParcel, CultivatedFieldRef, FieldCadastralLink, FieldIdentityAlias,
    LegacyCadastralValue, RecordVersion, ScopedParcelIdentity,
)

FIXTURE = Path(__file__).resolve().parents[1] / "shared/fixtures/cadastral_b021.json"
VERSION = RecordVersion(1, 0, 0)


class CadastralM2MTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.field = CultivatedFieldRef(self.fixture["farm_scope"], self.fixture["field_uuids"][0])

    def test_one_field_five_parcels_and_inverse_shared_parcel(self):
        before = json.dumps(self.fixture, sort_keys=True, ensure_ascii=False)
        parcels = tuple(CadastralParcel(
            self.field.farm_scope, p["uuid"], ScopedParcelIdentity(
                IdentifierScope("GR", "kaek", "hellenic-cadastre"), p["raw"]),
            p["raw"], "gr-kaek-ascii12-v1", VERSION,
        ) for p in self.fixture["parcels"])
        links = tuple(FieldCadastralLink(self.field, p.parcel_uuid, VERSION, i == 0, i != 0)
                      for i, p in enumerate(parcels))
        self.assertEqual(5, len({link.association_key for link in links}))
        self.assertEqual({self.field}, {link.field for link in links})
        self.assertNotIn(self.field.field_uuid, {p.parcel_uuid for p in parcels})
        second = CultivatedFieldRef(self.field.farm_scope, self.fixture["field_uuids"][1])
        inverse = FieldCadastralLink(second, parcels[0].parcel_uuid, VERSION)
        self.assertNotEqual(links[0].association_key, inverse.association_key)
        self.assertEqual(links[0].parcel_uuid, inverse.parcel_uuid)
        self.assertEqual(links[0].association_key, replace(links[0]).association_key)
        self.assertEqual(before, json.dumps(self.fixture, sort_keys=True, ensure_ascii=False))
        # DTO construction only: stored totals/union/rendering require later A–N gates.
        self.assertEqual(3.25, self.fixture["business"]["cultivated_area_stremma"])
        self.assertEqual(1, self.fixture["business"]["crop_link_count"])

    def test_every_identity_scope_dimension_and_farm_prevents_collision(self):
        base = IdentifierScope("GR", "synthetic-system", "fixture-authority", "A")
        scopes = (base, replace(base, country_code="ES"), replace(base, system_id="other"),
                  replace(base, authority_id="other"), replace(base, jurisdiction_key="B"))
        self.assertEqual(5, len({ScopedParcelIdentity(scope, "AB/00-1") for scope in scopes}))
        link = FieldCadastralLink(self.field, self.fixture["parcels"][0]["uuid"], VERSION)
        other = replace(link, field=replace(self.field, farm_scope=self.fixture["other_farm_scope"]))
        self.assertNotEqual(link.association_key, other.association_key)

    def test_legacy_strings_and_alias_namespaces_remain_independent(self):
        for raw in self.fixture["legacy_values"]:
            self.assertEqual(raw, LegacyCadastralValue(self.field, raw).raw)
        alias_uuid = self.fixture["parcels"][0]["uuid"]
        kaek = FieldIdentityAlias(self.field, "legacy-kaek", "fixture-dataset", alias_uuid)
        gis = replace(kaek, namespace="legacy-gis")
        self.assertNotEqual(kaek, gis)
        self.assertEqual(self.fixture["field_uuids"][0], kaek.field.field_uuid)
        with self.assertRaises(FrozenInstanceError):
            kaek.alias_uuid = self.field.field_uuid

    def test_versions_origins_tombstones_and_uuid_validation(self):
        parcel = self.fixture["parcels"][0]["uuid"]
        with self.assertRaises(ValueError):
            FieldCadastralLink(self.field, parcel, VERSION, False, False)
        tombstone = FieldCadastralLink(self.field, parcel, RecordVersion(2, 0, 2, 2), False, False)
        self.assertEqual(2, tombstone.version.deleted_at)
        for args in ((0, 0, 0), (True, 0, 0), (1, 2, 1), (1, 0, 1, 2), (1 << 63, 0, 0)):
            with self.assertRaises(ValueError):
                RecordVersion(*args)
        with self.assertRaises(ValueError):
            CultivatedFieldRef(self.field.farm_scope, "not-a-uuid")
