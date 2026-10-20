package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import androidx.test.platform.app.InstrumentationRegistry;
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
    @Test public void explicitOfflinePublicationReuseCancelAndCorruption()throws Exception {
        Path root=Files.createTempDirectory(InstrumentationRegistry.getInstrumentation().getContext().getCacheDir().toPath(),"offline-synthetic-");
        try(var index=SQLiteDatabase.create(null)) {
            var store=new InspireOffline.Store(root,index);var d=InspireOffline.parseFeed(bytes(FEED),new InspireOffline.FeedDescriptor("https://example.invalid/atom/feed.xml","source","terms"),0).get(0);var link=d.links().get(0);
            byte[] archive=zip("synthetic.txt");AtomicInteger calls=new AtomicInteger();
            CadastralProviderIO.Transport transport=(url,max,cancel,http)->{calls.incrementAndGet();return new CadastralProviderIO.Response(200,"application/zip",archive,url,"");};
            var bad=new InspireOffline.DownloadLink(link.url(),link.mediaType(),link.length(),"0".repeat(64));
            var wrong=new InspireOffline.Dataset(d.identifier(),d.title(),d.version(),d.updated(),d.spatialCoverage(),List.of(bad),d.feedUrl(),d.attribution(),d.rights(),d.termsReference(),d.retrievedAt(),d.spatialIdentifiers(),d.feedHash());
            assertThrows(IOException.class,()->store.download(wrong,bad,true,()->false,transport,null));
            assertEquals(InspireOffline.Availability.MISSING,store.availability(wrong,bad));
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
        }finally {
            // Only this test-created private directory; no farm/profile or shared cache.
            try(var paths=Files.list(root)){for(Path file:paths.toList())Files.deleteIfExists(file);}Files.deleteIfExists(root);
        }
    }
}
