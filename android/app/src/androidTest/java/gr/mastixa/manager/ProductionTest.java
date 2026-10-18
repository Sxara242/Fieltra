package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.*;

public class ProductionTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception{try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-production.zip")){return CatalogImport.read(in);}}
    private ProductionStore.Sale sale(String id,String product,double amount,double price){return new ProductionStore.Sale(id,"2026-09-07",product,"Product","","Buyer",amount,price,amount*price,"Cash","Notes","","");}
    @Test public void localStockIncomeLifecycleAndRollback() throws Exception{
        String name="production-local-test.db";context.deleteDatabase(name);
        try(var store=new FarmStore(context,name)){
            store.addField("Field",1);String field=store.fields().get(0).id(),product=new CatalogStore(store).saveProduct(null,"Product","kg",true);var registry=new ProductionStore(store);
            String harvest=registry.saveHarvest(new ProductionStore.Harvest(null,"2026-09-01",product,"Product",field,20,"",""));String sale=registry.saveSale(sale(null,product,5,10));assertEquals(15,registry.available(product),0);var income=new MoneyStore(store).entries("income").get(0);assertEquals(50,income.amount(),0);
            try{registry.saveSale(sale(sale,product,21,10));fail();}catch(IllegalArgumentException expected){}
            try{registry.saveHarvest(new ProductionStore.Harvest(harvest,"2026-09-01",product,"Product",field,4,"",""));fail();}catch(IllegalArgumentException expected){}
            try{registry.deleteHarvest(harvest);fail();}catch(IllegalArgumentException expected){}
            try{new CatalogStore(store).saveProduct(product,"Product","L",true);fail();}catch(IllegalArgumentException expected){}
            registry.saveSale(sale(sale,product,6,12));assertEquals(income.id(),new MoneyStore(store).entries("income").get(0).id());assertEquals(72,new MoneyStore(store).entries("income").get(0).amount(),0);
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_sale_income BEFORE UPDATE ON money_entries BEGIN SELECT RAISE(ABORT,'test'); END");try{registry.saveSale(sale(sale,product,7,12));fail();}catch(android.database.SQLException expected){}assertEquals(6,registry.sales().get(0).quantity(),0);try{registry.deleteSale(sale);fail();}catch(android.database.SQLException expected){}assertEquals(1,registry.sales().size());store.getWritableDatabase().execSQL("DROP TRIGGER reject_sale_income");
            registry.deleteSale(sale);assertTrue(new MoneyStore(store).entries("income").isEmpty());registry.deleteHarvest(harvest);assertTrue(registry.harvests().isEmpty());LocalBackup.inspect(store,LocalBackup.snapshot(store));
        }finally{context.deleteDatabase(name);}
    }
    @Test public void actualWindowsZipRelationshipsRepeatAndBackup() throws Exception{
        String name="production-import-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"production-before.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();var plan=CatalogImport.preview(store,data);assertEquals(1,plan.harvests());assertEquals(1,plan.sales());assertTrue(new ProductionStore(store).harvests().isEmpty());CatalogImport.apply(store,data,file);var registry=new ProductionStore(store);var sale=registry.sales().get(0);assertEquals(14,registry.available(sale.productId()),0);assertEquals(51,sale.total(),0);assertEquals("Πώληση;\nδεύτερη γραμμή",sale.notes());assertEquals(store.fields().get(0).id(),registry.harvests().get(0).fieldId());assertEquals(new PartnerStore(store).partners().get(0).id(),sale.buyerId());
            var income=new MoneyStore(store).entries("income").stream().filter(e->e.sourceType().equals("production_sale")).findFirst().orElseThrow();assertEquals(sale.id(),income.sourceId());assertEquals(51,income.amount(),0);assertEquals(2,new MoneyStore(store).entries("income").size());assertEquals(14,CatalogImport.apply(store,data,file).skipped());
            byte[] backup=LocalBackup.snapshot(store);registry.saveSale(sale(null,sale.productId(),1,9));LocalBackup.restore(store,backup,file);assertEquals(1,registry.sales().size());assertEquals(14,registry.available(sale.productId()),0);
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void linkIncomeImportedInEarlierStepWithoutDuplication() throws Exception{
        String name="production-prior-income-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"production-prior.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();var moneyOnly=new CatalogImport.Package(data.fields(),data.producer(),data.products(),data.links(),data.partners(),data.inventory(),data.money(),new ProductionImport.Data(List.of(),List.of()),data.activities(),data.work(),data.ignored());CatalogImport.apply(store,moneyOnly,file);String id=new MoneyStore(store).entries("income").stream().filter(e->e.windowsId().equals(data.production().sales().get(0).incomeWindowsId())).findFirst().orElseThrow().id();CatalogImport.apply(store,data,file);assertEquals(2,new MoneyStore(store).entries("income").size());assertEquals(id,new MoneyStore(store).entries("income").stream().filter(e->e.sourceType().equals("production_sale")).findFirst().orElseThrow().id());
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void failedSaleRollsBackEverythingAndMissingIncomeIsRejected() throws Exception{
        String name="production-failed-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"production-failed.json");
        try(var store=new FarmStore(context,name)){
            var data=fixture();var missing=new CatalogImport.Package(data.fields(),data.producer(),data.products(),data.links(),data.partners(),data.inventory(),List.of(),data.production(),data.activities(),data.work(),data.ignored());try{CatalogImport.preview(store,missing);fail();}catch(IllegalArgumentException expected){}
            store.getWritableDatabase().execSQL("CREATE TRIGGER reject_import_sale BEFORE INSERT ON production_sales BEGIN SELECT RAISE(ABORT,'test'); END");try{CatalogImport.apply(store,data,file);fail();}catch(android.database.SQLException expected){}assertTrue(store.fields().isEmpty());assertTrue(new MoneyStore(store).entries(null).isEmpty());assertTrue(new ProductionStore(store).harvests().isEmpty());try(var c=store.getReadableDatabase().rawQuery("SELECT count(*) FROM pending_changes",null)){c.moveToFirst();assertEquals(0,c.getInt(0));}
        }finally{context.deleteDatabase(name);file.delete();}
    }
    @Test public void schemaSixUpgradeAndRestore() throws Exception{
        String name="production-upgrade-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"production-old.json");byte[] old;
        try{
            try(var store=new FarmStore(context,name)){
                store.addField("Existing",2);var envelope=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var payload=new JSONObject(envelope.getString("payload"));payload.remove("production");payload.remove("production_sales");payload.remove("farm_activities");payload.remove("plant_protection_records");payload.remove("workers");payload.remove("labor_entries");payload.remove("planting_batches");payload.remove("equipment");payload.remove("equipment_maintenance");payload.remove("invoice_documents");payload.remove("year_locks");payload.remove("gis_records");LegacySchema.removeSync(payload);String data=payload.toString();var hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8)))hash.append(String.format("%02x",b&255));old=envelope.put("schema",6).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);var db=store.getWritableDatabase();LegacySchema.dropStage12(db);db.execSQL("DROP TABLE equipment_maintenance");db.execSQL("DROP TABLE equipment");db.execSQL("DROP INDEX money_service");db.execSQL("DROP TABLE planting_batches");db.execSQL("DROP TABLE plant_protection_records");db.execSQL("DROP TABLE labor_entries");db.execSQL("DROP TABLE workers");db.execSQL("DROP TABLE farm_activities");db.execSQL("DROP TABLE production_sales");db.execSQL("DROP TABLE production");db.execSQL("DROP INDEX money_sale");db.setVersion(6);
            }
            try(var store=new FarmStore(context,name)){assertEquals(15,store.getReadableDatabase().getVersion());assertEquals("Existing",store.fields().get(0).name());LocalBackup.restore(store,old,file);assertTrue(new ProductionStore(store).sales().isEmpty());assertEquals(1,store.fields().size());}
        }finally{context.deleteDatabase(name);file.delete();}
    }
}
