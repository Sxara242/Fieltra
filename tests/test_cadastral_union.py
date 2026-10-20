"""Synthetic topological acceptance source; hosted execution requires approval.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from shapely.geometry import box, mapping, Polygon, MultiPolygon, shape
from shapely.errors import GEOSException
from app.gis.cadastral_store import InputSnapshot, OverlayInput, RevisionConflict
from app.gis.cadastral_protocol import CultivatedFieldRef, FieldCadastralLink, RecordVersion
from app.gis.cadastral_union import build_union
from tests import test_cadastral_store as repository_specs
from tests.test_cadastral_migration import SCOPE, FIELD


def inputs(geometries):
    sources = tuple(OverlayInput(str(i),1,'synthetic',1,'READY',str(i),'source-hash',
        json.dumps(mapping(g)), 'EPSG:2100', '{}') for i,g in enumerate(geometries))
    return InputSnapshot(CultivatedFieldRef(SCOPE,FIELD),1,sources,'synthetic-fingerprint')


class UnionTests(unittest.TestCase):
    def test_mixed_failure_priority_is_independent_of_link_order(self):
        base=inputs([box(0,0,20,20)]);source=base.inputs[0]
        for states in (('INVALID_SOURCE','STALE','CONFLICT'),('CONFLICT','STALE','INVALID_SOURCE')):
            capture=replace(base,inputs=tuple(replace(source,state=state) for state in states))
            self.assertEqual('CONFLICT',build_union(capture).state)
        capture=replace(base,inputs=tuple(replace(source,state=state) for state in ('INVALID_SOURCE','STALE')))
        self.assertEqual('STALE',build_union(capture).state)

    def test_adjacent_five_and_overlap_exact_metrics_sources_unchanged(self):
        for step, area, perimeter in ((20,2000,240),(10,1200,160)):
            captured=inputs([box(i*step,0,i*step+20,20) for i in range(5)])
            before=repr(captured)
            result=build_union(captured)
            self.assertEqual('COMPLETE_DERIVED',result.state)
            derived=shape(json.loads(result.geometry_json))
            self.assertEqual('Polygon',derived.geom_type)
            self.assertTrue(derived.equals(box(0,0,100 if step==20 else 60,20)))
            self.assertAlmostEqual(area,derived.area)
            self.assertAlmostEqual(perimeter,derived.length)
            self.assertEqual(0,len(derived.interiors))
            self.assertEqual(1,len(result.exterior_vertices))
            self.assertEqual(before,repr(captured))

    def test_real_gaps_holes_multipart_point_touch(self):
        gaps=build_union(inputs([box(i*20.001,0,i*20.001+20,20) for i in range(5)]))
        self.assertEqual(5,len(shape(json.loads(gaps.geometry_json)).geoms))
        hole=Polygon([(0,0),(20,0),(20,20),(0,20),(0,0)],
                     [[(5,5),(15,5),(15,15),(5,15),(5,5)]])
        for original in (hole,MultiPolygon([box(0,0,20,20),box(40,0,60,20)])):
            result=build_union(inputs([original]))
            self.assertTrue(original.equals(shape(json.loads(result.geometry_json))))
        touch=build_union(inputs([box(0,0,20,20),box(20,20,40,40)]))
        self.assertEqual('MultiPolygon',shape(json.loads(touch.geometry_json)).geom_type)

    def test_missing_invalid_crs_conflict_and_engine_failure_never_complete(self):
        base=inputs([box(i*20,0,i*20+20,20) for i in range(5)])
        for alteration,state in ((dict(geometry_json=None),'PARTIAL'),(dict(source_crs='EPSG:3857'),'INVALID_SOURCE'),
                                 (dict(state='CONFLICT'),'CONFLICT'),(dict(state='STALE'),'STALE')):
            changed=replace(base,inputs=base.inputs[:-1]+(replace(base.inputs[-1],**alteration),))
            self.assertEqual(state,build_union(changed).state)
        invalid=inputs([Polygon([(0,0),(20,20),(20,0),(0,20),(0,0)])])
        self.assertEqual('INVALID_SOURCE',build_union(invalid).state)
        with patch('app.gis.cadastral_union.union_all',side_effect=GEOSException('synthetic')):
            self.assertEqual('UNION_FAILED',build_union(base).state)
        with self.assertRaises(InterruptedError):
            build_union(base,lambda:True)

    def test_master_fixture_business_figures_remain_independent(self):
        fixture=json.loads((Path(__file__).resolve().parents[1]/'shared/fixtures/cadastral_b021.json').read_text())
        before=json.dumps(fixture,sort_keys=True)
        sources=[Polygon(p['ring']) for p in fixture['parcels']]
        self.assertEqual('COMPLETE_DERIVED',build_union(inputs(sources)).state)
        self.assertEqual(before,json.dumps(fixture,sort_keys=True))
        self.assertEqual((3.25,100,20,200,50,150,8),tuple(fixture['business'][k] for k in
            ('cultivated_area_stremma','harvest_kg','sold_kg','income','expense','net','remaining_stock')))


class StaleUnionRepositoryTests(unittest.TestCase):
    setUp = repository_specs.RepositoryTests.setUp
    parcel = repository_specs.RepositoryTests.parcel
    def test_result_after_unlink_cannot_publish(self):
        p=self.parcel()
        self.repo.link(FieldCadastralLink(self.field,p.parcel_uuid,RecordVersion(1,0,0)),0)
        captured=self.repo.snapshot_inputs(self.field)
        result=build_union(captured)
        self.repo.unlink(self.field,p.parcel_uuid,1)
        with self.assertRaises(RevisionConflict):
            self.repo.publish_overlay(captured,result)
