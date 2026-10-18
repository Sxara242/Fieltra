package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.math.BigDecimal;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public class MoneyTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception{try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-money.zip")){return CatalogImport.read(in);}}
    private MoneyStore.Entry entry(String id,String kind,double amount){return new MoneyStore.Entry(id,kind,"2026-09-07","",kind.equals("expense")?"Category":"","Description","","Partner","Cash",amount,"Notes","","","");}
    private InventoryStore.Movement receipt(String id,String item,double price){return new InventoryStore.Movement(id,item,"2026-09-07","Παραλαβή",10,"","","Supplier",price,10*price,"Receipt notes","","","","");}
    @Test public void windowsImportLinksAmountsAndRepeat() throws Exception{
        String name="money-import-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"money-import-before.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();var preview=CatalogImport.preview(store,data);assertEquals(1,preview.income());assertEquals(2,preview.expenses());assertTrue(new MoneyStore(store).entries(null).isEmpty());
            CatalogImport.apply(store,data,file);var money=new MoneyStore(store);assertEquals(0,new BigDecimal("120.5").compareTo(MoneyStore.total(money.entries("income"))));assertEquals(0,new BigDecimal("60.25").compareTo(MoneyStore.total(money.entries("expense"))));
            var income=money.entries("income").get(0);assertEquals("Σημείωση;\nδεύτερη γραμμή",income.notes());assertEquals("Τράπεζα",income.payment());assertEquals(store.fields().get(0).id(),income.fieldId());assertEquals(new PartnerStore(store).partners().get(0).id(),income.partnerId());
            var automatic=money.entries("expense").stream().filter(e->e.sourceType().equals("inventory_receipt")).findFirst().orElseThrow();var movement=new InventoryStore(store).movements(null).stream().filter(m->m.id().equals(automatic.sourceId())).findFirst().orElseThrow();assertEquals(movement.cost(),automatic.amount(),0);assertEquals("Μετρητά",automatic.payment());
            assertEquals(11,CatalogImport.apply(store,data,file).skipped());assertEquals(3,money.entries(null).size());
            byte[] backup=LocalBackup.snapshot(store);money.save(entry(null,"expense",4));LocalBackup.restore(store,backup,file);assertEquals(3,money.entries(null).size());
            try{money.delete(automatic.id());fail();}catch(IllegalArgumentException expected){}
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void receiptLifecycleAndRollback(){
        String name="money-receipt-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            var inventory=new InventoryStore(store);var money=new MoneyStore(store);String item=inventory.saveItem(new InventoryStore.Item(null,"Item","","kg",0,""));String movement=inventory.saveMovement(receipt(null,item,2));assertEquals(20,money.entries("expense").get(0).amount(),0);String expense=money.entries("expense").get(0).id();
            inventory.saveMovement(receipt(movement,item,3));assertEquals(1,money.entries("expense").size());assertEquals(expense,money.entries("expense").get(0).id());assertEquals(30,money.entries("expense").get(0).amount(),0);
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_money BEFORE UPDATE ON money_entries BEGIN SELECT RAISE(ABORT,'test'); END");
            try{inventory.saveMovement(receipt(movement,item,4));fail();}catch(android.database.SQLException expected){}assertEquals(3,inventory.movements(item).get(0).price(),0);assertEquals(30,money.entries("expense").get(0).amount(),0);
            try{inventory.deleteMovement(movement);fail();}catch(android.database.SQLException expected){}assertEquals(1,inventory.movements(item).size());
            store.getWritableDatabase().execSQL("DROP TRIGGER fail_money");inventory.saveMovement(receipt(movement,item,0));assertTrue(money.entries("expense").isEmpty());inventory.saveMovement(receipt(movement,item,5));assertEquals(expense,money.entries("expense").get(0).id());inventory.deleteMovement(movement);assertTrue(money.entries("expense").isEmpty());assertTrue(inventory.movements(item).isEmpty());
        }finally{context.deleteDatabase(name);}
    }
    @Test public void manualValidationDeletionAndProfileIsolation() throws Exception{
        String name="money-crud-test.db",other="money-other-test.db";context.deleteDatabase(name);context.deleteDatabase(other);
        try(var store=new FarmStore(context,name);var isolated=new FarmStore(context,other)){
            var money=new MoneyStore(store);String id=money.save(entry(null,"income",0.1));money.save(entry(null,"income",0.2));assertEquals(0,new BigDecimal("0.3").compareTo(MoneyStore.total(money.entries("income"))));assertTrue(new MoneyStore(isolated).entries(null).isEmpty());
            money.save(entry(id,"income",5));try{money.save(entry(null,"expense",0));fail();}catch(IllegalArgumentException expected){}try{money.save(entry(null,"income",Double.NaN));fail();}catch(IllegalArgumentException expected){}
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_money_queue BEFORE INSERT ON pending_changes WHEN NEW.entity='money_entries' BEGIN SELECT RAISE(ABORT,'test'); END");
            try{money.save(entry(id,"income",99));fail();}catch(android.database.SQLException expected){}assertTrue(money.entries("income").stream().anyMatch(e->e.id().equals(id)&&e.amount()==5));store.getWritableDatabase().execSQL("DROP TRIGGER fail_money_queue");money.delete(id);assertEquals(1,money.entries("income").size());LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);context.deleteDatabase(other);}
    }
    @Test public void financeFailureRollsBackEntireZip() throws Exception{
        String name="money-rollback-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"money-failed.json");
        try(var store=new FarmStore(context,name)){
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_money_import BEFORE INSERT ON money_entries BEGIN SELECT RAISE(ABORT,'test'); END");try{CatalogImport.apply(store,fixture(),file);fail();}catch(android.database.SQLException expected){}
            assertTrue(store.fields().isEmpty());assertTrue(new InventoryStore(store).items().isEmpty());assertTrue(new PartnerStore(store).partners().isEmpty());assertTrue(new MoneyStore(store).entries(null).isEmpty());try(var c=store.getReadableDatabase().rawQuery("SELECT count(*) FROM pending_changes",null)){c.moveToFirst();assertEquals(0,c.getInt(0));}
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void inconsistentReceiptReferenceAndAmountAreRejected() throws Exception {
        String name="money-invalid-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            var data=fixture();var auto=data.money().stream().filter(e->e.sourceType().equals("inventory_receipt")).findFirst().orElseThrow();
            for(boolean missing:new boolean[]{true,false}){
                var entries=new ArrayList<>(data.money());entries.remove(auto);entries.add(new MoneyStore.Entry(null,auto.kind(),auto.date(),auto.fieldId(),auto.category(),auto.description(),auto.partnerId(),auto.partnerName(),auto.payment(),missing?auto.amount():auto.amount()+1,auto.notes(),auto.sourceType(),missing?"":auto.sourceId(),auto.windowsId()));
                var bad=new CatalogImport.Package(data.fields(),data.producer(),data.products(),data.links(),data.partners(),data.inventory(),entries,data.production(),data.activities(),data.work(),data.ignored());
                try{CatalogImport.preview(store,bad);fail();}catch(IllegalArgumentException expected){}assertTrue(new MoneyStore(store).entries(null).isEmpty());assertTrue(new InventoryStore(store).items().isEmpty());
            }
        }finally{context.deleteDatabase(name);}
    }
    @Test public void oldLocalReceiptsMigrateAndRestoreWithoutDuplicates() throws Exception{
        String name="money-migration-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"money-legacy-before.json");byte[] legacy;
        try{
            try(var store=new FarmStore(context,name)){
                var inv=new InventoryStore(store);String item=inv.saveItem(new InventoryStore.Item(null,"Existing","","kg",0,""));inv.saveMovement(receipt(null,item,2));
                var db=store.getWritableDatabase();db.delete("pending_changes","entity='money_entries'",null);db.execSQL("DELETE FROM money_entries");
                var envelope=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var payload=new JSONObject(envelope.getString("payload"));payload.remove("money_entries");payload.remove("production");payload.remove("production_sales");payload.remove("farm_activities");payload.remove("plant_protection_records");payload.remove("workers");payload.remove("labor_entries");payload.remove("planting_batches");payload.remove("equipment");payload.remove("equipment_maintenance");payload.remove("invoice_documents");payload.remove("year_locks");payload.remove("gis_records");LegacySchema.removeSync(payload);String data=payload.toString();var hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))hash.append(String.format("%02x",b&255));legacy=envelope.put("schema",5).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);
                LegacySchema.dropStage12(db);db.execSQL("DROP TABLE equipment_maintenance");db.execSQL("DROP TABLE equipment");db.execSQL("DROP INDEX money_service");db.execSQL("DROP TABLE planting_batches");db.execSQL("DROP TABLE plant_protection_records");db.execSQL("DROP TABLE labor_entries");db.execSQL("DROP TABLE workers");db.execSQL("DROP TABLE farm_activities");db.execSQL("DROP TABLE production_sales");db.execSQL("DROP TABLE production");db.execSQL("DROP TABLE money_entries");db.setVersion(5);
            }
            try(var store=new FarmStore(context,name)){
                assertEquals(15,store.getReadableDatabase().getVersion());assertEquals(1,new MoneyStore(store).entries("expense").size());assertEquals(20,new MoneyStore(store).entries("expense").get(0).amount(),0);LocalBackup.restore(store,legacy,file);assertEquals(1,new MoneyStore(store).entries("expense").size());LocalBackup.restore(store,legacy,file);assertEquals(1,new MoneyStore(store).entries("expense").size());
            }
        }finally{context.deleteDatabase(name);file.delete();}
    }
}
