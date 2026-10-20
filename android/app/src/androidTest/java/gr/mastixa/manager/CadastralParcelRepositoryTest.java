package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;
import static gr.mastixa.manager.CadastralProtocol.*;
import static gr.mastixa.manager.CountryExtensions.*;

/** Real isolated SQLite M:N source; no production FarmStore.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralParcelRepositoryTest {
    private CadastralParcel candidate(String raw) {
        return new CadastralParcel(CadastralSynthetic.SCOPE,UUID.randomUUID().toString(),new ScopedParcelIdentity(new IdentifierScope("GR","kaek","hellenic-cadastre",""),raw),raw,"gr-kaek-ascii12-v1",new RecordVersion(1,0,0,null));
    }
    @Test public void fiveLinksAndInverseSharingKeepAreaAndLegacyPrimary()throws Exception {
        try(var db=CadastralSynthetic.database()) {
            var repo=new CadastralParcelRepository(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION);
            var field=new CultivatedFieldRef(CadastralSynthetic.SCOPE,CadastralSynthetic.FIELD);CadastralParcel first=null;
            for(int n=1;n<=5;n++) {
                var p=repo.ensureParcel(candidate(String.format(Locale.ROOT,"51000000000%d",n)));if(first==null)first=p;
                var link=new FieldCadastralLink(field,p.parcelUuid(),new RecordVersion(1,0,0,null),n==1,n!=1);
                assertEquals(repo.link(link,0),repo.link(link,0));
            }
            assertEquals(5,repo.listLinks(field,false).size());
            try(var c=db.rawQuery("SELECT COUNT(*) FROM fields",null)){assertTrue(c.moveToFirst());assertEquals(1,c.getInt(0));}
            var same=repo.ensureParcel(candidate("510000000001"));assertEquals(first.parcelUuid(),same.parcelUuid());
            CadastralMigration.guarded(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,()->{
                db.execSQL("INSERT INTO fields VALUES(?,'510000000001',9,NULL)",new Object[]{CadastralSynthetic.OTHER});return null;
            });
            var other=new CultivatedFieldRef(CadastralSynthetic.SCOPE,CadastralSynthetic.OTHER);
            var second=repo.link(new FieldCadastralLink(other,same.parcelUuid(),new RecordVersion(1,0,0,null),false,true),0);
            assertEquals(2,repo.linkedFields(same.parcelUuid()).size());
            String request=repo.enqueue(same.parcelUuid(),"synthetic");assertEquals(request,repo.enqueue(same.parcelUuid(),"synthetic"));
            repo.unlink(other,same.parcelUuid(),second.version().revision());assertEquals(List.of(field),repo.linkedFields(same.parcelUuid()));
            assertThrows(CadastralParcelRepository.Conflict.class,()->repo.unlink(field,same.parcelUuid(),1));
            try(var c=db.rawQuery("SELECT kaek,area FROM fields WHERE id=?",new String[]{field.fieldUuid()})){assertTrue(c.moveToFirst());assertEquals("510000000001",c.getString(0));assertEquals(3.25,c.getDouble(1),0);}
            assertThrows(CadastralParcelRepository.Conflict.class,()->repo.link(new FieldCadastralLink(other,same.parcelUuid(),new RecordVersion(1,0,0,null),false,true),0));
        }
    }
    @Test public void storedBusinessLedgerAndStaleLookupStayIndependent()throws Exception {
        try(var db=CadastralSynthetic.database()) {
            CadastralMigration.guarded(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,()->{
                for(String table:List.of("product_fields","production","sales","income","expenses","inventory_receipts","activity_consumption"))
                    db.execSQL("CREATE TABLE "+table+"(field_id TEXT REFERENCES fields(id),value)");
                String[] tables={"product_fields","production","sales","income","expenses","inventory_receipts","activity_consumption"};Object[] values={"synthetic-crop",100,20,200,50,10,2};
                for(int n=0;n<tables.length;n++)db.execSQL("INSERT INTO "+tables[n]+" VALUES(?,?)",new Object[]{CadastralSynthetic.FIELD,values[n]});
                CadastralMigration.installFence(db);return null;
            });
            var repo=new CadastralParcelRepository(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION);var f=new CultivatedFieldRef(CadastralSynthetic.SCOPE,CadastralSynthetic.FIELD);
            for(int n=1;n<=5;n++) {
                var p=repo.ensureParcel(candidate(String.format(Locale.ROOT,"51000000000%d",n)));repo.link(new FieldCadastralLink(f,p.parcelUuid(),new RecordVersion(1,0,0,null),false,true),0);
                String token=repo.enqueue(p.parcelUuid(),"synthetic");String geometry=CadastralSynthetic.rectangle((n-1)*20,0,20,20);
                var source=new CadastralParcelRepository.SourceSnapshot(UUID.randomUUID().toString(),p.parcelUuid(),"synthetic","region","fixture",geometry,"synthetic payload","EPSG:2100",
                    "{\"source_url\":\"https://example.invalid/source\",\"terms_url\":\"synthetic\",\"attribution\":\"synthetic\"}",0,"synthetic",false);
                repo.completeLookup(source,token);assertThrows(CadastralParcelRepository.Conflict.class,()->repo.completeLookup(source,token));
            }
            var inputs=repo.snapshotInputs(f);var result=CadastralUnion.build(inputs,()->false);assertEquals(CadastralUnion.State.COMPLETE_DERIVED,result.state());repo.publishOverlay(inputs,result);
            for(String table:List.of("product_fields","production","sales","income","expenses","inventory_receipts","activity_consumption"))
                try(var c=db.rawQuery("SELECT COUNT(*) FROM "+table,null)){assertTrue(c.moveToFirst());assertEquals(1,c.getInt(0));}
            try(var c=db.rawQuery("SELECT (SELECT SUM(value) FROM income)-(SELECT SUM(value) FROM expenses),(SELECT SUM(value) FROM inventory_receipts)-(SELECT SUM(value) FROM activity_consumption)",null)) {
                assertTrue(c.moveToFirst());assertEquals(150,c.getInt(0));assertEquals(8,c.getInt(1));
            }
            var removed=repo.listLinks(f,false).get(4);repo.unlink(f,removed.parcelUuid(),removed.version().revision());
            assertThrows(CadastralParcelRepository.Conflict.class,()->repo.publishOverlay(inputs,result));
            try(var c=db.rawQuery("SELECT area FROM fields WHERE id=?",new String[]{f.fieldUuid()})){assertTrue(c.moveToFirst());assertEquals(3.25,c.getDouble(0),0);}
        }
    }
}
