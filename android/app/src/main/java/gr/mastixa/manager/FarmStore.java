package gr.mastixa.manager;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Local records and pending changes commit together. No network dependency. */
public final class FarmStore extends SQLiteOpenHelper {
    public record Field(String id, String name, double area, String kaek, String location, int trees, String notes) {}
    public FarmStore(Context context) { this(context, "mastixa.db"); }
    public FarmStore(Context context, String name) { super(context, name, null, 15); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE fields(id TEXT PRIMARY KEY, name TEXT NOT NULL, area REAL NOT NULL CHECK(area>=0), revision INTEGER NOT NULL, updated_at INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE pending_changes(operation_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, entity TEXT NOT NULL, operation TEXT NOT NULL, revision INTEGER NOT NULL, created_at INTEGER NOT NULL)");
        onUpgrade(db, 1, 15);
    }
    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE fields ADD COLUMN kaek TEXT NOT NULL DEFAULT ''");
            db.execSQL("ALTER TABLE fields ADD COLUMN location TEXT NOT NULL DEFAULT ''");
            db.execSQL("ALTER TABLE fields ADD COLUMN trees INTEGER NOT NULL DEFAULT 0 CHECK(trees>=0)");
            db.execSQL("ALTER TABLE fields ADD COLUMN notes TEXT NOT NULL DEFAULT ''");
            db.execSQL("ALTER TABLE fields ADD COLUMN deleted_at INTEGER");
        }
        if(oldVersion<3) CatalogStore.createTables(db);
        if(oldVersion<4) PartnerStore.createTables(db);
        if(oldVersion<5) InventoryStore.createTables(db);
        if(oldVersion<6) MoneyStore.createTables(db);
        if(oldVersion<7) ProductionStore.createTables(db);
        if(oldVersion<8) ActivityStore.createTables(db);
        if(oldVersion<9) WorkStore.createTables(db);
        if(oldVersion<10) WorkStore.createPlantings(db);
        if(oldVersion<11) WorkStore.createEquipment(db);
        if(oldVersion<12){DocumentStore.create(db);YearLocks.create(db);}
        if(oldVersion<13)GeoStore.create(db);
        if(oldVersion<14)GisSyncRepository.create(db);
        if(oldVersion<15)CadastralStore.create(db);
    }
    public void addField(String name, double area) {
        saveField(null,name,area,"","",0,"");
    }
    public void saveField(String existingId, String name, double area, String kaek, String location, int trees, String notes) {
        name = name.trim();
        if (name.isEmpty() || !Double.isFinite(area) || area < 0 || trees < 0) throw new IllegalArgumentException("Μη έγκυρα στοιχεία.");
        SQLiteDatabase db = getWritableDatabase();
        String id = existingId == null ? UUID.randomUUID().toString() : existingId; long now = System.currentTimeMillis();
        db.beginTransaction();
        try {
            ContentValues row = new ContentValues();
            int revision = existingId == null ? 1 : revision(db,id) + 1;
            row.put("id", id); row.put("name", name); row.put("area", area); row.put("revision", revision); row.put("updated_at", now);
            row.put("kaek",kaek.trim()); row.put("location",location.trim()); row.put("trees",trees); row.put("notes",notes.trim());
            if (existingId == null) db.insertOrThrow("fields", null, row);
            else if (db.update("fields",row,"id=? AND deleted_at IS NULL",new String[]{id}) != 1) throw new IllegalArgumentException("Το αγροτεμάχιο δεν υπάρχει.");
            enqueue(db,id,existingId == null ? "create" : "update",revision,now);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    private int revision(SQLiteDatabase db, String id) {
        try (Cursor c = db.rawQuery("SELECT revision FROM fields WHERE id=? AND deleted_at IS NULL",new String[]{id})) {
            if (!c.moveToFirst()) throw new IllegalArgumentException("Το αγροτεμάχιο δεν υπάρχει.");
            return c.getInt(0);
        }
    }
    private void enqueue(SQLiteDatabase db, String id, String operation, int revision, long now) {
        ContentValues change = new ContentValues();
        change.put("operation_id",UUID.randomUUID().toString()); change.put("entity_id",id);
        change.put("entity","fields"); change.put("operation",operation); change.put("revision",revision); change.put("created_at",now);
        db.insertOrThrow("pending_changes",null,change);
    }
    public void deleteField(String id) {
        SQLiteDatabase db = getWritableDatabase(); db.beginTransaction();
        try {
            int revision = revision(db,id)+1; long now = System.currentTimeMillis();
            ContentValues row = new ContentValues(); row.put("deleted_at",now); row.put("updated_at",now); row.put("revision",revision);
            db.update("fields",row,"id=?",new String[]{id});
            GeoStore.deleteForField(db,id,now);
            enqueue(db,id,"delete",revision,now); db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    public List<Field> fields() {
        List<Field> rows = new ArrayList<>();
        try (Cursor cursor = getReadableDatabase().rawQuery("SELECT id,name,area,kaek,location,trees,notes FROM fields WHERE deleted_at IS NULL ORDER BY updated_at DESC,id", null)) {
            while(cursor.moveToNext()) rows.add(new Field(cursor.getString(0), cursor.getString(1), cursor.getDouble(2),cursor.getString(3),cursor.getString(4),cursor.getInt(5),cursor.getString(6)));
        }
        return rows;
    }
}
