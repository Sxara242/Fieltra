package gr.mastixa.manager;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

/** Synthetic, checks-package-only local GPS/reference regressions. No network or device GPS required. */
public class AndroidGpsLocalTest {
    private ParcelGeometry rectangle(){return ParcelGeometry.manual("26 38\n26.001 38\n26.001 38.001\n26 38.001","EPSG:4326");}
    @Test public void reportedAccuracyChangesBoundaryClassificationIncludingHoles()throws Exception{
        var outer=rectangle();
        assertEquals(ParcelGeometry.FixRelation.INSIDE,outer.classifyFix(26.0005,38.0005,5));
        assertEquals(ParcelGeometry.FixRelation.OUTSIDE,outer.classifyFix(26.002,38.0005,5));
        assertEquals(ParcelGeometry.FixRelation.UNCERTAIN,outer.classifyFix(26.00001,38.0005,5));
        assertEquals(ParcelGeometry.FixRelation.UNCERTAIN,outer.classifyFix(25.99999,38.0005,5));
        assertEquals(ParcelGeometry.FixRelation.UNCERTAIN,outer.classifyFix(26,38.0005,0));
        assertEquals(ParcelGeometry.FixRelation.UNCERTAIN,outer.classifyFix(26.0005,38.0005,500));
        var hole=ParcelGeometry.manual("26.0003 38.0003\n26.0007 38.0003\n26.0007 38.0007\n26.0003 38.0007","EPSG:4326");
        var json=new JSONObject(outer.original);json.getJSONArray("coordinates").put(new JSONObject(hole.original).getJSONArray("coordinates").getJSONArray(0));
        var holed=ParcelGeometry.normalize(json.toString(),"EPSG:4326");
        assertEquals(ParcelGeometry.FixRelation.OUTSIDE,holed.classifyFix(26.0005,38.0005,5));
        assertEquals(ParcelGeometry.FixRelation.UNCERTAIN,holed.classifyFix(26.00031,38.0005,5));
        var other=ParcelGeometry.manual("26.003 38\n26.004 38\n26.004 38.001\n26.003 38.001","EPSG:4326");
        var parts=new org.json.JSONArray().put(new JSONObject(outer.original).getJSONArray("coordinates")).put(new JSONObject(other.original).getJSONArray("coordinates"));
        var multipart=ParcelGeometry.normalize(new JSONObject().put("type","MultiPolygon").put("coordinates",parts).toString(),"EPSG:4326");
        assertEquals(ParcelGeometry.FixRelation.INSIDE,multipart.classifyFix(26.0035,38.0005,5));
        for(double bad:new double[]{-1,Double.NaN,Double.POSITIVE_INFINITY})try{outer.classifyFix(26,38,bad);fail("Invalid accuracy accepted");}catch(IllegalArgumentException expected){}
    }
    @Test public void gpsPointPreservesFixTimeThroughEditAndLogicalBackup()throws Exception{
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();assertTrue(context.getPackageName().endsWith(".checks"));String name="gps-fix-time-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            farm.addField("Synthetic",1);String field=farm.fields().get(0).id();var geo=new GeoStore(farm);long timestamp=1700000000123L;
            String id=geo.saveGpsPoint(null,field,"tree","Δέντρο","",26,38,6,timestamp,0);
            geo.saveGpsPoint(id,field,"tree","Αλλαγμένος τίτλος","",26,38,6,timestamp,1);
            assertEquals(timestamp,geo.records(field,"point").get(0).payload().getLong("fix_time_ms"));
            String legacy=geo.savePoint(null,field,"note","Legacy","",26,38,5,0);
            assertFalse(geo.records(field,"point").stream().filter(r->r.id().equals(legacy)).findFirst().orElseThrow().payload().has("fix_time_ms"));
            byte[] backup=LocalBackup.snapshot(farm);assertEquals(1,LocalBackup.inspect(farm,backup));
            File recovery=new File(context.getCacheDir(),"gps-fix-time-recovery.json");
            try{LocalBackup.restore(farm,backup,recovery);assertEquals(timestamp,geo.records(field,"point").stream().filter(r->r.id().equals(id)).findFirst().orElseThrow().payload().getLong("fix_time_ms"));}finally{recovery.delete();}
            try{geo.saveGpsPoint(null,field,"tree","Bad","",26,38,6,0,0);fail("Missing GPS timestamp accepted");}catch(IllegalArgumentException expected){}
        }finally{context.deleteDatabase(name);}
    }
    @Test public void separateReferencePreservesCultivationOutboxAndBackupAndHidesStaleKaek()throws Exception{
        assertFalse(CadastralStore.ANDROID_KAEK_SYNC_ENABLED);
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();assertTrue(context.getPackageName().endsWith(".checks"));String name="cadastral-reference-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            farm.saveField(null,"Chosen name",7.5,"510201507004","",0,"");String field=farm.fields().get(0).id();var geo=new GeoStore(farm);var source=new CadastralStore(farm);var cultivated=rectangle();
            geo.saveGeometry(field,cultivated,"manual","",0);
            int pending;try(var c=farm.getReadableDatabase().rawQuery("SELECT count(*) FROM pending_changes",null)){c.moveToFirst();pending=c.getInt(0);}
            var reference=ParcelGeometry.manual("26 38\n26.002 38\n26.002 38.002\n26 38.002","EPSG:4326");
            source.saveImported(field,"510201507004",reference,"reference.geojson",0);
            assertEquals(cultivated.original,GeoStore.geometry(geo.parcel(field)).original);assertEquals(7.5,farm.fields().get(0).area(),0);assertEquals("Chosen name",farm.fields().get(0).name());
            assertEquals(reference.original,source.parcel(field).geometry().original);assertFalse(source.parcel(field).payload().getBoolean("verified_official"));
            try(var c=farm.getReadableDatabase().rawQuery("SELECT count(*) FROM pending_changes",null)){c.moveToFirst();assertEquals("Reference import never enters sync outbox",pending,c.getInt(0));}
            try{source.saveImported(field,"510201507004",cultivated,"stale.geojson",0);fail("Stale replacement accepted");}catch(IllegalArgumentException expected){}
            byte[] backup=LocalBackup.snapshot(farm);assertEquals(19,new JSONObject(new String(backup,StandardCharsets.UTF_8)).getInt("schema"));assertEquals(1,LocalBackup.inspect(farm,backup));
            File recovery=new File(context.getCacheDir(),"cadastral-reference-recovery.json");
            try{LocalBackup.restore(farm,backup,recovery);assertEquals(reference.original,source.parcel(field).geometry().original);}finally{recovery.delete();}
            farm.saveField(field,"Chosen name",7.5,"510201507005","",0,"");assertNull("Old KAEK geometry must not be shown for a changed identifier",source.parcel(field));assertEquals(1,source.revision(field));
            try{source.saveImported(field,"510201507004",reference,"wrong-kaek.geojson",1);fail("Mismatched KAEK accepted");}catch(IllegalArgumentException expected){}
            assertEquals(cultivated.original,GeoStore.geometry(geo.parcel(field)).original);
        }finally{context.deleteDatabase(name);}
    }
    @Test public void schema14UpgradeAddsOnlyEmptyReferenceTableAndPreservesExistingGeometry()throws Exception{
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();assertTrue(context.getPackageName().endsWith(".checks"));String name="cadastral-migration-test.db";context.deleteDatabase(name);String field;String original=rectangle().original;
        try{
            try(var farm=new FarmStore(context,name)){farm.addField("Preserved",3);field=farm.fields().get(0).id();new GeoStore(farm).saveGeometry(field,rectangle(),"manual","",0);farm.getWritableDatabase().execSQL("DROP TABLE cadastral_reference");farm.getWritableDatabase().setVersion(14);}
            try(var farm=new FarmStore(context,name)){assertEquals(15,farm.getReadableDatabase().getVersion());assertEquals(original,GeoStore.geometry(new GeoStore(farm).parcel(field)).original);assertNull(new CadastralStore(farm).parcel(field));assertEquals(3,farm.fields().get(0).area(),0);}
        }finally{context.deleteDatabase(name);}
    }
    @Test public void cadastralOnlyMapFitsAndDrawsBlueReferenceWithoutCultivatedGeometry(){
        var i=InstrumentationRegistry.getInstrumentation();var context=i.getTargetContext();assertTrue(context.getPackageName().endsWith(".checks"));
        i.runOnMainSync(()->{
            var map=new ParcelMapView(context);map.layout(0,0,800,600);map.setGeometries(null,rectangle());assertTrue(map.viewport()[2]>0);
            Bitmap bitmap=Bitmap.createBitmap(800,600,Bitmap.Config.ARGB_8888);map.draw(new Canvas(bitmap));int blue=0;
            for(int y=0;y<600;y++)for(int x=0;x<800;x++){int pixel=bitmap.getPixel(x,y);if(android.graphics.Color.blue(pixel)>170&&android.graphics.Color.red(pixel)<80)blue++;}
            assertTrue("Cadastral-only layer must be visible",blue>100);bitmap.recycle();
        });
    }
}
