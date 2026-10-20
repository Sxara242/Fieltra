package gr.mastixa.manager;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import org.json.*;

/** Regional local-dataset adapter; acquisition is explicitly outside this class.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class GreekCadastreProvider {
    public static final String ID="hellenic-cadastre-north-aegean";
    public static final String SOURCE="https://data.gov.gr/dataset/17226281-9e0f-431f-b1a3-c9e807cdd3cd/resource/f7ae8fc0-715f-45c1-86cb-5feb3b7377d0/download/periferia_voriou_egaiou.zip";
    public static final String TERMS="https://data.gov.gr/pages/terms-of-use";
    public static final String ATTRIBUTION="ΕΛΛΗΝΙΚΟ ΚΤΗΜΑΤΟΛΟΓΙΟ · data.gov.gr";
    private final GreekCadastreDataset dataset;
    public GreekCadastreProvider(GreekCadastreDataset dataset) { this.dataset=dataset; }
    public static boolean supports(String kaek) {
        return kaek!=null&&kaek.matches("[0-9]{12}")&&Set.of("33","43","51").contains(kaek.substring(0,2));
    }
    public Map<String,GreekCadastreDataset.Parcel> readMany(Path archive,Set<String> kaeks,CadastralMigration.Cancellation cancelled)throws IOException {
        return dataset.read(archive,kaeks,cancelled); // One ZIP scan for all linked KAEKs.
    }
    public record OfflineResult(InspireOffline.Availability availability,Map<String,GreekCadastreDataset.Parcel> parcels,
            String sourceUrl,String attribution,String rights,String termsReference) {
        public OfflineResult{parcels=Map.copyOf(parcels);}
    }
    public OfflineResult readOffline(InspireOffline.Store store,InspireOffline.Dataset selected,InspireOffline.DownloadLink link,
            Set<String> kaeks,CadastralMigration.Cancellation cancelled)throws IOException {
        var availability=store.availability(selected,link);
        if(availability!=InspireOffline.Availability.AVAILABLE)return new OfflineResult(availability,Map.of(),link.url(),selected.attribution(),selected.rights(),selected.termsReference());
        Path archive=store.local(selected,link);
        if(archive==null)return new OfflineResult(InspireOffline.Availability.MISSING,Map.of(),link.url(),selected.attribution(),selected.rights(),selected.termsReference());
        return new OfflineResult(availability,readMany(archive,kaeks,cancelled),link.url(),selected.attribution(),selected.rights(),selected.termsReference());
    }
    public static CadastralParcelRepository.SourceSnapshot sourceSnapshot(String parcelUuid,GreekCadastreDataset.Parcel source,String datasetVersion,OfflineResult acquisition) {
        try {
            JSONObject provenance=new JSONObject().put("source_url",acquisition==null?"urn:sha256:"+source.archiveHash():acquisition.sourceUrl())
                .put("terms_url",acquisition==null?"Unverified local archive terms":acquisition.termsReference())
                .put("attribution",acquisition==null?"Local regional-format archive; origin unverified":acquisition.attribution())
                .put("rights",acquisition==null?"":acquisition.rights()).put("archive_hash",source.archiveHash()).put("prj_hash",source.prjHash())
                .put("provider_reference_url",SOURCE).put("provider_terms_reference",TERMS);
            return new CadastralParcelRepository.SourceSnapshot(UUID.randomUUID().toString(),parcelUuid,ID,SOURCE,datasetVersion,source.geometryJson(),source.geometryJson(),
                "EPSG:2100",provenance.toString(),System.currentTimeMillis(),"local_dataset",false,null,source.sourceDate().isEmpty()?null:source.sourceDate());
        }catch(JSONException e){throw new IllegalArgumentException("Invalid local dataset provenance",e);}
    }
}
