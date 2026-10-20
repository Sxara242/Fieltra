package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;
import org.json.*;

/** Cross-platform synthetic metrics; no engine execution authorized yet.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralUnionTest {
    static CadastralParcelRepository.InputSnapshot input(List<String> geometries) {
        List<CadastralParcelRepository.OverlayInput> sources=new ArrayList<>();
        for(int n=0;n<geometries.size();n++)sources.add(new CadastralParcelRepository.OverlayInput("parcel-"+n,1,"synthetic",1,"READY","snapshot-"+n,"source-hash",geometries.get(n),"EPSG:2100","{}"));
        return new CadastralParcelRepository.InputSnapshot(new CadastralProtocol.CultivatedFieldRef(CadastralSynthetic.SCOPE,CadastralSynthetic.FIELD),1,sources,"synthetic-fingerprint");
    }
    @Test public void fiveAdjacentAndOverlappingRectangles()throws Exception {
        for(int step:new int[]{20,10}) {
            List<String> sources=new ArrayList<>();for(int n=0;n<5;n++)sources.add(CadastralSynthetic.rectangle(686000+n*step,4249000,20,20));
            var captured=input(sources);String original=captured.toString();var result=CadastralUnion.build(captured,()->false);
            assertEquals(CadastralUnion.State.COMPLETE_DERIVED,result.state());assertEquals(5,result.usableCount());assertEquals(original,captured.toString());
            var shape=CadastralUnion.parse(result.geometryJson(),"EPSG:2100",new int[]{0},()->false);
            assertEquals(step==20?2000:1200,shape.getArea(),1e-8);assertEquals(step==20?240:160,shape.getLength(),1e-8);
            assertEquals(1,shape.getNumGeometries());assertEquals(1,result.exteriorVertices().size());
            assertEquals(0,((org.locationtech.jts.geom.Polygon)shape).getNumInteriorRing());
            var expected=CadastralUnion.parse(CadastralSynthetic.rectangle(686000,4249000,step==20?100:60,20),"EPSG:2100",new int[]{0},()->false);
            assertTrue(shape.equalsTopo(expected));
        }
    }
    @Test public void gapsHolesAndPointTouchSurvive()throws Exception {
        List<String> gaps=new ArrayList<>();for(int n=0;n<5;n++)gaps.add(CadastralSynthetic.rectangle(n*20.001,0,20,20));
        var result=CadastralUnion.build(input(gaps),()->false);var shape=CadastralUnion.parse(result.geometryJson(),"EPSG:2100",new int[]{0},()->false);assertEquals(5,shape.getNumGeometries());
        var shell=new JSONObject(CadastralSynthetic.rectangle(0,0,20,20));shell.getJSONArray("coordinates").put(new JSONObject(CadastralSynthetic.rectangle(5,5,10,10)).getJSONArray("coordinates").getJSONArray(0));
        var hole=CadastralUnion.build(input(List.of(shell.toString())),()->false);assertEquals(300,CadastralUnion.parse(hole.geometryJson(),"EPSG:2100",new int[]{0},()->false).getArea(),1e-8);
        var touch=CadastralUnion.build(input(List.of(CadastralSynthetic.rectangle(0,0,20,20),CadastralSynthetic.rectangle(20,20,20,20))),()->false);
        assertEquals("MultiPolygon",new JSONObject(touch.geometryJson()).getString("type"));
    }
    @Test public void missingConflictInvalidAndCancellationCannotComplete()throws Exception {
        var captured=input(List.of(CadastralSynthetic.rectangle(0,0,20,20)));var s=captured.inputs().get(0);
        for(String state:List.of("PENDING","CONFLICT","STALE","INVALID_SOURCE")) {
            var altered=new CadastralParcelRepository.OverlayInput(s.parcelUuid(),1,s.providerId(),1,state,null,null,null,s.sourceCrs(),"{}");
            var inputs=new CadastralParcelRepository.InputSnapshot(captured.field(),1,List.of(altered),"changed");
            assertNotEquals(CadastralUnion.State.COMPLETE_DERIVED,CadastralUnion.build(inputs,()->false).state());
        }
        assertThrows(InterruptedException.class,()->CadastralUnion.build(captured,()->true));
        var invalid=CadastralUnion.build(input(List.of("{\"type\":\"Polygon\",\"coordinates\":[[[0,0],[20,20],[20,0],[0,20],[0,0]]]}")),()->false);
        assertEquals(CadastralUnion.State.INVALID_SOURCE,invalid.state());
        var unsupported=new CadastralParcelRepository.OverlayInput(s.parcelUuid(),1,s.providerId(),1,"READY",s.snapshotUuid(),s.contentHash(),s.geometryJson(),"EPSG:3857","{}");
        assertEquals(CadastralUnion.State.INVALID_SOURCE,CadastralUnion.build(new CadastralParcelRepository.InputSnapshot(captured.field(),1,List.of(unsupported),"unsupported"),()->false).state());
    }
    @Test public void mixedFailurePriorityIsIndependentOfLinkOrder()throws Exception {
        var captured=input(List.of(CadastralSynthetic.rectangle(0,0,20,20)));var s=captured.inputs().get(0);
        for(var states:List.of(List.of("INVALID_SOURCE","STALE","CONFLICT"),List.of("CONFLICT","STALE","INVALID_SOURCE"))){
            List<CadastralParcelRepository.OverlayInput> sources=new ArrayList<>();
            for(String state:states)sources.add(new CadastralParcelRepository.OverlayInput(s.parcelUuid(),1,s.providerId(),1,state,null,null,null,s.sourceCrs(),"{}"));
            assertEquals(CadastralUnion.State.CONFLICT,CadastralUnion.build(new CadastralParcelRepository.InputSnapshot(captured.field(),1,sources,"fixture"),()->false).state());
        }
    }
}
