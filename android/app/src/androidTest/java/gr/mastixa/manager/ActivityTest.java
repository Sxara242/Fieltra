package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.*;

public class ActivityTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception{try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-activities.zip")){return CatalogImport.read(in);}}
    private ActivityStore.Activity activity(String id,String field,String item,String status,double amount){return new ActivityStore.Activity(id,"2026-09-08",field,"Λίπανση",status,0,0,"Fertilizer",2,"kg",12.5,"Person","Notes",item,amount,0,"","","","");}
    private String seed(FarmStore store){store.addField("Field",1);var stock=new InventoryStore(store);String item=stock.saveItem(new InventoryStore.Item(null,"Fertilizer","Fertilizer","kg",0,""));stock.saveMovement(new InventoryStore.Movement(null,item,"2026-09-01","Παραλαβή",20,"","","",0,0,"","","","",""));return item;}
    @Test public void legacyColumnsAndChangingInventoryItem() throws Exception {
        var files=Map.of("tables/farm_activities.csv","id;activity_date;field_id;category;status;quantity;unit;description;notes\n42;2020-01-01;;Πότισμα;Ολοκληρώθηκε;3;m³;Παλαιά καταγραφή;Σημείωση\n".getBytes(StandardCharsets.UTF_8));
        var metadata=Map.of("farm_activities",new JSONObject().put("status","exported").put("file","tables/farm_activities.csv").put("rows",1));var legacy=ActivityImport.read(files,metadata).get(0);assertEquals(3,legacy.quantity(),0);assertEquals("m³",legacy.unit());
        String name="activity-item-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            String item=seed(store),field=store.fields().get(0).id();var stock=new InventoryStore(store);var registry=new ActivityStore(store);String other=stock.saveItem(new InventoryStore.Item(null,"Other","","kg",0,""));
            String id=registry.save(activity(null,field,other,"Προγραμματισμένη",4));try{stock.saveItem(new InventoryStore.Item(other,"Other","","L",0,""));fail();}catch(IllegalArgumentException expected){}
            stock.saveMovement(new InventoryStore.Movement(null,other,"2026-09-01","Παραλαβή",10,"","","",0,0,"","","","",""));registry.save(activity(id,field,item,"Ολοκληρώθηκε",4));registry.save(activity(id,field,other,"Ολοκληρώθηκε",6));assertEquals(20,stock.stock(item),0);assertEquals(4,stock.stock(other),0);LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void consumptionLifecycleStockRollbackAndCost() throws Exception {
        String name="activity-local-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            String item=seed(store),field=store.fields().get(0).id();var registry=new ActivityStore(store);var stock=new InventoryStore(store);
            String id=registry.save(activity(null,field,item,"Προγραμματισμένη",4));assertEquals(20,stock.stock(item),0);assertTrue(registry.activities().get(0).movementId().isEmpty());
            registry.save(activity(id,field,item,"Ολοκληρώθηκε",4));assertEquals(16,stock.stock(item),0);assertEquals(0,new MoneyStore(store).entries(null).size());String movement=registry.activities().get(0).movementId();
            try{stock.deleteMovement(movement);fail();}catch(IllegalArgumentException expected){}
            try{registry.save(activity(id,field,item,"Ολοκληρώθηκε",21));fail();}catch(IllegalArgumentException expected){}assertEquals(16,stock.stock(item),0);assertEquals(movement,registry.activities().get(0).movementId());
            registry.save(activity(id,field,item,"Ολοκληρώθηκε",6));assertEquals(14,stock.stock(item),0);assertEquals(2,stock.movements(null).size());
            registry.save(activity(id,field,item,"Ακυρώθηκε",6));assertEquals(20,stock.stock(item),0);registry.save(activity(id,field,item,"Ολοκληρώθηκε",3));assertEquals(17,stock.stock(item),0);
            registry.delete(id);assertEquals(20,stock.stock(item),0);assertTrue(registry.activities().isEmpty());LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void failedActivityWriteRollsBackConsumptionAndQueue() throws Exception {
        String name="activity-atomic-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            String item=seed(store),field=store.fields().get(0).id();var registry=new ActivityStore(store);String id=registry.save(activity(null,field,item,"Ολοκληρώθηκε",4));byte[] before=LocalBackup.snapshot(store);
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_activity BEFORE UPDATE ON farm_activities BEGIN SELECT RAISE(ABORT,'test'); END");
            try{registry.save(activity(id,field,item,"Ολοκληρώθηκε",7));fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));
            try{registry.delete(id);fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void realWindowsZipRepeatAndBackupPreserveAllActivityFields() throws Exception {
        String name="activity-import-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"activity-recovery.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();assertEquals(2,CatalogImport.preview(store,data).activities());assertTrue(store.fields().isEmpty());CatalogImport.apply(store,data,file);var registry=new ActivityStore(store);var a=registry.activities().stream().filter(x->x.category().equals("Λίπανση")).findFirst().orElseThrow();
            assertEquals(4,a.inventoryQuantity(),0);assertEquals(0,a.quantity(),0);assertEquals("",a.unit());assertEquals("kg/στρ",a.doseUnit());assertEquals("Παλαιότερη περιγραφή",a.description());assertEquals("Λίπανση;\nδεύτερη γραμμή",a.notes());assertEquals("Δημήτρης",a.responsible());assertEquals(12.5,a.cost(),0);assertEquals(13,new InventoryStore(store).stock(a.itemId()),0);assertEquals(store.fields().get(0).id(),a.fieldId());assertFalse(a.movementId().isEmpty());assertEquals(2,new MoneyStore(store).entries("expense").size());
            assertEquals(17,CatalogImport.apply(store,data,file).skipped());assertEquals(3,new InventoryStore(store).movements(null).size());byte[] backup=LocalBackup.snapshot(store);LocalBackup.restore(store,backup,file);assertEquals(2,registry.activities().size());
            try{registry.delete(a.id());fail();}catch(IllegalArgumentException expected){}
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void previouslyImportedMovementIsLinkedWithoutConsumingAgain() throws Exception {
        String name="activity-prior-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"activity-prior.json");
        try(var store=new FarmStore(context,name)){
            var d=fixture();CatalogImport.apply(store,new CatalogImport.Package(d.fields(),d.producer(),d.products(),d.links(),d.partners(),d.inventory(),d.money(),d.production(),List.of(),d.work(),d.ignored()),file);
            String movement=new InventoryStore(store).movements(null).stream().filter(m->m.sourceType().equals("farm_activity")).findFirst().orElseThrow().id();CatalogImport.apply(store,d,file);assertEquals(movement,new ActivityStore(store).activities().stream().filter(a->!a.movementId().isEmpty()).findFirst().orElseThrow().movementId());assertEquals(3,new InventoryStore(store).movements(null).size());
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void missingConsumptionRejectedAndFailedImportRollsBackEverything() throws Exception {
        String name="activity-invalid-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"activity-invalid.json");
        try(var store=new FarmStore(context,name)){
            var d=fixture();var inventory=new InventoryImport.Data(d.inventory().items(),d.inventory().movements().stream().filter(m->!m.sourceType().equals("farm_activity")).toList());var bad=new CatalogImport.Package(d.fields(),d.producer(),d.products(),d.links(),d.partners(),inventory,d.money(),d.production(),d.activities(),d.work(),d.ignored());try{CatalogImport.preview(store,bad);fail();}catch(IllegalArgumentException expected){}
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_activity_import BEFORE INSERT ON farm_activities BEGIN SELECT RAISE(ABORT,'test'); END");try{CatalogImport.apply(store,d,file);fail();}catch(android.database.SQLException expected){}assertTrue(store.fields().isEmpty());assertTrue(new InventoryStore(store).movements(null).isEmpty());assertTrue(new MoneyStore(store).entries(null).isEmpty());
        }finally{context.deleteDatabase(name);file.delete();}
    }
    private byte[] envelope(JSONObject envelope,JSONObject payload,int schema) throws Exception {String data=payload.toString();var hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))hash.append(String.format("%02x",b&255));return envelope.put("schema",schema).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);}
    @Test public void schemaSevenUpgradeRestoreAndCorruptConsumptionRejected() throws Exception {
        String name="activity-upgrade-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"activity-upgrade.json");byte[] old;
        try{
            try(var store=new FarmStore(context,name)){seed(store);var e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var p=new JSONObject(e.getString("payload"));p.remove("farm_activities");p.remove("plant_protection_records");p.remove("workers");p.remove("labor_entries");p.remove("planting_batches");p.remove("equipment");p.remove("equipment_maintenance");p.remove("invoice_documents");p.remove("year_locks");p.remove("gis_records");LegacySchema.removeSync(p);old=envelope(e,p,7);LegacySchema.dropStage12(store.getWritableDatabase());store.getWritableDatabase().execSQL("DROP TABLE equipment_maintenance");store.getWritableDatabase().execSQL("DROP TABLE equipment");store.getWritableDatabase().execSQL("DROP INDEX money_service");store.getWritableDatabase().execSQL("DROP TABLE planting_batches");store.getWritableDatabase().execSQL("DROP TABLE plant_protection_records");store.getWritableDatabase().execSQL("DROP TABLE labor_entries");store.getWritableDatabase().execSQL("DROP TABLE workers");store.getWritableDatabase().execSQL("DROP TABLE farm_activities");store.getWritableDatabase().setVersion(7);}
            try(var store=new FarmStore(context,name)){assertEquals(15,store.getReadableDatabase().getVersion());var stock=new InventoryStore(store);var registry=new ActivityStore(store);registry.save(activity(null,store.fields().get(0).id(),stock.items().get(0).id(),"Ολοκληρώθηκε",4));var e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var p=new JSONObject(e.getString("payload"));p.getJSONArray("farm_activities").getJSONObject(0).put("inventory_quantity",5);try{LocalBackup.inspect(store,envelope(e,p,14));fail();}catch(IOException expected){}LocalBackup.restore(store,old,file);assertTrue(registry.activities().isEmpty());assertEquals(20,stock.stock(stock.items().get(0).id()),0);}
        }finally{context.deleteDatabase(name);file.delete();}
    }
}
