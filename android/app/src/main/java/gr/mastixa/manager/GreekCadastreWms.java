package gr.mastixa.manager;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import static gr.mastixa.manager.CadastralProviderIO.*;

/** Optional orthophoto WMS, independent of cadastral vectors and existing maps.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class GreekCadastreWms {
    public record Descriptor(String endpoint,String attribution,String sourceTermsReference,boolean allowHttp,long cacheMaxBytes) {
        public Descriptor {url(endpoint,allowHttp);if(attribution.isBlank()||cacheMaxBytes<0)throw new IllegalArgumentException("Attribution/cache policy required");}
        public static Descriptor official(){return new Descriptor("http://gis.ktimanet.gr/wms/wmsopen/wmsserver.aspx","Ελληνικό Κτηματολόγιο — ορθοφωτογραφίες WMS","https://gis.ktimanet.gr/wms/ktbasemap/default.aspx",true,0);}
    }
    public record Layer(String name,String title,Set<String> crs,Set<String> styles) {
        public Layer{crs=Set.copyOf(crs);styles=Set.copyOf(styles);}
    }
    public record Capabilities(String version,List<Layer> layers,Set<String> formats,String sourceUrl,String fees,String accessConstraints) {
        public Capabilities{layers=List.copyOf(layers);formats=Set.copyOf(formats);}
    }
    private final Descriptor descriptor;private final Transport transport;
    private record RequestKey(String url,String format) {}
    private final Map<RequestKey,CompletableFuture<Response>> inflight=new HashMap<>();
    public GreekCadastreWms(Descriptor descriptor,Transport transport){this.descriptor=descriptor;this.transport=transport;}
    private static String encode(String s){try{return URLEncoder.encode(s,"UTF-8");}catch(UnsupportedEncodingException e){throw new AssertionError(e);}}
    private static String decode(String s){try{return URLDecoder.decode(s,"UTF-8");}catch(UnsupportedEncodingException e){throw new AssertionError(e);}}
    private static String request(String endpoint,Map<String,String> parameters) {
        URI original=url(endpoint,true);Map<String,String> query=new LinkedHashMap<>();
        if(original.getRawQuery()!=null)for(String pair:original.getRawQuery().split("&")) {
            String[] parts=pair.split("=",2);String key=decode(parts[0]);
            if(!Set.of("SERVICE","REQUEST","VERSION","LAYERS","STYLES","CRS","SRS","BBOX","WIDTH","HEIGHT","FORMAT","TRANSPARENT","BGCOLOR","EXCEPTIONS").contains(key.toUpperCase(Locale.ROOT)))query.put(key,parts.length==2?decode(parts[1]):"");
        }
        query.putAll(parameters);StringJoiner text=new StringJoiner("&");query.forEach((k,v)->text.add(encode(k)+"="+encode(v)));
        return endpoint.split("\\?",2)[0]+"?"+text;
    }
    public static String capabilitiesRequest(Descriptor descriptor,String version) {
        if(!Set.of("1.3.0","1.1.1").contains(version))throw new IllegalArgumentException("Unsupported WMS version");
        return request(descriptor.endpoint(),Map.of("SERVICE","WMS","REQUEST","GetCapabilities","VERSION",version));
    }
    public static Capabilities parseCapabilities(byte[] bytes,Descriptor descriptor)throws IOException {
        Element root=xml(bytes);String version=root.attributes().get("version");
        if(!Set.of("WMS_Capabilities","WMT_MS_Capabilities").contains(root.name())||version==null||!Set.of("1.3.0","1.1.1").contains(version))throw new IOException("Unsupported WMS capabilities/service exception");
        var capabilities=root.children("Capability");if(capabilities.size()!=1)throw new IOException("Missing/ambiguous WMS Capability");
        Element capability=capabilities.get(0);Set<String> formats=new HashSet<>();
        for(var req:capability.children("Request"))for(var map:req.children("GetMap"))for(var f:map.children("Format"))formats.add(f.text());
        List<Layer> layers=new ArrayList<>();for(var layer:capability.children("Layer"))visit(layer,Set.of(),Set.of(),layers);
        var service=root.children("Service");return new Capabilities(version,layers,formats,descriptor.endpoint(),service.isEmpty()?"":service.get(0).childText("Fees"),service.isEmpty()?"":service.get(0).childText("AccessConstraints"));
    }
    private static void visit(Element node,Set<String> inheritedCrs,Set<String> inheritedStyles,List<Layer> layers)throws IOException {
        Set<String> crs=new HashSet<>(inheritedCrs),styles=new HashSet<>(inheritedStyles);
        for(var c:node.children())if(Set.of("CRS","SRS").contains(c.name()))crs.addAll(Arrays.asList(c.text().split("\\s+")));
        for(var s:node.children("Style"))styles.add(s.childText("Name"));String name=node.childText("Name");
        if(!name.isEmpty()) {
            if(layers.stream().anyMatch(l->l.name().equals(name)))throw new IOException("Ambiguous WMS layer");
            layers.add(new Layer(name,node.childText("Title"),crs,styles));
        }
        for(var child:node.children("Layer"))visit(child,crs,styles,layers);
    }
    public static String mapRequest(Descriptor descriptor,Capabilities capabilities,List<String> layers,List<String> styles,
            String crs,double[] bbox,int width,int height,String format) {
        if(!Set.of("1.3.0","1.1.1").contains(capabilities.version()))throw new IllegalArgumentException("Unsupported WMS version");
        if(!descriptor.endpoint().equals(capabilities.sourceUrl())||width<1||height<1||width>2048||height>2048||bbox.length!=4)
            throw new IllegalArgumentException("Map source/dimension budget");
        for(double v:bbox)if(!Double.isFinite(v))throw new IllegalArgumentException("Finite BBOX required");
        if(bbox[0]>=bbox[2]||bbox[1]>=bbox[3])throw new IllegalArgumentException("Nonempty BBOX required");
        if(!Set.of("EPSG:2100","EPSG:3857","EPSG:4326","CRS:84").contains(crs))throw new IllegalArgumentException("Unreviewed CRS axes");
        if(Set.of("EPSG:4326","CRS:84").contains(crs)&&(bbox[0]< -180||bbox[2]>180||bbox[1]< -90||bbox[3]>90))throw new IllegalArgumentException("Geographic BBOX range");
        if(layers.isEmpty()||layers.size()>16||styles.size()!=layers.size()||!capabilities.formats().contains(format)||!Set.of("image/png","image/jpeg").contains(format))throw new IllegalArgumentException("Layers/styles/format budget");
        for(int n=0;n<layers.size();n++) {
            String name=layers.get(n),style=styles.get(n);var layer=capabilities.layers().stream().filter(l->l.name().equals(name)).findFirst().orElseThrow(()->new IllegalArgumentException("Unadvertised layer"));
            if(name.contains(",")||style.contains(",")||!layer.crs().contains(crs)||!style.isEmpty()&&!layer.styles().contains(style))throw new IllegalArgumentException("Unadvertised style/CRS");
        }
        double[] order=capabilities.version().equals("1.3.0")&&crs.equals("EPSG:4326")?new double[]{bbox[1],bbox[0],bbox[3],bbox[2]}:bbox;
        StringJoiner bounds=new StringJoiner(",");for(double value:order)bounds.add(Double.toString(value));Map<String,String> params=new LinkedHashMap<>();
        params.put("SERVICE","WMS");params.put("REQUEST","GetMap");params.put("VERSION",capabilities.version());params.put("LAYERS",String.join(",",layers));params.put("STYLES",String.join(",",styles));
        params.put("BBOX",bounds.toString());params.put("WIDTH",Integer.toString(width));params.put("HEIGHT",Integer.toString(height));params.put("FORMAT",format);params.put(capabilities.version().equals("1.3.0")?"CRS":"SRS",crs);
        return request(descriptor.endpoint(),params);
    }
    /** Same URL/format shares a future. Cancelling it affects all consumers. */
    public synchronized CompletableFuture<Response> submit(Executor executor,String text,String imageFormat,CadastralMigration.Cancellation cancelled) {
        if(imageFormat!=null&&!Set.of("image/png","image/jpeg").contains(imageFormat))throw new IllegalArgumentException("Unsupported WMS image format");
        URI base=url(descriptor.endpoint(),descriptor.allowHttp()),requested=url(text,descriptor.allowHttp());
        if(!Objects.equals(base.getScheme(),requested.getScheme())||!Objects.equals(base.getRawAuthority(),requested.getRawAuthority())||!Objects.equals(base.getPath(),requested.getPath()))throw new IllegalArgumentException("Unreviewed WMS endpoint");
        RequestKey key=new RequestKey(text,imageFormat);
        if(inflight.containsKey(key))return inflight.get(key);
        var future=CompletableFuture.supplyAsync(()->{
            try {
                if(cancelled.cancelled())throw new InterruptedIOException("Cancelled");
                Response response=transport.get(text,imageFormat==null?2*1024*1024:16*1024*1024,cancelled,descriptor.allowHttp());
                if(cancelled.cancelled())throw new InterruptedIOException("Cancelled");
                if(response.status()!=200||!text.equals(response.sourceUrl())||response.body().length>(imageFormat==null?2*1024*1024:16*1024*1024))throw new IOException("Unexpected WMS response");
                if(imageFormat!=null) {
                    byte[] data=response.body();boolean png=data.length>=8&&Arrays.equals(Arrays.copyOf(data,8),new byte[]{(byte)137,80,78,71,13,10,26,10});
                    boolean jpeg=data.length>=3&&data[0]==(byte)255&&data[1]==(byte)216&&data[2]==(byte)255;
                    if(!imageFormat.equals(response.contentType())||!(imageFormat.equals("image/png")?png:imageFormat.equals("image/jpeg")&&jpeg))throw new IOException("WMS image/service exception response");
                }else parseCapabilities(response.body(),descriptor);
                return response;
            }catch(IOException e){throw new CompletionException(e);}
        },executor);
        inflight.put(key,future);future.whenComplete((r,e)->{synchronized(this){inflight.remove(key,future);}});return future;
    }
}
