"""Offline gazetteer, explicit decisions and isolated native-widget regressions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.database import Database
from app.gis.geometry import normalize, transformer
from app.gis.kaek_lookup import ANDROID_KAEK_SYNC_ENABLED, LookupStore, StaleLookup
from app.gis.store import GeometryStore
from app.gis.toponyms import COLUMNS, Gazetteer, LICENSE, SOURCE, ToponymStore, gazetteer
from app.gis.toponym_widget import ToponymWidget

KAEK = "510201507004"
CHIOS = {"type": "Polygon", "coordinates": [[
    [26.055236463243467, 38.22430514189568], [26.055336940976364, 38.22429545217633],
    [26.055423839227814, 38.224306545629005], [26.055385427123213, 38.22426892114836],
    [26.05502474476528, 38.22341034951361], [26.054720382940715, 38.2234894806737],
    [26.054749723618897, 38.22353762704173], [26.054755391675126, 38.22353608600719],
    [26.0551168298248, 38.22411719236054], [26.055236463243467, 38.22430514189568]]]}


def document(rows):
    return dict(schema=1, source=SOURCE, license=LICENSE, attribution="GeoNames CC BY 4.0",
                acquired_at="2026-10-16", source_sha256="0"*64, columns=COLUMNS, features=rows)


def row(identity, name, feature, x, y):
    lon, lat = transformer("EPSG:2100", "EPSG:4326").transform(x, y)
    return [identity, name, name, feature, lon, lat, "2026-01-01"]


class GazetteerTests(unittest.TestCase):
    def test_real_chios_candidate_is_nearby_unconfirmed_point(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No network")):
            found = gazetteer().suggestions(normalize(CHIOS, "EPSG:4326"))
        candidate = next(item for item in found if item["geonames_id"] == 444549)
        self.assertEqual("Πλακοτές", candidate["name"])
        self.assertEqual("T.RDGE", candidate["feature"])
        self.assertTrue(180 < candidate["distance_m"] < 205)
        self.assertEqual("nearby_point", candidate["spatial_relation"])
        self.assertEqual("unconfirmed", candidate["confidence"])
        self.assertEqual(SOURCE, candidate["source"])
        self.assertEqual(LICENSE, candidate["license"])
        self.assertNotIn("official_toponym", candidate)

    def test_agricultural_locality_ranks_above_nearer_settlement(self):
        geometry = normalize({"type": "Polygon", "coordinates": [[[500000, 4200000],
            [500100, 4200000], [500100, 4200100], [500000, 4200100], [500000, 4200000]]]}, "EPSG:2100")
        data = Gazetteer(document([
            row(1, "Village", "P.PPL", 500050, 4200050),
            row(2, "Αγροτική θέση", "L.LCTY", 500250, 4200050),
            row(3, "Too far", "L.LCTY", 510000, 4200050),
        ]))
        found = data.suggestions(geometry)
        self.assertEqual([2, 1], [v["geonames_id"] for v in found])
        self.assertAlmostEqual(150, found[0]["distance_m"], delta=0.2)
        self.assertEqual("settlement", found[1]["feature_group"])

    def test_distance_uses_multipart_and_holes_not_centroid_or_area_extent(self):
        outer = [[500000, 4200000], [500100, 4200000], [500100, 4200100],
                 [500000, 4200100], [500000, 4200000]]
        hole = [[500040, 4200040], [500040, 4200060], [500060, 4200060],
                [500060, 4200040], [500040, 4200040]]
        second = [[500200, 4200000], [500300, 4200000], [500300, 4200100],
                  [500200, 4200100], [500200, 4200000]]
        geometry = normalize({"type": "MultiPolygon", "coordinates": [[outer, hole], [second]]}, "EPSG:2100")
        found = Gazetteer(document([row(1, "Hole", "L.LCTY", 500050, 4200050),
            row(2, "Second part", "L.LCTY", 500250, 4200050)])).suggestions(geometry)
        self.assertEqual(2, found[0]["geonames_id"])
        self.assertEqual("mapped_point_within_parcel", found[0]["spatial_relation"])
        self.assertAlmostEqual(10, found[1]["distance_m"], delta=0.2)
        self.assertEqual("nearby_point", found[1]["spatial_relation"])


class ToponymTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch("app.database.DATA_DIR", self.root / "data"))
        self.db = Database(self.root / "farm.db")
        self.field = self.db.execute("INSERT INTO fields(name,kaek) VALUES(?,?)", ("My field", KAEK))
        self.lookup = LookupStore(self.db, clock=lambda: 1000)

        class Provider:
            identity = "test-provider"
            source_url = "https://example.org/source"
            terms_url = "https://example.org/terms"
            attribution = "Synthetic fixture"
            def supports(self, value): return True

        self.provider = Provider()
        self.lookup.enqueue(self.field, self.provider)
        request = self.lookup.claim(self.provider)
        payload = dict(request, kind="kaek-result", geometry=CHIOS, source_crs="EPSG:4326",
                       source_date="2026-10-06", retrieved_at=1000, provider=self.provider.identity,
                       source_url=self.provider.source_url, terms_url=self.provider.terms_url,
                       attribution=self.provider.attribution)
        self.lookup.complete(payload, self.provider)
        self.store = ToponymStore(self.db, clock=lambda: 2000)
        self.context = self.store.context(self.field)
        self.candidate = next(item for item in gazetteer().suggestions(self.context["geometry"])
                              if item["geonames_id"] == 444549)

    def snapshot(self):
        with self.db.connect() as con:
            return "\n".join(con.iterdump())

    def test_confirmation_keeps_suggestion_separate_and_field_geometry_unchanged(self):
        manual = normalize({"type": "Polygon", "coordinates": [[[26.055, 38.2235],
            [26.0552, 38.2235], [26.0552, 38.2237], [26.055, 38.2235]]]}, "EPSG:4326")
        GeometryStore(self.db).save(self.field, manual)
        before_field = dict(self.db.query_one("SELECT * FROM fields WHERE id=?", (self.field,)))
        before_geometry = dict(self.db.query_one("SELECT * FROM parcel_geometry WHERE field_id=?", (self.field,)))
        before_cadastral = dict(self.db.query_one("SELECT * FROM cadastral_geometry"))
        self.store.save(self.field, self.context, decision="confirmed", name="Πάνω Πλακοτές", candidate=self.candidate)
        restored = ToponymStore(Database(self.db.path)).load(self.field)
        self.assertEqual("Πάνω Πλακοτές", restored["confirmed_name"])
        self.assertEqual("Πλακοτές", restored["candidate"]["name"])
        self.assertEqual(444549, restored["candidate"]["geonames_id"])
        self.assertEqual(before_field, dict(self.db.query_one("SELECT * FROM fields WHERE id=?", (self.field,))))
        self.assertEqual(before_geometry, dict(self.db.query_one("SELECT * FROM parcel_geometry WHERE field_id=?", (self.field,))))
        self.assertEqual(before_cadastral, dict(self.db.query_one("SELECT * FROM cadastral_geometry")))
        self.assertFalse(ANDROID_KAEK_SYNC_ENABLED)

    def test_reject_clear_and_manual_name_survive_reopening(self):
        self.store.save(self.field, self.context, decision="rejected", candidate=self.candidate)
        self.assertEqual("", self.store.load(self.field)["confirmed_name"])
        self.assertEqual(444549, self.store.load(self.field)["candidate"]["geonames_id"])
        self.store.save(self.field, self.context, decision="unspecified", candidate=self.candidate)
        self.assertEqual({}, self.store.load(self.field)["candidate"])
        self.assertEqual("unspecified", self.store.load(self.field)["decision"])
        self.store.save(self.field, self.context, decision="confirmed", name="Δική μου θέση")
        saved = ToponymStore(Database(self.db.path)).load(self.field)
        self.assertEqual("Δική μου θέση", saved["confirmed_name"])
        self.assertEqual({}, saved["candidate"])

    def test_changed_kaek_deleted_field_or_new_geometry_reject_stale_writes(self):
        self.db.execute("UPDATE fields SET kaek=? WHERE id=?", ("510201507005", self.field))
        before = self.snapshot()
        with self.assertRaises(StaleLookup):
            self.store.save(self.field, self.context, decision="confirmed", name="Stale")
        self.assertEqual(before, self.snapshot())
        self.assertEqual("unspecified", self.store.load(self.field)["decision"])
        self.db.execute("UPDATE fields SET kaek=? WHERE id=?", (KAEK, self.field))
        self.db.execute("UPDATE cadastral_geometry SET result_hash='new-result'")
        with self.assertRaises(StaleLookup):
            self.store.save(self.field, self.context, decision="confirmed", name="Stale")
        self.db.execute("DELETE FROM fields WHERE id=?", (self.field,))
        with self.assertRaises(StaleLookup):
            self.store.save(self.field, self.context, decision="confirmed", name="Deleted")

    def test_widget_load_selection_and_refresh_are_read_only_until_confirmation(self):
        before = self.snapshot()
        widget = ToponymWidget(self.db, self.field)
        self.addCleanup(widget.deleteLater)
        self.assertEqual(widget.candidates[0]['name'], widget.name.text())
        self.assertEqual(0, widget.suggestions.currentIndex())
        index = next(i for i, item in enumerate(widget.candidates) if item["geonames_id"] == 444549)
        widget.suggestions.setCurrentIndex(index)
        widget.name.setText("Πάνω Πλακοτές")
        widget._edited()
        widget.refresh()
        self.assertEqual("Πάνω Πλακοτές", widget.name.text())
        self.assertEqual(before, self.snapshot())
        widget.confirm.click()
        self.assertEqual("Πάνω Πλακοτές", self.store.load(self.field)["confirmed_name"])
        self.assertEqual("Πλακοτές", self.store.load(self.field)["candidate"]["name"])

    def test_unretrieved_field_without_identity_never_causes_refresh_writes(self):
        field = self.db.execute("INSERT INTO fields(name,kaek) VALUES(?,?)", ("Unretrieved", "000123"))
        before = self.snapshot()
        widget = ToponymWidget(self.db, field)
        self.addCleanup(widget.deleteLater)
        widget.refresh()
        self.assertFalse(widget.confirm.isEnabled())
        self.assertIsNone(widget.context)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
