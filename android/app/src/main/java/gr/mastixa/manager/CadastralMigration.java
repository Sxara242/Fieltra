package gr.mastixa.manager;

import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteTransactionListener;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Isolated synthetic stores only. No FarmStore/startup/restore integration.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralMigration {
    private CadastralMigration() {}
    public static String hash(byte[] bytes) {
        try {
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder text=new StringBuilder();
            for(byte b:digest) text.append(String.format(Locale.ROOT,"%02x",b&255));
            return text.toString();
        } catch(java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    public static String hash(String text) { return hash(text.getBytes(StandardCharsets.UTF_8)); }
    public static void validate(SQLiteDatabase db) {
        try(var c=db.rawQuery("PRAGMA integrity_check",null)) {
            if(!c.moveToFirst()||!"ok".equals(c.getString(0))||c.moveToNext())
                throw new IllegalStateException("Target integrity failed");
        }
        try(var c=db.rawQuery("PRAGMA foreign_key_check",null)) {
            if(c.moveToFirst())throw new IllegalStateException("Target foreign keys failed");
        }
    }
    /** Schema is the canonical shared/fixtures/cadastral_schema_v2.sql stream.
     * Synthetic fixture fields(id TEXT PRIMARY KEY) already exist. The caller
     * owns the connection and stream. No database name/version is activated. */
    public static void createSyntheticTarget(SQLiteDatabase db, InputStream schema,
            String scope,String activation,String sourceHash)throws IOException {
        CadastralProtocol.farmScope(scope); CadastralProtocol.canonicalUuid(activation);
        if(db.inTransaction())throw new IllegalStateException("Idle isolated connection required");
        try(var c=db.rawQuery("SELECT farm_scope FROM cadastral_synthetic_input",null)) {
            if(!c.moveToFirst()||!scope.equals(c.getString(0))||c.moveToNext())
                throw new IllegalArgumentException("Explicit synthetic input required");
        }
        byte[] bytes=readBounded(schema,128*1024,()->false);
        db.setForeignKeyConstraintsEnabled(true);
        db.beginTransaction();
        try {
            String sql=new String(bytes,StandardCharsets.UTF_8).replace("FIELD_REFERENCE","fields(id)");
            for(String statement:sql.split(";"))if(!statement.isBlank())db.execSQL(statement);
            db.execSQL("INSERT INTO farm_configuration VALUES(1,'GR',1,0,0)");
            db.execSQL("INSERT INTO cadastral_storage_state VALUES(1,2,2,?,?,'PREPARED',0,?,'')",new Object[]{scope,activation,sourceHash});
            installFence(db);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        validate(db);
    }
    private static Map<String,String> fences(SQLiteDatabase db) {
        Map<String,String> result=new LinkedHashMap<>();
        List<String> tables=new ArrayList<>();
        try(var c=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table'",null)) {
            while(c.moveToNext())tables.add(c.getString(0));
        }
        for(String table:tables) {
            if(table.startsWith("sqlite_")||table.equals("cadastral_storage_state"))continue;
            String quoted="\""+table.replace("\"","\"\"")+"\"";
            for(String op:List.of("INSERT","UPDATE","DELETE")) {
                String name="cad_fence_"+hash(table+op).substring(0,20);
                result.put(name,"CREATE TRIGGER "+name+
                    " BEFORE "+op+" ON "+quoted+" WHEN COALESCE((SELECT permit FROM cadastral_storage_state WHERE id=1),0)!=1 "+
                    "BEGIN SELECT RAISE(ABORT,'cadastral_upgrade_required'); END");
            }
        }
        for(String op:List.of("UPDATE","DELETE"))result.put("cad_snapshot_"+op,"CREATE TRIGGER cad_snapshot_"+op+
            " BEFORE "+op+" ON cadastral_snapshots BEGIN SELECT RAISE(ABORT,'immutable_source'); END");
        return result;
    }
    private static Map<String,String> existingFences(SQLiteDatabase db) {
        Map<String,String> result=new HashMap<>();try(var c=db.rawQuery("SELECT name,sql FROM sqlite_master WHERE type='trigger'",null)){
            while(c.moveToNext())result.put(c.getString(0),c.getString(1));
        }return result;
    }
    public static void verifyFence(SQLiteDatabase db) {
        var actual=existingFences(db);for(var e:fences(db).entrySet())if(!e.getValue().equals(actual.get(e.getKey())))throw new IllegalStateException("Missing/altered write fence");
    }
    public static void installFence(SQLiteDatabase db) {
        var actual=existingFences(db);for(var e:fences(db).entrySet()){
            if(actual.containsKey(e.getKey())){if(!e.getValue().equals(actual.get(e.getKey())))throw new IllegalStateException("Conflicting write-fence definition");}
            else db.execSQL(e.getValue());
        }
    }
    public record SyntheticField(String fieldUuid,String rawKaek,boolean confirmedGreek,
            List<CadastralProtocol.FieldIdentityAlias> aliases) {
        public SyntheticField{CadastralProtocol.canonicalUuid(fieldUuid);Objects.requireNonNull(rawKaek);
            aliases=aliases.stream().sorted(Comparator.comparing(CadastralProtocol.FieldIdentityAlias::namespace)
                .thenComparing(CadastralProtocol.FieldIdentityAlias::dataset).thenComparing(CadastralProtocol.FieldIdentityAlias::aliasUuid)).collect(java.util.stream.Collectors.toUnmodifiableList());}
    }
    /** Import caller-verified mappings in an isolated copied fixture. Existing
     * Android UUIDs and every business row remain unchanged. Real legacy source
     * extraction and filesystem snapshot/copy/activation are intentionally absent. */
    public static String importSyntheticRows(SQLiteDatabase db,String scope,String activation,List<SyntheticField> fields) {
        List<SyntheticField> ordered=fields.stream().sorted(Comparator.comparing(SyntheticField::fieldUuid)).collect(java.util.stream.Collectors.toList());
        if(ordered.stream().map(SyntheticField::fieldUuid).distinct().count()!=ordered.size())throw new IllegalArgumentException("Duplicate/conflicting field mapping");
        JSONArray plan=new JSONArray();
        for(var f:ordered) {
            JSONArray aliases=new JSONArray();for(var a:f.aliases())aliases.put(new JSONArray().put(a.namespace()).put(a.dataset()).put(a.aliasUuid()));
            plan.put(new JSONArray().put(f.fieldUuid()).put(f.rawKaek()).put(f.confirmedGreek()).put(aliases));
        }
        String sourceHash;
        try(var c=db.rawQuery("SELECT source_hash FROM cadastral_storage_state WHERE id=1",null)){if(!c.moveToFirst())throw new IllegalStateException("Missing stage");sourceHash=c.getString(0);}
        String receiptBase=new JSONArray().put(scope).put(activation).put(sourceHash).put(hash(plan.toString())).put(2).toString();
        return guarded(db,scope,activation,()->{
            String old;try(var c=db.rawQuery("SELECT receipt_hash FROM cadastral_storage_state WHERE id=1",null)){c.moveToFirst();old=c.getString(0);}
            if(!old.isEmpty()) {if(!old.equals(hash(receiptBase+migrationStateHash(db))))throw new IllegalStateException("Different migration plan/state requires recovery");validate(db);return old;}
            for(var f:ordered) {
                try(var c=db.rawQuery("SELECT kaek FROM fields WHERE id=?",new String[]{f.fieldUuid()})) {
                    if(!c.moveToFirst()||!f.rawKaek().equals(c.getString(0)))throw new IllegalArgumentException("Source mapping differs");
                }
                for(var alias:f.aliases()) {
                    if(!alias.field().equals(new CadastralProtocol.CultivatedFieldRef(scope,f.fieldUuid())))throw new IllegalArgumentException("Cross-field alias");
                    db.execSQL("INSERT INTO field_identity_aliases VALUES(?,?,?,?)",new Object[]{alias.namespace(),alias.dataset(),alias.aliasUuid(),f.fieldUuid()});
                }
                var scopeKey=new CountryExtensions.IdentifierScope("GR","kaek","hellenic-cadastre","");
                var validation=new CountryExtensions.GreekIdentifierAdapter().validate(f.rawKaek(),scopeKey);
                String classification=f.confirmedGreek()?(validation.state()==CountryExtensions.ValidationState.VALID?"confirmed_greek":"invalid"):"unclassified";
                String parcel=null;
                if(classification.equals("confirmed_greek")) {
                    // Per-store SQL in this transaction; preserve existing full scoped identity.
                    try(var c=db.rawQuery("SELECT parcel_uuid FROM cadastral_parcels WHERE country_code='GR' AND system_id='kaek' AND authority_id='hellenic-cadastre' AND jurisdiction_key='' AND identifier_key=?",new String[]{f.rawKaek()})) {if(c.moveToFirst())parcel=c.getString(0);}
                    if(parcel==null) {
                        parcel=UUID.randomUUID().toString();db.execSQL("INSERT INTO cadastral_parcels VALUES(?,'GR','kaek','hellenic-cadastre','',?,?,?,'valid',1,0,0,NULL)",new Object[]{parcel,f.rawKaek(),f.rawKaek(),validation.validatorVersion()});
                        db.execSQL("INSERT INTO cadastral_parcel_aliases VALUES(?,?)",new Object[]{parcel,parcel});
                        db.execSQL("INSERT INTO cadastral_identifier_spellings VALUES(?,?,'confirmed_synthetic_legacy')",new Object[]{parcel,f.rawKaek()});
                    }
                    db.execSQL("INSERT INTO field_cadastral_links VALUES(?,?,1,0,1,0,0,NULL)",new Object[]{f.fieldUuid(),parcel});
                }
                String payload=new JSONArray().put(f.fieldUuid()).put(f.rawKaek()).put(f.confirmedGreek()).toString();
                db.execSQL("INSERT INTO cadastral_legacy_bindings VALUES('fields',?,?,?,?,?,NULL,?,'synthetic',?)",new Object[]{f.fieldUuid(),hash(payload),f.fieldUuid(),f.rawKaek(),parcel,classification,payload.getBytes(StandardCharsets.UTF_8)});
            }
            String receipt=hash(receiptBase+migrationStateHash(db));
            db.execSQL("UPDATE cadastral_storage_state SET receipt_hash=? WHERE id=1",new Object[]{receipt});validate(db);return receipt;
        });
    }
    private static String migrationStateHash(SQLiteDatabase db) {
        JSONArray tables=new JSONArray();
        for(String table:List.of("farm_configuration","field_identity_aliases","cadastral_parcels","cadastral_parcel_aliases",
                "cadastral_identifier_spellings","field_cadastral_links","cadastral_snapshots","cadastral_parcel_state","cadastral_legacy_bindings")) {
            List<String> rows=new ArrayList<>();
            try(var c=db.rawQuery("SELECT * FROM "+table,null)) {
                while(c.moveToNext()) {
                    JSONArray row=new JSONArray();for(int n=0;n<c.getColumnCount();n++)row.put(c.isNull(n)?JSONObject.NULL:
                        c.getType(n)==android.database.Cursor.FIELD_TYPE_BLOB?"sha256:"+hash(c.getBlob(n)):c.getString(n));rows.add(row.toString());
                }
            }Collections.sort(rows);tables.put(new JSONArray().put(table).put(new JSONArray(rows)));
        }return hash(tables.toString());
    }
    @FunctionalInterface public interface Write<T> { T run(); }
    public static <T>T guarded(SQLiteDatabase db,String scope,String activation,Write<T> action) {
        if(db.inTransaction())throw new IllegalStateException("Nested writer refused");
        final boolean[] finish={false},committed={false},rolledBack={false};
        db.beginTransactionWithListener(new SQLiteTransactionListener(){
            @Override public void onBegin(){}
            @Override public void onCommit(){
                if(!finish[0])throw new IllegalStateException("Independent commit/yield refused before SQLite commit");
                committed[0]=true;
            }
            @Override public void onRollback(){rolledBack[0]=true;}
        });
        try {
            verifyFence(db);
            try(var c=db.rawQuery("SELECT farm_scope,activation_id,schema_version,min_writer,permit FROM cadastral_storage_state WHERE id=1",null)) {
                if(!c.moveToFirst()||!scope.equals(c.getString(0))||!activation.equals(c.getString(1))||c.getInt(2)!=2||c.getInt(3)!=2||c.getInt(4)!=0)
                    throw new IllegalStateException("Store identity/version/permit mismatch");
            }
            db.execSQL("UPDATE cadastral_storage_state SET permit=1 WHERE id=1");
            T result=action.run();
            if(!db.inTransaction()||rolledBack[0])throw new IllegalStateException("Independent transaction end refused");
            verifyFence(db);
            try(var c=db.rawQuery("SELECT farm_scope,activation_id,schema_version,min_writer,permit FROM cadastral_storage_state WHERE id=1",null)) {
                if(!c.moveToFirst()||!scope.equals(c.getString(0))||!activation.equals(c.getString(1))||c.getInt(2)!=2||c.getInt(3)!=2||c.getInt(4)!=1)
                    throw new IllegalStateException("Writer changed guard identity/permit");
            }
            db.execSQL("UPDATE cadastral_storage_state SET permit=0 WHERE id=1");
            db.setTransactionSuccessful();finish[0]=true;
            db.endTransaction();
            if(db.inTransaction()||!committed[0])throw new IllegalStateException("Unbalanced nested transaction refused");
            return result;
        } finally {
            finish[0]=false;
            // Entry required no transaction; any remaining level belongs here.
            while(db.inTransaction())db.endTransaction();
        }
    }
    public enum Recovery { ACTIVE, PREPARED_REQUIRES_SOURCE_LOCK, RECOVER_ACTIVATION, RESTORE_DETECTED, RECOVERY_REQUIRED }
    /** No multi-file atomicity claim. Missing/replaced legacy markers deny fallback. */
    public static Recovery resolve(Map<String,String> expected,Map<String,String> legacy,Map<String,String> target) {
        if(target==null)return Recovery.RECOVERY_REQUIRED;
        if(!"2".equals(target.get("schema_version"))||!"2".equals(target.get("min_writer"))||!"0".equals(target.get("permit"))||
            !("PREPARED".equals(target.get("phase"))||"ACTIVE".equals(target.get("phase"))))return Recovery.RECOVERY_REQUIRED;
        for(String k:List.of("activation_id","farm_scope","source_hash","receipt_hash"))
            if(expected.get(k)==null||!expected.get(k).equals(target.get(k)))return Recovery.RECOVERY_REQUIRED;
        if(legacy==null)return "PREPARED".equals(target.get("phase"))?Recovery.PREPARED_REQUIRES_SOURCE_LOCK:Recovery.RESTORE_DETECTED;
        for(String k:List.of("activation_id","farm_scope","source_hash","receipt_hash"))
            if(!expected.get(k).equals(legacy.get(k)))return Recovery.RESTORE_DETECTED;
        return "ACTIVE".equals(target.get("phase"))?Recovery.ACTIVE:Recovery.RECOVER_ACTIVATION;
    }
    @FunctionalInterface public interface Cancellation { boolean cancelled(); }
    public static byte[] readExact(InputStream stream,int length,Cancellation cancel)throws IOException {
        if(length<0)throw new IOException("Invalid bounded length");byte[] data=new byte[length];int offset=0;
        while(offset<length){if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
            int count=stream.read(data,offset,Math.min(16384,length-offset));if(count<0)throw new EOFException("Truncated bounded input");if(count==0)throw new IOException("Non-progressing input");offset+=count;}
        if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
        if(stream.read()!=-1)throw new IOException("Input exceeds declared length");return data;
    }
    public static byte[] readBounded(InputStream stream,int maximum,Cancellation cancel)throws IOException {
        if(maximum<0)throw new IOException("Invalid input budget");
        if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[16384];int count;
        while((count=stream.read(buffer))!=-1) {
            if(count==0)throw new IOException("Non-progressing bounded input");
            if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
            if(out.size()>(long)maximum-count)throw new IOException("Input exceeds budget");
            out.write(buffer,0,count);
        }
        if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
        return out.toByteArray();
    }
}
