package gr.mastixa.manager;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.*;

public class PlantingTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception{try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-plantings.zip")){return CatalogImport.read(in);}}
    private WorkStore.Planting batch(String id,String field,int planted,int alive){return new WorkStore.Planting(id,"2026-09-08",field,planted,alive,"Cuttings","Nursery","Variety","4 x 4 m",120.5,"Notes","");}
    @Test public void localLifecycleValidationAndAtomicQueue() throws Exception {
        String name="planting-local-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){store.saveField(null,"Field",1,"","",12,"");String field=store.fields().get(0).id();var w=new WorkStore(store);String id=w.savePlanting(batch(null,field,30,27));assertEquals(12,store.fields().get(0).trees());assertTrue(new MoneyStore(store).entries(null).isEmpty());
            byte[] before=LocalBackup.snapshot(store);try{w.savePlanting(batch(id,field,20,21));fail();}catch(IllegalArgumentException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_planting_queue BEFORE INSERT ON pending_changes WHEN NEW.entity='planting_batches' BEGIN SELECT RAISE(ABORT,'test'); END");try{w.savePlanting(batch(id,field,30,25));fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));try{w.deletePlanting(id);fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));store.getWritableDatabase().execSQL("DROP TRIGGER reject_planting_queue");w.savePlanting(batch(id,field,30,25));assertEquals(25,w.plantings().get(0).trees_alive());w.deletePlanting(id);assertTrue(w.plantings().isEmpty());LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void actualWindowsZipRepeatFieldsAndBackup() throws Exception {
        String name="planting-import-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"planting-recovery.json");
        try(var store=new FarmStore(context,name)){var d=fixture();assertEquals(1,CatalogImport.preview(store,d).plantings());assertTrue(store.fields().isEmpty());CatalogImport.apply(store,d,file);var w=new WorkStore(store);var a=w.plantings().get(0);assertEquals(30,a.trees_planted());assertEquals(27,a.trees_alive());assertEquals("2026-02-15",a.planting_date());assertEquals("Μοσχεύματα",a.material_type());assertEquals("Δοκιμαστικό φυτώριο",a.source());assertEquals("Ποικιλία Α",a.variety());assertEquals("4 x 4 m",a.spacing());assertEquals(120.5,a.cost(),0);assertEquals("Φύτευση;\nδεύτερη γραμμή",a.notes());assertEquals(store.fields().get(0).id(),a.field_id());assertEquals(15,CatalogImport.apply(store,d,file).skipped());byte[] backup=LocalBackup.snapshot(store);w.savePlanting(batch(null,a.field_id(),10,9));LocalBackup.restore(store,backup,file);assertEquals(1,w.plantings().size());try{w.deletePlanting(a.id());fail();}catch(IllegalArgumentException expected){}
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void missingFieldAndFailedImportLeaveNothing() throws Exception {
        String name="planting-invalid-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"planting-invalid.json");
        try(var store=new FarmStore(context,name)){var d=fixture();var only=new CatalogImport.Package(List.of(),null,List.of(),List.of(),List.of(),new InventoryImport.Data(List.of(),List.of()),List.of(),new ProductionImport.Data(List.of(),List.of()),List.of(),new WorkImport.Data(List.of(),List.of(),List.of(),d.work().plantings()),List.of());try{CatalogImport.preview(store,only);fail();}catch(IllegalArgumentException expected){}
            byte[] before=LocalBackup.snapshot(store);store.getWritableDatabase().execSQL("CREATE TRIGGER reject_planting_import BEFORE INSERT ON planting_batches BEGIN SELECT RAISE(ABORT,'test'); END");try{CatalogImport.apply(store,d,file);fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);file.delete();}
    }
    private byte[] envelope(JSONObject e,JSONObject p,int schema) throws Exception{String data=p.toString();var h=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))h.append(String.format("%02x",b&255));return e.put("schema",schema).put("payload",data).put("sha256",h.toString()).toString().getBytes(StandardCharsets.UTF_8);}
    @Test public void schemaNineUpgradeRestoreAndInvalidTrees() throws Exception {
        String name="planting-upgrade-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"planting-old.json");byte[] old;
        try{try(var store=new FarmStore(context,name)){store.addField("Field",2);var e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var p=new JSONObject(e.getString("payload"));var legacy=new JSONObject();for(String table:new String[]{"fields","pending_changes","producer","products","product_fields","business_partners","inventory_items","inventory_movements","money_entries","production","production_sales","farm_activities","plant_protection_records","workers","labor_entries"})legacy.put(table,p.getJSONArray(table));old=envelope(e,legacy,9);LegacySchema.dropStage12(store.getWritableDatabase());store.getWritableDatabase().execSQL("DROP TABLE equipment_maintenance");store.getWritableDatabase().execSQL("DROP TABLE equipment");store.getWritableDatabase().execSQL("DROP INDEX money_service");store.getWritableDatabase().execSQL("DROP TABLE planting_batches");store.getWritableDatabase().setVersion(9);}
            try(var store=new FarmStore(context,name)){assertEquals(15,store.getReadableDatabase().getVersion());var w=new WorkStore(store);w.savePlanting(batch(null,store.fields().get(0).id(),30,27));var e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var p=new JSONObject(e.getString("payload"));p.getJSONArray("planting_batches").getJSONObject(0).put("trees_alive",31);try{LocalBackup.inspect(store,envelope(e,p,19));fail();}catch(IllegalArgumentException expected){}LocalBackup.restore(store,old,file);assertTrue(w.plantings().isEmpty());assertEquals(1,store.fields().size());}
        }finally{context.deleteDatabase(name);file.delete();}
    }
}
