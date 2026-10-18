package gr.mastixa.manager;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.*;

public class WorkTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception{try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-work.zip")){return CatalogImport.read(in);}}
    private String seed(FarmStore store){store.addField("Field",2);var stock=new InventoryStore(store);String item=stock.saveItem(new InventoryStore.Item(null,"Item","Supplies","L",0,""));stock.saveMovement(new InventoryStore.Movement(null,item,"2026-01-01","Παραλαβή",20,"","","",0,0,"","","","",""));return item;}
    private WorkStore.Protection protection(String id,String field,String item,double amount){return new WorkStore.Protection(id,"2026-09-08",field,item,"Purpose","Product","Ingredient","00123",0.5,"L/stremma",40,2,"Person","Calm",14,15,"Notes",amount,"","");}
    private WorkStore.Labor labor(String id,String field,String worker,double hours,double rate){return new WorkStore.Labor(id,"2026-09-08",field,worker,"Harvest",hours,rate,0,"Notes","");}
    @Test public void protectionInventoryLifecycleAndAtomicFailure() throws Exception {
        String name="work-protection-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            String item=seed(store),field=store.fields().get(0).id();var work=new WorkStore(store);var stock=new InventoryStore(store);String id=work.saveProtection(protection(null,field,item,2));assertEquals(18,stock.stock(item),0);assertTrue(new MoneyStore(store).entries(null).isEmpty());
            work.saveProtection(protection(id,field,item,5));assertEquals(15,stock.stock(item),0);assertEquals(2,stock.movements(null).size());byte[] before=LocalBackup.snapshot(store);
            try{work.saveProtection(protection(id,field,item,21));fail();}catch(IllegalArgumentException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_protection_movement BEFORE UPDATE ON inventory_movements BEGIN SELECT RAISE(ABORT,'test'); END");try{work.saveProtection(protection(id,field,item,3));fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));try{work.deleteProtection(id);fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));store.getWritableDatabase().execSQL("DROP TRIGGER reject_protection_movement");
            work.saveProtection(protection(id,field,"",0));assertEquals(20,stock.stock(item),0);work.deleteProtection(id);assertTrue(work.protections().isEmpty());LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void laborCostWorkerHistoryInactiveAndRollback() throws Exception {
        String name="work-labor-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            store.addField("Field",1);String field=store.fields().get(0).id();var work=new WorkStore(store);String worker=work.saveWorker(new WorkStore.Worker(null,"Worker","Role","00123",8.5,1,"Notes",""));String entry=work.saveLabor(labor(null,field,worker,6,8.5));assertEquals(51,work.labor().get(0).cost(),0);assertTrue(new MoneyStore(store).entries(null).isEmpty());
            try{work.saveWorker(new WorkStore.Worker(null,"worker","","",0,1,"",""));fail();}catch(IllegalArgumentException expected){}
            try{work.deleteWorker(worker);fail();}catch(IllegalArgumentException expected){}work.saveWorker(new WorkStore.Worker(worker,"Worker","Role","00123",10,0,"Notes",""));assertEquals(51,work.labor().get(0).cost(),0);
            try{work.saveLabor(labor(null,field,worker,2,10));fail();}catch(IllegalArgumentException expected){}work.saveLabor(labor(entry,field,worker,5,9));assertEquals(45,work.labor().get(0).cost(),0);
            byte[] before=LocalBackup.snapshot(store);store.getWritableDatabase().execSQL("CREATE TRIGGER reject_labor_queue BEFORE INSERT ON pending_changes WHEN NEW.entity='labor_entries' BEGIN SELECT RAISE(ABORT,'test'); END");try{work.saveLabor(labor(entry,field,worker,2,10));fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));store.getWritableDatabase().execSQL("DROP TRIGGER reject_labor_queue");work.deleteLabor(entry);try{work.deleteWorker(worker);fail();}catch(IllegalArgumentException expected){}LocalBackup.inspect(store,LocalBackup.snapshot(store));
            String unused=work.saveWorker(new WorkStore.Worker(null,"Unused","","",0,1,"",""));work.deleteWorker(unused);assertEquals(1,work.workers().size());
        }finally{context.deleteDatabase(name);}
    }
    @Test public void realWindowsZipAllFieldsRelationshipsRepeatAndBackup() throws Exception {
        String name="work-import-test.db";context.deleteDatabase(name);var recovery=new File(context.getCacheDir(),"work-import.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();var plan=CatalogImport.preview(store,data);assertEquals(1,plan.protections());assertEquals(2,plan.workers());assertEquals(1,plan.labor());assertTrue(store.fields().isEmpty());CatalogImport.apply(store,data,recovery);var work=new WorkStore(store);var p=work.protections().get(0);var l=work.labor().get(0);var w=work.workers().stream().filter(x->x.id().equals(l.worker_id())).findFirst().orElseThrow();
            assertEquals("000123",p.authorization_number());assertEquals("Δοκιμαστική ουσία",p.active_ingredient());assertEquals("L/στρ.",p.dose_unit());assertEquals(0.5,p.dose(),0);assertEquals(40,p.spray_volume_l(),0);assertEquals(2.5,p.area_stremma(),0);assertEquals("Δημήτρης",p.applicator());assertEquals("Ήπιος",p.weather());assertEquals(14,p.harvest_interval_days());assertEquals(15,p.cost(),0);assertEquals("Επέμβαση;\nδεύτερη γραμμή",p.notes());assertEquals(15,new InventoryStore(store).stock(p.inventory_item_id()),0);assertEquals(store.fields().get(0).id(),p.field_id());assertFalse(p.movement_id().isEmpty());
            assertEquals("00306900000000",w.phone());assertEquals("Συγκομιδή",w.role());assertEquals(8.5,w.default_hourly_rate(),0);assertEquals(1,w.active());assertEquals("Εργάτης;\nσημείωση",w.notes());assertEquals(51,l.cost(),0);assertEquals(6,l.hours(),0);assertEquals(8.5,l.hourly_rate(),0);assertEquals("Εργασία;\nσημείωση",l.notes());assertEquals(store.fields().get(0).id(),l.field_id());assertEquals(2,new MoneyStore(store).entries("expense").size());
            assertEquals(19,CatalogImport.apply(store,data,recovery).skipped());assertEquals(3,new InventoryStore(store).movements(null).size());byte[] backup=LocalBackup.snapshot(store);LocalBackup.restore(store,backup,recovery);assertEquals(1,work.protections().size());assertEquals(2,work.workers().size());assertEquals(1,work.labor().size());
            try{work.deleteProtection(p.id());fail();}catch(IllegalArgumentException expected){}try{work.deleteLabor(l.id());fail();}catch(IllegalArgumentException expected){}
        }finally{context.deleteDatabase(name);recovery.delete();}
    }
    @Test public void previouslyImportedInventoryIsLinkedAndWorkerConflictRejected() throws Exception {
        String name="work-prior-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"work-prior.json");
        try(var store=new FarmStore(context,name)){
            var d=fixture();CatalogImport.apply(store,new CatalogImport.Package(d.fields(),d.producer(),d.products(),d.links(),d.partners(),d.inventory(),d.money(),d.production(),d.activities(),WorkImport.Data.empty(),d.ignored()),file);String movement=new InventoryStore(store).movements(null).stream().filter(m->m.sourceType().equals("plant_protection")).findFirst().orElseThrow().id();CatalogImport.apply(store,d,file);assertEquals(movement,new WorkStore(store).protections().get(0).movement_id());assertEquals(3,new InventoryStore(store).movements(null).size());
        }finally{context.deleteDatabase(name);file.delete();}
        try(var store=new FarmStore(context,name)){var w=fixture().work().workers().get(0);new WorkStore(store).saveWorker(new WorkStore.Worker(null,w.name(),w.role(),"different",w.default_hourly_rate(),w.active(),w.notes(),""));try{CatalogImport.preview(store,fixture());fail();}catch(IllegalArgumentException expected){}assertTrue(store.fields().isEmpty());}finally{context.deleteDatabase(name);}
    }
    @Test public void missingRelationsAndImportFailureRollbackAllRegistries() throws Exception {
        String name="work-invalid-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"work-invalid.json");
        try(var store=new FarmStore(context,name)){
            var d=fixture();var missing=new WorkImport.Data(d.work().protections(),List.of(),d.work().labor());var bad=new CatalogImport.Package(d.fields(),d.producer(),d.products(),d.links(),d.partners(),d.inventory(),d.money(),d.production(),d.activities(),missing,d.ignored());try{CatalogImport.preview(store,bad);fail();}catch(IllegalArgumentException expected){}
            var inventory=new InventoryImport.Data(d.inventory().items(),d.inventory().movements().stream().filter(m->!m.sourceType().equals("plant_protection")).toList());bad=new CatalogImport.Package(d.fields(),d.producer(),d.products(),d.links(),d.partners(),inventory,d.money(),d.production(),d.activities(),d.work(),d.ignored());try{CatalogImport.preview(store,bad);fail();}catch(IllegalArgumentException expected){}
            byte[] before=LocalBackup.snapshot(store);store.getWritableDatabase().execSQL("CREATE TRIGGER reject_work_import BEFORE INSERT ON plant_protection_records BEGIN SELECT RAISE(ABORT,'test'); END");try{CatalogImport.apply(store,d,file);fail();}catch(android.database.SQLException expected){}assertArrayEquals(before,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);file.delete();}
    }
    private byte[] envelope(JSONObject e,JSONObject p,int schema) throws Exception {String data=p.toString();var hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))hash.append(String.format("%02x",b&255));return e.put("schema",schema).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);}
    @Test public void schemaEightUpgradeRestoreAndCorruptLinksRejected() throws Exception {
        String name="work-upgrade-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"work-upgrade.json");byte[] old;
        try{
            try(var store=new FarmStore(context,name)){seed(store);var e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var p=new JSONObject(e.getString("payload"));p.remove("plant_protection_records");p.remove("workers");p.remove("labor_entries");p.remove("planting_batches");p.remove("equipment");p.remove("equipment_maintenance");p.remove("invoice_documents");p.remove("year_locks");p.remove("gis_records");LegacySchema.removeSync(p);old=envelope(e,p,8);var db=store.getWritableDatabase();LegacySchema.dropStage12(db);db.execSQL("DROP TABLE equipment_maintenance");db.execSQL("DROP TABLE equipment");db.execSQL("DROP INDEX money_service");db.execSQL("DROP TABLE planting_batches");db.execSQL("DROP TABLE plant_protection_records");db.execSQL("DROP TABLE labor_entries");db.execSQL("DROP TABLE workers");db.setVersion(8);}
            try(var store=new FarmStore(context,name)){assertEquals(15,store.getReadableDatabase().getVersion());var work=new WorkStore(store);String field=store.fields().get(0).id(),item=new InventoryStore(store).items().get(0).id();work.saveProtection(protection(null,field,item,2));String worker=work.saveWorker(new WorkStore.Worker(null,"Worker","","",9,1,"",""));work.saveLabor(labor(null,field,worker,2,9));
                var e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var p=new JSONObject(e.getString("payload"));p.getJSONArray("plant_protection_records").getJSONObject(0).put("inventory_quantity",3);try{LocalBackup.inspect(store,envelope(e,p,14));fail();}catch(IOException expected){}
                e=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));p=new JSONObject(e.getString("payload"));p.getJSONArray("labor_entries").getJSONObject(0).put("worker_id","missing");try{LocalBackup.inspect(store,envelope(e,p,14));fail();}catch(IOException expected){}
                LocalBackup.restore(store,old,file);assertTrue(work.protections().isEmpty());assertTrue(work.workers().isEmpty());assertTrue(work.labor().isEmpty());assertEquals(20,new InventoryStore(store).stock(item),0);
            }
        }finally{context.deleteDatabase(name);file.delete();}
    }
}
