package gr.mastixa.manager;

import android.util.Xml;
import android.security.NetworkSecurityPolicy;
import java.io.*;
import java.net.*;
import java.util.*;
import org.xmlpull.v1.*;

/** Bounded explicit HTTP/XML only, no auto-start or security-policy changes.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralProviderIO {
    private CadastralProviderIO() {}
    public static URI url(String text,boolean allowHttp) {
        if(text==null)throw new IllegalArgumentException("Provider URL required");
        try {
            URI u=new URI(text);
            if(text.length()>4096||u.getHost()==null||u.getPort()==0||u.getPort()>65535||u.getUserInfo()!=null||u.getFragment()!=null||
                !("https".equals(u.getScheme())||allowHttp&&"http".equals(u.getScheme())))throw new IllegalArgumentException("Invalid provider URL");
            return u;
        }catch(URISyntaxException e){throw new IllegalArgumentException("Invalid provider URL");}
    }
    public record Response(int status,String contentType,byte[] body,String sourceUrl,String etag) {
        public Response { body=body.clone(); }
        @Override public byte[] body(){return body.clone();}
    }
    @FunctionalInterface public interface Transport {
        Response get(String url,int maxBytes,CadastralMigration.Cancellation cancelled,boolean allowHttp)throws IOException;
    }
    public static Response get(String text,int maxBytes,CadastralMigration.Cancellation cancel,boolean allowHttp)throws IOException {
        URI uri=url(text,allowHttp);
        if(uri.getScheme().equals("http")&&!NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted(uri.getHost()))
            throw new IOException("HTTP transport blocked by existing Android policy");
        if(cancel.cancelled())throw new InterruptedIOException("Cancelled");
        long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(30);
        HttpURLConnection connection=(HttpURLConnection)uri.toURL().openConnection();
        connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(15000);connection.setReadTimeout(15000);
        connection.setRequestProperty("Accept-Encoding","identity");connection.setRequestProperty("User-Agent","Fieltra/1.0.1");
        try {
            if(connection.getResponseCode()!=200)throw new IOException("Provider HTTP response rejected");
            long length=connection.getContentLengthLong();String encoding=connection.getContentEncoding();
            if(length>maxBytes||encoding!=null&&!encoding.equalsIgnoreCase("identity"))throw new IOException("Provider input budget/encoding");
            byte[] data;
            try(InputStream in=connection.getInputStream()) {
                data=CadastralMigration.readBounded(in,maxBytes,()->cancel.cancelled()||System.nanoTime()>deadline);
            }
            if(length>=0&&length!=data.length)throw new IOException("Truncated provider response");
            String type=connection.getContentType();if(type==null)type="";
            return new Response(200,type.split(";",2)[0].trim().toLowerCase(Locale.ROOT),data,text,connection.getHeaderField("ETag"));
        }finally{connection.disconnect();}
    }
    public record Element(String namespace,String name,Map<String,String> attributes,String text,List<Element> children,List<Object> content) {
        public Element { attributes=Map.copyOf(attributes);children=List.copyOf(children);content=List.copyOf(content); }
        private void appendText(StringBuilder result){for(Object part:content){if(part instanceof Element)((Element)part).appendText(result);else result.append(part);}}
        public String allText(){StringBuilder result=new StringBuilder();appendText(result);return result.toString().trim();}
        public List<Element> children(String name){return children.stream().filter(c->c.name().equals(name)).toList();}
        public String childText(String name){return children(name).stream().map(Element::allText).findFirst().orElse("");}
    }
    private static final class Builder {
        String namespace,name;Map<String,String> attributes=new HashMap<>();StringBuilder text=new StringBuilder();List<Element> children=new ArrayList<>();List<Object> content=new ArrayList<>();
        Element finish(){return new Element(namespace,name,attributes,text.toString().trim(),children,content);}
    }
    /** Pull parsing rejects DTD/entity expansion before building a bounded tree. */
    public static Element xml(byte[] bytes)throws IOException {
        if(bytes.length>2*1024*1024)throw new IOException("XML input budget");
        try {
            XmlPullParser parser=Xml.newPullParser();parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES,true);
            parser.setFeature(XmlPullParser.FEATURE_PROCESS_DOCDECL,false);
            parser.setInput(new ByteArrayInputStream(bytes),null);Deque<Builder> stack=new ArrayDeque<>();Element root=null;int nodes=0;
            for(int event=parser.nextToken();event!=XmlPullParser.END_DOCUMENT;event=parser.nextToken()) {
                if(event==XmlPullParser.DOCDECL)throw new IOException("DTD forbidden");
                if(event==XmlPullParser.ENTITY_REF&&!Set.of("amp","lt","gt","apos","quot").contains(parser.getName()))throw new IOException("Entity forbidden");
                if(event==XmlPullParser.START_TAG) {
                    if(++nodes>20000||stack.size()>=64||parser.getAttributeCount()>64)throw new IOException("XML structure budget");
                    Builder b=new Builder();b.name=parser.getName();b.namespace=parser.getNamespace();
                    for(int n=0;n<parser.getAttributeCount();n++) {
                        String ns=parser.getAttributeNamespace(n),name=parser.getAttributeName(n);
                        b.attributes.put(ns==null||ns.isEmpty()?name:"{"+ns+"}"+name,parser.getAttributeValue(n));
                    }stack.push(b);
                } else if(event==XmlPullParser.END_TAG) {
                    if(stack.isEmpty())throw new IOException("Malformed XML");Element completed=stack.pop().finish();
                    if(stack.isEmpty()){if(root!=null)throw new IOException("Multiple XML roots");root=completed;}else {stack.peek().children.add(completed);stack.peek().content.add(completed);}
                } else if((event==XmlPullParser.TEXT||event==XmlPullParser.CDSECT||event==XmlPullParser.ENTITY_REF)&&!stack.isEmpty()) {
                    String text=parser.getText();if(text==null)throw new IOException("Unresolved XML entity");stack.peek().text.append(text);stack.peek().content.add(text);
                }
            }
            if(root==null||!stack.isEmpty())throw new IOException("Missing XML root");return root;
        }catch(XmlPullParserException e){throw new IOException("Invalid XML",e);}
    }
}
