package gr.mastixa.manager;

import android.database.sqlite.SQLiteDatabase;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;

/** Generated only by later authorized hosted instrumentation; no official bytes.
 * SPDX-License-Identifier: AGPL-3.0-only */
final class CadastralSynthetic {
    /** Private checks-app directory, owned by one test; close preserves primary failures. */
    static final class Fixture implements AutoCloseable {
        final Path root;
        private Fixture(Path root){this.root=root;}
        @Override public void close()throws IOException {
            // walkFileTree does not follow symlinks; never visit a shared cache parent.
            Files.walkFileTree(root,new SimpleFileVisitor<Path>() {
                @Override public FileVisitResult visitFile(Path file,java.nio.file.attribute.BasicFileAttributes attrs)throws IOException {
                    Files.delete(file);return FileVisitResult.CONTINUE;
                }
                @Override public FileVisitResult postVisitDirectory(Path directory,IOException failure)throws IOException {
                    if(failure!=null)throw failure;Files.delete(directory);return FileVisitResult.CONTINUE;
                }
            });
        }
    }
    static Fixture fixture()throws IOException {
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        if(!context.getPackageName().endsWith(".checks"))throw new IOException("Synthetic checks application required");
        File cache=context.getCacheDir();if(cache==null)throw new IOException("Checks cache unavailable");
        Path parent=cache.toPath();Files.createDirectories(parent);
        if(!Files.isDirectory(parent)||!Files.isWritable(parent)||Files.isSymbolicLink(parent))throw new IOException("Checks cache not writable/private");
        return new Fixture(Files.createTempDirectory(parent.toRealPath(),"b02-synthetic-"));
    }
    static final String SCOPE="synthetic-farm-A",ACTIVATION="30000000-0000-4000-8000-000000000001";
    static final String FIELD="10000000-0000-4000-8000-000000000001",OTHER="10000000-0000-4000-8000-000000000002";
    static SQLiteDatabase database()throws IOException {
        SQLiteDatabase db=SQLiteDatabase.create(null);
        try {
            db.execSQL("CREATE TABLE cadastral_synthetic_input(farm_scope TEXT)");db.execSQL("INSERT INTO cadastral_synthetic_input VALUES(?)",new Object[]{SCOPE});
            db.execSQL("CREATE TABLE fields(id TEXT PRIMARY KEY,kaek TEXT,area REAL,deleted_at INTEGER)");
            db.execSQL("INSERT INTO fields VALUES(?,'510000000001',3.25,NULL)",new Object[]{FIELD});
            try(InputStream schema=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("cadastral_schema_v2.sql")) {
                CadastralMigration.createSyntheticTarget(db,schema,SCOPE,ACTIVATION,"synthetic-source");
            }return db;
        }catch(IOException|RuntimeException|Error failure){try{db.close();}catch(RuntimeException cleanup){failure.addSuppressed(cleanup);}throw failure;}
    }
    static String rectangle(double x,double y,double width,double height)throws JSONException {
        JSONArray ring=new JSONArray();for(double[] p:new double[][]{{x,y},{x,y+height},{x+width,y+height},{x+width,y},{x,y}})ring.put(new JSONArray().put(p[0]).put(p[1]));
        return new JSONObject().put("type","Polygon").put("coordinates",new JSONArray().put(ring)).toString();
    }
    static byte[] header(int bytes,double x,double y) {
        ByteBuffer b=ByteBuffer.allocate(100).order(ByteOrder.BIG_ENDIAN);b.putInt(0,9994);b.putInt(24,bytes/2);
        b.order(ByteOrder.LITTLE_ENDIAN);b.putInt(28,1000);b.putInt(32,5);b.putDouble(36,x);b.putDouble(44,y);b.putDouble(52,x+20);b.putDouble(60,y+20);return b.array();
    }
    static final byte[] PRJ="SYNTHETIC EPSG:2100 TEST-ONLY PRJ SENTINEL".getBytes(StandardCharsets.UTF_8);
    /** Byte-faithful stored ZIP records. Hostile names never pass through ZipEntry. */
    static byte[] rawZip(String[] names,String[] localNames)throws IOException {
        if(names.length!=localNames.length)throw new IllegalArgumentException("One local name per central name");
        ByteArrayOutputStream body=new ByteArrayOutputStream(),central=new ByteArrayOutputStream();
        for(int n=0;n<names.length;n++) {
            byte[] name=names[n].getBytes(StandardCharsets.UTF_8),local=localNames[n].getBytes(StandardCharsets.UTF_8);
            byte[] data=names[n].endsWith("/")?new byte[0]:new byte[]{1,2,3};CRC32 crc=new CRC32();crc.update(data);int offset=body.size();
            ByteBuffer loc=ByteBuffer.allocate(30).order(ByteOrder.LITTLE_ENDIAN);
            loc.putInt(0x04034b50).putShort((short)20).putShort((short)0x800).putShort((short)0).putShort((short)0).putShort((short)33)
                .putInt((int)crc.getValue()).putInt(data.length).putInt(data.length).putShort((short)local.length).putShort((short)0);
            body.write(loc.array());body.write(local);body.write(data);
            ByteBuffer cen=ByteBuffer.allocate(46).order(ByteOrder.LITTLE_ENDIAN);
            cen.putInt(0x02014b50).putShort((short)20).putShort((short)20).putShort((short)0x800).putShort((short)0).putShort((short)0).putShort((short)33)
                .putInt((int)crc.getValue()).putInt(data.length).putInt(data.length).putShort((short)name.length).putShort((short)0).putShort((short)0)
                .putShort((short)0).putShort((short)0).putInt(0).putInt(offset);central.write(cen.array());central.write(name);
        }
        ByteBuffer end=ByteBuffer.allocate(22).order(ByteOrder.LITTLE_ENDIAN);
        end.putInt(0x06054b50).putShort((short)0).putShort((short)0).putShort((short)names.length).putShort((short)names.length)
            .putInt(central.size()).putInt(body.size()).putShort((short)0);
        body.write(central.toByteArray());body.write(end.array());return body.toByteArray();
    }
    static byte[] rawZip(String... names)throws IOException{return rawZip(names,names);}
    static byte[] dataset(String memberOverride,boolean truncatedShx)throws IOException {
        int length=44+4+5*16;ByteBuffer shp=ByteBuffer.allocate(108+length);shp.put(header(shp.capacity(),686000,4249000));
        shp.order(ByteOrder.BIG_ENDIAN).putInt(1).putInt(length/2);shp.order(ByteOrder.LITTLE_ENDIAN).putInt(5);
        shp.putDouble(686000).putDouble(4249000).putDouble(686020).putDouble(4249020).putInt(1).putInt(5).putInt(0);
        for(double[] p:new double[][]{{686000,4249000},{686000,4249020},{686020,4249020},{686020,4249000},{686000,4249000}})shp.putDouble(p[0]).putDouble(p[1]);
        ByteBuffer shx=ByteBuffer.allocate(108);shx.put(header(108,686000,4249000));shx.order(ByteOrder.BIG_ENDIAN).putInt(50).putInt(length/2);
        int width=1+80+80;ByteBuffer dbf=ByteBuffer.allocate(97+width+1).order(ByteOrder.LITTLE_ENDIAN);dbf.put(0,(byte)3);dbf.putInt(4,1);dbf.putShort(8,(short)97);dbf.putShort(10,(short)width);
        String[] names={"KAEK","bLfSpnVr"};for(int n=0;n<2;n++){int pos=32+32*n;byte[] name=names[n].getBytes(StandardCharsets.US_ASCII);for(int k=0;k<name.length;k++)dbf.put(pos+k,name[k]);dbf.put(pos+11,(byte)'C');dbf.put(pos+16,(byte)80);}
        dbf.put(96,(byte)13);Arrays.fill(dbf.array(),97,97+width,(byte)' ');
        byte[] kaek="510000000001".getBytes(StandardCharsets.US_ASCII),date="2026-10-20".getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(kaek,0,dbf.array(),98,kaek.length);System.arraycopy(date,0,dbf.array(),178,date.length);dbf.put(dbf.capacity()-1,(byte)26);
        ByteArrayOutputStream output=new ByteArrayOutputStream();
        try(ZipOutputStream zip=new ZipOutputStream(output)) {
            String[] extensions={".shp",".shx",".dbf",".prj",".cpg"};byte[][] contents={shp.array(),truncatedShx?Arrays.copyOf(shx.array(),107):shx.array(),dbf.array(),PRJ,"UTF-8".getBytes(StandardCharsets.US_ASCII)};
            for(int n=0;n<extensions.length;n++){zip.putNextEntry(new ZipEntry(n==0&&memberOverride!=null?memberOverride:"synthetic"+extensions[n]));zip.write(contents[n]);zip.closeEntry();}
        }return output.toByteArray();
    }
}
