package gr.mastixa.manager;

import org.json.*;
import org.locationtech.jts.geom.*;
import org.locationtech.jts.operation.valid.IsValidOp;
import org.locationtech.proj4j.*;
import net.sf.geographiclib.Geodesic;
import net.sf.geographiclib.PolygonArea;
import java.util.*;

/** Original XY ring order is preserved. WGS84 JSON always uses longitude, latitude. */
public final class ParcelGeometry {
    public record Vertex(int part,int ring,int index,double x,double y) {}
    public final String original,sourceCrs,wgs84;
    public final double area,perimeter,centroidLon,centroidLat;
    public final double[] bbox;
    private final Geometry geometry;
    private static final GeometryFactory FACTORY=new GeometryFactory();
    private static final CRSFactory CRS_FACTORY=new CRSFactory();
    private static final CoordinateTransformFactory TRANSFORMS=new CoordinateTransformFactory();
    private static final Map<String,String> CRS_DIMENSIONS=readCrsDimensions();
    private static Map<String,String> readCrsDimensions(){
        Map<String,String> result=new HashMap<>();
        try(var stream=ParcelGeometry.class.getResourceAsStream("/gr/mastixa/manager/crs-2d.txt")){
            if(stream==null)throw new IllegalStateException("CRS dimensional metadata missing");
            try(var reader=new java.io.BufferedReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8))){String line;while((line=reader.readLine())!=null)if(!line.isBlank()&&!line.startsWith("#")){String[] parts=line.split(" ");result.put("EPSG:"+parts[0],parts[1]);}}
        }catch(java.io.IOException e){throw new IllegalStateException("CRS metadata unreadable",e);}return Map.copyOf(result);
    }

    private ParcelGeometry(String original,String crs,String wgs,Geometry shape,double area,double perimeter,double lon,double lat){
        this.original=original;sourceCrs=crs;wgs84=wgs;geometry=shape;this.area=area;this.perimeter=perimeter;centroidLon=lon;centroidLat=lat;
        Envelope box=shape.getEnvelopeInternal();bbox=new double[]{box.getMinX(),box.getMinY(),box.getMaxX(),box.getMaxY()};
    }
    public static void position(double lon,double lat){if(!Double.isFinite(lon)||!Double.isFinite(lat)||lon< -180||lon>180||lat< -90||lat>90)throw new IllegalArgumentException("Invalid WGS84 longitude/latitude");}
    public boolean contains(double lon,double lat){position(lon,lat);return geometry.covers(FACTORY.createPoint(new Coordinate(lon,lat)));}
    public enum FixRelation { INSIDE, OUTSIDE, UNCERTAIN }
    /** Approximate local tangent-plane distance to every boundary, including holes.
     * Reported phone accuracy is an uncertainty estimate, never a survey guarantee. */
    public FixRelation classifyFix(double lon,double lat,double accuracy){
        position(lon,lat);if(!Double.isFinite(accuracy)||accuracy<0)throw new IllegalArgumentException("Invalid GPS accuracy");
        Geometry local=geometry.getBoundary().copy();
        local.apply((CoordinateFilter)c->{var relative=Geodesic.WGS84.Inverse(lat,lon,c.y,c.x);double bearing=Math.toRadians(relative.azi1);c.x=relative.s12*Math.sin(bearing);c.y=relative.s12*Math.cos(bearing);});local.geometryChanged();
        double distance=local.distance(FACTORY.createPoint(new Coordinate(0,0)));
        if(distance<=accuracy+.01)return FixRelation.UNCERTAIN;
        return contains(lon,lat)?FixRelation.INSIDE:FixRelation.OUTSIDE;
    }
    public static String crs(String value){
        String name=value.trim().toUpperCase(Locale.ROOT);
        if(!name.matches("EPSG:[0-9]{4,6}"))throw new IllegalArgumentException("Source EPSG CRS required");
        if(!CRS_DIMENSIONS.containsKey(name))throw new IllegalArgumentException("Unsupported CRS dimensions, units or axes. Use a 2D east/north CRS, or convert on Desktop.");
        CRS_FACTORY.createFromName(name);return name;
    }
    public static double[] transform(double x,double y,String source,String target){
        if(!Double.isFinite(x)||!Double.isFinite(y))throw new IllegalArgumentException("Invalid source coordinate");
        if("G".equals(CRS_DIMENSIONS.get(crs(source))))position(x,y);
        var operation=TRANSFORMS.createTransform(CRS_FACTORY.createFromName(crs(source)),CRS_FACTORY.createFromName(crs(target)));
        var result=new ProjCoordinate();operation.transform(new ProjCoordinate(x,y),result);
        if(!Double.isFinite(result.x)||!Double.isFinite(result.y))throw new IllegalArgumentException("Coordinate transformation failed");
        return new double[]{result.x,result.y};
    }
    public static JSONArray parts(JSONObject value)throws JSONException{
        String type=value.getString("type");JSONArray coords=value.getJSONArray("coordinates");
        if(type.equals("Polygon"))return new JSONArray().put(coords);
        if(type.equals("MultiPolygon"))return coords;
        throw new IllegalArgumentException("Only Polygon / MultiPolygon supported");
    }
    public static List<Vertex> vertices(String json){
        try{
            List<Vertex> result=new ArrayList<>();var polygons=parts(new JSONObject(json));
            for(int p=0;p<polygons.length();p++){var polygon=polygons.getJSONArray(p);
                for(int r=0;r<polygon.length();r++){var ring=polygon.getJSONArray(r);
                    for(int v=0;v<ring.length()-1;v++){var xy=ring.getJSONArray(v);result.add(new Vertex(p+1,r+1,v+1,xy.getDouble(0),xy.getDouble(1)));}
                }
            }return List.copyOf(result);
        }catch(JSONException e){throw new IllegalArgumentException("Invalid geometry JSON",e);}
    }
    private static Geometry shape(JSONObject value)throws JSONException{
        var input=parts(value);if(input.length()==0)throw new IllegalArgumentException("Empty geometry");
        List<Polygon> polygons=new ArrayList<>();int count=0;
        for(int p=0;p<input.length();p++){
            var polygon=input.getJSONArray(p);if(polygon.length()==0)throw new IllegalArgumentException("Empty polygon");
            List<LinearRing> rings=new ArrayList<>();
            for(int r=0;r<polygon.length();r++){
                var ring=polygon.getJSONArray(r);if(ring.length()<4)throw new IllegalArgumentException("Ring needs three vertices and closure");
                count+=ring.length()-1;if(count>20000)throw new IllegalArgumentException("Too many vertices");
                Coordinate[] coordinates=new Coordinate[ring.length()];
                for(int n=0;n<ring.length();n++){
                    var xy=ring.getJSONArray(n);if(xy.length()!=2||!(xy.get(0) instanceof Number)||!(xy.get(1) instanceof Number))throw new IllegalArgumentException("Expected numeric XY coordinates");
                    double x=xy.getDouble(0),y=xy.getDouble(1);if(!Double.isFinite(x)||!Double.isFinite(y))throw new IllegalArgumentException("Non-finite coordinate");
                    coordinates[n]=new Coordinate(x,y);
                    if(n>0&&coordinates[n].equals2D(coordinates[n-1]))throw new IllegalArgumentException("Duplicate adjacent vertex");
                }
                if(!coordinates[0].equals2D(coordinates[coordinates.length-1]))throw new IllegalArgumentException("Unclosed ring");
                rings.add(FACTORY.createLinearRing(coordinates));
            }
            polygons.add(FACTORY.createPolygon(rings.get(0),rings.subList(1,rings.size()).toArray(new LinearRing[0])));
        }
        Geometry geometry=value.getString("type").equals("Polygon")?polygons.get(0):FACTORY.createMultiPolygon(polygons.toArray(new Polygon[0]));
        IsValidOp valid=new IsValidOp(geometry);if(geometry.isEmpty()||!valid.isValid()||geometry.getArea()<=0)throw new IllegalArgumentException("Invalid polygon: "+valid.getValidationError());
        return geometry;
    }
    public static ParcelGeometry normalize(String json,String source){
        try{
            source=crs(source);JSONObject original=new JSONObject(json);shape(original);
            JSONObject normalized=new JSONObject(original.toString());normalized.remove("crs");normalized.remove("bbox");var polygons=parts(normalized);
            var operation=TRANSFORMS.createTransform(CRS_FACTORY.createFromName(source),CRS_FACTORY.createFromName("EPSG:4326"));
            for(int p=0;p<polygons.length();p++){var polygon=polygons.getJSONArray(p);
                for(int r=0;r<polygon.length();r++){var ring=polygon.getJSONArray(r);
                    for(int n=0;n<ring.length();n++){var xy=ring.getJSONArray(n);if("G".equals(CRS_DIMENSIONS.get(source)))position(xy.getDouble(0),xy.getDouble(1));var result=new ProjCoordinate();operation.transform(new ProjCoordinate(xy.getDouble(0),xy.getDouble(1)),result);position(result.x,result.y);xy.put(0,result.x);xy.put(1,result.y);}
                }
            }
            Geometry shape=shape(normalized);Envelope box=shape.getEnvelopeInternal();
            if(box.getWidth()>5||box.getHeight()>5||Math.max(Math.abs(box.getMinY()),Math.abs(box.getMaxY()))>85)throw new IllegalArgumentException("Geometry exceeds local parcel scope (5 degrees / polar / antimeridian)");
            double area=0,perimeter=0;
            for(int p=0;p<polygons.length();p++){var polygon=polygons.getJSONArray(p);
                for(int r=0;r<polygon.length();r++){var ring=polygon.getJSONArray(r);var measure=new PolygonArea(Geodesic.WGS84,false);
                    for(int n=0;n<ring.length()-1;n++){var xy=ring.getJSONArray(n);measure.AddPoint(xy.getDouble(1),xy.getDouble(0));}
                    var result=measure.Compute(false,true);area+=(r==0?1:-1)*Math.abs(result.area);perimeter+=result.perimeter;
                }
            }
            if(area<=0||!Double.isFinite(area))throw new IllegalArgumentException("Invalid geodesic area");
            Geometry projected=shape.copy();var mercator=TRANSFORMS.createTransform(CRS_FACTORY.createFromName("EPSG:4326"),CRS_FACTORY.createFromName("EPSG:3857"));
            projected.apply((CoordinateFilter)c->{var result=new ProjCoordinate();mercator.transform(new ProjCoordinate(c.x,c.y),result);c.x=result.x;c.y=result.y;});projected.geometryChanged();
            Point centroid=projected.getCentroid();double[] center=transform(centroid.getX(),centroid.getY(),"EPSG:3857","EPSG:4326");
            return new ParcelGeometry(original.toString(),source,normalized.toString(),shape,area,perimeter,center[0],center[1]);
        }catch(JSONException e){throw new IllegalArgumentException("Invalid geometry JSON",e);}
    }
    public static ParcelGeometry manual(String text,String source){
        try{
            JSONArray ring=new JSONArray();for(String line:text.split("\\R"))if(!line.isBlank()){
                String[] values=line.trim().replace(';',' ').replace(',',' ').split("\\s+");
                if(values.length!=2)throw new IllegalArgumentException("Each line: X Y / longitude latitude");
                ring.put(new JSONArray().put(Double.parseDouble(values[0])).put(Double.parseDouble(values[1])));
            }
            if(ring.length()>0){var first=ring.getJSONArray(0);var last=ring.getJSONArray(ring.length()-1);if(first.getDouble(0)!=last.getDouble(0)||first.getDouble(1)!=last.getDouble(1))ring.put(new JSONArray(first.toString()));}
            return normalize(new JSONObject().put("type","Polygon").put("coordinates",new JSONArray().put(ring)).toString(),source);
        }catch(JSONException e){throw new IllegalArgumentException(e);}
    }
}
