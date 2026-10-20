package gr.mastixa.manager;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.util.*;
import org.json.*;
import static gr.mastixa.manager.CadastralProtocol.*;
import static gr.mastixa.manager.CountryExtensions.*;

/** Caller-owned isolated connection; no FarmStore, business writes or networking.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralParcelRepository implements ParcelRepository {
    public static final class Conflict extends IllegalArgumentException {
        public Conflict(String message) { super(message); }
    }
    public record SourceSnapshot(String snapshotUuid,String parcelUuid,String providerId,String datasetId,
            String datasetVersion,String geometryJson,byte[] sourcePayload,String sourceCrs,
            String provenanceJson,long acquiredAt,String origin,boolean officialSourceVerified,String snapshotDate,String sourceDate) {
        public SourceSnapshot(String snapshotUuid,String parcelUuid,String providerId,String datasetId,String datasetVersion,
                String geometryJson,String sourcePayload,String sourceCrs,String provenanceJson,long acquiredAt,String origin,boolean officialSourceVerified) {
            this(snapshotUuid,parcelUuid,providerId,datasetId,datasetVersion,geometryJson,sourcePayload.getBytes(java.nio.charset.StandardCharsets.UTF_8),sourceCrs,provenanceJson,acquiredAt,origin,officialSourceVerified,null,null);
        }
        public SourceSnapshot(String snapshotUuid,String parcelUuid,String providerId,String datasetId,String datasetVersion,
                String geometryJson,String sourcePayload,String sourceCrs,String provenanceJson,long acquiredAt,String origin,boolean officialSourceVerified,String snapshotDate,String sourceDate) {
            this(snapshotUuid,parcelUuid,providerId,datasetId,datasetVersion,geometryJson,sourcePayload.getBytes(java.nio.charset.StandardCharsets.UTF_8),sourceCrs,provenanceJson,acquiredAt,origin,officialSourceVerified,snapshotDate,sourceDate);
        }
        public SourceSnapshot {
            canonicalUuid(snapshotUuid);canonicalUuid(parcelUuid);
            sourcePayload=sourcePayload.clone();
            if(acquiredAt<0||providerId==null||providerId.isBlank()||datasetId==null||datasetId.isBlank()||sourceCrs==null||origin==null||origin.isBlank())
                throw new IllegalArgumentException("Versioned source identity/provenance required");
        }
        @Override public byte[] sourcePayload(){return sourcePayload.clone();}
        public String contentHash() {
            return CadastralFingerprint.fingerprint("fieltra-cadastral-source-v1",geometryJson,sourcePayload,sourceCrs,
                providerId,datasetId,datasetVersion,provenanceJson,origin,officialSourceVerified?"1":"0",snapshotDate,sourceDate);
        }
    }
    public record OverlayInput(String parcelUuid,long linkRevision,String providerId,long selectedRevision,
            String state,String snapshotUuid,String contentHash,String geometryJson,String sourceCrs,String provenanceJson) {}
    public record InputSnapshot(CultivatedFieldRef field,long configurationRevision,List<OverlayInput> inputs,String fingerprint) {
        public InputSnapshot { inputs=List.copyOf(inputs); }
    }
    private final SQLiteDatabase db;
    private final String scope,activation;
    private boolean writing;
    private final Thread owner=Thread.currentThread();
    public CadastralParcelRepository(SQLiteDatabase db,String scope,String activation) {
        this.db=db;this.scope=scope;this.activation=activation;
        try(var c=db.rawQuery("PRAGMA foreign_keys",null)) {
            if(!c.moveToFirst()||c.getInt(0)!=1)throw new IllegalStateException("Foreign keys required");
        }
        try(var c=db.rawQuery("SELECT farm_scope,activation_id FROM cadastral_storage_state WHERE id=1",null)) {
            if(!c.moveToFirst()||!scope.equals(c.getString(0))||!activation.equals(c.getString(1)))
                throw new IllegalArgumentException("Farm/store mismatch");
        }
    }
    private <T>T write(CadastralMigration.Write<T> action) {
        if(Thread.currentThread()!=owner)throw new IllegalStateException("Repository belongs to connection-owning thread");
        if(writing)return action.run();
        return CadastralMigration.guarded(db,scope,activation,()->{writing=true;try{return action.run();}finally{writing=false;}});
    }
    private void field(CultivatedFieldRef field) {
        if(!scope.equals(field.farmScope()))throw new IllegalArgumentException("Cross-farm association refused");
        try(var c=db.rawQuery("SELECT 1 FROM fields WHERE id=? AND deleted_at IS NULL",new String[]{field.fieldUuid()})) {
            if(!c.moveToFirst())throw new IllegalArgumentException("Existing active cultivated field required");
        }
    }
    private void invalidate(String parcel) {
        db.execSQL("UPDATE cadastral_field_overlays SET status='STALE' WHERE field_uuid IN(SELECT field_uuid FROM field_cadastral_links WHERE parcel_uuid=?)",new Object[]{parcel});
    }
    private CadastralParcel parcel(Cursor c) {
        return new CadastralParcel(scope,c.getString(0),new ScopedParcelIdentity(new IdentifierScope(c.getString(1),
            c.getString(2),c.getString(3),c.getString(4)),c.getString(5)),c.getString(6),c.getString(7),
            new RecordVersion(c.getLong(9),c.getLong(10),c.getLong(11),c.isNull(12)?null:c.getLong(12)));
    }
    public CadastralParcel findParcel(ScopedParcelIdentity identity) {
        var s=identity.scope();
        try(var c=db.rawQuery("SELECT * FROM cadastral_parcels WHERE country_code=? AND system_id=? AND authority_id=? AND jurisdiction_key=? AND identifier_key=?",
                new String[]{s.countryCode(),s.systemId(),s.authorityId(),s.jurisdictionKey(),identity.comparisonKey()})) {
            return c.moveToFirst()?parcel(c):null;
        }
    }
    @Override public CadastralParcel ensureParcel(CadastralParcel candidate) {
        if(!scope.equals(candidate.farmScope())||candidate.version().deletedAt()!=null)throw new IllegalArgumentException("Active same-farm parcel required");
        var validation=new CountryRegistry().get(candidate.identity().scope().countryCode()).validate(candidate.identifierRaw(),candidate.identity().scope());
        if(validation.state()!=ValidationState.VALID||!candidate.identity().comparisonKey().equals(validation.comparisonKey())||
                !candidate.validatorVersion().equals(validation.validatorVersion()))throw new IllegalArgumentException("Unsupported/unverified identifier");
        return write(()->{
            var old=findParcel(candidate.identity());var p=old==null?candidate:old;
            if(old!=null&&old.version().deletedAt()!=null)throw new Conflict("Retired identity requires explicit recovery");
            try(var c=db.rawQuery("SELECT parcel_uuid FROM cadastral_parcel_aliases WHERE alias_uuid=?",new String[]{candidate.parcelUuid()})) {
                if(c.moveToFirst()&&!p.parcelUuid().equals(c.getString(0)))throw new Conflict("Conflicting parcel UUID mapping");
            }
            if(old==null) {
                var s=p.identity().scope();var v=p.version();
                db.execSQL("INSERT INTO cadastral_parcels VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",new Object[]{p.parcelUuid(),s.countryCode(),
                    s.systemId(),s.authorityId(),s.jurisdictionKey(),p.identity().comparisonKey(),p.identifierRaw(),p.validatorVersion(),
                    "valid",v.revision(),v.createdAt(),v.updatedAt(),v.deletedAt()});
            }
            db.execSQL("INSERT OR IGNORE INTO cadastral_parcel_aliases VALUES(?,?)",new Object[]{candidate.parcelUuid(),p.parcelUuid()});
            db.execSQL("INSERT OR IGNORE INTO cadastral_identifier_spellings VALUES(?,?,'validated')",new Object[]{p.parcelUuid(),candidate.identifierRaw()});
            return p;
        });
    }
    private FieldCadastralLink link(Cursor c) {
        return new FieldCadastralLink(new CultivatedFieldRef(scope,c.getString(0)),c.getString(1),
            new RecordVersion(c.getLong(4),c.getLong(5),c.getLong(6),c.isNull(7)?null:c.getLong(7)),c.getInt(2)==1,c.getInt(3)==1);
    }
    private FieldCadastralLink getLink(CultivatedFieldRef f,String p) {
        try(var c=db.rawQuery("SELECT * FROM field_cadastral_links WHERE field_uuid=? AND parcel_uuid=?",new String[]{f.fieldUuid(),p})) {
            return c.moveToFirst()?link(c):null;
        }
    }
    @Override public FieldCadastralLink link(FieldCadastralLink association,long expectedRevision) {
        field(association.field());
        if(association.version().deletedAt()!=null)throw new IllegalArgumentException("Use unlink");
        return write(()->{
            var old=getLink(association.field(),association.parcelUuid());
            field(association.field());
            if(old!=null&&old.legacySlot()&&!association.legacySlot())throw new Conflict("Primary slot change requires later confirmed flow");
            if(old!=null&&old.version().deletedAt()==null&&old.legacySlot()==association.legacySlot()&&old.manualLink()==association.manualLink()
                &&(expectedRevision==0||expectedRevision==old.version().revision()))return old;
            if((old==null?0:old.version().revision())!=expectedRevision)throw new Conflict("Stale link revision");
            if(association.legacySlot())try(var c=db.rawQuery("SELECT 1 FROM fields f JOIN cadastral_parcels p ON f.kaek=p.identifier_raw WHERE f.id=? AND p.parcel_uuid=?",
                    new String[]{association.field().fieldUuid(),association.parcelUuid()})) {
                if(!c.moveToFirst())throw new Conflict("Primary legacy projection differs");
            }
            long now=Math.max(System.currentTimeMillis(),old==null?0:old.version().updatedAt());
            // No UPSERT syntax: Android API26's system SQLite predates SQLite 3.24.
            if(old==null)db.execSQL("INSERT INTO field_cadastral_links VALUES(?,?,?,?,?,?,?,NULL)",new Object[]{association.field().fieldUuid(),
                association.parcelUuid(),association.legacySlot()?1:0,association.manualLink()?1:0,1,now,now});
            else db.execSQL("UPDATE field_cadastral_links SET legacy_slot=?,manual_link=?,revision=revision+1,updated_at=?,deleted_at=NULL WHERE field_uuid=? AND parcel_uuid=?",
                new Object[]{association.legacySlot()?1:0,association.manualLink()?1:0,now,association.field().fieldUuid(),association.parcelUuid()});
            invalidate(association.parcelUuid());return getLink(association.field(),association.parcelUuid());
        });
    }
    @Override public FieldCadastralLink unlink(CultivatedFieldRef f,String p,long expectedRevision) {
        field(f);
        return write(()->{
            field(f);
            var old=getLink(f,p);
            if(old==null||old.version().revision()!=expectedRevision)throw new Conflict("Stale unlink");
            if(old.legacySlot()&&old.version().deletedAt()==null)throw new Conflict("Primary slot requires later confirmed compatibility flow");
            if(old.version().deletedAt()!=null)return old;
            long now=Math.max(System.currentTimeMillis(),old.version().updatedAt());
            db.execSQL("UPDATE field_cadastral_links SET revision=revision+1,updated_at=?,deleted_at=? WHERE field_uuid=? AND parcel_uuid=?",new Object[]{now,now,f.fieldUuid(),p});
            invalidate(p);
            if(linkedFields(p).isEmpty())db.execSQL("UPDATE cadastral_lookup_jobs SET status='cancelled' WHERE parcel_uuid=? AND status IN('queued','running')",new Object[]{p});
            return getLink(f,p);
        });
    }
    @Override public List<FieldCadastralLink> listLinks(CultivatedFieldRef f,boolean includeDeleted) {
        field(f);List<FieldCadastralLink> result=new ArrayList<>();
        try(var c=db.rawQuery("SELECT * FROM field_cadastral_links WHERE field_uuid=?"+(includeDeleted?"":" AND deleted_at IS NULL")+" ORDER BY parcel_uuid",new String[]{f.fieldUuid()})) {
            while(c.moveToNext())result.add(link(c));
        }
        return List.copyOf(result);
    }
    public List<CultivatedFieldRef> linkedFields(String parcel) {
        List<CultivatedFieldRef> result=new ArrayList<>();
        try(var c=db.rawQuery("SELECT field_uuid FROM field_cadastral_links WHERE parcel_uuid=? AND deleted_at IS NULL ORDER BY field_uuid",new String[]{parcel})) {
            while(c.moveToNext())result.add(new CultivatedFieldRef(scope,c.getString(0)));
        }return List.copyOf(result);
    }
    public String addSnapshot(SourceSnapshot s) {
        canonicalUuid(s.snapshotUuid());canonicalUuid(s.parcelUuid());
        if(s.geometryJson().getBytes(java.nio.charset.StandardCharsets.UTF_8).length>16*1024*1024||
            s.sourcePayload().length>16*1024*1024)throw new IllegalArgumentException("Source budget exceeded");
        try {
            new JSONObject(s.geometryJson());var provenance=new JSONObject(s.provenanceJson());
            for(String key:List.of("source_url","terms_url","attribution"))if(provenance.getString(key).isBlank())throw new IllegalArgumentException("Source provenance required");
        }catch(JSONException e){throw new IllegalArgumentException("Invalid source metadata",e);}
        if(s.officialSourceVerified()&&!s.origin().equals("verified_provider"))throw new IllegalArgumentException("Imported data cannot become official");
        return write(()->{
            try(var c=db.rawQuery("SELECT snapshot_uuid FROM cadastral_snapshots WHERE parcel_uuid=? AND content_hash=?",new String[]{s.parcelUuid(),s.contentHash()})) {
                if(c.moveToFirst())return c.getString(0);
            }
            db.execSQL("INSERT INTO cadastral_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",new Object[]{s.snapshotUuid(),s.parcelUuid(),s.providerId(),s.datasetId(),
                s.datasetVersion(),s.geometryJson(),s.sourcePayload(),s.sourceCrs(),s.contentHash(),CadastralMigration.hash(s.geometryJson()),
                s.provenanceJson(),s.snapshotDate(),s.sourceDate(),s.acquiredAt(),s.origin(),s.officialSourceVerified()?1:0});
            db.execSQL("INSERT OR IGNORE INTO cadastral_parcel_state VALUES(?,?,NULL,1,'PENDING',NULL)",new Object[]{s.parcelUuid(),s.providerId()});
            long count;
            try(var c=db.rawQuery("SELECT COUNT(*) FROM cadastral_snapshots WHERE parcel_uuid=? AND provider_id=?",new String[]{s.parcelUuid(),s.providerId()})){c.moveToFirst();count=c.getLong(0);}
            if(count>1)db.execSQL("UPDATE cadastral_parcel_state SET selected_snapshot_uuid=NULL,selected_revision=selected_revision+1,state='CONFLICT' WHERE parcel_uuid=? AND provider_id=?",new Object[]{s.parcelUuid(),s.providerId()});
            invalidate(s.parcelUuid());return s.snapshotUuid();
        });
    }
    public void selectSnapshot(String parcel,String provider,String snapshot,long expectedRevision) {
        write(()->{
            try(var c=db.rawQuery("SELECT 1 FROM cadastral_snapshots WHERE parcel_uuid=? AND provider_id=? AND snapshot_uuid=?",new String[]{parcel,provider,snapshot})) {
                if(!c.moveToFirst())throw new IllegalArgumentException("Snapshot/provider mismatch");
            }
            try(var c=db.rawQuery("SELECT selected_snapshot_uuid,selected_revision,state FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?",new String[]{parcel,provider})) {
                if(c.moveToFirst()&&snapshot.equals(c.getString(0))&&expectedRevision==c.getLong(1)&&"READY".equals(c.getString(2)))return null;
            }
            var statement=db.compileStatement("UPDATE cadastral_parcel_state SET selected_snapshot_uuid=?,selected_revision=selected_revision+1,state='READY',last_error=NULL WHERE parcel_uuid=? AND provider_id=? AND selected_revision=?");
            try {statement.bindString(1,snapshot);statement.bindString(2,parcel);statement.bindString(3,provider);statement.bindLong(4,expectedRevision);
                if(statement.executeUpdateDelete()!=1)throw new Conflict("Stale source selection");
            }finally{statement.close();}
            invalidate(parcel);return null;
        });
    }
    private long sourceRevision(String p,String provider) {
        try(var c=db.rawQuery("SELECT COALESCE(MAX(selected_revision),0) FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?",new String[]{p,provider})) {c.moveToFirst();return c.getLong(0);}
    }
    public String enqueue(String p,String provider) {
        return write(()->{
            if(linkedFields(p).isEmpty())throw new Conflict("No active links");
            long revision=sourceRevision(p,provider);String superseded=null;
            try(var c=db.rawQuery("SELECT request_uuid,requested_revision FROM cadastral_lookup_jobs WHERE parcel_uuid=? AND provider_id=? AND status IN('queued','running')",new String[]{p,provider})) {
                if(c.moveToFirst()){if(c.getLong(1)==revision)return c.getString(0);superseded=c.getString(0);}
            }
            if(superseded!=null)db.execSQL("UPDATE cadastral_lookup_jobs SET status='superseded' WHERE request_uuid=?",new Object[]{superseded});
            String token=UUID.randomUUID().toString();
            db.execSQL("INSERT INTO cadastral_lookup_jobs(job_uuid,parcel_uuid,provider_id,requested_revision,request_uuid,status) VALUES(?,?,?,?,?,'queued')",new Object[]{UUID.randomUUID().toString(),p,provider,sourceRevision(p,provider),token});return token;
        });
    }
    public boolean requestIsCurrent(String p,String provider,String token) {
        try(var c=db.rawQuery("SELECT requested_revision FROM cadastral_lookup_jobs WHERE parcel_uuid=? AND provider_id=? AND request_uuid=? AND status IN('queued','running')",new String[]{p,provider,token})) {
            return c.moveToFirst()&&c.getLong(0)==sourceRevision(p,provider)&&!linkedFields(p).isEmpty();
        }
    }
    public String completeLookup(SourceSnapshot snapshot,String request) {
        return write(()->{
            if(!requestIsCurrent(snapshot.parcelUuid(),snapshot.providerId(),request))throw new Conflict("Stale asynchronous lookup");
            String selected=addSnapshot(snapshot);String state;long revision;
            try(var c=db.rawQuery("SELECT selected_revision,state FROM cadastral_parcel_state WHERE parcel_uuid=? AND provider_id=?",new String[]{snapshot.parcelUuid(),snapshot.providerId()})) {
                c.moveToFirst();revision=c.getLong(0);state=c.getString(1);
            }
            if(state.equals("PENDING"))selectSnapshot(snapshot.parcelUuid(),snapshot.providerId(),selected,revision);
            db.execSQL("UPDATE cadastral_lookup_jobs SET status='done',result_hash=? WHERE request_uuid=?",new Object[]{snapshot.contentHash(),request});return selected;
        });
    }
    public InputSnapshot snapshotInputs(CultivatedFieldRef f) {
        if(Thread.currentThread()!=owner)throw new IllegalStateException("Capture inputs on connection-owning thread");
        field(f);boolean own=!db.inTransaction();if(own)db.beginTransactionNonExclusive();
        try {
            long revision;try(var c=db.rawQuery("SELECT revision FROM farm_configuration WHERE id=1",null)){c.moveToFirst();revision=c.getLong(0);}
            List<OverlayInput> result=new ArrayList<>();List<Object> fingerprint=new ArrayList<>(List.of("fieltra-cadastral-input-v1",scope,f.fieldUuid(),Long.toString(revision)));
            for(var link:listLinks(f,false)) {
                List<OverlayInput> candidates=new ArrayList<>();
                try(var c=db.rawQuery("SELECT s.provider_id,s.selected_revision,s.state,s.selected_snapshot_uuid,g.content_hash,g.original_geometry_json,g.source_crs,g.provenance_json FROM cadastral_parcel_state s LEFT JOIN cadastral_snapshots g ON g.parcel_uuid=s.parcel_uuid AND g.snapshot_uuid=s.selected_snapshot_uuid WHERE s.parcel_uuid=? ORDER BY s.provider_id",new String[]{link.parcelUuid()})) {
                    while(c.moveToNext())candidates.add(new OverlayInput(link.parcelUuid(),link.version().revision(),c.getString(0),c.getLong(1),c.getString(2),c.getString(3),c.getString(4),c.getString(5),c.getString(6),c.getString(7)));
                }
                var input=candidates.size()==1?candidates.get(0):new OverlayInput(link.parcelUuid(),link.version().revision(),"",0,candidates.isEmpty()?"PENDING":"CONFLICT",null,null,null,null,null);
                result.add(input);Collections.addAll(fingerprint,input.parcelUuid(),Long.toString(input.linkRevision()),input.providerId(),Long.toString(input.selectedRevision()),input.state(),input.snapshotUuid(),input.contentHash(),input.geometryJson(),input.sourceCrs(),input.provenanceJson());
            }
            return new InputSnapshot(f,revision,result,CadastralFingerprint.fingerprint(fingerprint.toArray()));
        }finally{if(own)db.endTransaction();}
    }
    public void publishOverlay(InputSnapshot inputs,CadastralUnion.Result result) {
        write(()->{
            if(!inputs.fingerprint().equals(result.fingerprint())||!inputs.equals(snapshotInputs(inputs.field()))||result.requiredCount()!=inputs.inputs().size())throw new Conflict("Stale union result");
            db.execSQL("DELETE FROM cadastral_field_overlays WHERE field_uuid=?",new Object[]{inputs.field().fieldUuid()});
            db.execSQL("INSERT INTO cadastral_field_overlays VALUES(?,?,?,?,?,?,?,?,?,?,?)",new Object[]{inputs.field().fieldUuid(),inputs.fingerprint(),result.engine(),"EPSG:2100","unsnapped-floating",
                result.geometryJson(),result.state().name(),result.requiredCount(),result.usableCount(),result.diagnostic(),System.currentTimeMillis()});return null;
        });
    }
}
