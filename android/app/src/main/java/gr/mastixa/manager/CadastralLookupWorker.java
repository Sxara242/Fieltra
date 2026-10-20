package gr.mastixa.manager;

import java.io.*;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;

/** Explicit executor/local archive only. Completion must CAS on the store owner.
 * Does not start itself, touch GPS, publish DB data or request network access.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralLookupWorker {
    private CadastralLookupWorker() {}
    public record Request(String parcelUuid,String kaek,String requestUuid,long expectedSourceRevision) {}
    public record Result(Request request,GreekCadastreDataset.Parcel parcel,String status) {}
    public static Future<List<Result>> submit(ExecutorService executor,GreekCadastreProvider provider,
            Path archive,List<Request> requests,CadastralMigration.Cancellation cancel) {
        List<Request> captured=List.copyOf(requests);
        return executor.submit(()->{
            if(captured.isEmpty()||captured.size()>128)throw new IllegalArgumentException("Request budget");
            Set<String> kaeks=new HashSet<>();for(var r:captured)kaeks.add(r.kaek());
            var found=provider.readMany(archive,kaeks,cancel);List<Result> result=new ArrayList<>();
            for(var r:captured)result.add(new Result(r,found.get(r.kaek()),found.containsKey(r.kaek())?"FOUND":"NOT_IN_SNAPSHOT"));
            return List.copyOf(result);
        });
    }
}
