package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import static org.junit.Assert.*;

public class LocalBackupTest {
    private static String sha256(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder();
        for (byte b : digest) result.append(String.format("%02x", b & 255));
        return result.toString();
    }

    private static byte[] downgrade(byte[] current, int schema) throws Exception {
        JSONObject envelope = new JSONObject(new String(current, StandardCharsets.UTF_8));
        JSONObject payload = new JSONObject(envelope.getString("payload"));
        if(schema<19)payload.remove("cadastral_reference");
        if (schema < 18) {
            for (String table : SensorDataBackup.TABLES) payload.remove(table);
        }
        if (schema < 17) {
            payload.remove("planting_replantings");
        }
        if (schema < 16) {
            payload.remove("individual_plants");
            payload.remove("plant_events");
        }
        if (schema < 15) {
            for (String table : new String[]{
                "crop_programs", "crop_program_rules", "crop_program_assignments", "crop_tasks"
            }) payload.remove(table);
        }
        String data = payload.toString();
        envelope.put("schema", schema);
        envelope.put("payload", data);
        envelope.put("sha256", sha256(data));
        return envelope.toString().getBytes(StandardCharsets.UTF_8);
    }

    @Test public void schema18RestorePreservesCultivationWithoutInventingCadastralReference() throws Exception {
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        assertTrue(context.getPackageName().endsWith(".checks"));
        String database="backup-schema18-test.db";
        File recovery=new File(context.getCacheDir(),"backup-schema18-recovery.json");
        context.deleteDatabase(database);
        try(FarmStore store=new FarmStore(context,database)) {
            store.saveField(null,"Historical field",2,"510201507004","",0,"");
            String field=store.fields().get(0).id();
            ParcelGeometry cultivated=ParcelGeometry.manual("26 38\n26.001 38\n26.001 38.001\n26 38.001","EPSG:4326");
            GeoStore geo=new GeoStore(store);
            geo.saveGeometry(field,cultivated,"manual","",0);
            CadastralStore cadastre=new CadastralStore(store);
            cadastre.saveImported(field,"510201507004",cultivated,"synthetic-reference.geojson",0);
            byte[] current=LocalBackup.snapshot(store);
            byte[] historical=downgrade(current,18);
            assertEquals(18,new JSONObject(new String(historical,StandardCharsets.UTF_8)).getInt("schema"));
            assertEquals(1,LocalBackup.inspect(store,historical));
            assertNotNull(cadastre.parcel(field));
            store.addField("After backup",7);
            LocalBackup.restore(store,historical,recovery);
            assertEquals(1,store.fields().size());
            assertEquals("Historical field",store.fields().get(0).name());
            assertEquals(2,store.fields().get(0).area(),0);
            assertEquals(cultivated.original,GeoStore.geometry(geo.parcel(field)).original);
            assertNull("Schema18 contains no official/reference geometry",cadastre.parcel(field));
            assertEquals(19,new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8)).getInt("schema"));
        } finally { context.deleteDatabase(database); recovery.delete(); }
    }

    @Test public void roundTripAndRejectedRestore() throws Exception {
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        context.deleteDatabase("backup-test.db"); File recovery=new File(context.getCacheDir(),"recovery-test.json");
        try(FarmStore store=new FarmStore(context,"backup-test.db")) {
            store.saveField(null,"Χίος",2,"001","Πυργί",20,"Σημειώσεις");
            String fieldId=store.fields().get(0).id();
            CropProgramStore crop=new CropProgramStore(store);
            CropProgram.Rule rule=new CropProgram.Rule(
                "spring-check","Spring inspection","inspection","fixed_date","backup proof",
                3,15,null,null,null,null,null
            );
            crop.saveProgram("backup-program","Backup program","mastic","Phase 12C", List.of(rule));
            var generated=crop.generateForField("backup-program",fieldId,2026);
            assertEquals(1,generated.size());
            String taskKey=generated.get(0).generationKey();
            crop.setTaskStatus(taskKey,"completed");

            WorkStore work = new WorkStore(store);
            String batchId = work.savePlanting(new WorkStore.Planting(
                null,"2026-03-01",fieldId,20,19,"Δενδρύλλια","","Mastic","2 x 6",0,"",""
            ));
            PlantTrackingStore plants = new PlantTrackingStore(store);
            plants.savePlant(new PlantTracking.Plant(
                "backup-plant",fieldId,batchId,"A-001","2026-03-01","Mastic",38.25,26.02,
                "active","good","backup proof"
            ));
            plants.appendEvent(new PlantTracking.Event(
                "backup-event","backup-plant","2026-03-20","health","poor",""
            ));
            PlantingHistory plantingHistory = new PlantingHistory(store);
            plantingHistory.add("backup-replanting",batchId,"2026-03-25",1,"replacement");

            SensorDataStore sensors = new SensorDataStore(store);
            sensors.saveDevice(new SensorData.Device(
                "backup-sensor","Weather station","manual",fieldId,"external-1","active","backup proof"
            ));
            sensors.saveChannel(new SensorData.Channel(
                "backup-temp","backup-sensor","air_temperature","celsius","Air"
            ));
            sensors.appendObservation(new SensorData.Observation(
                "backup-observation","backup-temp","2026-03-25T06:00:00Z",-2.5,"good","packet-1"
            ));

            byte[] bytes=LocalBackup.snapshot(store);
            assertEquals(19,new JSONObject(new String(bytes,StandardCharsets.UTF_8)).getInt("schema"));
            assertEquals(1,LocalBackup.inspect(store,bytes));
            assertEquals(1,LocalBackup.inspect(store,downgrade(bytes,18)));
            byte[] schema17=downgrade(bytes,17);
            byte[] schema16=downgrade(bytes,16);
            byte[] schema15=downgrade(bytes,15);
            byte[] schema14=downgrade(bytes,14);
            assertEquals(1,LocalBackup.inspect(store,schema17));
            assertEquals(1,LocalBackup.inspect(store,schema16));
            assertEquals(1,LocalBackup.inspect(store,schema15));
            assertEquals(1,LocalBackup.inspect(store,schema14));

            crop.saveProgram("newer-only","Newer only","","",List.of(rule));
            plants.savePlant(new PlantTracking.Plant(
                "newer-plant",fieldId,"","","","",null,null,"active","unknown",""
            ));
            plantingHistory.add("newer-replanting",batchId,"2026-03-30",1,"newer only");
            sensors.saveDevice(new SensorData.Device(
                "newer-sensor","Newer sensor","manual","","","active",""
            ));
            assertEquals(2,store.getReadableDatabase().rawQuery("SELECT id FROM crop_programs",null).getCount());
            assertEquals(2,plants.plants(null,false).size());
            assertEquals(2,plantingHistory.events(batchId).size());
            assertEquals(2,sensors.devices(false).size());

            LocalBackup.restore(store,schema17,recovery);
            assertEquals(1,plants.plants(null,false).size());
            assertEquals(1,plantingHistory.events(batchId).size());
            assertTrue(sensors.devices(true).isEmpty());

            LocalBackup.restore(store,schema16,recovery);
            assertEquals(1,plants.plants(null,false).size());
            assertTrue(plantingHistory.events(batchId).isEmpty());
            assertTrue(sensors.devices(true).isEmpty());

            LocalBackup.restore(store,schema15,recovery);
            try(var c=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM crop_programs",null)) { c.moveToFirst(); assertEquals(1,c.getInt(0)); }
            assertTrue(plants.plants(null,true).isEmpty());
            assertTrue(plantingHistory.events(batchId).isEmpty());
            assertTrue(sensors.devices(true).isEmpty());

            LocalBackup.restore(store,bytes,recovery);
            try(var c=store.getReadableDatabase().rawQuery("SELECT name,crop,description,active FROM crop_programs WHERE id='backup-program'",null)) {
                assertTrue(c.moveToFirst());
                assertEquals("Backup program",c.getString(0));
                assertEquals("mastic",c.getString(1));
                assertEquals("Phase 12C",c.getString(2));
                assertEquals(1,c.getInt(3));
            }
            try(var c=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM crop_program_rules WHERE program_id='backup-program'",null)) { c.moveToFirst(); assertEquals(1,c.getInt(0)); }
            try(var c=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM crop_program_assignments WHERE program_id='backup-program' AND field_id=? AND season_year=2026",new String[]{fieldId})) { c.moveToFirst(); assertEquals(1,c.getInt(0)); }
            var restoredTasks=crop.tasks("backup-program",fieldId,2026);
            assertEquals(1,restoredTasks.size());
            assertEquals(taskKey,restoredTasks.get(0).generationKey());
            assertEquals("completed",restoredTasks.get(0).status());
            assertEquals(1,plants.plants(null,false).size());
            assertEquals("poor",plants.snapshot("backup-plant").health());
            assertEquals(1,plants.events("backup-plant").size());
            assertEquals(1,plantingHistory.events(batchId).size());
            assertEquals(1,plantingHistory.totals(batchId).replantings());
            assertEquals(1,sensors.devices(false).size());
            assertEquals("backup-sensor",sensors.devices(false).get(0).id());
            assertEquals(1,sensors.observations("backup-temp").size());
            assertEquals(-2.5,sensors.snapshot("backup-sensor").channels().get(0).latestValue(),0.000001);

            LocalBackup.restore(store,schema14,recovery);
            try(var c=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM crop_programs",null)) { c.moveToFirst(); assertEquals(0,c.getInt(0)); }
            assertTrue(crop.tasks(null,null,null).isEmpty());
            assertTrue(plants.plants(null,true).isEmpty());
            assertTrue(plantingHistory.events(batchId).isEmpty());
            assertTrue(sensors.devices(true).isEmpty());

            LocalBackup.restore(store,bytes,recovery);
            store.addField("Νεότερο",3); LocalBackup.restore(store,bytes,recovery);
            assertEquals(1,store.fields().size()); assertEquals("001",store.fields().get(0).kaek());
            try(var in=new java.io.FileInputStream(recovery)) { assertEquals(2,LocalBackup.inspect(store,LocalBackup.read(in))); }
            try { LocalBackup.restore(store,"invalid".getBytes(),recovery); fail(); } catch(org.json.JSONException expected) {}
            assertEquals(1,store.fields().size());
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_restore BEFORE INSERT ON fields BEGIN SELECT RAISE(ABORT,'test'); END");
            try { LocalBackup.restore(store,bytes,recovery); fail(); } catch(android.database.SQLException expected) {}
            assertEquals(1,store.fields().size());
        } finally { context.deleteDatabase("backup-test.db"); recovery.delete(); }
    }
}
