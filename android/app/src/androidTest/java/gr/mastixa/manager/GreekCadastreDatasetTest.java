package gr.mastixa.manager;

import org.junit.Test;
import static org.junit.Assert.*;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import java.nio.*;

/** Test-only generated SHP/SHX/DBF/ZIP fixtures, never official bytes.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class GreekCadastreDatasetTest {
    @Test public void regionalFormatLeadingStringAndSourceHash()throws Exception {
        Path file=Files.createTempFile(InstrumentationRegistry.getInstrumentation().getContext().getCacheDir().toPath(),"cadastre-fixture-",".zip");
        try {
            byte[] archive=CadastralSynthetic.dataset(null,false);Files.write(file,archive);
            // This synthetic sentinel fingerprint is NEVER a production CRS allowlist.
            var reader=new GreekCadastreDataset(Set.of(CadastralMigration.hash(CadastralSynthetic.PRJ)));
            var found=reader.read(file,Set.of("510000000001","510000000002"),()->false);
            assertEquals(1,found.size());assertEquals("510000000001",found.get("510000000001").kaek());
            assertEquals(CadastralMigration.hash(archive),found.get("510000000001").archiveHash());assertArrayEquals(archive,Files.readAllBytes(file));
        }finally{Files.deleteIfExists(file);}
    }
    @Test public void traversalMalformedIndexUnverifiedCrsAndCancellationFail()throws Exception {
        Path file=Files.createTempFile(InstrumentationRegistry.getInstrumentation().getContext().getCacheDir().toPath(),"cadastre-malformed-",".zip");
        try {
            var reader=new GreekCadastreDataset(Set.of(CadastralMigration.hash(CadastralSynthetic.PRJ)));
            Files.write(file,CadastralSynthetic.dataset("../escape.shp",false));assertThrows(IOException.class,()->reader.read(file,Set.of("510000000001"),()->false));
            Files.write(file,CadastralSynthetic.dataset(null,true));assertThrows(IOException.class,()->reader.read(file,Set.of("510000000001"),()->false));
            Files.write(file,CadastralSynthetic.dataset(null,false));
            var unknown=new GreekCadastreDataset(Set.of(CadastralMigration.hash("unverified")));assertThrows(IOException.class,()->unknown.read(file,Set.of("510000000001"),()->false));
            assertThrows(InterruptedIOException.class,()->reader.read(file,Set.of("510000000001"),()->true));
        }finally{Files.deleteIfExists(file);}
    }
    private static byte[] changeMember(byte[] original,String suffix,java.util.function.UnaryOperator<byte[]> change)throws IOException {
        ByteArrayOutputStream result=new ByteArrayOutputStream();
        try(var input=new ZipInputStream(new ByteArrayInputStream(original));var output=new ZipOutputStream(result)) {
            ZipEntry entry;while((entry=input.getNextEntry())!=null) {
                byte[] data=CadastralMigration.readBounded(input,4*1024*1024,()->false);
                if(entry.getName().endsWith(suffix))data=change.apply(data);
                if(data!=null){output.putNextEntry(new ZipEntry(entry.getName()));output.write(data);output.closeEntry();}input.closeEntry();
            }
        }return result.toByteArray();
    }
    @Test public void malformedShpDbfCpgMissingMemberAndZipBombFailClosed()throws Exception {
        Path file=Files.createTempFile(InstrumentationRegistry.getInstrumentation().getContext().getCacheDir().toPath(),"cadastre-boundaries-",".zip");
        try {
            byte[] valid=CadastralSynthetic.dataset(null,false);List<byte[]> bad=new ArrayList<>();
            bad.add(changeMember(valid,".shp",data->Arrays.copyOf(data,data.length-1)));
            bad.add(changeMember(valid,".shp",data->{ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).putDouble(156,Double.NaN);return data;}));
            bad.add(changeMember(valid,".dbf",data->{data[0]=4;return data;}));
            bad.add(changeMember(valid,".cpg",data->"ISO-8859-7".getBytes(java.nio.charset.StandardCharsets.US_ASCII)));
            bad.add(changeMember(valid,".cpg",data->null));
            bad.add(changeMember(valid,".shp",data->new byte[2*1024*1024]));
            var reader=new GreekCadastreDataset(Set.of(CadastralMigration.hash(CadastralSynthetic.PRJ)));
            for(byte[] archive:bad){Files.write(file,archive);assertThrows(IOException.class,()->reader.read(file,Set.of("510000000001"),()->false));}
        }finally{Files.deleteIfExists(file);}
    }
}
