package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;

/** Synthetic-only storage-fence source. NOT RUN in implementation package.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralMigrationTest {
    @Test public void defaultDenyAndInterruptedPermitRollback()throws Exception {
        try(var db=CadastralSynthetic.database()) {
            assertThrows(android.database.sqlite.SQLiteException.class,()->db.execSQL("UPDATE fields SET area=99"));
            assertThrows(IllegalStateException.class,()->CadastralMigration.guarded(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,()->{
                db.execSQL("UPDATE fields SET area=99");throw new IllegalStateException("Synthetic interruption");
            }));
            try(var c=db.rawQuery("SELECT area FROM fields WHERE id=?",new String[]{CadastralSynthetic.FIELD})){assertTrue(c.moveToFirst());assertEquals(3.25,c.getDouble(0),0);}
            try(var c=db.rawQuery("SELECT permit FROM cadastral_storage_state",null)){assertTrue(c.moveToFirst());assertEquals(0,c.getInt(0));}
        }
    }
    @Test public void oldFileRestoreAndPartialActivationRefuseFallback() {
        Map<String,String> expected=Map.of("activation_id","synthetic","farm_scope","fixture","source_hash","source","receipt_hash","receipt");
        Map<String,String> target=new HashMap<>(expected);target.put("phase","PREPARED");
        target.put("schema_version","2");target.put("min_writer","2");target.put("permit","0");
        assertEquals(CadastralMigration.Recovery.PREPARED_REQUIRES_SOURCE_LOCK,CadastralMigration.resolve(expected,null,target));
        assertEquals(CadastralMigration.Recovery.RECOVER_ACTIVATION,CadastralMigration.resolve(expected,expected,target));
        target.put("phase","ACTIVE");assertEquals(CadastralMigration.Recovery.ACTIVE,CadastralMigration.resolve(expected,expected,target));
        assertEquals(CadastralMigration.Recovery.RESTORE_DETECTED,CadastralMigration.resolve(expected,null,target));
        target.put("source_hash","wrong");assertEquals(CadastralMigration.Recovery.RECOVERY_REQUIRED,CadastralMigration.resolve(expected,expected,target));
    }
    @Test public void syntheticRowsPreserveAndroidUuidsAndRetryReceipt()throws Exception {
        try(var db=CadastralSynthetic.database()) {
            var rows=List.of(new CadastralMigration.SyntheticField(CadastralSynthetic.FIELD,"510000000001",true,List.of()));
            String first=CadastralMigration.importSyntheticRows(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,rows);
            assertEquals(first,CadastralMigration.importSyntheticRows(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,rows));
            try(var c=db.rawQuery("SELECT field_uuid,raw_kaek,classification FROM cadastral_legacy_bindings",null)) {
                assertTrue(c.moveToFirst());assertEquals(CadastralSynthetic.FIELD,c.getString(0));assertEquals("510000000001",c.getString(1));assertEquals("confirmed_greek",c.getString(2));
            }
            try(var c=db.rawQuery("SELECT COUNT(*) FROM fields",null)){assertTrue(c.moveToFirst());assertEquals(1,c.getInt(0));}
        }
    }
}
