package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static gr.mastixa.manager.CadastralProtocol.*;
import static gr.mastixa.manager.CountryExtensions.*;

/** Guard/hash/CAS regressions requiring Android SQLite/JSON, not JVM unit tests.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralHardeningTest {
    private record Vector(Object[] fields,String hash) {}
    private static Map<String,Vector> vectors()throws IOException {
        Map<String,Vector> result=new HashMap<>();
        try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("cadastral_fingerprints.tsv")) {
            String text=new String(CadastralMigration.readBounded(in,65536,()->false),StandardCharsets.UTF_8);
            for(String line:text.split("\\R")){if(line.isEmpty()||line.startsWith("#"))continue;String[] row=line.split("\t",-1),encoded=row[1].split(",",-1);Object[] values=new Object[encoded.length];
                for(int n=0;n<values.length;n++)values[n]=encoded[n].equals("-")?null:Base64.getDecoder().decode(encoded[n]);result.put(row[0],new Vector(values,row[2]));}
        }return result;
    }
    private static String text(Object value){return new String((byte[])value,StandardCharsets.UTF_8);}
    private static CadastralParcelRepository.SourceSnapshot source(Vector v,String parcel) {
        var f=v.fields();return new CadastralParcelRepository.SourceSnapshot("30000000-0000-4000-8000-000000000001",parcel,text(f[4]),text(f[5]),text(f[6]),text(f[1]),(byte[])f[2],text(f[3]),text(f[7]),0,text(f[8]),false,null,text(f[11]));
    }
    @Test public void sourceAndCapturedInputUseSharedBinaryGoldenVectors()throws Exception {
        var vectors=vectors();assertEquals(4,vectors.size());for(var v:vectors.values())assertEquals(v.hash(),CadastralFingerprint.fingerprint(v.fields()));
        try(var db=CadastralSynthetic.database()) {
            var repo=new CadastralParcelRepository(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION);
            var field=new CultivatedFieldRef(CadastralSynthetic.SCOPE,CadastralSynthetic.FIELD);String parcel="20000000-0000-4000-8000-000000000001";
            repo.ensureParcel(new CadastralParcel(CadastralSynthetic.SCOPE,parcel,new ScopedParcelIdentity(new IdentifierScope("GR","kaek","hellenic-cadastre",""),"510000000001"),"510000000001","gr-kaek-ascii12-v1",new RecordVersion(1,0,0,null)));
            repo.link(new FieldCadastralLink(field,parcel,new RecordVersion(1,0,0,null),false,true),0);
            var s=source(vectors.get("source-snapshot"),parcel);assertEquals(vectors.get("source-snapshot").hash(),s.contentHash());
            byte[] copy=s.sourcePayload();copy[0]=99;assertEquals(vectors.get("source-snapshot").hash(),s.contentHash());
            repo.completeLookup(s,repo.enqueue(parcel,"synthetic"));var captured=repo.snapshotInputs(field);
            assertEquals(vectors.get("input-snapshot").hash(),captured.fingerprint());
            var forged=new CadastralParcelRepository.InputSnapshot(field,1,List.of(),captured.fingerprint());
            assertThrows(CadastralParcelRepository.Conflict.class,()->repo.publishOverlay(forged,CadastralUnion.build(forged,()->false)));
        }
    }
    @Test public void earlyCommitAndMissingFenceCannotLeavePermitEnabled()throws Exception {
        try(var db=CadastralSynthetic.database()) {
            assertThrows(IllegalStateException.class,()->CadastralMigration.guarded(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,()->{
                db.execSQL("UPDATE fields SET area=99");db.setTransactionSuccessful();db.endTransaction();return null;
            }));
            try(var c=db.rawQuery("SELECT permit FROM cadastral_storage_state",null)){assertTrue(c.moveToFirst());assertEquals(0,c.getInt(0));}
            try(var c=db.rawQuery("SELECT area FROM fields",null)){assertTrue(c.moveToFirst());assertEquals(3.25,c.getDouble(0),0);}
            String name;try(var c=db.rawQuery("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='fields' LIMIT 1",null)){assertTrue(c.moveToFirst());name=c.getString(0);}
            db.execSQL("DROP TRIGGER "+name);
            assertThrows(IllegalStateException.class,()->CadastralMigration.guarded(db,CadastralSynthetic.SCOPE,CadastralSynthetic.ACTIVATION,()->null));
        }
    }
    @Test public void mixedXmlRightsAndUnsafeUrlsAreHandled()throws Exception {
        String xml="<feed xmlns='http://www.w3.org/2005/Atom'><link rel='license' href='terms.html'/><entry><id>urn:fixture</id><rights>One <b xmlns='http://www.w3.org/1999/xhtml'>two</b> three</rights></entry></feed>";
        var d=InspireOffline.parseFeed(xml.getBytes(StandardCharsets.UTF_8),new InspireOffline.FeedDescriptor("https://example.invalid/feed","source","terms"),0).get(0);
        assertEquals("One two three",d.rights());
        assertEquals("https://example.invalid/terms.html",d.termsReference());
        for(String url:List.of("https://@example.invalid/","https://example.invalid:99999/","https://example.invalid/#"))assertThrows(IllegalArgumentException.class,()->CadastralProviderIO.url(url,false));
    }
}
