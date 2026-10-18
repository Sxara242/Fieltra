package gr.mastixa.manager;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.json.*;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import static org.junit.Assert.*;

public class GeoStoreTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private ParcelGeometry fixture(){return ParcelGeometry.manual("26 38\n26.001 38\n26.001 38.001\n26 38.001","EPSG:4326");}
    @Test public void geometryPointsBackupConflictsAndFieldTombstone()throws Exception{
        assertTrue(context.getPackageName().endsWith(".checks"));String name="gis-store-test.db";context.deleteDatabase(name);File recovery=new File(context.getCacheDir(),"gis-recovery.json");
        try(var farm=new FarmStore(context,name)){
            farm.addField("Synthetic GIS field",1);String field=farm.fields().get(0).id();GeoStore geo=new GeoStore(farm);
            geo.saveGeometry(field,fixture(),"manual","",0);String point=geo.savePoint(null,field,"tree","Tree","",26.0005,38.0005,5,0);
            // Logical backup format 19 is separate from SQLite database version 15.
            byte[] backup=LocalBackup.snapshot(farm);assertEquals(19,new JSONObject(new String(backup,StandardCharsets.UTF_8)).getInt("schema"));assertEquals(1,LocalBackup.inspect(farm,backup));
            try{geo.saveGeometry(field,fixture(),"manual","",0);fail("Expected stale write rejection");}catch(IllegalArgumentException expected){}
            assertArrayEquals(backup,LocalBackup.snapshot(farm));
            geo.delete(point,1);assertTrue(geo.records(field,"point").isEmpty());LocalBackup.restore(farm,backup,recovery);assertEquals(1,geo.records(field,"point").size());
            farm.deleteField(field);assertTrue(geo.records(null,null).isEmpty());assertEquals(0,LocalBackup.inspect(farm,LocalBackup.snapshot(farm)));
            try(var c=farm.getReadableDatabase().rawQuery("SELECT count(*) FROM gis_records WHERE deleted_at IS NOT NULL",null)){c.moveToFirst();assertEquals(2,c.getInt(0));}
        }finally{context.deleteDatabase(name);recovery.delete();}
    }
    @Test public void schema12MigrationAndBackupRestoreRetainFields()throws Exception{
        String name="gis-stage12-test.db";context.deleteDatabase(name);byte[] old;
        try{
            try(var farm=new FarmStore(context,name)){
                farm.addField("Pre-GIS",2);var envelope=new JSONObject(new String(LocalBackup.snapshot(farm),StandardCharsets.UTF_8));var payload=new JSONObject(envelope.getString("payload"));payload.remove("gis_records");LegacySchema.removeSync(payload);
                String data=payload.toString();byte[] hash=MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8));StringBuilder hex=new StringBuilder();for(byte b:hash)hex.append(String.format("%02x",b&255));
                old=envelope.put("schema",12).put("payload",data).put("sha256",hex.toString()).toString().getBytes(StandardCharsets.UTF_8);
                LegacySchema.dropSync(farm.getWritableDatabase());farm.getWritableDatabase().execSQL("DROP TABLE gis_records");farm.getWritableDatabase().setVersion(12);
            }
            try(var farm=new FarmStore(context,name)){
                assertEquals(15,farm.getReadableDatabase().getVersion());assertEquals("Pre-GIS",farm.fields().get(0).name());assertEquals(1,LocalBackup.inspect(farm,old));
                new GeoStore(farm).saveGeometry(farm.fields().get(0).id(),fixture(),"manual","",0);
                File recovery=new File(context.getCacheDir(),"gis-stage12.json");try{LocalBackup.restore(farm,old,recovery);assertTrue(new GeoStore(farm).records(null,null).isEmpty());assertEquals(1,farm.fields().size());}finally{recovery.delete();}
            }
        }finally{context.deleteDatabase(name);}
    }
    @Test public void invalidPayloadAndMissingParentDoNotChangeDatabase()throws Exception{
        String name="gis-invalid-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            farm.addField("Synthetic",1);GeoStore geo=new GeoStore(farm);byte[] before=LocalBackup.snapshot(farm);
            try{geo.savePoint(null,"missing","note","Test","",26,38,5,0);fail();}catch(IllegalArgumentException expected){}
            try{geo.savePoint(null,farm.fields().get(0).id(),"tree","Test","",26,38,-5,0);fail();}catch(IllegalArgumentException expected){}
            assertArrayEquals(before,LocalBackup.snapshot(farm));
        }finally{context.deleteDatabase(name);}
    }
}
