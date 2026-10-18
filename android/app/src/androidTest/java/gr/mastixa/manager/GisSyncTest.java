package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import static org.junit.Assert.*;

public class GisSyncTest {
    @Test public void pointWithoutBoundariesStaysQueuedUntilParentCanSync()throws Exception{
        assertTrue(context.getPackageName().endsWith(".checks"));String name="sync-unmapped-point-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            farm.addField("Unmapped field",1);String id=farm.fields().get(0).id();var geo=new GeoStore(farm);String point=geo.savePoint(null,id,"note","Keep this point","Local until mapped",26,38,5,0);
            var repo=new GisSyncRepository(farm,DATASET);var server=new Server();
            assertEquals("Never publish a child whose required parcel cannot be transferred",0,GisSyncContract.run(repo,server).pushed());assertTrue(server.rows.isEmpty());assertNull(repo.state(point));assertNotNull(repo.document(point));
            try(var c=farm.getReadableDatabase().rawQuery("SELECT 1 FROM pending_changes WHERE entity='gis_records' AND entity_id=?",new String[]{point})){assertTrue(c.moveToFirst());}
            geo.saveGeometry(id,ParcelGeometry.manual("26 38\n26.001 38\n26.001 38.001\n26 38.001","EPSG:4326"),"fixture","",0);
            assertEquals(2,GisSyncContract.run(repo,server).pushed());assertEquals(2,server.rows.size());assertEquals(0,GisSyncContract.run(repo,server).pushed());assertEquals(1,geo.records(id,"point").size());
        }finally{context.deleteDatabase(name);}
    }
    @Test public void storageFailureRollsBackMetadataGeometryAndAckThenRetryConverges()throws Exception{
        assertTrue(context.getPackageName().endsWith(".checks"));String aName="sync-failure-a-test.db",bName="sync-failure-b-test.db";context.deleteDatabase(aName);context.deleteDatabase(bName);
        try(var a=new FarmStore(context,aName);var b=new FarmStore(context,bName)){
            String id=seed(a);var ra=new GisSyncRepository(a,DATASET);var rb=new GisSyncRepository(b,DATASET);var server=new Server();GisSyncContract.run(ra,server);GisSyncContract.run(rb,server);
            rename(a,"Remote new name");GisSyncContract.run(ra,server);byte[] before=LocalBackup.snapshot(b);long cursor=rb.cursor();
            b.getWritableDatabase().execSQL("CREATE TRIGGER qa_storage_failure BEFORE UPDATE ON gis_records BEGIN SELECT RAISE(ABORT,'simulated storage failure'); END");
            try{GisSyncContract.run(rb,server);fail("Injected disk failure must propagate");}catch(android.database.sqlite.SQLiteException expected){assertTrue(expected.getMessage().contains("simulated storage failure"));}finally{b.getWritableDatabase().execSQL("DROP TRIGGER qa_storage_failure");}
            assertEquals(cursor,rb.cursor());assertArrayEquals(before,LocalBackup.snapshot(b));assertEquals(1,GisSyncContract.run(rb,server).pulled());
            assertEquals(GisSyncContract.canonical(ra.document(id)),GisSyncContract.canonical(rb.document(id)));assertEquals(new GisSyncContract.Result(0,0,0),GisSyncContract.run(rb,server));assertEquals(1,b.fields().size());
        }finally{context.deleteDatabase(aName);context.deleteDatabase(bName);}
    }
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private static final String DATASET="00000000-0000-0000-0000-000000000010";
    private static final class Server implements GisSyncContract.Transport {
        final Map<String,GisSyncContract.Remote> rows=new HashMap<>();long sequence;int uploads;boolean offline,loseAck;
        public GisSyncContract.Batch pull(long cursor)throws Exception{
            if(offline)throw new IOException("Offline fixture");List<GisSyncContract.Remote> out=new ArrayList<>();for(var row:rows.values())if(row.sequence()>cursor)out.add(GisSyncContract.Remote.from(new JSONObject(row.json().toString())));return new GisSyncContract.Batch(sequence,out);
        }
        public GisSyncContract.Remote push(JSONObject input,long expected)throws Exception{
            if(offline)throw new IOException("Offline fixture");JSONObject record=GisSyncContract.validate(input);var old=rows.get(record.getString("id"));
            if(old!=null&&GisSyncContract.canonical(old.record()).equals(GisSyncContract.canonical(record)))return old;
            if(expected!=(old==null?0:old.version()))throw new GisSyncContract.Conflict(old);
            var remote=new GisSyncContract.Remote(record,expected+1,++sequence);rows.put(record.getString("id"),remote);uploads++;
            if(loseAck){loseAck=false;throw new IOException("Committed upload; acknowledgement lost");}return remote;
        }
    }
    private String seed(FarmStore farm){farm.addField("Synthetic sync",1);String id=farm.fields().get(0).id();new GeoStore(farm).saveGeometry(id,ParcelGeometry.manual("26 38\n26.001 38\n26.001 38.001\n26 38.001","EPSG:4326"),"fixture","",0);return id;}
    private void rename(FarmStore farm,String name){var f=farm.fields().get(0);farm.saveField(f.id(),name,f.area(),f.kaek(),f.location(),f.trees(),f.notes());}

    @Test public void bothDirectionsOfflineConflictBackupAndExplicitResolution()throws Exception{
        assertTrue(context.getPackageName().endsWith(".checks"));String aName="sync-a-test.db",bName="sync-b-test.db";context.deleteDatabase(aName);context.deleteDatabase(bName);File recovery=new File(context.getCacheDir(),"sync-recovery.json");
        try(var a=new FarmStore(context,aName);var b=new FarmStore(context,bName)){
            String id=seed(a);var ra=new GisSyncRepository(a,DATASET);var rb=new GisSyncRepository(b,DATASET);var server=new Server();
            assertEquals(1,GisSyncContract.run(ra,server).pushed());assertEquals(1,GisSyncContract.run(rb,server).pulled());
            assertEquals(GisSyncContract.canonical(ra.document(id)),GisSyncContract.canonical(rb.document(id)));
            assertEquals(0,GisSyncContract.run(rb,server).pushed());assertEquals(1,server.uploads);
            rename(b,"Android edit");GisSyncContract.run(rb,server);GisSyncContract.run(ra,server);assertEquals("Android edit",a.fields().get(0).name());
            server.offline=true;rename(a,"PC offline");rename(b,"Android offline");try{GisSyncContract.run(ra,server);fail();}catch(IOException expected){}
            server.offline=false;GisSyncContract.run(ra,server);assertEquals(1,GisSyncContract.run(rb,server).conflicts());
            var conflict=rb.conflicts().get(0);assertEquals("Android offline",conflict.local().getJSONObject("data").getString("name"));assertEquals("PC offline",conflict.remote().record().getJSONObject("data").getString("name"));
            byte[] backup=LocalBackup.snapshot(b);assertEquals(1,LocalBackup.inspect(b,backup));
            rename(b,"Later local edit");try{rb.resolve(conflict.id(),"remote");fail();}catch(IllegalArgumentException expected){}
            assertTrue(rb.blocked(id));LocalBackup.restore(b,backup,recovery);assertEquals(1,rb.conflicts().size());
            rb.resolve(conflict.id(),"local");GisSyncContract.run(rb,server);GisSyncContract.run(ra,server);assertEquals("Android offline",a.fields().get(0).name());assertTrue(rb.conflicts().isEmpty());
            assertEquals(0,GisSyncContract.run(rb,server).pushed());
        }finally{context.deleteDatabase(aName);context.deleteDatabase(bName);recovery.delete();}
    }
    @Test public void lostAcknowledgementDeleteConflictAndReopen()throws Exception{
        String name="sync-lost-ack-test.db";context.deleteDatabase(name);Server server=new Server();String id;
        try{
            try(var farm=new FarmStore(context,name)){
                id=seed(farm);var repo=new GisSyncRepository(farm,DATASET);server.loseAck=true;
                try{GisSyncContract.run(repo,server);fail();}catch(IOException expected){}assertNull(repo.state(id));
            }
            try(var farm=new FarmStore(context,name)){
                var repo=new GisSyncRepository(farm,DATASET);GisSyncContract.run(repo,server);assertEquals(1,server.uploads);assertNotNull(repo.state(id));
                JSONObject deleted=new JSONObject(server.rows.get(id).record().toString()).put("deleted_at",2000L);server.push(deleted,1);rename(farm,"Retain this edit");
                assertEquals(1,GisSyncContract.run(repo,server).conflicts());assertTrue(repo.document(id).isNull("deleted_at"));
                repo.resolve(repo.conflicts().get(0).id(),"remote");assertEquals(2000,repo.document(id).getLong("deleted_at"));assertEquals(1,farm.fields().size());
                assertEquals("fixture",repo.document(id).getJSONObject("data").getString("geometry_source"));
            }
        }finally{context.deleteDatabase(name);}
    }
    @Test public void schema13MigrationAndLegacyBackupPreserveGeometry()throws Exception{
        String name="sync-stage13-test.db";context.deleteDatabase(name);byte[] legacy;String id;File recovery=new File(context.getCacheDir(),"sync-stage13-recovery.json");
        try{
            try(var farm=new FarmStore(context,name)){
                id=seed(farm);JSONObject envelope=new JSONObject(new String(LocalBackup.snapshot(farm),StandardCharsets.UTF_8));JSONObject payload=new JSONObject(envelope.getString("payload"));LegacySchema.removeSync(payload);
                String data=payload.toString();StringBuilder hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))hash.append(String.format(Locale.ROOT,"%02x",b&255));
                legacy=envelope.put("schema",13).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);LegacySchema.dropSync(farm.getWritableDatabase());farm.getWritableDatabase().setVersion(13);
            }
            try(var farm=new FarmStore(context,name)){
                assertEquals(15,farm.getReadableDatabase().getVersion());assertNotNull(new GeoStore(farm).parcel(id));assertEquals(1,LocalBackup.inspect(farm,legacy));
                GisSyncContract.run(new GisSyncRepository(farm,DATASET),new Server());LocalBackup.restore(farm,legacy,recovery);
                assertNotNull(new GeoStore(farm).parcel(id));assertNull(new GisSyncRepository(farm,DATASET).state(id));assertEquals(0,new GisSyncRepository(farm,DATASET).cursor());
            }
        }finally{context.deleteDatabase(name);recovery.delete();}
    }
    @Test public void desktopWireFixturePreservesSourceCoordinatesAndReturnsAndroidEdits()throws Exception{
        String name="sync-wire-exchange-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            JSONObject fixture;try(InputStream input=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("gis_sync_exchange.json")){fixture=new JSONObject(new String(LocalBackup.read(input),StandardCharsets.UTF_8));}
            JSONArray records=fixture.getJSONArray("records");var repo=new GisSyncRepository(farm,DATASET);
            for(int i=0;i<records.length();i++)repo.apply(new GisSyncContract.Remote(records.getJSONObject(i),1,i+1),null);
            assertEquals(3,repo.documents().size());String id=records.getJSONObject(0).getString("id");
            assertEquals("EPSG:2100",repo.document(id).getJSONObject("data").getString("source_crs"));
            assertEquals(500000.12345678,repo.document(id).getJSONObject("data").getJSONObject("original_geometry").getJSONArray("coordinates").getJSONArray(0).getJSONArray(0).getDouble(0),0);
            assertEquals("Συνθετικό χωράφι",farm.fields().get(0).name());assertNotNull(new GeoStore(farm).parcel(id));
            String point=records.getJSONObject(1).getString("id");new GeoStore(farm).savePoint(point,id,"valve","Αλλαγή Android","Return fixture",24.0017,37.95,5.5,1);
            JSONArray returned=new JSONArray();for(JSONObject record:repo.documents())returned.put(record);
            try(FileOutputStream output=new FileOutputStream(new File(context.getExternalFilesDir(null),"gis-sync-android-return.json"))){output.write(new JSONObject().put("records",returned).put("wgs84",new JSONObject(GeoStore.geometry(new GeoStore(farm).parcel(id)).wgs84)).toString().getBytes(StandardCharsets.UTF_8));}
            assertEquals(1,LocalBackup.inspect(farm,LocalBackup.snapshot(farm)));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void divergentPolygonsArePreservedWithoutMerge()throws Exception{
        String aName="sync-polygon-a-test.db",bName="sync-polygon-b-test.db";context.deleteDatabase(aName);context.deleteDatabase(bName);
        try(var a=new FarmStore(context,aName);var b=new FarmStore(context,bName)){
            String id=seed(a);var ra=new GisSyncRepository(a,DATASET);var rb=new GisSyncRepository(b,DATASET);Server server=new Server();GisSyncContract.run(ra,server);GisSyncContract.run(rb,server);
            int index=0;for(var farm:List.of(a,b)){
                var geo=new GeoStore(farm);var old=geo.parcel(id);JSONObject source=new JSONObject(old.payload().getString("original_geojson"));
                source.getJSONArray("coordinates").getJSONArray(0).getJSONArray(1).put(0,26.001+(++index)*.0001);
                geo.saveGeometry(id,ParcelGeometry.normalize(source.toString(),"EPSG:4326"),"fixture","",old.revision());
            }
            String left=GisSyncContract.canonical(ra.document(id).getJSONObject("data").getJSONObject("original_geometry")),right=GisSyncContract.canonical(rb.document(id).getJSONObject("data").getJSONObject("original_geometry"));assertNotEquals(left,right);
            GisSyncContract.run(ra,server);assertEquals(1,GisSyncContract.run(rb,server).conflicts());var conflict=rb.conflicts().get(0);
            assertEquals(right,GisSyncContract.canonical(conflict.local().getJSONObject("data").getJSONObject("original_geometry")));assertEquals(left,GisSyncContract.canonical(conflict.remote().record().getJSONObject("data").getJSONObject("original_geometry")));
            rb.resolve(conflict.id(),"remote");assertEquals(left,GisSyncContract.canonical(rb.document(id).getJSONObject("data").getJSONObject("original_geometry")));assertEquals(0,GisSyncContract.run(rb,server).pushed());
        }finally{context.deleteDatabase(aName);context.deleteDatabase(bName);}
    }
    @Test public void desktopRoundTripConvergesAndRetriesDoNotDuplicate()throws Exception{
        String name="sync-final-exchange-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            String external=InstrumentationRegistry.getArguments().getString("sync_roundtrip","");JSONObject initial,expected;
            if(!external.isEmpty()){
                assertEquals("gis-sync-windows-return.json",external);
                try(InputStream input=new FileInputStream(new File(context.getExternalFilesDir(null),"gis-sync-android-return.json"))){initial=new JSONObject(new String(LocalBackup.read(input),StandardCharsets.UTF_8));}
                try(InputStream input=new FileInputStream(new File(context.getExternalFilesDir(null),external))){expected=new JSONObject(new String(LocalBackup.read(input),StandardCharsets.UTF_8));}
            }else{
                try(InputStream input=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("gis_sync_exchange.json")){initial=new JSONObject(new String(LocalBackup.read(input),StandardCharsets.UTF_8));}
                expected=new JSONObject(initial.toString());expected.getJSONArray("records").getJSONObject(1).put("deleted_at",2000L).put("updated_at",2000L);
            }
            var repo=new GisSyncRepository(farm,DATASET);JSONArray originals=initial.getJSONArray("records"),finalRows=expected.getJSONArray("records");
            for(int i=0;i<originals.length();i++)repo.apply(new GisSyncContract.Remote(originals.getJSONObject(i),1,i+1),null);
            Server server=new Server();for(int i=0;i<finalRows.length();i++){JSONObject row=finalRows.getJSONObject(i);server.rows.put(row.getString("id"),new GisSyncContract.Remote(row,2,i+1));}server.sequence=finalRows.length();
            assertEquals(0,GisSyncContract.run(repo,server).pushed());assertEquals(0,GisSyncContract.run(repo,server).pushed());assertEquals(0,server.uploads);
            assertEquals(3,repo.documents().size());assertTrue(repo.conflicts().isEmpty());
            for(int i=0;i<finalRows.length();i++)assertEquals(GisSyncContract.canonical(finalRows.getJSONObject(i)),GisSyncContract.canonical(repo.document(finalRows.getJSONObject(i).getString("id"))));
            String id=originals.getJSONObject(0).getString("id"),point=originals.getJSONObject(1).getString("id");
            assertTrue(repo.document(id).isNull("deleted_at"));assertFalse(repo.document(point).isNull("deleted_at"));assertEquals("EPSG:2100",repo.document(id).getJSONObject("data").getString("source_crs"));
            JSONObject wgs84=new JSONObject(GeoStore.geometry(new GeoStore(farm).parcel(id)).wgs84);
            if(expected.has("wgs84")){
                var actual=ParcelGeometry.vertices(wgs84.toString());var reference=ParcelGeometry.vertices(expected.getJSONObject("wgs84").toString());assertEquals(reference.size(),actual.size());
                for(int i=0;i<actual.size();i++){assertEquals(reference.get(i).x(),actual.get(i).x(),2e-7);assertEquals(reference.get(i).y(),actual.get(i).y(),2e-7);}
            }
            JSONArray returned=new JSONArray();for(JSONObject row:repo.documents())returned.put(row);
            try(FileOutputStream output=new FileOutputStream(new File(context.getExternalFilesDir(null),"gis-sync-final-android.json"))){output.write(new JSONObject().put("records",returned).put("wgs84",wgs84).toString().getBytes(StandardCharsets.UTF_8));}
        }finally{context.deleteDatabase(name);}
    }
    @Test public void staleApplyAndDirtyChildCannotBeOverwritten()throws Exception{
        String name="sync-stale-test.db";context.deleteDatabase(name);
        try(var farm=new FarmStore(context,name)){
            String id=seed(farm);var repo=new GisSyncRepository(farm,DATASET);Server server=new Server();GisSyncContract.run(repo,server);
            JSONObject current=repo.document(id);String digest=GisSyncContract.fingerprint(current);rename(farm,"New local edit");
            try{repo.apply(server.rows.get(id),digest);fail();}catch(IllegalArgumentException expected){}
            assertEquals("New local edit",farm.fields().get(0).name());assertEquals(1,repo.state(id).version());GisSyncContract.run(repo,server);
            new GeoStore(farm).savePoint(null,id,"tree","New tree","",26,38,5,0);
            var deleted=new JSONObject(server.rows.get(id).record().toString()).put("deleted_at",2000L);server.push(deleted,server.rows.get(id).version());
            var result=GisSyncContract.run(repo,server);assertEquals(1,result.conflicts());assertEquals(0,result.pushed());assertTrue(repo.document(id).isNull("deleted_at"));assertEquals(1,new GeoStore(farm).records(id,"point").size());
        }finally{context.deleteDatabase(name);}
    }
}
