package gr.mastixa.manager;

import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.time.OffsetDateTime;
import java.util.*;
import java.util.zip.*;
import org.json.*;
import static gr.mastixa.manager.CadastralProviderIO.*;

/** Generic explicit Atom/local vector store. No configured live feed, WMS cache,
 * extraction, farm connection or automatic acquisition.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class InspireOffline {
    private InspireOffline() {}
    private static final String ATOM="http://www.w3.org/2005/Atom",BASE="{http://www.w3.org/XML/1998/namespace}base";
    private static final int MAX_ZIP=32*1024*1024;
    public record FeedDescriptor(String sourceUrl,String attribution,String termsReference) {
        public FeedDescriptor{url(sourceUrl,false);if(attribution.isBlank()||termsReference.isBlank())throw new IllegalArgumentException("Feed provenance required");}
    }
    public record DownloadLink(String url,String mediaType,Long length,String expectedSha256) {
        public DownloadLink(String url,String mediaType,Long length){this(url,mediaType,length,null);}
        public DownloadLink {
            CadastralProviderIO.url(url,false);
            if(length!=null&&length<0||expectedSha256!=null&&!expectedSha256.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Invalid size/reviewed SHA256");
        }
    }
    public record Dataset(String identifier,String title,String version,String updated,String spatialCoverage,
            List<DownloadLink> links,String feedUrl,String attribution,String rights,String termsReference,long retrievedAt,
            List<String> spatialIdentifiers,String feedHash) {
        public Dataset{links=List.copyOf(links);spatialIdentifiers=List.copyOf(spatialIdentifiers);
            if(version!=null&&version.isEmpty())version=null;if(updated!=null&&updated.isEmpty())updated=null;if(spatialCoverage!=null&&spatialCoverage.isEmpty())spatialCoverage=null;}
    }
    private static List<Element> children(Element element,String namespace,String name) {
        return element.children().stream().filter(c->c.namespace().equals(namespace)&&c.name().equals(name)).toList();
    }
    private static String text(Element element,String namespace,String name) {
        return children(element,namespace,name).stream().map(InspireOffline::allText).findFirst().orElse("");
    }
    private static String allText(Element e){return e.allText();}
    private static String resolve(String base,String relative){String result=url(base,false).resolve(relative).toString();url(result,false);return result;}
    public static List<Dataset> parseFeed(byte[] data,FeedDescriptor descriptor,long retrievedAt)throws IOException {
        Element root=xml(data);if(!root.namespace().equals(ATOM)||!root.name().equals("feed")||retrievedAt<0)throw new IOException("Atom feed/timestamp required");
        var entries=children(root,ATOM,"entry");if(entries.size()>512)throw new IOException("Feed entry budget");
        String base=resolve(descriptor.sourceUrl(),root.attributes().getOrDefault(BASE,"")),rights=text(root,ATOM,"rights");Set<String> seen=new HashSet<>();List<Dataset> result=new ArrayList<>();
        String feedTerms=descriptor.termsReference();
        for(var link:children(root,ATOM,"link"))if("license".equals(link.attributes().get("rel"))){
            String href=link.attributes().get("href");if(href==null||href.isEmpty())throw new IOException("Feed license has no URL");
            feedTerms=resolve(resolve(base,link.attributes().getOrDefault(BASE,"")),href);
        }
        for(var entry:entries) {
            String identifier=text(entry,ATOM,"id");if(identifier.isEmpty()||!seen.add(identifier))throw new IOException("Missing/duplicate dataset ID");
            String entryBase=resolve(base,entry.attributes().getOrDefault(BASE,"")),stamp=text(entry,ATOM,"updated");
            if(!stamp.isEmpty())try{OffsetDateTime.parse(stamp);}catch(java.time.format.DateTimeParseException e){throw new IOException("Dataset date requires timezone");}
            List<DownloadLink> links=new ArrayList<>();String terms=feedTerms;
            for(var link:children(entry,ATOM,"link")) {
                String rel=link.attributes().getOrDefault("rel","alternate"),type=link.attributes().getOrDefault("type","");
                if(!Set.of("enclosure","alternate","license").contains(rel))continue;
                String href=link.attributes().get("href");if(href==null)throw new IOException("Missing dataset URL");
                String source=resolve(resolve(entryBase,link.attributes().getOrDefault(BASE,"")),href);
                if(rel.equals("license")){terms=source;continue;}
                if(rel.equals("alternate")&&Set.of("application/atom+xml","text/html","").contains(type))continue;
                Long length=null;String value=link.attributes().get("length");
                if(value!=null){if(!value.matches("[0-9]{1,18}"))throw new IOException("Invalid dataset size");length=Long.parseLong(value);}
                links.add(new DownloadLink(source,type,length));
            }
            if(links.size()>32)throw new IOException("Dataset link budget");
            String coverage=text(entry,"http://www.georss.org/georss","box");
            if(!coverage.isEmpty())try {
                String[] values=coverage.split("\\s+");if(values.length!=4)throw new IllegalArgumentException();double[] box=new double[4];
                for(int n=0;n<4;n++){box[n]=Double.parseDouble(values[n]);if(!Double.isFinite(box[n]))throw new IllegalArgumentException();}
                if(!(box[0]>= -90&&box[0]<box[2]&&box[2]<=90&&box[1]>= -180&&box[1]<box[3]&&box[3]<=180))throw new IllegalArgumentException();
            }catch(IllegalArgumentException e){throw new IOException("Invalid GeoRSS coverage");}
            String entryRights=text(entry,ATOM,"rights");List<String> identifiers=new ArrayList<>();
            var codes=children(entry,"http://inspire.ec.europa.eu/schemas/inspire_dls/1.0","spatial_dataset_identifier_code");
            var namespaces=children(entry,"http://inspire.ec.europa.eu/schemas/inspire_dls/1.0","spatial_dataset_identifier_namespace");
            if(codes.size()!=namespaces.size())throw new IOException("Ambiguous INSPIRE identifiers");
            for(int n=0;n<codes.size();n++)identifiers.add(new JSONArray().put(codes.get(n).text()).put(namespaces.get(n).text()).toString());
            result.add(new Dataset(identifier,text(entry,ATOM,"title"),text(entry,"http://purl.org/dc/terms/","hasVersion"),stamp,coverage,links,
                descriptor.sourceUrl(),descriptor.attribution(),entryRights.isEmpty()?rights:entryRights,terms,retrievedAt,identifiers,CadastralMigration.hash(data)));
        }return List.copyOf(result);
    }
    public static String fileHash(Path path,CadastralMigration.Cancellation cancel)throws IOException {
        try {
            MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[65536];int count;long total=0;
            try(InputStream in=Files.newInputStream(path)){while((count=in.read(buffer))!=-1){if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");if((total+=count)>MAX_ZIP)throw new IOException("Hash input exceeds archive budget");digest.update(buffer,0,count);}}
            StringBuilder result=new StringBuilder();for(byte b:digest.digest())result.append(String.format(Locale.ROOT,"%02x",b&255));return result.toString();
        }catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}
    }
    /** No extraction API exists: ZIP paths never become filesystem paths. */
    public static void inspectZip(Path archive,CadastralMigration.Cancellation cancel)throws IOException {
        if(Files.size(archive)>MAX_ZIP)throw new IOException("ZIP compressed budget");
        Set<String> names=new HashSet<>();long total=0;int count=0;
        try(ZipFile zip=new ZipFile(archive.toFile())) {
            var entries=zip.entries();
            while(entries.hasMoreElements()) {
                ZipEntry e=entries.nextElement();String name=e.getName();
                if(++count>256||name.isEmpty()||name.startsWith("/")||name.contains("\\")||name.contains(":")||name.indexOf(0)>=0||!names.add(name.toLowerCase(Locale.ROOT)))throw new IOException("Unsafe ZIP member");
                for(String component:name.split("/",-1))if(component.equals("..")||component.equals("."))throw new IOException("ZIP traversal");
                if(e.getSize()<0||e.getSize()>48*1024*1024||(total+=e.getSize())>64*1024*1024||e.getSize()>Math.max(1,e.getCompressedSize())*1000L)throw new IOException("ZIP expansion budget");
                CRC32 crc=new CRC32();long consumed=0;byte[] buffer=new byte[65536];int n;
                try(InputStream in=zip.getInputStream(e)){while((n=in.read(buffer))!=-1){if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");consumed+=n;if(consumed>e.getSize())throw new IOException("ZIP length mismatch");crc.update(buffer,0,n);}}
                if(consumed!=e.getSize()||crc.getValue()!=e.getCrc())throw new IOException("ZIP CRC/length mismatch");
            }
        }if(count==0)throw new IOException("Empty ZIP");
    }
    public static boolean resumeIsValid(int status,String contentRange,String etag,String previousEtag,long offset,long total) {
        if(status!=206||etag==null||etag.startsWith("W/")||!etag.equals(previousEtag)||contentRange==null)return false;
        var match=java.util.regex.Pattern.compile("bytes ([0-9]{1,18})-([0-9]{1,18})/([0-9]{1,18})").matcher(contentRange);
        return match.matches()&&Long.parseLong(match.group(1))==offset&&Long.parseLong(match.group(2))>=offset&&Long.parseLong(match.group(2))<total&&Long.parseLong(match.group(3))==total;
    }
    public enum Availability { AVAILABLE,MISSING,CORRUPT }
    @FunctionalInterface public interface DatasetValidator {void validate(Path archive)throws IOException;}
    public static final class Store {
        private final Path root;private final SQLiteDatabase index;
        /** Explicit dedicated offline index, NEVER the selected FarmStore database. */
        public Store(Path root,SQLiteDatabase dedicatedIndex)throws IOException {
            try(var c=dedicatedIndex.rawQuery("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('offline_datasets','android_metadata')",null)) {
                if(c.moveToFirst())throw new IOException("Dedicated offline index required");
            }
            if(Files.isSymbolicLink(root))throw new IOException("Offline root cannot be symbolic");
            Files.createDirectories(root);this.root=root.toRealPath();index=dedicatedIndex;
            index.execSQL("CREATE TABLE IF NOT EXISTS offline_datasets(dataset_key TEXT PRIMARY KEY,identifier TEXT NOT NULL,version TEXT,sha256 TEXT NOT NULL,byte_count INTEGER NOT NULL,provenance_json TEXT NOT NULL,stored_at INTEGER NOT NULL)");
        }
        private String key(Dataset d,DownloadLink l){return CadastralFingerprint.fingerprint("fieltra-offline-dataset-v1",d.feedUrl(),d.identifier(),d.version(),d.updated(),l.url(),l.expectedSha256());}
        public Path local(Dataset d,DownloadLink l)throws IOException {
            try(var c=index.rawQuery("SELECT sha256,byte_count FROM offline_datasets WHERE dataset_key=?",new String[]{key(d,l)})) {
                if(!c.moveToFirst())return null;String hash=c.getString(0);long size=c.getLong(1);
                if(!hash.matches("[0-9a-f]{64}")||size>MAX_ZIP||size<0)throw new IOException("Corrupt offline index");
                Path path=root.resolve(hash+".zip");if(Files.isSymbolicLink(path)||l.expectedSha256()!=null&&!hash.equals(l.expectedSha256()))throw new IOException("Corrupt offline dataset identity");if(!Files.exists(path))return null;
                if(Files.isSymbolicLink(path)||Files.size(path)!=size||!fileHash(path,()->false).equals(hash))throw new IOException("Corrupt offline dataset");return path;
            }
        }
        public Availability availability(Dataset d,DownloadLink l) {
            try{return local(d,l)==null?Availability.MISSING:Availability.AVAILABLE;}catch(IOException e){return Availability.CORRUPT;}
        }
        /** Run on an explicit executor. Fresh-only download; no partial append. */
        public Path download(Dataset d,DownloadLink l,boolean initiatedByUser,CadastralMigration.Cancellation cancel,
                Transport transport,DatasetValidator validator)throws IOException {
            if(!initiatedByUser||!d.links().contains(l))throw new IllegalArgumentException("Explicit user-selected dataset/link required");
            url(l.url(),false);
            if(!Set.of("application/zip","application/x-zip-compressed").contains(l.mediaType())||l.length()!=null&&l.length()>MAX_ZIP)throw new IOException("Unsupported/oversized vector archive");
            Path cached=local(d,l);if(cached!=null)return cached;
            if(cancel.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
            Response response=transport.get(l.url(),MAX_ZIP,cancel,false);byte[] data=response.body();
            if(response.status()!=200||!response.sourceUrl().equals(l.url())||data.length>MAX_ZIP||l.length()!=null&&data.length!=l.length())throw new IOException("Dataset response mismatch");
            Path temporary=Files.createTempFile(root,"download-",".part");
            try {
                try(var stream=new FileOutputStream(temporary.toFile())){stream.write(data);stream.getFD().sync();}
                inspectZip(temporary,cancel);if(validator!=null)validator.validate(temporary);
                if(cancel.cancelled())throw new InterruptedIOException("Cancelled");
                String hash=CadastralMigration.hash(data);Path target=root.resolve(hash+".zip");
                if(l.expectedSha256()!=null&&!hash.equals(l.expectedSha256()))throw new IOException("Dataset checksum mismatch");
                try{Files.createLink(target,temporary);}catch(FileAlreadyExistsException e){if(Files.isSymbolicLink(target)||Files.size(target)!=data.length||!fileHash(target,cancel).equals(hash))throw new IOException("Corrupt existing content-addressed dataset");}
                String provenance;
                try {
                    provenance=new JSONObject().put("feed_url",d.feedUrl()).put("feed_hash",d.feedHash()).put("source_url",l.url()).put("attribution",d.attribution())
                        .put("rights",d.rights()).put("terms_reference",d.termsReference()).put("retrieval_timestamp",System.currentTimeMillis()).put("updated",d.updated())
                        .put("version",d.version()).put("spatial_coverage",d.spatialCoverage()).put("spatial_identifiers",new JSONArray(d.spatialIdentifiers()))
                        .put("sha256",hash).put("format",l.mediaType()).put("category","offline-vector-candidate").put("official_source_verified",false).toString();
                }catch(JSONException e){throw new IOException("Invalid dataset metadata",e);}
                if(index.inTransaction())throw new IOException("Nested offline index writer refused");index.beginTransaction();
                try {
                    index.execSQL("DELETE FROM offline_datasets WHERE dataset_key=?",new Object[]{key(d,l)});
                    index.execSQL("INSERT INTO offline_datasets VALUES(?,?,?,?,?,?,?)",new Object[]{key(d,l),d.identifier(),d.version(),hash,data.length,provenance,System.currentTimeMillis()});index.setTransactionSuccessful();
                }finally{index.endTransaction();}
                return target; // A crash before index commit leaves a verified orphan, never a partial AVAILABLE entry.
            }finally{Files.deleteIfExists(temporary);}
        }
    }
}
