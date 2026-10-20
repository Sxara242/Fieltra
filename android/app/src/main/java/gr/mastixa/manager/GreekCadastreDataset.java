package gr.mastixa.manager;

import java.io.*;
import java.nio.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;
import org.locationtech.jts.geom.*;
import org.locationtech.jts.algorithm.Orientation;
import org.locationtech.jts.operation.valid.IsValidOp;

/** Local ZIP/SHP5/SHX/dBASE III reader matching the existing regional contract.
 * Unsupported variants fail closed. No network, extraction or UI dependency.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class GreekCadastreDataset {
    public static final int MAX_ZIP=32*1024*1024, MAX_TOTAL=64*1024*1024, MAX_ENTRY=48*1024*1024;
    private static final GeometryFactory FACTORY=new GeometryFactory();
    public record Parcel(String kaek,String geometryJson,String sourceDate,String archiveHash,String prjHash) {}
    private final Set<String> verifiedPrjHashes;
    /** Only hashes independently checked as EPSG:2100 (e.g. Windows CRS parser).
     * A string containing AUTHORITY[EPSG,2100] alone is NOT CRS verification.
     * Live regional PRJ bytes have not been checked for this new Android reader. */
    public GreekCadastreDataset(Set<String> verifiedEpsg2100PrjHashes) {
        if(verifiedEpsg2100PrjHashes.isEmpty())throw new IllegalArgumentException("Verified EPSG:2100 PRJ fingerprints required");
        for(String h:verifiedEpsg2100PrjHashes)if(!h.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Invalid PRJ fingerprint");
        verifiedPrjHashes=Set.copyOf(verifiedEpsg2100PrjHashes);
    }
    private static IOException invalid(String reason) { return new IOException(reason); }
    private static void check(boolean condition,String reason)throws IOException { if(!condition)throw invalid(reason); }
    private static String utf8(byte[] bytes)throws IOException {
        try{return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();}
        catch(CharacterCodingException e){throw invalid("Invalid UTF-8");}
    }
    private static void cancel(CadastralMigration.Cancellation c)throws InterruptedIOException {
        if(c.cancelled()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
    }
    public Map<String,Parcel> read(Path archive,Set<String> requested,CadastralMigration.Cancellation cancelled)throws IOException {
        final var requestedCancel=cancelled;final long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(60);
        cancelled=()->requestedCancel.cancelled()||System.nanoTime()>deadline;
        check(!requested.isEmpty()&&requested.size()<=128,"Request budget exceeded");
        for(String kaek:requested)check(GreekCadastreProvider.supports(kaek),"Unsupported regional KAEK");
        check(Files.size(archive)<=MAX_ZIP,"ZIP exceeds compressed budget");
        String archiveHash=InspireOffline.fileHash(archive,cancelled);
        Map<String,byte[]> members=new HashMap<>();long total=0;String stem=null;int entries=0;
        try(ZipFile zip=new ZipFile(archive.toFile())) {
            var iterator=zip.entries();
            while(iterator.hasMoreElements()) {
                cancel(cancelled);ZipEntry e=iterator.nextElement();String name=e.getName();
                check(++entries<=5&&!e.isDirectory()&&!name.contains("\\")&&!name.contains(":")&&!name.startsWith("/")&&name.indexOf(0)<0,"Unsafe ZIP member");
                Path path=Paths.get(name);
                for(Path component:path)check(!component.toString().equals("..")&&!component.toString().equals("."),"ZIP path traversal");
                check(path.getNameCount()==1,"Regional ZIP requires flat members");
                int dot=name.lastIndexOf('.');check(dot>0,"Missing member extension");
                String ext=name.substring(dot).toLowerCase(Locale.ROOT),base=name.substring(0,dot);
                check(Set.of(".shp",".shx",".dbf",".prj",".cpg").contains(ext)&&!members.containsKey(ext),"Unexpected/duplicate ZIP member");
                if(stem==null)stem=base;check(stem.equals(base),"Mixed regional dataset names");
                check(e.getSize()>=0&&e.getSize()<=MAX_ENTRY&&e.getCompressedSize()>0&&e.getSize()<=e.getCompressedSize()*1000L,"ZIP expansion budget exceeded");
                check((total+=e.getSize())<=MAX_TOTAL,"ZIP aggregate budget exceeded");
                byte[] data;try(InputStream stream=zip.getInputStream(e)){data=CadastralMigration.readExact(stream,(int)e.getSize(),cancelled);}
                check(data.length==e.getSize(),"ZIP length mismatch");CRC32 crc=new CRC32();crc.update(data);check(crc.getValue()==e.getCrc(),"ZIP checksum mismatch");members.put(ext,data);
            }
        }
        check(members.size()==5,"Incomplete regional ZIP");
        check(utf8(members.get(".cpg")).trim().equalsIgnoreCase("UTF-8"),"Unsupported CPG encoding");
        String prjHash=CadastralMigration.hash(members.get(".prj"));
        check(verifiedPrjHashes.contains(prjHash),"Unsupported or unverified PRJ");
        byte[] shp=members.get(".shp"),shx=members.get(".shx"),dbf=members.get(".dbf");
        header(shp);header(shx);check((shx.length-100)%8==0,"Malformed SHX");
        int records=(shx.length-100)/8;check(records<=500000,"Record budget exceeded");
        DbfLayout attributes=dbf(dbf,records);
        Map<String,Parcel> found=new HashMap<>();ByteBuffer index=ByteBuffer.wrap(shx).order(ByteOrder.BIG_ENDIAN);
        ByteBuffer source=ByteBuffer.wrap(shp);int next=100,totalVertices=0;
        // Hash the exact original ZIP, never a reserialized/extracted equivalent.
        check(archiveHash.equals(InspireOffline.fileHash(archive,cancelled)),"Regional archive changed during reading");
        for(int row=0;row<records;row++) {
            cancel(cancelled);long offset=2L*index.getInt(100+8*row),length=2L*index.getInt(104+8*row);
            check(offset==next&&length>=4&&offset+8+length<=shp.length,"Invalid SHX range");
            source.order(ByteOrder.BIG_ENDIAN);check(source.getInt((int)offset)==row+1&&source.getInt((int)offset+4)*2L==length,"SHP/SHX record mismatch");
            next=(int)(offset+8+length);Attribute attribute=attribute(dbf,row,attributes);
            source.order(ByteOrder.LITTLE_ENDIAN);check(source.getInt((int)offset+8)==5,"Unsupported SHP record type");
            if(attribute.deleted()||!requested.contains(attribute.kaek()))continue;
            check(!found.containsKey(attribute.kaek()),"Ambiguous duplicate KAEK");
            source.order(ByteOrder.LITTLE_ENDIAN);int start=(int)offset+8;
            check(length>=44&&source.getInt(start)==5,"Only non-null 2D Polygon SHP records supported");
            int parts=source.getInt(start+36),points=source.getInt(start+40);
            check(parts>0&&parts<=5000&&points>=4&&points<=20000&&44L+4L*parts+16L*points==length,"Malformed polygon counts");
            totalVertices+=points;check(totalVertices<=100000,"Selected geometry budget exceeded");
            List<LinearRing> shells=new ArrayList<>(),holes=new ArrayList<>();int previous=-1;
            for(int part=0;part<parts;part++) {
                int first=source.getInt(start+44+4*part),end=part+1==parts?points:source.getInt(start+48+4*part);
                check(first>=0&&first>previous&&(part!=0||first==0)&&end-first>=4&&end<=points,"Invalid part offsets");previous=first;
                Coordinate[] coordinates=new Coordinate[end-first];
                for(int n=first;n<end;n++) {
                    if((n&1023)==0)cancel(cancelled);
                    int pos=start+44+4*parts+16*n;double x=source.getDouble(pos),y=source.getDouble(pos+8);
                    check(Double.isFinite(x)&&Double.isFinite(y),"Non-finite coordinate");coordinates[n-first]=new Coordinate(x,y);
                }
                check(coordinates[0].equals2D(coordinates[coordinates.length-1]),"Unclosed SHP ring");
                LinearRing ring=FACTORY.createLinearRing(coordinates);
                if(Orientation.isCCW(coordinates))holes.add(ring);else shells.add(ring);
            }
            List<Polygon> polygons=new ArrayList<>();Map<LinearRing,List<LinearRing>> byShell=new LinkedHashMap<>();
            for(var shell:shells)check(byShell.put(shell,new ArrayList<>())==null,"Duplicate SHP exterior");
            for(var hole:holes) {
                LinearRing owner=null;double area=Double.POSITIVE_INFINITY;
                for(var shell:shells) {cancel(cancelled);var polygon=FACTORY.createPolygon(shell);if(polygon.covers(FACTORY.createPolygon(hole))&&polygon.getArea()<area){owner=shell;area=polygon.getArea();}}
                check(owner!=null,"Uncontained SHP hole");byShell.get(owner).add(hole);
            }
            for(var entry:byShell.entrySet())polygons.add(FACTORY.createPolygon(entry.getKey(),entry.getValue().toArray(new LinearRing[0])));
            check(!polygons.isEmpty(),"Missing SHP shell");Geometry geometry=polygons.size()==1?polygons.get(0):FACTORY.createMultiPolygon(polygons.toArray(new Polygon[0]));
            check(!geometry.isEmpty()&&new IsValidOp(geometry).isValid()&&geometry.getArea()>0,"Invalid SHP polygon topology");
            found.put(attribute.kaek(),new Parcel(attribute.kaek(),CadastralUnion.geoJson(geometry),attribute.date(),archiveHash,prjHash));
        }
        check(next==shp.length,"Trailing/unindexed SHP data");return Map.copyOf(found);
    }
    private static void header(byte[] bytes)throws IOException {
        check(bytes.length>=100,"Truncated SHP/SHX header");ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
        check(b.getInt(0)==9994&&b.getInt(24)*2L==bytes.length,"Invalid SHP/SHX length/magic");
        b.order(ByteOrder.LITTLE_ENDIAN);check(b.getInt(28)==1000&&b.getInt(32)==5,"Unsupported SHP version/type");
        for(int n=36;n<100;n+=8)check(Double.isFinite(b.getDouble(n)),"Invalid SHP bounds");
    }
    private record Attribute(String kaek,String date,boolean deleted) {}
    private record DbfLayout(int header,int width,Map<String,int[]> fields) {}
    private static DbfLayout dbf(byte[] bytes,int expected)throws IOException {
        check(bytes.length>=33&&(bytes[0]&255)==3,"Only dBASE III supported");ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        int rows=b.getInt(4),header=Short.toUnsignedInt(b.getShort(8)),width=Short.toUnsignedInt(b.getShort(10));
        check(rows==expected&&header==97&&width>1&&header+(long)rows*width<=bytes.length&&bytes[96]==13,"Malformed DBF dimensions");
        check(bytes.length==header+(long)rows*width||bytes.length==header+(long)rows*width+1&&bytes[bytes.length-1]==26,"Trailing DBF data");
        Map<String,int[]> fields=new HashMap<>();int offset=1;
        for(int pos=32;pos<96;pos+=32) {
            int end=pos;while(end<pos+11&&bytes[end]!=0)end++;
            String name=utf8(Arrays.copyOfRange(bytes,pos,end));int size=bytes[pos+16]&255;
            check(bytes[pos+11]=='C'&&size>0&&fields.put(name,new int[]{offset,size})==null,"Unsupported DBF field");offset+=size;
        }
        check(fields.keySet().equals(Set.of("KAEK","bLfSpnVr"))&&offset==width,"Unexpected DBF schema");
        return new DbfLayout(header,width,Map.copyOf(fields));
    }
    private static Attribute attribute(byte[] bytes,int row,DbfLayout layout)throws IOException {
        int pos=layout.header()+row*layout.width();check(bytes[pos]==32||bytes[pos]==42,"Invalid DBF record marker");
        String kaek=field(bytes,pos,layout.fields().get("KAEK")),date=field(bytes,pos,layout.fields().get("bLfSpnVr"));
        try{java.time.LocalDate.parse(date);}catch(java.time.format.DateTimeParseException e){date="";}
        return new Attribute(kaek,date,bytes[pos]==42);
    }
    private static String field(byte[] bytes,int row,int[] field)throws IOException {
        int start=row+field[0],end=start+field[1];while(end>start&&bytes[end-1]==32)end--;
        return utf8(Arrays.copyOfRange(bytes,start,end)); // No numeric coercion or leading-zero removal.
    }
}
