package gr.mastixa.manager;

/** Helpers used by instrumentation tests to emulate historical database/backup schemas. */
final class LegacySchema {
    private LegacySchema() {}

    static void removeSync(org.json.JSONObject payload) {
        for (String table : GisSyncRepository.TABLES) payload.remove(table);
        // Every backup schema that predates GIS sync also predates later additive
        // logical-backup tables such as Phase 12 crop programs and Phase 14/15 history.
        for (String table : CropProgramBackup.TABLES) payload.remove(table);
        for (String table : PlantTrackingBackup.TABLES) payload.remove(table);
        payload.remove(PlantingHistory.TABLE);
        for (String table : SensorDataBackup.TABLES) payload.remove(table);
        payload.remove("cadastral_reference");
    }

    static void dropSync(android.database.sqlite.SQLiteDatabase db) {
        db.execSQL("DROP TABLE IF EXISTS cadastral_reference");
        for (String table : GisSyncRepository.TABLES) db.execSQL("DROP TABLE IF EXISTS " + table);
    }

    static void dropStage12(android.database.sqlite.SQLiteDatabase db) {
        dropSync(db);
        db.execSQL("DROP TABLE IF EXISTS gis_records");
        for (var pair : YearLocks.DATED) {
            for (String event : new String[]{"INSERT", "UPDATE", "DELETE"}) {
                db.execSQL("DROP TRIGGER IF EXISTS year_guard_" + pair[0] + "_" + event);
            }
        }
        db.execSQL("DROP TABLE invoice_documents");
        db.execSQL("DROP TABLE year_locks");
    }
}
