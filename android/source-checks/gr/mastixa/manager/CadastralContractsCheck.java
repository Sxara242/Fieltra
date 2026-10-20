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
    private static void check(boolean condition,String name){if(!condition)throw new AssertionError(name);}
    private static void refuses(Runnable action){try{action.run();}catch(IllegalArgumentException expected){return;}throw new AssertionError("Expected refusal");}
    public static void main(String[] args)throws Exception {
        if(args.length!=1)throw new IllegalArgumentException("Shared fingerprint TSV required");int vectors=0;
        for(String line:Files.readAllLines(Path.of(args[0]),StandardCharsets.UTF_8)) {
            if(line.isEmpty()||line.startsWith("#"))continue;
            String[] columns=line.split("\t",-1);check(columns.length==3,"TSV structure");
            String[] encoded=columns[1].split(",",-1);Object[] fields=new Object[encoded.length];
            for(int n=0;n<fields.length;n++)fields[n]=encoded[n].equals("-")?null:Base64.getDecoder().decode(encoded[n]);
            check(columns[2].equals(CadastralFingerprint.fingerprint(fields)),columns[0]);vectors++;
        }
        check(vectors==4,"All golden framing/source/input vectors required");
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
