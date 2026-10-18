package gr.mastixa.manager;

import android.content.ContentValues;
import android.database.sqlite.SQLiteDatabase;
import org.json.*;
import java.util.*;

/** Versioned profile-local GIS objects. Indexed identity/lifecycle plus typed JSON payload. */
public final class GeoStore {
    public static final String[] COLUMNS={"id","field_id","kind","payload","created_at","updated_at","deleted_at","last_sync_at","revision"};
    public static final List<String> POINT_TYPES=List.of("tree","valve","irrigation","tank","borehole","problem","note","other");
    public record Record(String id,String fieldId,String kind,JSONObject payload,long created,long updated,long revision){}
    private final FarmStore store;
    public GeoStore(FarmStore store){this.store=store;}
    static void create(SQLiteDatabase db){
        db.execSQL("CREATE TABLE gis_records(id TEXT PRIMARY KEY,field_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('parcel','point','track')),payload TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,deleted_at INTEGER,last_sync_at INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL CHECK(revision>0))");
        db.execSQL("CREATE INDEX gis_field_kind ON gis_records(field_id,kind,deleted_at)");
        db.execSQL("CREATE UNIQUE INDEX gis_one_parcel ON gis_records(field_id) WHERE kind='parcel'");
    }
    public List<Record> records(String fieldId,String kind){
        List<Record> rows=new ArrayList<>();String where="g.deleted_at IS NULL AND f.deleted_at IS NULL";List<String> args=new ArrayList<>();
        if(fieldId!=null){where+=" AND g.field_id=?";args.add(fieldId);}if(kind!=null){where+=" AND g.kind=?";args.add(kind);}
        try(var c=store.getReadableDatabase().rawQuery("SELECT g.id,g.field_id,g.kind,g.payload,g.created_at,g.updated_at,g.revision FROM gis_records g JOIN fields f ON f.id=g.field_id WHERE "+where+" ORDER BY g.created_at,g.id",args.toArray(new String[0]))){
            while(c.moveToNext())rows.add(new Record(c.getString(0),c.getString(1),c.getString(2),new JSONObject(c.getString(3)),c.getLong(4),c.getLong(5),c.getLong(6)));
        }catch(JSONException e){throw new IllegalStateException("Invalid stored GIS data",e);}return rows;
    }
    public Record parcel(String fieldId){var rows=records(fieldId,"parcel");return rows.isEmpty()?null:rows.get(0);}
    public static ParcelGeometry geometry(Record row){return ParcelGeometry.normalize(row.payload().optString("original_geojson"),row.payload().optString("source_crs"));}
    static JSONObject geometryPayload(ParcelGeometry geometry,String source,String sourceDate)throws JSONException{
        return new JSONObject().put("original_geojson",geometry.original).put("source_crs",geometry.sourceCrs).put("wgs84_geojson",geometry.wgs84)
            .put("area_m2",geometry.area).put("perimeter_m",geometry.perimeter).put("centroid_lon",geometry.centroidLon).put("centroid_lat",geometry.centroidLat)
            .put("bbox",new JSONArray(geometry.bbox)).put("geometry_source",source).put("geometry_source_date",sourceDate);
    }
    public String saveGeometry(String fieldId,ParcelGeometry geometry,String source,String sourceDate,long expectedRevision){
        try{
            JSONObject payload=geometryPayload(geometry,source,sourceDate);
            return save(fieldId,fieldId,"parcel",payload,expectedRevision);
        }catch(JSONException e){throw new IllegalArgumentException(e);}
    }
    public String savePoint(String id,String fieldId,String type,String title,String notes,double lon,double lat,double accuracy,long expectedRevision){
        try{return save(id,fieldId,"point",new JSONObject().put("point_type",type).put("title",title.trim()).put("notes",notes).put("longitude",lon).put("latitude",lat).put("accuracy",accuracy),expectedRevision);}
        catch(JSONException e){throw new IllegalArgumentException(e);}
    }
    /** Timestamp belongs to the received GPS fix, not to the later Save action. */
    public String saveGpsPoint(String id,String fieldId,String type,String title,String notes,double lon,double lat,double accuracy,long fixTime,long expectedRevision){
        if(fixTime<=0)throw new IllegalArgumentException("GPS fix timestamp required");
        try{return save(id,fieldId,"point",new JSONObject().put("point_type",type).put("title",title.trim()).put("notes",notes).put("longitude",lon).put("latitude",lat).put("accuracy",accuracy).put("fix_time_ms",fixTime),expectedRevision);}
        catch(JSONException e){throw new IllegalArgumentException(e);}
    }
    public String save(String id,String fieldId,String kind,JSONObject payload,long expectedRevision){
        validatePayload(kind,payload);long now=System.currentTimeMillis();String identity=id==null?UUID.randomUUID().toString():id;
        SQLiteDatabase db=store.getWritableDatabase();db.beginTransaction();
        try{
            try(var field=db.rawQuery("SELECT 1 FROM fields WHERE id=? AND deleted_at IS NULL",new String[]{fieldId})){if(!field.moveToFirst())throw new IllegalArgumentException("Missing field");}
            long created=now,revision=0;
            try(var c=db.rawQuery("SELECT field_id,kind,created_at,revision,deleted_at FROM gis_records WHERE id=?",new String[]{identity})){
                if(c.moveToFirst()){if(!c.getString(0).equals(fieldId)||!c.getString(1).equals(kind)||!c.isNull(4))throw new IllegalArgumentException("GIS identity conflict");created=c.getLong(2);revision=c.getLong(3);}
            }
            if(revision!=expectedRevision)throw new IllegalArgumentException("Τα δεδομένα άλλαξαν. Άνοιξε ξανά / GIS revision conflict");
            ContentValues row=new ContentValues();row.put("id",identity);row.put("field_id",fieldId);row.put("kind",kind);row.put("payload",payload.toString());row.put("created_at",created);row.put("updated_at",now);row.put("revision",revision+1);
            if(revision==0)db.insertOrThrow("gis_records",null,row);else db.update("gis_records",row,"id=?",new String[]{identity});
            enqueue(db,identity,revision==0?"create":"update",revision+1,now);db.setTransactionSuccessful();return identity;
        }finally{db.endTransaction();}
    }
    private static void enqueue(SQLiteDatabase db,String id,String operation,long revision,long now){
        ContentValues row=new ContentValues();row.put("operation_id",UUID.randomUUID().toString());row.put("entity_id",id);row.put("entity","gis_records");row.put("operation",operation);row.put("revision",revision);row.put("created_at",now);db.insertOrThrow("pending_changes",null,row);
    }
    public void delete(String id,long expectedRevision){
        SQLiteDatabase db=store.getWritableDatabase();db.beginTransaction();
        try{
            long now=System.currentTimeMillis();ContentValues row=new ContentValues();row.put("deleted_at",now);row.put("updated_at",now);row.put("revision",expectedRevision+1);
            if(db.update("gis_records",row,"id=? AND revision=? AND deleted_at IS NULL",new String[]{id,Long.toString(expectedRevision)})!=1)throw new IllegalArgumentException("GIS revision conflict");
            enqueue(db,id,"delete",expectedRevision+1,now);db.setTransactionSuccessful();
        }finally{db.endTransaction();}
    }
    static void deleteForField(SQLiteDatabase db,String fieldId,long now){
        try(var c=db.rawQuery("SELECT id,revision FROM gis_records WHERE field_id=? AND deleted_at IS NULL",new String[]{fieldId})){
            while(c.moveToNext()){String id=c.getString(0);long revision=c.getLong(1)+1;ContentValues row=new ContentValues();row.put("deleted_at",now);row.put("updated_at",now);row.put("revision",revision);db.update("gis_records",row,"id=?",new String[]{id});enqueue(db,id,"delete",revision,now);}
        }
    }
    public static void validatePayload(String kind,JSONObject value){
        try{
            if(value.toString().length()>4*1024*1024)throw new IllegalArgumentException("GIS object exceeds 4 MB");
            if(kind.equals("parcel")){
                var geometry=ParcelGeometry.normalize(value.getString("original_geojson"),value.getString("source_crs"));
                String normalized=value.getString("wgs84_geojson");
                ParcelGeometry.normalize(normalized,"EPSG:4326");
                if(!ParcelGeometry.vertices(geometry.wgs84).equals(ParcelGeometry.vertices(normalized))||!new JSONObject(geometry.wgs84).getString("type").equals(new JSONObject(normalized).getString("type")))throw new IllegalArgumentException("Normalized geometry mismatch");
                for(String key:List.of("area_m2","perimeter_m","centroid_lon","centroid_lat"))if(!Double.isFinite(value.getDouble(key)))throw new IllegalArgumentException("Invalid geometry metrics");
                if(Math.abs(geometry.area-value.getDouble("area_m2"))>.01||Math.abs(geometry.perimeter-value.getDouble("perimeter_m"))>.001||Math.abs(geometry.centroidLon-value.getDouble("centroid_lon"))>1e-8||Math.abs(geometry.centroidLat-value.getDouble("centroid_lat"))>1e-8)throw new IllegalArgumentException("Geometry metrics mismatch");
                var bbox=value.getJSONArray("bbox");if(bbox.length()!=4)throw new IllegalArgumentException("Invalid bbox");for(int i=0;i<4;i++)if(!Double.isFinite(bbox.getDouble(i))||Math.abs(bbox.getDouble(i)-geometry.bbox[i])>1e-8)throw new IllegalArgumentException("BBox mismatch");
                value.getString("geometry_source");value.getString("geometry_source_date");
            }else if(kind.equals("point")){
                if(!POINT_TYPES.contains(value.getString("point_type"))||value.getString("title").isBlank())throw new IllegalArgumentException("Point type/title required");
                ParcelGeometry.position(value.getDouble("longitude"),value.getDouble("latitude"));double accuracy=value.getDouble("accuracy");if(!Double.isFinite(accuracy)||accuracy<0)throw new IllegalArgumentException("Invalid accuracy");value.getString("notes");
                if(value.has("fix_time_ms")&&(!(value.get("fix_time_ms") instanceof Number)||value.getDouble("fix_time_ms")!=value.getLong("fix_time_ms")||value.getLong("fix_time_ms")<=0))throw new IllegalArgumentException("Invalid GPS fix timestamp");
            }else if(kind.equals("track")){
                var points=value.getJSONArray("positions");if(points.length()>20000)throw new IllegalArgumentException("Track exceeds 20000 points");
                long previous=0;for(int i=0;i<points.length();i++){var p=points.getJSONArray(i);if(p.length()!=4)throw new IllegalArgumentException("Track position requires lon/lat/accuracy/time");ParcelGeometry.position(p.getDouble(0),p.getDouble(1));if(!Double.isFinite(p.getDouble(2))||p.getDouble(2)<0||p.getLong(3)<previous)throw new IllegalArgumentException("Invalid track fix");previous=p.getLong(3);}
                if(!List.of("recording","paused","stopped").contains(value.getString("state"))||value.getLong("duration_ms")<0||value.getLong("started_at")<0||value.getLong("ended_at")<0||!Double.isFinite(value.getDouble("distance_m"))||value.getDouble("distance_m")<0)throw new IllegalArgumentException("Invalid track state");value.getString("title");
                Set<Integer> starts=new HashSet<>();var segments=value.optJSONArray("segment_starts");int last=-1;
                if(segments!=null)for(int i=0;i<segments.length();i++){int index=segments.getInt(i);if(index<=last||index<0||index>=points.length())throw new IllegalArgumentException("Invalid track segment");starts.add(index);last=index;}
                if(points.length()>0&&segments!=null&&!starts.contains(0))throw new IllegalArgumentException("First track segment missing");
                double distance=0;for(int i=1;i<points.length();i++)if(!starts.contains(i)){var a=points.getJSONArray(i-1);var b=points.getJSONArray(i);distance+=net.sf.geographiclib.Geodesic.WGS84.Inverse(a.getDouble(1),a.getDouble(0),b.getDouble(1),b.getDouble(0)).s12;}
                if(Math.abs(distance-value.getDouble("distance_m"))>.01)throw new IllegalArgumentException("Track distance mismatch");
            }else throw new IllegalArgumentException("Unknown GIS kind");
        }catch(JSONException e){throw new IllegalArgumentException("Invalid GIS payload",e);}
    }
}
