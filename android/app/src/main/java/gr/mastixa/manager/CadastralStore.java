package gr.mastixa.manager;

import android.content.ContentValues;
import android.database.sqlite.SQLiteDatabase;
import java.util.UUID;
import org.json.*;

/** Device-local cadastral reference. Never a cultivated parcel or sync-outbox entry. */
final class CadastralStore {
    static final boolean ANDROID_KAEK_SYNC_ENABLED=false;
    static final String[] COLUMNS={"id","field_id","kaek","payload","created_at","updated_at","revision"};
    record Record(String id,String fieldId,String kaek,JSONObject payload,long created,long updated,long revision){
        ParcelGeometry geometry(){return ParcelGeometry.normalize(payload.optString("original_geojson"),payload.optString("source_crs"));}
    }
    private final FarmStore farm;
    CadastralStore(FarmStore farm){this.farm=farm;}
    static void create(SQLiteDatabase db){db.execSQL("CREATE TABLE IF NOT EXISTS cadastral_reference(id TEXT PRIMARY KEY,field_id TEXT NOT NULL UNIQUE,kaek TEXT NOT NULL,payload TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,revision INTEGER NOT NULL CHECK(revision>0))");}
    Record parcel(String field){
        try(var c=farm.getReadableDatabase().rawQuery("SELECT c.id,c.field_id,c.kaek,c.payload,c.created_at,c.updated_at,c.revision FROM cadastral_reference c JOIN fields f ON f.id=c.field_id WHERE c.field_id=? AND f.deleted_at IS NULL AND TRIM(f.kaek)=c.kaek",new String[]{field})){
            return c.moveToFirst()?new Record(c.getString(0),c.getString(1),c.getString(2),new JSONObject(c.getString(3)),c.getLong(4),c.getLong(5),c.getLong(6)):null;
        }catch(JSONException e){throw new IllegalStateException("Invalid cadastral reference",e);}
    }
    void saveImported(String field,String kaek,ParcelGeometry geometry,String filename,long expected){
        if(!kaek.matches("[0-9]{12}")||filename.isBlank())throw new IllegalArgumentException("KAEK and source required");
        SQLiteDatabase db=farm.getWritableDatabase();db.beginTransaction();
        try{
            try(var f=db.rawQuery("SELECT 1 FROM fields WHERE id=? AND deleted_at IS NULL AND TRIM(kaek)=?",new String[]{field,kaek})){if(!f.moveToFirst())throw new IllegalArgumentException("Field/KAEK changed");}
            String id=UUID.randomUUID().toString();long now=System.currentTimeMillis(),created=now,revision=0;
            try(var c=db.rawQuery("SELECT id,created_at,revision FROM cadastral_reference WHERE field_id=?",new String[]{field})){if(c.moveToFirst()){id=c.getString(0);created=c.getLong(1);revision=c.getLong(2);}}
            if(revision!=expected)throw new IllegalArgumentException("Cadastral reference revision conflict");
            JSONObject payload=GeoStore.geometryPayload(geometry,filename,"").put("origin","local_file_import").put("verified_official",false);
            GeoStore.validatePayload("parcel",payload);
            ContentValues row=new ContentValues();row.put("id",id);row.put("field_id",field);row.put("kaek",kaek);row.put("payload",payload.toString());row.put("created_at",created);row.put("updated_at",now);row.put("revision",revision+1);
            if(revision==0)db.insertOrThrow("cadastral_reference",null,row);else db.update("cadastral_reference",row,"id=?",new String[]{id});
            db.setTransactionSuccessful();
        }catch(JSONException e){throw new IllegalArgumentException(e);}finally{db.endTransaction();}
    }
    // A changed KAEK hides the previous reference; replacement remains explicit and revision-checked.
    long revision(String field){try(var c=farm.getReadableDatabase().rawQuery("SELECT revision FROM cadastral_reference WHERE field_id=?",new String[]{field})){return c.moveToFirst()?c.getLong(0):0;}}
    static void validateBackup(JSONObject row)throws JSONException{
        if(row.getString("id").isBlank()||row.getString("field_id").isBlank()||!row.getString("kaek").matches("[0-9]{12}"))throw new IllegalArgumentException("Invalid cadastral identity");
        JSONObject payload=new JSONObject(row.getString("payload"));GeoStore.validatePayload("parcel",payload);
        if(!payload.getString("origin").equals("local_file_import")||payload.getBoolean("verified_official"))throw new IllegalArgumentException("Invalid cadastral provenance");
    }
}
