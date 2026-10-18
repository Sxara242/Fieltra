package gr.mastixa.manager;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Versioned logical snapshot of all current application tables. */
public final class LocalBackup {
    private static final int LIMIT = 50 * 1024 * 1024;
    private static final int CURRENT_SCHEMA = 19;
    private static final String[] TABLES = {"fields", "pending_changes", "producer", "products", "product_fields", "business_partners", "inventory_items", "inventory_movements", "money_entries", "production", "production_sales", "farm_activities", "plant_protection_records", "workers", "labor_entries", "planting_batches", "equipment", "equipment_maintenance", "invoice_documents", "year_locks", "gis_records", "gis_sync_state", "gis_sync_cursor", "gis_sync_conflicts", "crop_programs", "crop_program_rules", "crop_program_assignments", "crop_tasks", "individual_plants", "plant_events", "planting_replantings", "sensor_devices", "sensor_channels", "sensor_observations", "cadastral_reference"};
    private static final String[][] COLUMNS = {
        {"id","name","area","revision","updated_at","kaek","location","trees","notes","deleted_at"},
        {"operation_id","entity_id","entity","operation","revision","created_at"},
        {"id","name","tax_id","phone","email","notes","revision","updated_at"},
        {"id","name","unit","is_active","revision","updated_at"},
        {"id","product_id","field_id","variety","planting_date","cultivation_status","revision","updated_at"},
        {"id","name","partner_type","tax_id","contact_person","phone","email","address","products","payment_terms","notes","revision","updated_at","deleted_at"},
        InventoryStore.ITEM_COLUMNS,InventoryStore.MOVEMENT_COLUMNS,MoneyStore.COLUMNS,ProductionStore.HARVEST_COLUMNS,ProductionStore.SALE_COLUMNS,ActivityStore.COLUMNS,WorkStore.PROTECTION_COLUMNS,WorkStore.WORKER_COLUMNS,WorkStore.LABOR_COLUMNS,WorkStore.PLANTING_COLUMNS,WorkStore.EQUIPMENT_COLUMNS,WorkStore.SERVICE_COLUMNS,DocumentStore.COLUMNS,YearLocks.COLUMNS,GeoStore.COLUMNS,GisSyncRepository.COLUMNS[0],GisSyncRepository.COLUMNS[1],GisSyncRepository.COLUMNS[2],CropProgramBackup.COLUMNS[0],CropProgramBackup.COLUMNS[1],CropProgramBackup.COLUMNS[2],CropProgramBackup.COLUMNS[3],PlantTrackingBackup.COLUMNS[0],PlantTrackingBackup.COLUMNS[1],PlantingHistory.COLUMNS,SensorDataBackup.COLUMNS[0],SensorDataBackup.COLUMNS[1],SensorDataBackup.COLUMNS[2],CadastralStore.COLUMNS
    };
    private static String hash(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder(); for(byte b : digest) result.append(String.format("%02x",b & 255)); return result.toString();
    }
    private static int tableCountForSchema(int schema) throws IOException {
        return switch(schema) {
            case 2 -> 2;
            case 3 -> 5;
            case 4 -> 6;
            case 5 -> 8;
            case 6 -> 9;
            case 7 -> 11;
            case 8 -> 12;
            case 9 -> 15;
            case 10 -> 16;
            case 11 -> 18;
            case 12 -> 20;
            case 13 -> 21;
            case 14 -> 24;
            case 15 -> 28;
            case 16 -> 30;
            case 17 -> 31;
            case 18 -> 34;
            case 19 -> TABLES.length;
            default -> throw new IOException("Μη συμβατό αντίγραφο Mastixa Android.");
        };
    }
    public static byte[] snapshot(FarmStore store) throws Exception {
        SQLiteDatabase db = store.getWritableDatabase(); CropProgramStore.create(db); PlantTrackingStore.create(db); PlantingHistory.create(db); SensorDataStore.create(db); JSONObject payload = new JSONObject();
        db.beginTransaction();
        try {
            for (int t=0;t<TABLES.length;t++) {
                JSONArray rows = new JSONArray();
                try(Cursor c = db.query(TABLES[t],COLUMNS[t],null,null,null,null,null)) {
                    while(c.moveToNext()) {
                        JSONObject row = new JSONObject();
                        for(int i=0;i<c.getColumnCount();i++) row.put(c.getColumnName(i),c.isNull(i) ? JSONObject.NULL : c.getType(i)==Cursor.FIELD_TYPE_INTEGER ? c.getLong(i) : c.getType(i)==Cursor.FIELD_TYPE_FLOAT ? c.getDouble(i) : c.getString(i));
                        rows.put(row);
                    }
                }
                payload.put(TABLES[t],rows);
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        String data = payload.toString();
        byte[] bytes = new JSONObject().put("format","mastixa-android-backup").put("version",1).put("schema",CURRENT_SCHEMA).put("payload",data).put("sha256",hash(data)).toString().getBytes(StandardCharsets.UTF_8);
        if(bytes.length>LIMIT) throw new IOException("Το αντίγραφο υπερβαίνει το όριο 50 MB.");
        return bytes;
    }
    public static byte[] read(InputStream input) throws IOException {
        if(input==null) throw new IOException("Δεν ανοίγει το αρχείο.");
        ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] buffer = new byte[8192]; int count;
        while((count=input.read(buffer))!=-1) { if(out.size()+count>LIMIT) throw new IOException("Το αρχείο υπερβαίνει τα 50 MB."); out.write(buffer,0,count); }
        return out.toByteArray();
    }
    private static SQLiteDatabase validate(FarmStore store, byte[] bytes) throws Exception {
        if(bytes.length>LIMIT) throw new IOException("Πολύ μεγάλο αρχείο.");
        JSONObject envelope = new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        int schema=envelope.getInt("schema");
        if(!"mastixa-android-backup".equals(envelope.getString("format")) || envelope.getInt("version")!=1 || schema<2 || schema>CURRENT_SCHEMA) throw new IOException("Μη συμβατό αντίγραφο Mastixa Android.");
        String data = envelope.getString("payload");
        if(!hash(data).equals(envelope.getString("sha256"))) throw new IOException("Το αρχείο είναι αλλοιωμένο.");
        JSONObject payload = new JSONObject(data);
        int tableCount=tableCountForSchema(schema);
        if(payload.length()!=tableCount) throw new IOException("Μη έγκυρη δομή.");
        SQLiteDatabase stage = SQLiteDatabase.create(null);
        try {
            store.onCreate(stage);
            CropProgramStore.create(stage);
            PlantTrackingStore.create(stage);
            PlantingHistory.create(stage);
            SensorDataStore.create(stage);
            for(int t=0;t<tableCount;t++) {
                JSONArray rows = payload.getJSONArray(TABLES[t]);
                for(int n=0;n<rows.length();n++) {
                    JSONObject row = rows.getJSONObject(n); ContentValues values = new ContentValues();
                    if(row.length()!=COLUMNS[t].length) throw new IOException("Μη έγκυρα πεδία.");
                    for(String key:COLUMNS[t]) {
                        Object value = row.get(key);
                        boolean decimal=java.util.Set.of("area","minimum_stock","quantity","unit_price","total_cost","amount","quantity_kg","price_per_kg","total_amount","duration_minutes","water_quantity_m3","dose","cost","inventory_quantity","spray_volume_l","area_stremma","default_hourly_rate","hours","hourly_rate","current_meter","meter_value","next_service_meter").contains(key) || PlantTrackingBackup.isDecimalColumn(key) || SensorDataBackup.isDecimalColumn(key);
                        boolean numeric = decimal || key.equals("revision") || key.equals("updated_at") || key.equals("trees") || key.equals("deleted_at") || key.equals("created_at") || key.equals("last_sync_at") || key.equals("remote_version") || key.equals("position") || key.equals("resolved_at") || key.equals("is_locked") || key.equals("is_active") || key.equals("active") || key.equals("harvest_interval_days") || key.equals("trees_planted") || key.equals("trees_alive") || key.equals("tree_count") || CropProgramBackup.isIntegerColumn(key);
                        boolean nullableNumeric = key.equals("deleted_at") || (t==17 && key.equals("next_service_meter")) || CropProgramBackup.isNullableIntegerColumn(key) || PlantTrackingBackup.isNullableNumericColumn(key);
                        if(value==JSONObject.NULL && nullableNumeric) values.putNull(key);
                        else if(numeric && value instanceof Number) {
                            double number = ((Number)value).doubleValue();
                            if(!Double.isFinite(number) || (!PlantTrackingBackup.isDecimalColumn(key) && !SensorDataBackup.allowsNegativeNumeric(key) && number<0) || (!decimal && (number!=Math.rint(number) || number>Long.MAX_VALUE))) throw new IOException("Μη έγκυρος αριθμός.");
                            if(decimal) values.put(key,number); else values.put(key,((Number)value).longValue());
                        } else if(!numeric && value instanceof String) values.put(key,(String)value);
                        else throw new IOException("Μη έγκυρος τύπος πεδίου.");
                    }
                    if(row.has("revision") && row.getLong("revision")<1) throw new IOException("Μη έγκυρη έκδοση εγγραφής.");
                    if(t>=21 && t<=23) GisSyncRepository.validateBackup(t-21,row);
                    if(t>=24 && t<=27) CropProgramBackup.validateRow(t-24,row);
                    if(t>=28 && t<=29) PlantTrackingBackup.validateRow(t-28,row);
                    if(t==30) PlantingHistory.validateBackupRow(row);
                    if(t>=31 && t<=33) SensorDataBackup.validateRow(t-31,row);
                    if(t==34) CadastralStore.validateBackup(row);
                    if(t==20){if(row.getString("id").isBlank()||row.getString("field_id").isBlank())throw new IOException("Missing GIS identity");GeoStore.validatePayload(row.getString("kind"),new JSONObject(row.getString("payload")));}
                    if(t==0 && (row.getString("id").isBlank() || row.getString("name").isBlank() || row.getLong("trees")>Integer.MAX_VALUE)) throw new IOException("Μη έγκυρο αγροτεμάχιο.");
                    if(t==1 && (row.getString("operation_id").isBlank() || !java.util.Set.of("fields","producer","products","product_fields","business_partners","inventory_items","inventory_movements","money_entries","production","production_sales","farm_activities","plant_protection_records","workers","labor_entries","planting_batches","equipment","equipment_maintenance","invoice_documents","year_locks","gis_records").contains(row.getString("entity")) || !java.util.Set.of("create","update","delete").contains(row.getString("operation")))) throw new IOException("Μη έγκυρη αλλαγή.");
                    if(t==3 && (row.getString("id").isBlank() || row.getString("name").isBlank() || row.getString("unit").isBlank())) throw new IOException("Μη έγκυρο προϊόν.");
                    if(t==5 && (row.getString("id").isBlank() || row.getString("name").isBlank() || !java.util.Set.of("supplier","buyer","both").contains(row.getString("partner_type")))) throw new IOException("Μη έγκυρος συνεργάτης.");
                    if(t==6) { if(row.getString("id").isBlank()) throw new IOException("Λείπει ταυτότητα είδους."); InventoryStore.validateItem(new InventoryStore.Item(row.getString("id"),row.getString("name"),row.getString("category"),row.getString("unit"),row.getDouble("minimum_stock"),row.getString("notes"))); }
                    if(t==7) { if(row.getString("id").isBlank()) throw new IOException("Λείπει ταυτότητα κίνησης."); InventoryStore.validateMovement(new InventoryStore.Movement(row.getString("id"),row.getString("item_id"),row.getString("movement_date"),row.getString("movement_type"),row.getDouble("quantity"),row.getString("field_id"),row.getString("partner_id"),row.getString("supplier_name"),row.getDouble("unit_price"),row.getDouble("total_cost"),row.getString("notes"),row.getString("source_type"),row.getString("source_id"),row.getString("expense_id"),row.getString("windows_id"))); }
                    if(t==8) { if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα οικονομικής εγγραφής.");MoneyStore.validate(new MoneyStore.Entry(row.getString("id"),row.getString("kind"),row.getString("entry_date"),row.getString("field_id"),row.getString("category"),row.getString("description"),row.getString("partner_id"),row.getString("partner_name"),row.getString("payment_method"),row.getDouble("amount"),row.getString("notes"),row.getString("source_type"),row.getString("source_id"),row.getString("windows_id"))); }
                    if(t==9){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα παραγωγής.");ProductionStore.validate(new ProductionStore.Harvest(row.getString("id"),row.getString("entry_date"),row.getString("product_id"),row.getString("product"),row.getString("field_id"),row.getDouble("quantity_kg"),row.getString("notes"),row.getString("windows_id")));}
                    if(t==10){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα πώλησης.");ProductionStore.validate(new ProductionStore.Sale(row.getString("id"),row.getString("sale_date"),row.getString("product_id"),row.getString("product"),row.getString("buyer_id"),row.getString("buyer_name"),row.getDouble("quantity_kg"),row.getDouble("price_per_kg"),row.getDouble("total_amount"),row.getString("payment_method"),row.getString("notes"),row.getString("income_windows_id"),row.getString("windows_id")));}
                    if(t==11){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα εργασίας.");ActivityStore.validate(new ActivityStore.Activity(row.getString("id"),row.getString("activity_date"),row.getString("field_id"),row.getString("category"),row.getString("status"),row.getDouble("duration_minutes"),row.getDouble("water_quantity_m3"),row.getString("product"),row.getDouble("dose"),row.getString("dose_unit"),row.getDouble("cost"),row.getString("responsible"),row.getString("notes"),row.getString("inventory_item_id"),row.getDouble("inventory_quantity"),row.getDouble("quantity"),row.getString("unit"),row.getString("description"),row.getString("movement_id"),row.getString("windows_id")));}
                    if(t==12){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα εγγραφής.");if(row.getLong("harvest_interval_days")>Integer.MAX_VALUE)throw new IOException("Μη έγκυρες ημέρες αναμονής.");WorkStore.validate(new WorkStore.Protection(row.getString("id"),row.getString("application_date"),row.getString("field_id"),row.getString("inventory_item_id"),row.getString("purpose"),row.getString("product_name"),row.getString("active_ingredient"),row.getString("authorization_number"),row.getDouble("dose"),row.getString("dose_unit"),row.getDouble("spray_volume_l"),row.getDouble("area_stremma"),row.getString("applicator"),row.getString("weather"),row.getInt("harvest_interval_days"),row.getDouble("cost"),row.getString("notes"),row.getDouble("inventory_quantity"),row.getString("movement_id"),row.getString("windows_id")));}
                    if(t==13){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα εγγραφής.");WorkStore.validate(new WorkStore.Worker(row.getString("id"),row.getString("name"),row.getString("role"),row.getString("phone"),row.getDouble("default_hourly_rate"),row.getInt("active"),row.getString("notes"),row.getString("windows_id")));}
                    if(t==14){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα εγγραφής.");WorkStore.validate(new WorkStore.Labor(row.getString("id"),row.getString("work_date"),row.getString("field_id"),row.getString("worker_id"),row.getString("work_type"),row.getDouble("hours"),row.getDouble("hourly_rate"),row.getDouble("cost"),row.getString("notes"),row.getString("windows_id")));}
                    if(t==15){if(row.getString("id").isBlank()||row.getLong("trees_planted")>Integer.MAX_VALUE||row.getLong("trees_alive")>Integer.MAX_VALUE)throw new IOException("Μη έγκυρη φύτευση.");WorkStore.validate(new WorkStore.Planting(row.getString("id"),row.getString("planting_date"),row.getString("field_id"),row.getInt("trees_planted"),row.getInt("trees_alive"),row.getString("material_type"),row.getString("source"),row.getString("variety"),row.getString("spacing"),row.getDouble("cost"),row.getString("notes"),row.getString("windows_id")));}
                    if(t==16){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα μηχανήματος/service.");WorkStore.validate(new WorkStore.Equipment(row.getString("id"),row.getString("name"),row.getString("category"),row.getString("brand_model"),row.getString("equipment_code"),row.getString("purchase_date"),row.getString("fuel"),row.getString("meter_type"),row.getDouble("current_meter"),row.getString("status"),row.getString("notes"),row.getString("windows_id")));}
                    if(t==17){if(row.getString("id").isBlank())throw new IOException("Λείπει ταυτότητα μηχανήματος/service.");WorkStore.validate(new WorkStore.Service(row.getString("id"),row.getString("equipment_id"),row.getString("service_date"),row.getString("service_type"),row.getDouble("cost"),row.getDouble("meter_value"),row.getString("technician"),row.getString("notes"),row.getString("next_service_date"),row.isNull("next_service_meter")?null:row.getDouble("next_service_meter"),row.getString("expense_windows_id"),row.getString("windows_id")));}
                    if(t==18) DocumentStore.validate(new DocumentStore.Document(row.getString("id"),row.getString("invoice_date"),new JSONObject(row.getString("metadata")),row.getString("attachment"),row.getString("sha256"),row.getString("financial_id"),row.getString("windows_id")));
                    if(t==19 && (!row.getString("id").matches("[1-9][0-9]{3}") || row.getInt("is_locked")>1))throw new IOException("Invalid year lock");
                    if(t==4) {
                        CatalogStore.validateCultivation(row.getString("planting_date"),row.getString("cultivation_status"));
                        if(!row.getString("id").equals(row.getString("product_id")+":"+row.getString("field_id"))) throw new IOException("Μη έγκυρη σύνδεση.");
                    }
                    stage.insertOrThrow(TABLES[t],null,values);
                }
            }
            try(var c=stage.rawQuery("SELECT 1 FROM invoice_documents d LEFT JOIN money_entries m ON m.id=d.financial_id WHERE d.financial_id<>'' AND m.id IS NULL LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Document finance link missing");}
            try(var c=stage.rawQuery("SELECT 1 FROM money_entries m LEFT JOIN invoice_documents d ON d.id=m.source_id WHERE m.source_type='invoice_document' AND (d.id IS NULL OR (m.deleted_at IS NULL AND (d.deleted_at IS NOT NULL OR d.financial_id<>m.id))) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Inconsistent invoice posting");}
            for(String entity:new String[]{"fields","producer","products","product_fields","business_partners","inventory_items","inventory_movements","money_entries","production","production_sales","farm_activities","plant_protection_records","workers","labor_entries","planting_batches","equipment","equipment_maintenance","invoice_documents","year_locks","gis_records"}) {
                String allowedDelete=entity.equals("product_fields")?" AND p.operation<>'delete'":"";
                try(Cursor c=stage.rawQuery("SELECT 1 FROM pending_changes p LEFT JOIN "+entity+" f ON f.id=p.entity_id WHERE p.entity=?"+allowedDelete+" AND (f.id IS NULL OR p.revision>f.revision) LIMIT 1",new String[]{entity})) { if(c.moveToFirst()) throw new IOException("Ασύνδετες αλλαγές."); }
            }
            try(Cursor c=stage.rawQuery("SELECT 1 FROM product_fields l LEFT JOIN products p ON p.id=l.product_id LEFT JOIN fields f ON f.id=l.field_id WHERE p.id IS NULL OR f.id IS NULL LIMIT 1",null)) { if(c.moveToFirst()) throw new IOException("Ασύνδετη καλλιέργεια."); }
            try(Cursor c=stage.rawQuery("SELECT 1 FROM inventory_movements m LEFT JOIN inventory_items i ON i.id=m.item_id LEFT JOIN fields f ON f.id=m.field_id LEFT JOIN business_partners p ON p.id=m.partner_id WHERE i.id IS NULL OR (m.field_id<>'' AND f.id IS NULL) OR (m.partner_id<>'' AND p.id IS NULL) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετη κίνηση αποθήκης.");}
            try(Cursor c=stage.rawQuery("SELECT item_id FROM inventory_movements WHERE deleted_at IS NULL GROUP BY item_id HAVING SUM(CASE WHEN movement_type IN ('Παραλαβή','Διόρθωση +') THEN quantity ELSE -quantity END)<-0.000001",null)){if(c.moveToFirst())throw new IOException("Αρνητικό απόθεμα.");}
            if(schema<6) {try(var c=stage.rawQuery("SELECT id FROM inventory_movements WHERE deleted_at IS NULL AND windows_id='' AND source_type=''",null)){while(c.moveToNext())MoneyStore.syncReceipt(stage,c.getString(0),false);}}
            try(Cursor c=stage.rawQuery("SELECT 1 FROM money_entries e LEFT JOIN fields f ON f.id=e.field_id LEFT JOIN business_partners p ON p.id=e.partner_id LEFT JOIN inventory_movements m ON m.id=e.source_id WHERE (e.field_id<>'' AND f.id IS NULL) OR (e.partner_id<>'' AND p.id IS NULL) OR (e.source_type='inventory_receipt' AND (m.id IS NULL OR e.kind<>'expense' OR (e.deleted_at IS NULL AND (m.deleted_at IS NOT NULL OR m.movement_type<>'Παραλαβή' OR ABS(m.total_cost-e.amount)>0.005)))) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετη ή ασυνεπής οικονομική εγγραφή.");}
            try(Cursor c=stage.rawQuery("SELECT 1 FROM production h LEFT JOIN products p ON p.id=h.product_id LEFT JOIN fields f ON f.id=h.field_id WHERE p.id IS NULL OR (h.field_id<>'' AND f.id IS NULL) UNION ALL SELECT 1 FROM production_sales s LEFT JOIN products p ON p.id=s.product_id LEFT JOIN business_partners b ON b.id=s.buyer_id WHERE p.id IS NULL OR (s.buyer_id<>'' AND b.id IS NULL) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετη παραγωγή/πώληση.");}
            try(Cursor c=stage.rawQuery("SELECT product_id FROM (SELECT product_id,quantity_kg AS amount FROM production WHERE deleted_at IS NULL UNION ALL SELECT product_id,-quantity_kg FROM production_sales WHERE deleted_at IS NULL) GROUP BY product_id HAVING SUM(amount)<-0.000001",null)){if(c.moveToFirst())throw new IOException("Πωλήσεις πάνω από την παραγωγή.");}
            try(Cursor c=stage.rawQuery("SELECT 1 FROM money_entries e LEFT JOIN production_sales s ON s.id=e.source_id WHERE e.source_type='production_sale' AND (s.id IS NULL OR e.kind<>'income' OR (e.deleted_at IS NULL AND (s.deleted_at IS NOT NULL OR ABS(s.total_amount-e.amount)>0.005))) UNION ALL SELECT 1 FROM production_sales s LEFT JOIN money_entries e ON e.source_type='production_sale' AND e.source_id=s.id AND e.deleted_at IS NULL WHERE s.deleted_at IS NULL AND e.id IS NULL LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασυνεπές έσοδο πώλησης.");}
            try(var c=stage.rawQuery("SELECT 1 FROM farm_activities a LEFT JOIN fields f ON f.id=a.field_id LEFT JOIN inventory_items i ON i.id=a.inventory_item_id LEFT JOIN inventory_movements m ON m.id=a.movement_id WHERE (a.field_id<>'' AND f.id IS NULL) OR (a.inventory_item_id<>'' AND i.id IS NULL) OR (a.movement_id<>'' AND m.id IS NULL) OR (a.deleted_at IS NULL AND ((a.category='Λίπανση' AND a.status='Ολοκληρώθηκε' AND a.inventory_quantity>0 AND (m.id IS NULL OR m.deleted_at IS NOT NULL OR m.movement_type<>'Κατανάλωση' OR m.item_id<>a.inventory_item_id OR m.field_id<>a.field_id OR m.movement_date<>a.activity_date OR ABS(m.quantity-a.inventory_quantity)>0.000001 OR (a.windows_id='' AND (m.source_type<>'android_farm_activity' OR m.source_id<>a.id OR m.windows_id<>'')) OR (a.windows_id<>'' AND (m.source_type<>'farm_activity' OR m.source_id<>a.windows_id OR m.windows_id='')))) OR ((a.category<>'Λίπανση' OR a.status<>'Ολοκληρώθηκε' OR a.inventory_quantity=0) AND a.movement_id<>''))) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασυνεπής εργασία ή κατανάλωση αποθήκης.");}
            try(var c=stage.rawQuery("SELECT movement_id FROM farm_activities WHERE deleted_at IS NULL AND movement_id<>'' GROUP BY movement_id HAVING COUNT(*)>1 UNION ALL SELECT m.id FROM inventory_movements m LEFT JOIN farm_activities a ON a.id=m.source_id WHERE m.source_type='android_farm_activity' AND (a.id IS NULL OR (m.deleted_at IS NULL AND (a.deleted_at IS NOT NULL OR a.movement_id<>m.id))) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετη ή διπλή κατανάλωση εργασίας.");}
            try(var c=stage.rawQuery("SELECT 1 FROM labor_entries l LEFT JOIN workers w ON w.id=l.worker_id LEFT JOIN fields f ON f.id=l.field_id WHERE w.id IS NULL OR (l.field_id<>'' AND f.id IS NULL) OR (l.windows_id='' AND ABS(l.cost-l.hours*l.hourly_rate)>0.005) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασυνεπή εργατικά ή εργαζόμενος.");}
            try(var c=stage.rawQuery("SELECT LOWER(TRIM(name)) FROM workers WHERE deleted_at IS NULL GROUP BY LOWER(TRIM(name)) HAVING COUNT(*)>1 LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Διπλό όνομα εργαζομένου.");}
            try(var c=stage.rawQuery("SELECT 1 FROM plant_protection_records a LEFT JOIN fields f ON f.id=a.field_id LEFT JOIN inventory_items i ON i.id=a.inventory_item_id LEFT JOIN inventory_movements m ON m.id=a.movement_id WHERE f.id IS NULL OR (a.inventory_item_id<>'' AND i.id IS NULL) OR (a.movement_id<>'' AND m.id IS NULL) OR (a.deleted_at IS NULL AND ((a.inventory_quantity>0 AND (m.id IS NULL OR m.deleted_at IS NOT NULL OR m.movement_type<>'Κατανάλωση' OR m.item_id<>a.inventory_item_id OR m.field_id<>a.field_id OR m.movement_date<>a.application_date OR ABS(m.quantity-a.inventory_quantity)>0.000001 OR (a.windows_id='' AND (m.source_type<>'android_plant_protection' OR m.source_id<>a.id OR m.windows_id<>'')) OR (a.windows_id<>'' AND (m.source_type<>'plant_protection' OR m.source_id<>a.windows_id OR m.windows_id='')))) OR (a.inventory_quantity=0 AND a.movement_id<>''))) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασυνεπής φυτοπροστασία ή κατανάλωση.");}
            try(var c=stage.rawQuery("SELECT movement_id FROM plant_protection_records WHERE deleted_at IS NULL AND movement_id<>'' GROUP BY movement_id HAVING COUNT(*)>1 UNION ALL SELECT m.id FROM inventory_movements m LEFT JOIN plant_protection_records a ON a.id=m.source_id WHERE m.source_type='android_plant_protection' AND (a.id IS NULL OR (m.deleted_at IS NULL AND (a.deleted_at IS NOT NULL OR a.movement_id<>m.id))) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετη κατανάλωση φυτοπροστασίας.");}
            try(var c=stage.rawQuery("SELECT 1 FROM planting_batches p LEFT JOIN fields f ON f.id=p.field_id WHERE f.id IS NULL LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετη φύτευση.");}
            try(var c=stage.rawQuery("SELECT 1 FROM equipment_maintenance s LEFT JOIN equipment e ON e.id=s.equipment_id WHERE e.id IS NULL LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασύνδετο service.");}
            try(var c=stage.rawQuery("SELECT 1 FROM money_entries e LEFT JOIN equipment_maintenance s ON s.id=e.source_id WHERE e.source_type='equipment_maintenance' AND (s.id IS NULL OR e.kind<>'expense' OR (e.deleted_at IS NULL AND (s.deleted_at IS NOT NULL OR s.cost<=0 OR ABS(s.cost-e.amount)>0.005 OR s.service_date<>e.entry_date))) UNION ALL SELECT 1 FROM equipment_maintenance s LEFT JOIN money_entries e ON e.source_type='equipment_maintenance' AND e.source_id=s.id AND e.deleted_at IS NULL WHERE s.deleted_at IS NULL AND s.cost>0 AND e.id IS NULL LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Ασυνεπές έξοδο συντήρησης.");}
            try(var c=stage.rawQuery("SELECT 1 FROM gis_records g LEFT JOIN fields f ON f.id=g.field_id WHERE f.id IS NULL OR (g.deleted_at IS NULL AND f.deleted_at IS NOT NULL) LIMIT 1",null)){if(c.moveToFirst())throw new IOException("GIS field relationship mismatch");}
            CropProgramBackup.validateRelations(stage);
            PlantTrackingBackup.validateRelations(stage);
            PlantingHistory.validateRelations(stage);
            SensorDataBackup.validateRelations(stage);
            try(var c=stage.rawQuery("SELECT 1 FROM cadastral_reference c LEFT JOIN fields f ON f.id=c.field_id WHERE f.id IS NULL LIMIT 1",null)){if(c.moveToFirst())throw new IOException("Cadastral field relationship mismatch");}
            return stage;
        } catch(Exception error) { stage.close(); throw error; }
    }
    public static int inspect(FarmStore store, byte[] bytes) throws Exception {
        try(SQLiteDatabase stage=validate(store,bytes); Cursor c=stage.rawQuery("SELECT count(*) FROM fields WHERE deleted_at IS NULL",null)) { c.moveToFirst(); return c.getInt(0); }
    }
    public static boolean legacy(byte[] bytes) throws Exception { return new JSONObject(new String(bytes,StandardCharsets.UTF_8)).getInt("schema")==2; }
    public static void restore(FarmStore store, byte[] bytes, File recovery) throws Exception {
        try(SQLiteDatabase stage=validate(store,bytes)) {
            AtomicFile safe = new AtomicFile(recovery); FileOutputStream output=null;
            try { output=safe.startWrite(); output.write(snapshot(store)); safe.finishWrite(output); }
            catch(Exception error) { if(output!=null) safe.failWrite(output); throw error; }
            SQLiteDatabase db=store.getWritableDatabase(); CropProgramStore.create(db); PlantTrackingStore.create(db); PlantingHistory.create(db); SensorDataStore.create(db); db.beginTransaction();
            try {
                db.delete("year_locks",null,null); // Explicit full restore replaces lock policy too, inside this transaction.
                for(int t=0;t<TABLES.length;t++) {
                    db.delete(TABLES[t],null,null);
                    try(Cursor c=stage.query(TABLES[t],COLUMNS[t],null,null,null,null,null)) {
                        while(c.moveToNext()) { ContentValues row=new ContentValues(); android.database.DatabaseUtils.cursorRowToContentValues(c,row); db.insertOrThrow(TABLES[t],null,row); }
                    }
                }
                db.setTransactionSuccessful();
            } finally { db.endTransaction(); }
        }
    }
}
