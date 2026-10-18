package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.*;

public class PartnerTest {
    private final android.content.Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    private CatalogImport.Package fixture() throws Exception {
        try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("windows-partners.zip")) { return CatalogImport.read(in); }
    }
    private PartnerStore.Partner partner(String id,String name,String type) { return new PartnerStore.Partner(id,name,type,"0012","Contact","0030","a@example.com","Address","Products","30 days","Note\nline"); }
    @Test public void windowsImportAllDetailsRepeatAndAtomicRollback() throws Exception {
        String dbName="partners-import-test.db";context.deleteDatabase(dbName);var recovery=new File(context.getCacheDir(),"partners-import-before.json");
        try(var store=new FarmStore(context,dbName)) {
            var data=fixture(); assertEquals(1,CatalogImport.preview(store,data).partners());assertTrue(new PartnerStore(store).partners().isEmpty());
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_partner BEFORE INSERT ON business_partners BEGIN SELECT RAISE(ABORT,'test'); END");
            try {CatalogImport.apply(store,data,recovery);fail();} catch(android.database.SQLException expected) {}
            assertTrue(store.fields().isEmpty());assertTrue(new CatalogStore(store).products().isEmpty());
            try(var c=store.getReadableDatabase().rawQuery("SELECT count(*) FROM pending_changes",null)){c.moveToFirst();assertEquals(0,c.getInt(0));}
            store.getWritableDatabase().execSQL("DROP TRIGGER fail_partner");
            assertEquals(1,CatalogImport.apply(store,data,recovery).partners());var registry=new PartnerStore(store);var p=registry.partners().get(0);
            assertNotEquals(data.partners().get(0).id(),p.id());assertEquals("both",p.type());assertEquals("001234567",p.taxId());assertEquals("Μαρία",p.contact());assertEquals("00302100000000",p.phone());assertEquals("partner@example.com",p.email());assertEquals("Χίος 82100",p.address());assertEquals("Μαστίχα; εργαλεία",p.products());assertEquals("30 ημέρες",p.paymentTerms());assertEquals("Πρώτη γραμμή;\nΔεύτερη γραμμή",p.notes());
            assertEquals(5,CatalogImport.apply(store,data,recovery).skipped());
            registry.save(new PartnerStore.Partner(p.id(),"Renamed",p.type(),p.taxId(),p.contact(),p.phone(),p.email(),p.address(),p.products(),p.paymentTerms(),p.notes()));
            assertEquals(0,CatalogImport.preview(store,data).partners());assertEquals("Renamed",registry.partners().get(0).name());
        } finally {context.deleteDatabase(dbName);recovery.delete();}
    }
    @Test public void crudFilteringIsolationAndRollback() throws Exception {
        String dbName="partners-crud-test.db",other="partners-isolation-test.db";context.deleteDatabase(dbName);context.deleteDatabase(other);
        try(var store=new FarmStore(context,dbName);var isolated=new FarmStore(context,other)) {
            var registry=new PartnerStore(store);String id=registry.save(partner(null," Συνεργάτης ","both"));
            assertTrue(new PartnerStore(isolated).partners().isEmpty());var p=registry.partners().get(0);
            assertEquals("Συνεργάτης",p.name());assertTrue(PartnerStore.matches(p,"συνεργάτης","supplier"));assertTrue(PartnerStore.matches(p,"0012","buyer"));assertTrue(PartnerStore.matches(p,"Products","both"));assertFalse(PartnerStore.matches(p,"missing","all"));
            try {registry.save(partner(null,"συνεργάτης","buyer"));fail();} catch(IllegalArgumentException expected) {}
            try {registry.save(partner(null," ","buyer"));fail();} catch(IllegalArgumentException expected) {}
            try {registry.save(partner(null,"Other","invalid"));fail();} catch(IllegalArgumentException expected) {}
            store.getWritableDatabase().execSQL("CREATE TRIGGER fail_queue BEFORE INSERT ON pending_changes BEGIN SELECT RAISE(ABORT,'test'); END");
            try {registry.save(partner(id,"Changed","buyer"));fail();} catch(android.database.SQLException expected) {}
            try {registry.delete(id);fail();} catch(android.database.SQLException expected) {}
            assertEquals("Συνεργάτης",registry.partners().get(0).name());
            store.getWritableDatabase().execSQL("DROP TRIGGER fail_queue");registry.save(partner(id,"Changed","buyer"));registry.delete(id);assertTrue(registry.partners().isEmpty());
            try {registry.save(partner(id,"Resurrect","buyer"));fail();} catch(IllegalArgumentException expected) {}
            assertEquals(0,LocalBackup.inspect(store,LocalBackup.snapshot(store)));
            try(var c=store.getReadableDatabase().rawQuery("SELECT revision,deleted_at FROM business_partners WHERE id=?",new String[]{id})){assertTrue(c.moveToFirst());assertEquals(3,c.getInt(0));assertFalse(c.isNull(1));}
        } finally {context.deleteDatabase(dbName);context.deleteDatabase(other);}
    }
    @Test public void backupRoundTripAndSchemaThreeUpgrade() throws Exception {
        String name="partners-backup-test.db";context.deleteDatabase(name);var file=new File(context.getCacheDir(),"partners-backup-before.json");
        try {
            byte[] old;
            try(var store=new FarmStore(context,name)) {
                store.addField("Preserved",1);new CatalogStore(store).saveProduct(null,"Product","kg",true);
                var envelope=new JSONObject(new String(LocalBackup.snapshot(store),StandardCharsets.UTF_8));var payload=new JSONObject(envelope.getString("payload"));payload.remove("business_partners");payload.remove("inventory_items");payload.remove("inventory_movements");payload.remove("money_entries");payload.remove("production");payload.remove("production_sales");payload.remove("farm_activities");payload.remove("plant_protection_records");payload.remove("workers");payload.remove("labor_entries");payload.remove("planting_batches");payload.remove("equipment");payload.remove("equipment_maintenance");payload.remove("invoice_documents");payload.remove("year_locks");payload.remove("gis_records");LegacySchema.removeSync(payload);String data=payload.toString();
                var hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8))) hash.append(String.format("%02x",b&255));
                old=envelope.put("schema",3).put("payload",data).put("sha256",hash.toString()).toString().getBytes(StandardCharsets.UTF_8);
                LegacySchema.dropStage12(store.getWritableDatabase());store.getWritableDatabase().execSQL("DROP TABLE equipment_maintenance");store.getWritableDatabase().execSQL("DROP TABLE equipment");store.getWritableDatabase().execSQL("DROP INDEX money_service");store.getWritableDatabase().execSQL("DROP TABLE planting_batches");store.getWritableDatabase().execSQL("DROP TABLE plant_protection_records");store.getWritableDatabase().execSQL("DROP TABLE labor_entries");store.getWritableDatabase().execSQL("DROP TABLE workers");store.getWritableDatabase().execSQL("DROP TABLE farm_activities");store.getWritableDatabase().execSQL("DROP TABLE production_sales");store.getWritableDatabase().execSQL("DROP TABLE production");store.getWritableDatabase().execSQL("DROP TABLE money_entries");store.getWritableDatabase().execSQL("DROP TABLE inventory_movements");store.getWritableDatabase().execSQL("DROP TABLE inventory_items");store.getWritableDatabase().execSQL("DROP TABLE business_partners");store.getWritableDatabase().setVersion(3);
            }
            try(var store=new FarmStore(context,name)) {
                assertEquals(15,store.getReadableDatabase().getVersion());assertEquals("Preserved",store.fields().get(0).name());assertEquals(1,new CatalogStore(store).products().size());
                var registry=new PartnerStore(store);String id=registry.save(partner(null,"Backup partner","supplier"));byte[] snapshot=LocalBackup.snapshot(store);registry.delete(id);
                LocalBackup.restore(store,snapshot,file);assertEquals("Note\nline",registry.partners().get(0).notes());
                LocalBackup.restore(store,old,file);assertTrue(registry.partners().isEmpty());assertEquals(1,new CatalogStore(store).products().size());
            }
        } finally {context.deleteDatabase(name);file.delete();}
    }
}
