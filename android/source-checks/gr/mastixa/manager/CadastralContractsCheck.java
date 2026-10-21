package gr.mastixa.manager;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static gr.mastixa.manager.CadastralProtocol.*;
import static gr.mastixa.manager.CountryExtensions.*;

/** Standalone hosted-JVM checks: no Android, JUnit, emulator or new dependency.
 * Not discovered by Gradle testDebugUnitTest; exact javac/java commands in context.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralContractsCheck {
    private static final Set<String> VECTOR_IDS=Set.of("framing-null","framing-bytes","source-snapshot","input-snapshot");
    private static void check(boolean condition,String name){if(!condition)throw new AssertionError(name);}
    private static void refuses(Runnable action){try{action.run();}catch(IllegalArgumentException expected){return;}throw new AssertionError("Expected refusal");}
    private static String refusal(Runnable action) {
        try{action.run();}catch(IllegalArgumentException expected){return expected.getClass().getName()+":"+expected.getMessage();}
        throw new AssertionError("Expected deterministic argument refusal");
    }
    private static String vectorRefusal(List<String> lines) {
        try{verifyVectors(lines);}catch(AssertionError expected){return expected.getMessage();}
        throw new AssertionError("Expected vector integrity refusal");
    }
    private static void verifyVectors(List<String> lines) {
        Set<String> seen=new HashSet<>();
        for(String line:lines) {
            if(line.isEmpty()||line.startsWith("#"))continue;
            String[] columns=line.split("\t",-1);check(columns.length==3,"TSV structure");
            check(VECTOR_IDS.contains(columns[0]),"Unexpected vector ID: "+columns[0]);
            check(seen.add(columns[0]),"Duplicate vector ID: "+columns[0]);
            check(columns[2].matches("[0-9a-f]{64}"),"Expected SHA256 format");
            String[] encoded=columns[1].split(",",-1);Object[] fields=new Object[encoded.length];
            for(int n=0;n<fields.length;n++)fields[n]=encoded[n].equals("-")?null:Base64.getDecoder().decode(encoded[n]);
            check(columns[2].equals(CadastralFingerprint.fingerprint(fields)),columns[0]);
        }
        check(seen.equals(VECTOR_IDS),"Missing golden vector IDs");
    }
    public static void main(String[] args)throws Exception {
        if(args.length!=1)throw new IllegalArgumentException("Shared fingerprint TSV required");
        List<String> lines=Files.readAllLines(Path.of(args[0]),StandardCharsets.UTF_8);
        verifyVectors(lines);
        List<String> vectors=lines.stream().filter(s->!s.isEmpty()&&!s.startsWith("#")).toList();
        for(int n=0;n<vectors.size();n++) {
            List<String> missing=new ArrayList<>(vectors);missing.remove(n);
            check(vectorRefusal(missing).equals("Missing golden vector IDs"),"Each required ID must be present");
            check(vectorRefusal(missing).equals(vectorRefusal(missing)),"Deterministic missing-vector refusal");
            List<String> duplicate=new ArrayList<>(vectors);duplicate.add(vectors.get(n));
            check(vectorRefusal(duplicate).startsWith("Duplicate vector ID:"),"Duplicate IDs refused");
        }
        List<String> unexpected=new ArrayList<>(vectors);unexpected.set(0,"unexpected"+vectors.get(0).substring(vectors.get(0).indexOf('\t')));
        check(vectorRefusal(unexpected).startsWith("Unexpected vector ID:"),"Unexpected IDs refused");
        check(!CadastralFingerprint.fingerprint((Object)null).equals(CadastralFingerprint.fingerprint("")),"Null differs from empty");
        check(CadastralFingerprint.fingerprint("\ud83c\udf31").equals(CadastralFingerprint.fingerprint("\ud83c\udf31".getBytes(StandardCharsets.UTF_8))),"Valid supplementary UTF8");
        for(Object unsupported:List.of(1,1L,true,new Object(),List.of("text"))) {
            Runnable invalid=()->CadastralFingerprint.fingerprint(unsupported);
            check(refusal(invalid).equals(refusal(invalid)),"Unsupported types fail deterministically");
        }
        for(String malformed:List.of("\ud800","\udc00","prefix\ud800suffix","\udc00\ud800")) {
            Runnable invalid=()->CadastralFingerprint.fingerprint(malformed);
            check(refusal(invalid).equals(refusal(invalid)),"Malformed Unicode fails deterministically");
        }
        var scope=new IdentifierScope("GR","kaek","hellenic-cadastre","");var adapter=new GreekIdentifierAdapter();
        for(String valid:List.of("000000000001","510000000001"))check(adapter.validate(valid,scope).state()==ValidationState.VALID,valid);
        for(String invalid:List.of("","123"," 510000000001","510000000001 ","５１０００００００００１","٥١٠٠٠٠٠٠٠٠٠١"))check(adapter.validate(invalid,scope).state()==ValidationState.INVALID,"Strict ASCII");
        check(new CountryRegistry().get("ES").descriptor().providerIds().isEmpty(),"Generic fallback");
        var field=new CultivatedFieldRef("default","10000000-0000-4000-8000-000000000001");
        Set<AssociationKey> links=new HashSet<>();for(int n=1;n<=5;n++)links.add(new AssociationKey(field.farmScope(),field.fieldUuid(),String.format(Locale.ROOT,"20000000-0000-4000-8000-%012d",n)));
        check(links.size()==5,"Five associations, one field");
        var config=new FarmCountryConfiguration("default",new RecordVersion(1,0,0,null));check(config.cultivationCountry().equals("GR"),"Explicit default DTO");
        refuses(()->new RecordVersion(0,0,0,null));refuses(()->new CultivatedFieldRef("default","invalid"));
        System.out.println("Cadastral pure-JVM contracts and four shared vectors passed");
    }
}
