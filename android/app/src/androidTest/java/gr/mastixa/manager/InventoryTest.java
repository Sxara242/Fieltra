package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public class InventoryTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception {try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-inventory.zip")){return CatalogImport.read(in);}}
    private InventoryStore.Movement movement(String id,String item,String type,double quantity){return new InventoryStore.Movement(id,item,"2026-09-07",type,quantity,"","","",0,0,"Notes","","","","");}
    @Test public void importedStockRelationsCostsRepeatAndBackup() throws Exception {
        String name="inventory-import-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"inventory-before.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();var preview=CatalogImport.preview(store,data);assertEquals(1,preview.inventoryItems());assertEquals(2,preview.inventoryMovements());assertTrue(new InventoryStore(store).items().isEmpty());
            CatalogImport.apply(store,data,file);var inventory=new InventoryStore(store);var item=inventory.items().get(0);assertEquals(17,inventory.stock(item.id()),0.00001);assertEquals(5,item.minimum(),0);assertEquals("Σημείωση; είδους",item.notes());
            var receipt=inventory.movements(item.id()).stream().filter(m->m.type().equals("Παραλαβή")).findFirst().orElseThrow();assertEquals(2.5,receipt.price(),0);assertEquals(50,receipt.cost(),0);assertEquals("Παραλαβή;\nδεύτερη γραμμή",receipt.notes());assertEquals(store.fields().get(0).id(),receipt.fieldId());assertEquals(new PartnerStore(store).partners().get(0).id(),receipt.partnerId());
            var consumption=inventory.movements(item.id()).stream().filter(m->m.type().equals("Κατανάλωση")).findFirst().orElseThrow();assertEquals("fertilization",consumption.sourceType());assertEquals("42",consumption.sourceId());
            assertEquals(8,CatalogImport.apply(store,data,file).skipped());assertEquals(2,inventory.movements(item.id()).size());
            try{inventory.deleteMovement(receipt.id());fail();}catch(IllegalArgumentException expected){}
            byte[] backup=LocalBackup.snapshot(store);inventory.saveMovement(movement(null,item.id(),"Κατανάλωση",2));assertEquals(15,inventory.stock(item.id()),0);
            LocalBackup.restore(store,backup,file);assertEquals(17,inventory.stock(item.id()),0);assertEquals(2,inventory.movements(item.id()).size());
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void stockValidationEditDeleteAndAtomicQueue() throws Exception {
        String name="inventory-crud-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            var inv=new InventoryStore(store);String item=inv.saveItem(new InventoryStore.Item(null,"Item","Category","kg",2,""));
            try{inv.saveMovement(movement(null,item,"Κατανάλωση",1));fail();}catch(IllegalArgumentException expected){}
            String receipt=inv.saveMovement(movement(null,item,"Παραλαβή",10));String consumption=inv.saveMovement(movement(null,item,"Κατανάλωση",7));assertEquals(3,inv.stock(item),0);
            try{inv.saveMovement(movement(receipt,item,"Παραλαβή",5));fail();}catch(IllegalArgumentException expected){}
            try{inv.deleteMovement(receipt);fail();}catch(IllegalArgumentException expected){}
            try{inv.deleteItem(item);fail();}catch(IllegalArgumentException expected){}
            try{inv.saveItem(new InventoryStore.Item(item,"Item","Category","L",2,""));fail();}catch(IllegalArgumentException expected){}
            try{inv.saveItem(new InventoryStore.Item(null,"item","Category","kg",2,""));fail();}catch(IllegalArgumentException expected){}
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_stock_queue BEFORE INSERT ON pending_changes BEGIN SELECT RAISE(ABORT,'test'); END");
            try{inv.saveMovement(movement(consumption,item,"Κατανάλωση",1));fail();}catch(android.database.SQLException expected){}
            try{inv.deleteMovement(consumption);fail();}catch(android.database.SQLException expected){}
            assertEquals(3,inv.stock(item),0);store.getWritableDatabase().execSQL("DROP TRIGGER fail_stock_queue");
            inv.deleteMovement(consumption);inv.deleteMovement(receipt);inv.deleteItem(item);assertTrue(inv.items().isEmpty());LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void allImportRollsBackWhenInventoryFails() throws Exception {
        String name="inventory-rollback-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"inventory-failed.json");
        try(var store=new FarmStore(context,name)){
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_inventory BEFORE INSERT ON inventory_movements BEGIN SELECT RAISE(ABORT,'test'); END");
            try{CatalogImport.apply(store,fixture(),file);fail();}catch(android.database.SQLException expected){}
            assertTrue(store.fields().isEmpty());assertTrue(new PartnerStore(store).partners().isEmpty());assertTrue(new CatalogStore(store).products().isEmpty());assertTrue(new InventoryStore(store).items().isEmpty());
            try(var c=store.getReadableDatabase().rawQuery("SELECT count(*) FROM pending_changes",null)){c.moveToFirst();assertEquals(0,c.getInt(0));}
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void rejectMissingRelationshipsAndNegativePackage() throws Exception {
        String name="inventory-invalid-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            var data=fixture();var bad=new ArrayList<>(data.inventory().movements());var original=bad.get(0);
            bad.add(new InventoryStore.Movement(null,original.itemId(),"2026-09-07","Κατανάλωση",100,"","","",0,0,"","","","","999"));
            var changed=new CatalogImport.Package(data.fields(),data.producer(),data.products(),data.links(),data.partners(),new InventoryImport.Data(data.inventory().items(),bad),data.money(),data.production(),data.activities(),data.work(),data.ignored());
            try{CatalogImport.preview(store,changed);fail();}catch(IllegalArgumentException expected){}assertTrue(new InventoryStore(store).items().isEmpty());
            var files=new LinkedHashMap<String,byte[]>();try(var zip=new ZipInputStream(InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-inventory.zip"))){ZipEntry entry;while((entry=zip.getNextEntry())!=null)files.put(entry.getName(),zip.readAllBytes());}
            files.remove("tables/business_partners.csv");var out=new ByteArrayOutputStream();try(var zip=new ZipOutputStream(out)){for(var e:files.entrySet()){zip.putNextEntry(new ZipEntry(e.getKey()));zip.write(e.getValue());zip.closeEntry();}}
            try{CatalogImport.read(new ByteArrayInputStream(out.toByteArray()));fail();}catch(IOException expected){}
        }finally{context.deleteDatabase(name);}
    }
    @Test public void schemaFourMigrationAndLegacyRestore() throws Exception {
        String name="inventory-migration-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"inventory-legacy-before.json");
        try{
            byte[] old;
            try(var store=new FarmStore(context,name)){
                store.addField("Kept",1);new PartnerStore(store).save(new PartnerStore.Partner(null,"Partner","supplier","001","","","","","","",""));
                var envelope=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var payload=new JSONObject(envelope.getString("payload"));payload.remove("inventory_items");payload.remove("inventory_movements");payload.remove("money_entries");payload.remove("production");payload.remove("production_sales");payload.remove("farm_activities");payload.remove("plant_protection_records");payload.remove("workers");payload.remove("labor_entries");payload.remove("planting_batches");payload.remove("equipment");payload.remove("equipment_maintenance");payload.remove("invoice_documents");payload.remove("year_locks");payload.remove("gis_records");LegacySchema.removeSync(payload);String data=payload.toString();var hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))hash.append(String.format("%02x",b&255));old=envelope.put("schema",4).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);
                LegacySchema.dropStage12(store.getWritableDatabase());store.getWritableDatabase().execSQL("DROP TABLE equipment_maintenance");store.getWritableDatabase().execSQL("DROP TABLE equipment");store.getWritableDatabase().execSQL("DROP INDEX money_service");store.getWritableDatabase().execSQL("DROP TABLE planting_batches");store.getWritableDatabase().execSQL("DROP TABLE plant_protection_records");store.getWritableDatabase().execSQL("DROP TABLE labor_entries");store.getWritableDatabase().execSQL("DROP TABLE workers");store.getWritableDatabase().execSQL("DROP TABLE farm_activities");store.getWritableDatabase().execSQL("DROP TABLE production_sales");store.getWritableDatabase().execSQL("DROP TABLE production");store.getWritableDatabase().execSQL("DROP TABLE money_entries");store.getWritableDatabase().execSQL("DROP TABLE inventory_movements");store.getWritableDatabase().execSQL("DROP TABLE inventory_items");store.getWritableDatabase().setVersion(4);
            }
            try(var store=new FarmStore(context,name)){
                assertEquals(15,store.getReadableDatabase().getVersion());assertEquals("Kept",store.fields().get(0).name());assertEquals(1,new PartnerStore(store).partners().size());
                new InventoryStore(store).saveItem(new InventoryStore.Item(null,"New","","kg",0,""));LocalBackup.restore(store,old,file);assertTrue(new InventoryStore(store).items().isEmpty());assertEquals(1,new PartnerStore(store).partners().size());
            }
        }finally{context.deleteDatabase(name);file.delete();}
    }
}
