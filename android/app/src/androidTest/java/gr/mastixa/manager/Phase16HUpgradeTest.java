package gr.mastixa.manager;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.io.IOException;
import org.junit.Assume;
import org.junit.Test;
import static org.junit.Assert.*;

/** Ordinary suite: isolated v11 migration. Real APK replacement: explicit staged opt-in. */
public class Phase16HUpgradeTest {
    private static final String DB = "phase16h-upgrade.db";
    private static final String PREFS = "phase16h-upgrade";
    private static final String SENTINEL = "phase16h-preserved";
    private static final String FIELD = "Phase 16H upgrade sentinel";
    private static final String FIELD_ID = "16000000-0000-4000-8000-000000000001";

    @Test public void seedLegacyState() throws Exception {
        Assume.assumeTrue("PENDING real APK replacement: run explicit phase16hStage=seed on approved OLD APK",
            "seed".equals(InstrumentationRegistry.getArguments().getString("phase16hStage")));
        Context c = context();
        assertChecks(c);
        assertFalse("Do not overwrite an outstanding replacement fixture", c.getDatabasePath(DB).exists());
        createLegacy(c, DB);
        assertTrue(c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear()
            .putString("sentinel", SENTINEL).putInt("seedVersion", version(c)).commit());
    }

    @Test public void syntheticV11MigrationPreservesIdentityAndData() throws Exception {
        Context c=context();assertChecks(c);
        String name="phase16h-synthetic-"+UUID.randomUUID()+".db";
        try(AutoCloseable cleanup=()->{
            if(!c.deleteDatabase(name)&&c.getDatabasePath(name).exists())throw new IOException("Synthetic database cleanup failed");
        }) {
            createLegacy(c,name);
            // Exercise the real DDL inside a deliberately uncommitted transaction.
            // A failed migration must leave the old schema/data available for retry.
            try(SQLiteDatabase db=SQLiteDatabase.openDatabase(c.getDatabasePath(name).getPath(),null,SQLiteDatabase.OPEN_READWRITE);
                    FarmStore migration=new FarmStore(c,name)) {
                db.beginTransaction();
                try {
                    migration.onUpgrade(db,11,15);
                    assertTrue(tableExists(db,"cadastral_reference"));
                    db.setVersion(15);
                }finally{db.endTransaction();} // intentionally no setTransactionSuccessful
                assertEquals(11,userVersion(db));
                for(String table:new String[]{"invoice_documents","year_locks","gis_records","cadastral_reference"})assertFalse(tableExists(db,table));
                for(String table:GisSyncRepository.TABLES)assertFalse(tableExists(db,table));
            }
            verifyMigration(c,name);
        }
    }

    private static void createLegacy(Context c,String name)throws Exception {
        // Build schema 11 directly. No current FarmStore/onCreate, no downgrade of a v15 DB.
        java.io.File file=c.getDatabasePath(name),parent=file.getParentFile();
        if(parent==null||(!parent.isDirectory()&&!parent.mkdirs()))throw new IOException("Checks database directory unavailable");
        try(SQLiteDatabase db=SQLiteDatabase.openOrCreateDatabase(file,null)) {
            db.beginTransaction();
            try {
                db.execSQL("CREATE TABLE fields(id TEXT PRIMARY KEY,name TEXT NOT NULL,area REAL NOT NULL CHECK(area>=0),revision INTEGER NOT NULL,updated_at INTEGER NOT NULL,kaek TEXT NOT NULL DEFAULT '',location TEXT NOT NULL DEFAULT '',trees INTEGER NOT NULL DEFAULT 0 CHECK(trees>=0),notes TEXT NOT NULL DEFAULT '',deleted_at INTEGER)");
                db.execSQL("CREATE TABLE pending_changes(operation_id TEXT PRIMARY KEY,entity_id TEXT NOT NULL,entity TEXT NOT NULL,operation TEXT NOT NULL,revision INTEGER NOT NULL,created_at INTEGER NOT NULL)");
                CatalogStore.createTables(db);PartnerStore.createTables(db);InventoryStore.createTables(db);
                MoneyStore.createTables(db);ProductionStore.createTables(db);ActivityStore.createTables(db);
                WorkStore.createTables(db);WorkStore.createPlantings(db);WorkStore.createEquipment(db);
                db.execSQL("INSERT INTO fields VALUES(?,?,12.5,7,123456789,'012345678901','upgrade-fixture',17,'must survive package replacement',NULL)",new Object[]{FIELD_ID,FIELD});
                db.execSQL("INSERT INTO pending_changes VALUES('phase16h-operation',?,'fields','create',7,123456789)",new Object[]{FIELD_ID});
                db.setVersion(11);db.setTransactionSuccessful();
            }finally{db.endTransaction();}
            assertEquals(11,userVersion(db));
            for(String table:new String[]{"invoice_documents","year_locks","gis_records","cadastral_reference"})assertFalse(tableExists(db,table));
            for(String table:GisSyncRepository.TABLES)assertFalse(tableExists(db,table));
            assertFalse(db.inTransaction());
        }
    }

    @Test public void verifyPreservedAndMigrated() throws Exception {
        Assume.assumeTrue("PENDING real APK replacement: explicit phase16hStage=verify after data-preserving install -r",
            "verify".equals(InstrumentationRegistry.getArguments().getString("phase16hStage")));
        Context c = context();assertChecks(c);
        assertEquals(SENTINEL, c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("sentinel", null));
        int seeded=c.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getInt("seedVersion",-1);
        assertTrue("Seed version evidence required",seeded>=0);
        assertTrue("A single APK run cannot accept replacement",seeded!=version(c));
        try(SQLiteDatabase db=SQLiteDatabase.openDatabase(c.getDatabasePath(DB).getPath(),null,SQLiteDatabase.OPEN_READONLY)) {
            assertEquals("Verification must start at legacy schema",11,userVersion(db));
        }
        verifyMigration(c,DB);
        // Retain state if verification fails; remove only this fixture after acceptance assertions.
        c.deleteDatabase(DB);
        assertFalse(c.getDatabasePath(DB).exists());
        assertTrue(c.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().clear().commit());
    }

    private static void verifyMigration(Context c,String name) throws Exception {
        try (FarmStore farm = new FarmStore(c, name)) {
            var fields = farm.fields();
            assertEquals("Migration must preserve the seeded field", 1, fields.size());
            var field = fields.get(0);
            assertEquals(FIELD_ID,field.id());
            assertEquals(FIELD, field.name());
            assertEquals(12.5, field.area(), 0.000001);
            assertEquals("012345678901", field.kaek());
            assertEquals("upgrade-fixture", field.location());
            assertEquals(17, field.trees());
            assertEquals("must survive package replacement", field.notes());

            SQLiteDatabase db = farm.getReadableDatabase();
            assertEquals(15, userVersion(db));
            assertTrue(tableExists(db, "invoice_documents"));
            assertTrue(tableExists(db, "year_locks"));
            assertTrue(tableExists(db, "gis_records"));
            assertTrue(tableExists(db, "cadastral_reference"));
            for (String table : GisSyncRepository.TABLES) assertTrue("Missing migrated table: " + table, tableExists(db, table));
            try(Cursor row=db.rawQuery("SELECT revision,updated_at FROM fields WHERE id=?",new String[]{FIELD_ID})) {
                assertTrue(row.moveToFirst());assertEquals(7,row.getInt(0));assertEquals(123456789L,row.getLong(1));
            }
            try(Cursor row=db.rawQuery("SELECT entity_id,revision FROM pending_changes WHERE operation_id='phase16h-operation'",null)) {
                assertTrue(row.moveToFirst());assertEquals(FIELD_ID,row.getString(0));assertEquals(7,row.getInt(1));assertFalse(row.moveToNext());
            }
            assertFalse(db.inTransaction());
        }
    }

    private static int version(Context c)throws PackageManager.NameNotFoundException {
        return c.getPackageManager().getPackageInfo(c.getPackageName(),0).versionCode;
    }
    private static void assertChecks(Context c){assertTrue("Only synthetic checks app permitted",c.getPackageName().endsWith(".checks"));}

    @Test public void storageAccessUsesSafWithoutBroadStoragePermissions() throws Exception {
        Context c = context();
        PackageInfo info = c.getPackageManager().getPackageInfo(c.getPackageName(), PackageManager.GET_PERMISSIONS);
        Set<String> requested = new HashSet<>();
        if (info.requestedPermissions != null) requested.addAll(Arrays.asList(info.requestedPermissions));
        assertFalse(requested.contains("android.permission.READ_EXTERNAL_STORAGE"));
        assertFalse(requested.contains("android.permission.WRITE_EXTERNAL_STORAGE"));
        assertFalse(requested.contains("android.permission.MANAGE_EXTERNAL_STORAGE"));

        // Do not require DocumentsUI to be installed in this isolated headless AVD.
        // ExportFailureUiTest exercises the application's actual ACTION_CREATE_DOCUMENT
        // launch path and verifies the unavailable-picker fallback separately.
    }

    private static Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }

    private static int userVersion(SQLiteDatabase db) {
        try (Cursor c = db.rawQuery("PRAGMA user_version", null)) {
            assertTrue(c.moveToFirst());
            return c.getInt(0);
        }
    }

    private static boolean tableExists(SQLiteDatabase db, String table) {
        try (Cursor c = db.rawQuery("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", new String[]{table})) {
            return c.moveToFirst();
        }
    }
}
