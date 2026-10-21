package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import java.util.concurrent.atomic.AtomicInteger;

/** WMS/Atom/offline protocol source with injected fake transport only.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastreProvidersTest {
    @Test public void wmsCoalescingIncludesFormatAndRemovesCompletedRequests()throws Exception {
        var descriptor=GreekCadastreWms.Descriptor.official();String url=GreekCadastreWms.capabilitiesRequest(descriptor,"1.3.0");
        Queue<Runnable> pending=new ArrayDeque<>();AtomicInteger calls=new AtomicInteger();
        var client=new GreekCadastreWms(descriptor,(source,max,cancel,http)->{calls.incrementAndGet();return new CadastralProviderIO.Response(200,"text/xml",bytes(WMS),source,"");});
        var first=client.submit(pending::add,url,null,()->false);
        assertSame(first,client.submit(pending::add,url,null,()->false));
        var image=client.submit(pending::add,url,"image/png",()->false);assertNotSame(first,image);
        assertEquals(0,calls.get());pending.remove().run();assertEquals(200,first.join().status());
        pending.remove().run();assertThrows(java.util.concurrent.CompletionException.class,image::join);
        var cancelled=client.submit(pending::add,url,null,()->true);assertNotSame(first,cancelled);
        pending.remove().run();assertThrows(java.util.concurrent.CompletionException.class,cancelled::join);assertEquals(2,calls.get());
    }
    private static byte[] bytes(String s){return s.getBytes(StandardCharsets.UTF_8);}
    private static final String WMS="<WMS_Capabilities version=\"1.3.0\" xmlns=\"http://www.opengis.net/wms\"><Capability><Request><GetMap><Format>image/png</Format></GetMap></Request><Layer><CRS>EPSG:4326</CRS><Layer><Name>synthetic-layer</Name></Layer></Layer></Capability></WMS_Capabilities>";
    private static final String FEED="<feed xmlns=\"http://www.w3.org/2005/Atom\"><id>urn:synthetic:feed</id><rights>synthetic rights</rights><entry><id>urn:synthetic:region</id><updated>2026-10-20T00:00:00Z</updated><link rel=\"enclosure\" type=\"application/zip\" href=\"region.zip\"/></entry></feed>";
    @Test public void advertisedWmsLayerAndVersionAxes()throws Exception {
        var descriptor=GreekCadastreWms.Descriptor.official();var caps=GreekCadastreWms.parseCapabilities(bytes(WMS),descriptor);
        String v13=GreekCadastreWms.mapRequest(descriptor,caps,List.of("synthetic-layer"),List.of(""),"EPSG:4326",new double[]{19,34,30,42},256,256,"image/png");
        assertTrue(v13.contains("BBOX=34.0%2C19.0%2C42.0%2C30.0"));assertTrue(v13.contains("CRS=EPSG%3A4326"));
        var old=new GreekCadastreWms.Capabilities("1.1.1",caps.layers(),caps.formats(),caps.sourceUrl(),"","");
        String v11=GreekCadastreWms.mapRequest(descriptor,old,List.of("synthetic-layer"),List.of(""),"EPSG:4326",new double[]{19,34,30,42},256,256,"image/png");
        assertTrue(v11.contains("BBOX=19.0%2C34.0%2C30.0%2C42.0"));assertTrue(v11.contains("SRS=EPSG%3A4326"));
        assertThrows(IllegalArgumentException.class,()->GreekCadastreWms.mapRequest(descriptor,caps,List.of("invented-layer"),List.of(""),"EPSG:4326",new double[]{19,34,30,42},256,256,"image/png"));
    }
    @Test public void xmlDtdIsRejectedAndFeedRightsRetained()throws Exception {
        assertThrows(IOException.class,()->CadastralProviderIO.xml(bytes("<!DOCTYPE feed [<!ENTITY attack SYSTEM 'file:///forbidden'>]><feed>&attack;</feed>")));
        var descriptor=new InspireOffline.FeedDescriptor("https://example.invalid/atom/feed.xml","synthetic source","synthetic terms");
        var entry=InspireOffline.parseFeed(bytes(FEED),descriptor,0).get(0);
        assertEquals("https://example.invalid/atom/region.zip",entry.links().get(0).url());assertEquals("synthetic rights",entry.rights());assertEquals(CadastralMigration.hash(bytes(FEED)),entry.feedHash());
        assertFalse(InspireOffline.resumeIsValid(200,null,"\"v1\"","\"v1\"",100,200));
        assertTrue(InspireOffline.resumeIsValid(206,"bytes 100-199/200","\"v1\"","\"v1\"",100,200));
    }
    private static byte[] zip(String name)throws IOException {
        var bytes=new ByteArrayOutputStream();try(var z=new ZipOutputStream(bytes)){z.putNextEntry(new ZipEntry(name));z.write(new byte[]{1,2,3});z.closeEntry();}return bytes.toByteArray();
    }
    private static void zipSecurityCases(Path file)throws Exception {
        Files.write(file,CadastralSynthetic.rawZip("folder/","folder/nested/","folder/nested/valid.txt"));
        InspireOffline.inspectZip(file,()->false);
        Files.write(file,zip("folder/valid.txt"));InspireOffline.inspectZip(file,()->false); // deflate + data descriptor
        for(String hostile:new String[]{"../escape","folder/../escape","/absolute","C:relative","C:/absolute",
                "folder\\escape","folder\\..\\escape","\\\\host\\share","//host/share","folder//file","folder/./file",
                "folder//","","folder/..","name.","name ","folder./file","folder /file","nul"+(char)0+"suffix"}) {
            Files.write(file,CadastralSynthetic.rawZip(hostile));
            assertThrows("Hostile member: "+hostile,IOException.class,()->InspireOffline.inspectZip(file,()->false));
        }
        for(String[] collision:new String[][]{{"same","same"},{"Name","name"},{"caf\u00e9","cafe\u0301"},
                {"Stra\u00dfe","STRASSE"},{"\u03c3","\u03c2"},{"folder/","folder"},{"folder","folder/child"},
                {"folder/child","FOLDER"},{"caf\u00e9","cafe\u0301/child"},{"folder/","FOLDER/"},
                {"folder","folder/"},{"folder/","folder/"},{"cafe\u0301/child","CAF\u00c9"}}) {
            Files.write(file,CadastralSynthetic.rawZip(collision));
            assertThrows(Arrays.toString(collision),IOException.class,()->InspireOffline.inspectZip(file,()->false));
        }
        // Equal byte lengths, genuinely different LOC and CEN names.
        Files.write(file,CadastralSynthetic.rawZip(new String[]{"safe.txt"},new String[]{"evil.txt"}));
        assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        Files.write(file,CadastralSynthetic.rawZip(new String[]{"safe.txt"},new String[]{"../x.txt"}));
        assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        byte[] encrypted=CadastralSynthetic.rawZip("safe.txt");
        int central=30+"safe.txt".length()+3;
        encrypted[6]|=1;encrypted[central+8]|=1;Files.write(file,encrypted);
        assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        byte[] crcMismatch=CadastralSynthetic.rawZip("safe.txt");crcMismatch[14]^=1;Files.write(file,crcMismatch);
        assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        byte[] invalidUtf8=CadastralSynthetic.rawZip("safe.txt");invalidUtf8[30]=(byte)0xff;invalidUtf8[central+46]=(byte)0xff;Files.write(file,invalidUtf8);
        assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        String[] many=new String[257];for(int n=0;n<many.length;n++)many[n]="entry-"+n;
        Files.write(file,CadastralSynthetic.rawZip(many));assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        Files.write(file,CadastralSynthetic.rawZip("empty/"));
        assertThrows(InterruptedIOException.class,()->InspireOffline.inspectZip(file,()->true));
        Thread.currentThread().interrupt();
        try{assertThrows(InterruptedIOException.class,()->InspireOffline.inspectZip(file,()->false));}finally{Thread.interrupted();}
    }
    private static void refusesZipName(Path file,String reason,String... names)throws Exception {
        Files.write(file,CadastralSynthetic.rawZip(names));
        IOException failure=assertThrows(IOException.class,()->InspireOffline.inspectZip(file,()->false));
        assertTrue("Expected policy refusal: "+reason+", actual: "+failure,failure.getMessage().contains(reason));
    }
    /** Deterministic policy boundaries, no timing/benchmark assertions or new test identities. */
    private static void zipNameResourceCases(Path file)throws Exception {
        Files.write(file,CadastralSynthetic.rawZip("folder/file.txt","folder/","folder/nested/second.txt","folder/nested/"));
        InspireOffline.inspectZip(file,()->false); // explicit directory may follow its implicit children
        String deepest="a/".repeat(63)+"file"; // exactly 64 components
        for(String accepted:new String[]{"x".repeat(4096),"\u00e9".repeat(2048),"\ud83c\udf31".repeat(1024),deepest}) {
            Files.write(file,CadastralSynthetic.rawZip(accepted));InspireOffline.inspectZip(file,()->false);
        }
        refusesZipName(file,"filename byte budget","a/".repeat(30000)+"x"); // 30,001 components; early length refusal
        refusesZipName(file,"filename byte budget","x".repeat(65535)); // exact ZIP uint16 name-field maximum
        refusesZipName(file,"filename byte budget","x".repeat(4097));
        refusesZipName(file,"filename byte budget","\u00e9".repeat(2048)+"x");
        refusesZipName(file,"filename byte budget","\ud83c\udf31".repeat(1024)+"x");
        refusesZipName(file,"filename byte budget","\u0130".repeat(1366)); // full fold expands beyond 4096 UTF-8 bytes
        refusesZipName(file,"component depth budget","a/".repeat(64)+"file");
        String[] longNames=new String[65],foldedNames=new String[65];
        for(int n=0;n<longNames.length;n++) {
            String suffix=String.format(Locale.ROOT,"%04d",n);
            longNames[n]="x".repeat(4092)+suffix;
            foldedNames[n]="\u0130".repeat(1364)+suffix; // decoded2732; canonical4096 bytes
        }
        // 64 * 4096 = exactly 256KiB. The next distinct member must refuse.
        Files.write(file,CadastralSynthetic.rawZip(Arrays.copyOf(longNames,64)));InspireOffline.inspectZip(file,()->false);
        refusesZipName(file,"aggregate filename budget",longNames);
        Files.write(file,CadastralSynthetic.rawZip(Arrays.copyOf(foldedNames,64)));InspireOffline.inspectZip(file,()->false);
        refusesZipName(file,"aggregate canonical filename budget",foldedNames);
        String[] members=new String[256];for(int n=0;n<members.length;n++)members[n]="member-"+n;
        Files.write(file,CadastralSynthetic.rawZip(members));InspireOffline.inspectZip(file,()->false);
        Files.write(file,CadastralSynthetic.rawZip(deepest));
        // False initially; changes while a single name is being validated, before payload reads.
        AtomicInteger checkpoints=new AtomicInteger();
        assertThrows(InterruptedIOException.class,()->InspireOffline.inspectZip(file,()->checkpoints.incrementAndGet()>=16));
        assertEquals(16,checkpoints.get());
        checkpoints.set(0);
        try {
            assertThrows(InterruptedIOException.class,()->InspireOffline.inspectZip(file,()->{
                if(checkpoints.incrementAndGet()==16)Thread.currentThread().interrupt();return false;
            }));
            assertTrue("Interruption must remain signalled",Thread.currentThread().isInterrupted());
        }finally{Thread.interrupted();}
    }
    @Test public void explicitOfflinePublicationReuseCancelAndCorruption()throws Exception {
        try(var fixture=CadastralSynthetic.fixture();var index=SQLiteDatabase.create(null)) {
            Path root=fixture.root;
            var store=new InspireOffline.Store(root,index);var d=InspireOffline.parseFeed(bytes(FEED),new InspireOffline.FeedDescriptor("https://example.invalid/atom/feed.xml","source","terms"),0).get(0);var link=d.links().get(0);
            byte[] archive=zip("synthetic.txt");AtomicInteger calls=new AtomicInteger();
            CadastralProviderIO.Transport transport=(url,max,cancel,http)->{calls.incrementAndGet();return new CadastralProviderIO.Response(200,"application/zip",archive,url,"");};
            var bad=new InspireOffline.DownloadLink(link.url(),link.mediaType(),link.length(),"0".repeat(64));
            var wrong=new InspireOffline.Dataset(d.identifier(),d.title(),d.version(),d.updated(),d.spatialCoverage(),List.of(bad),d.feedUrl(),d.attribution(),d.rights(),d.termsReference(),d.retrievedAt(),d.spatialIdentifiers(),d.feedHash());
            assertThrows(IOException.class,()->store.download(wrong,bad,true,()->false,transport,null));
            assertEquals(InspireOffline.Availability.MISSING,store.availability(wrong,bad));
            try(var files=Files.list(root)){assertEquals(0,files.filter(p->p.toString().endsWith(".zip")||p.toString().endsWith(".part")).count());}
            byte[] deepArchive=CadastralSynthetic.rawZip("a/".repeat(4000)+"x");
            CadastralProviderIO.Transport hostile=(url,max,cancel,http)->new CadastralProviderIO.Response(200,"application/zip",deepArchive,url,"");
            assertThrows(IOException.class,()->store.download(d,link,true,()->false,hostile,null));
            assertEquals(InspireOffline.Availability.MISSING,store.availability(d,link));
            try(var files=Files.list(root)){assertEquals(0,files.filter(p->p.toString().endsWith(".zip")||p.toString().endsWith(".part")).count());}
            calls.set(0);
            assertThrows(IllegalArgumentException.class,()->store.download(d,link,false,()->false,transport,null));
            assertThrows(InterruptedIOException.class,()->store.download(d,link,true,()->true,transport,null));assertEquals(0,calls.get());
            Path target=store.download(d,link,true,()->false,transport,null);assertEquals(target,store.download(d,link,true,()->false,transport,null));assertEquals(1,calls.get());
            var newer=new InspireOffline.Dataset(d.identifier(),d.title(),"fixture-v2",d.updated(),d.spatialCoverage(),d.links(),d.feedUrl(),d.attribution(),d.rights(),d.termsReference(),d.retrievedAt(),d.spatialIdentifiers(),d.feedHash());
            assertEquals(InspireOffline.Availability.MISSING,store.availability(newer,link));
            assertEquals(InspireOffline.Availability.AVAILABLE,store.availability(d,link));Files.write(target,new byte[]{9});assertEquals(InspireOffline.Availability.CORRUPT,store.availability(d,link));
            Path malformed=root.resolve("bad.zip");Files.write(malformed,zip("../escape"));assertThrows(IOException.class,()->InspireOffline.inspectZip(malformed,()->false));
            Files.write(malformed,archive);assertThrows(InterruptedIOException.class,()->InspireOffline.inspectZip(malformed,()->true));
            zipSecurityCases(malformed); // Same B02 method inventory; every case must reach assertions on API26 and API36.
            zipNameResourceCases(malformed);
        }
    }
}
