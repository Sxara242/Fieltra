package gr.mastixa.manager;

import java.util.*;
import java.util.concurrent.*;
import java.nio.charset.StandardCharsets;
import org.json.*;
import org.locationtech.jts.geom.*;
import org.locationtech.jts.operation.valid.IsValidOp;
import org.locationtech.jts.operation.overlayng.UnaryUnionNG;

/** Unsnapped floating-precision topology, no buffer/repair/snap fallback.
 * Never called by map/GPS code. Source strings remain immutable.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralUnion {
    private CadastralUnion() {}
    public enum State { NONE,PENDING,PARTIAL,COMPLETE_DERIVED,STALE,CONFLICT,INVALID_SOURCE,UNION_FAILED,TOO_LARGE }
    public static final int MAX_VERTICES=100000,MAX_BYTES=16*1024*1024;
    public static final String ENGINE="JTS/1.20.0/UnaryUnionNG";
    private static final GeometryFactory FACTORY=new GeometryFactory(new PrecisionModel(PrecisionModel.FLOATING),2100);
    public record XY(double x,double y) {}
    public record Result(State state,String fingerprint,int requiredCount,int usableCount,String geometryJson,
            List<List<XY>> exteriorVertices,String engine,String diagnostic) {
        public Result {
            if(state==null||usableCount<0||usableCount>requiredCount||state==State.COMPLETE_DERIVED&&(requiredCount==0||usableCount!=requiredCount||geometryJson==null)||
                state!=State.COMPLETE_DERIVED&&geometryJson!=null)throw new IllegalArgumentException("Invalid overlay state/completeness");
            exteriorVertices=exteriorVertices.stream().map(List::copyOf).toList();
        }
    }
    private static Result result(State state,CadastralParcelRepository.InputSnapshot input,int usable,String diagnostic,Geometry geometry) {
        List<List<XY>> exteriors=new ArrayList<>();
        if(geometry!=null)for(int p=0;p<geometry.getNumGeometries();p++) {
            Coordinate[] ring=((Polygon)geometry.getGeometryN(p)).getExteriorRing().getCoordinates();List<XY> vertices=new ArrayList<>();
            for(int n=0;n<ring.length-1;n++)vertices.add(new XY(ring[n].x,ring[n].y));exteriors.add(List.copyOf(vertices));
        }
        return new Result(state,input.fingerprint(),input.inputs().size(),usable,geometry==null?null:geoJson(geometry),exteriors,ENGINE,diagnostic);
    }
    public static Future<Result> submit(ExecutorService executor,CadastralParcelRepository.InputSnapshot input,CadastralMigration.Cancellation cancel) {
        return executor.submit(()->build(input,cancel));
    }
    public static Result build(CadastralParcelRepository.InputSnapshot input,CadastralMigration.Cancellation cancel) throws InterruptedException {
        int required=input.inputs().size(),usable=0;long bytes=0;int[] vertices={0};long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
        if(required==0)return result(State.NONE,input,0,"",null);
        for(State priority:List.of(State.CONFLICT,State.STALE,State.INVALID_SOURCE))
            if(input.inputs().stream().anyMatch(s->priority.name().equals(s.state())))return result(priority,input,0,"",null);
        for(var source:input.inputs()) {
            bytes+=source.geometryJson()==null?0:source.geometryJson().getBytes(StandardCharsets.UTF_8).length;
            if(bytes>MAX_BYTES)return result(State.TOO_LARGE,input,0,"geometry_byte_budget",null);
        }
        if(bytes>MAX_BYTES)return result(State.TOO_LARGE,input,0,"geometry_byte_budget",null);
        List<Geometry> shapes=new ArrayList<>();
        try {
            for(var source:input.inputs()) {
                check(cancel,deadline);
                if(!source.state().equals("READY")||source.geometryJson()==null||source.snapshotUuid()==null||source.contentHash()==null)continue;
                if(source.sourceCrs()==null||!Set.of("EPSG:2100","EPSG:4326").contains(source.sourceCrs()))return result(State.INVALID_SOURCE,input,usable,"unsupported_crs",null);
                Geometry geometry=parse(source.geometryJson(),source.sourceCrs(),vertices,cancel);
                shapes.add(geometry);usable++;
            }
            if(usable!=required)return result(usable==0?State.PENDING:State.PARTIAL,input,usable,"missing_required_source",null);
        } catch(Budget e){return result(State.TOO_LARGE,input,usable,"source_vertex_budget",null);}
          catch(CancellationException e){throw new InterruptedException("Cancelled");}
          catch(JSONException e){return result(State.INVALID_SOURCE,input,usable,"invalid_source_json",null);}
          catch(RuntimeException e){return result(State.INVALID_SOURCE,input,usable,"invalid_source_or_transform/"+e.getClass().getSimpleName(),null);}
          catch(TimeoutException e){return result(State.TOO_LARGE,input,usable,"worker_time_budget",null);}
        try {
            check(cancel,deadline);
            // FLOATING avoids fixed precision rounding. Do not use OverlayNGRobust:
            // its fallback strategy can snap after a topology failure.
            Geometry combined=UnaryUnionNG.union(shapes,FACTORY,new PrecisionModel(PrecisionModel.FLOATING));
            check(cancel,deadline);
            if(combined.getNumPoints()>MAX_VERTICES)return result(State.TOO_LARGE,input,usable,"derived_vertex_budget",null);
            if(!(combined instanceof Polygon||combined instanceof MultiPolygon)||combined.isEmpty()||!new IsValidOp(combined).isValid()||!Double.isFinite(combined.getArea())||!Double.isFinite(combined.getLength()))
                return result(State.UNION_FAILED,input,usable,"invalid_derived_topology",null);
            return result(State.COMPLETE_DERIVED,input,usable,"",combined);
        } catch(TopologyException e){return result(State.UNION_FAILED,input,usable,"topology_engine_failure",null);}
          catch(TimeoutException e){return result(State.TOO_LARGE,input,usable,"worker_time_budget",null);}
    }
    private static void check(CadastralMigration.Cancellation cancel,long deadline)throws InterruptedException,TimeoutException {
        if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedException("Cancelled");
        if(System.nanoTime()>deadline)throw new TimeoutException("Budget");
    }
    private static final class Budget extends IllegalArgumentException {}
    static Geometry parse(String json,String crs,int[] count,CadastralMigration.Cancellation cancel)throws JSONException,InterruptedException {
        JSONObject value=new JSONObject(json);String type=value.getString("type");
        if(!type.equals("Polygon")&&!type.equals("MultiPolygon"))throw new IllegalArgumentException("Polygon source required");
        JSONArray parts=type.equals("Polygon")?new JSONArray().put(value.getJSONArray("coordinates")):value.getJSONArray("coordinates");
        if(parts.length()==0)throw new IllegalArgumentException("Empty source");List<Polygon> result=new ArrayList<>();
        for(int p=0;p<parts.length();p++) {
            JSONArray polygon=parts.getJSONArray(p);if(polygon.length()==0)throw new IllegalArgumentException("Empty part");List<LinearRing> rings=new ArrayList<>();
            for(int r=0;r<polygon.length();r++) {
                JSONArray ring=polygon.getJSONArray(r);if(ring.length()<4)throw new IllegalArgumentException("Short ring");
                if((count[0]+=ring.length())>MAX_VERTICES)throw new Budget();Coordinate[] coordinates=new Coordinate[ring.length()];
                for(int n=0;n<ring.length();n++) {
                    if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedException("Cancelled");
                    JSONArray xy=ring.getJSONArray(n);if(xy.length()!=2||!(xy.get(0) instanceof Number)||!(xy.get(1) instanceof Number))throw new IllegalArgumentException("Numeric XY required");
                    double x=xy.getDouble(0),y=xy.getDouble(1);if(!Double.isFinite(x)||!Double.isFinite(y))throw new IllegalArgumentException("Finite XY required");
                    if(crs.equals("EPSG:4326")) {
                        if(x<19||x>30||y<34||y>42.5)throw new IllegalArgumentException("Outside Greek extent");
                    }
                    coordinates[n]=new Coordinate(x,y);
                }
                if(!coordinates[0].equals2D(coordinates[coordinates.length-1]))throw new IllegalArgumentException("Unclosed ring");rings.add(FACTORY.createLinearRing(coordinates));
            }
            result.add(FACTORY.createPolygon(rings.get(0),rings.subList(1,rings.size()).toArray(new LinearRing[0])));
        }
        Geometry geometry=type.equals("Polygon")?result.get(0):FACTORY.createMultiPolygon(result.toArray(new Polygon[0]));
        if(geometry.isEmpty()||geometry.getArea()<=0||!Double.isFinite(geometry.getArea())||!Double.isFinite(geometry.getLength())||!new IsValidOp(geometry).isValid())throw new IllegalArgumentException("Invalid original polygon topology");
        if(crs.equals("EPSG:4326")) {
            var factory=new org.locationtech.proj4j.CRSFactory();
            var operation=new org.locationtech.proj4j.CoordinateTransformFactory().createTransform(factory.createFromName(crs),factory.createFromName("EPSG:2100"));
            geometry=geometry.copy();geometry.apply((CoordinateFilter)c->{
                if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new CancellationException("Cancelled");
                var transformed=new org.locationtech.proj4j.ProjCoordinate();operation.transform(new org.locationtech.proj4j.ProjCoordinate(c.x,c.y),transformed);
                if(!Double.isFinite(transformed.x)||!Double.isFinite(transformed.y))throw new IllegalArgumentException("Non-finite transformed XY");c.x=transformed.x;c.y=transformed.y;
            });geometry.geometryChanged();
            if(geometry.isEmpty()||geometry.getArea()<=0||!Double.isFinite(geometry.getArea())||!Double.isFinite(geometry.getLength())||!new IsValidOp(geometry).isValid())throw new IllegalArgumentException("Invalid transformed polygon topology");
        }
        return geometry;
    }
    static String geoJson(Geometry geometry) {
        try {
            JSONArray parts=new JSONArray();
            for(int p=0;p<geometry.getNumGeometries();p++) {
                Polygon polygon=(Polygon)geometry.getGeometryN(p);JSONArray rings=new JSONArray().put(ring(polygon.getExteriorRing().getCoordinates()));
                for(int h=0;h<polygon.getNumInteriorRing();h++)rings.put(ring(polygon.getInteriorRingN(h).getCoordinates()));parts.put(rings);
            }
            return new JSONObject().put("type",geometry instanceof Polygon?"Polygon":"MultiPolygon").put("coordinates",geometry instanceof Polygon?parts.getJSONArray(0):parts).toString();
        }catch(JSONException e){throw new IllegalArgumentException("Cannot serialize derived geometry",e);}
    }
    private static JSONArray ring(Coordinate[] coordinates)throws JSONException {
        JSONArray ring=new JSONArray();for(var c:coordinates)ring.put(new JSONArray().put(c.x).put(c.y));return ring;
    }
}
