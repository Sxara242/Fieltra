package gr.mastixa.manager;

import android.content.Context;
import android.graphics.*;
import android.view.*;
import android.location.Location;
import java.util.*;

/** Native provider-independent Web Mercator canvas. No network required for geometry/GPS. */
public final class ParcelMapView extends View {
    private static final double R=6378137;
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path polygonPath=new Path(),trackPath=new Path();
    private final List<List<double[]>> rings=new ArrayList<>();
    private final List<List<double[]>> cadastralRings=new ArrayList<>();
    private ParcelGeometry cadastralGeometry;
    private final List<double[]> savedPoints=new ArrayList<>();
    private final List<List<double[]>> trackSegments=new ArrayList<>();
    private double centerX,centerY,scale=1,minX,maxX,minY,maxY;
    private double[] centroid;
    private float lastX,lastY;
    private boolean fitPending=true;
    public boolean vertices=true,boundary=true,cadastralBoundary=true,followGps=false;
    private Location location;
    private AndroidBasemap basemap;
    private final ScaleGestureDetector pinch;
    public ParcelMapView(Context context){
        super(context);setBackgroundColor(Color.rgb(237,241,232));
        pinch=new ScaleGestureDetector(context,new ScaleGestureDetector.SimpleOnScaleGestureListener(){@Override public boolean onScale(ScaleGestureDetector detector){scale=Math.max(.00001,Math.min(20,scale*detector.getScaleFactor()));invalidate();return true;}});
    }
    public static double[] project(double lon,double lat){return new double[]{R*Math.toRadians(lon),R*Math.log(Math.tan(Math.PI/4+Math.toRadians(Math.max(-85,Math.min(85,lat)))/2))};}
    private float x(double value){return (float)((value-centerX)*scale+getWidth()/2.0);}
    private float y(double value){return (float)((centerY-value)*scale+getHeight()/2.0);}
    public void setGeometry(ParcelGeometry geometry){
        setGeometries(geometry,cadastralGeometry);
    }
    public void setGeometries(ParcelGeometry cultivated,ParcelGeometry cadastral){
        cadastralGeometry=cadastral;
        rings.clear();cadastralRings.clear();minX=minY=Double.POSITIVE_INFINITY;maxX=maxY=Double.NEGATIVE_INFINITY;
        appendRings(cultivated,rings);appendRings(cadastral,cadastralRings);
        var focus=cultivated!=null?cultivated:cadastral;centroid=focus==null?null:project(focus.centroidLon,focus.centroidLat);
        fitParcel();invalidate();
    }
    private void appendRings(ParcelGeometry geometry,List<List<double[]>> target){
        if(geometry==null)return;
        List<double[]> ring=null;int lastPart=-1,lastRing=-1;
        for(var vertex:ParcelGeometry.vertices(geometry.wgs84)){
            if(vertex.part()!=lastPart||vertex.ring()!=lastRing){ring=new ArrayList<>();target.add(ring);lastPart=vertex.part();lastRing=vertex.ring();}
            double[] point=project(vertex.x(),vertex.y());ring.add(point);minX=Math.min(minX,point[0]);maxX=Math.max(maxX,point[0]);minY=Math.min(minY,point[1]);maxY=Math.max(maxY,point[1]);
        }
    }
    public void fitParcel(){
        if(rings.isEmpty()&&cadastralRings.isEmpty())return;
        if(getWidth()==0||getHeight()==0){fitPending=true;return;}
        centerX=(minX+maxX)/2;centerY=(minY+maxY)/2;scale=.75*Math.min(getWidth()/Math.max(1,maxX-minX),getHeight()/Math.max(1,maxY-minY));fitPending=false;invalidate();
    }
    public void setPoints(List<GeoStore.Record> records){savedPoints.clear();for(var record:records)savedPoints.add(project(record.payload().optDouble("longitude"),record.payload().optDouble("latitude")));invalidate();}
    public void setLocation(Location value){location=new Location(value);if(followGps)centerGps();invalidate();}
    public void clearLocation(){location=null;invalidate();}
    public void setBasemap(AndroidBasemap provider){if(basemap!=null)basemap.close();basemap=provider;invalidate();}
    public void networkAvailable(){if(basemap!=null)basemap.networkAvailable();}
    public double[] viewport(){return new double[]{centerX,centerY,scale};}
    public void restoreViewport(double[] state){if(state==null||state.length!=3)return;for(double number:state)if(!Double.isFinite(number))return;if(state[2]<=0)return;centerX=state[0];centerY=state[1];scale=state[2];fitPending=false;invalidate();}
    public void setTrack(org.json.JSONObject payload){
        trackSegments.clear();if(payload!=null)try{var points=payload.getJSONArray("positions");var starts=payload.optJSONArray("segment_starts");Set<Integer> breaks=new HashSet<>();if(starts!=null)for(int i=0;i<starts.length();i++)breaks.add(starts.getInt(i));List<double[]> segment=null;
            for(int i=0;i<points.length();i++){if(i==0||breaks.contains(i)){segment=new ArrayList<>();trackSegments.add(segment);}var point=points.getJSONArray(i);segment.add(project(point.getDouble(0),point.getDouble(1)));}
        }catch(org.json.JSONException e){throw new IllegalArgumentException("Invalid track",e);}invalidate();
    }
    public void centerGps(){if(location==null)return;double[] p=project(location.getLongitude(),location.getLatitude());centerX=p[0];centerY=p[1];if(rings.isEmpty()&&cadastralRings.isEmpty())scale=.5;invalidate();}
    public void fitTrack(){
        double left=Double.POSITIVE_INFINITY,right=Double.NEGATIVE_INFINITY,bottom=Double.POSITIVE_INFINITY,top=Double.NEGATIVE_INFINITY;
        for(var segment:trackSegments)for(var p:segment){left=Math.min(left,p[0]);right=Math.max(right,p[0]);bottom=Math.min(bottom,p[1]);top=Math.max(top,p[1]);}
        if(!Double.isFinite(left)||getWidth()==0||getHeight()==0)return;
        centerX=(left+right)/2;centerY=(bottom+top)/2;scale=Math.min(20,.75*Math.min(getWidth()/Math.max(1,right-left),getHeight()/Math.max(1,top-bottom)));fitPending=false;invalidate();
    }
    public void zoom(double factor){scale=Math.max(.00001,Math.min(20,scale*factor));invalidate();}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){if(fitPending)fitParcel();}
    @Override protected void onDraw(Canvas canvas){
        super.onDraw(canvas);Path polygon=polygonPath;polygon.reset();polygon.setFillType(Path.FillType.EVEN_ODD);
        if(basemap!=null)basemap.draw(canvas,centerX,centerY,scale,getWidth(),getHeight());
        for(var ring:rings){for(int i=0;i<ring.size();i++){double[] p=ring.get(i);if(i==0)polygon.moveTo(x(p[0]),y(p[1]));else polygon.lineTo(x(p[0]),y(p[1]));}polygon.close();}
        if(boundary){paint.setStyle(Paint.Style.FILL);paint.setColor(Color.argb(65,55,135,75));canvas.drawPath(polygon,paint);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(3);paint.setColor(Color.rgb(35,104,62));canvas.drawPath(polygon,paint);}
        if(cadastralBoundary){
            var reference=new Path();reference.setFillType(Path.FillType.EVEN_ODD);
            for(var ring:cadastralRings){for(int i=0;i<ring.size();i++){var p=ring.get(i);if(i==0)reference.moveTo(x(p[0]),y(p[1]));else reference.lineTo(x(p[0]),y(p[1]));}reference.close();}
            paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(3);paint.setColor(Color.rgb(40,95,210));paint.setPathEffect(new DashPathEffect(new float[]{12,8},0));canvas.drawPath(reference,paint);paint.setPathEffect(null);
        }
        paint.setStyle(Paint.Style.FILL);
        if(vertices){paint.setColor(Color.rgb(25,65,40));for(var ring:rings)for(double[] p:ring)canvas.drawCircle(x(p[0]),y(p[1]),5,paint);}
        if(centroid!=null){paint.setColor(Color.rgb(195,85,30));canvas.drawCircle(x(centroid[0]),y(centroid[1]),6,paint);}
        paint.setColor(Color.rgb(128,62,150));for(double[] p:savedPoints)canvas.drawCircle(x(p[0]),y(p[1]),7,paint);
        paint.setColor(Color.rgb(155,70,180));paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(4);for(var segment:trackSegments){var path=trackPath;path.reset();for(int i=0;i<segment.size();i++){var p=segment.get(i);if(i==0)path.moveTo(x(p[0]),y(p[1]));else path.lineTo(x(p[0]),y(p[1]));}canvas.drawPath(path,paint);}paint.setStyle(Paint.Style.FILL);
        if(location!=null){double[] p=project(location.getLongitude(),location.getLatitude());float radius=(float)Math.min(100000,location.getAccuracy()/Math.cos(Math.toRadians(Math.max(-85,Math.min(85,location.getLatitude()))))*scale);paint.setColor(Color.argb(45,30,100,220));canvas.drawCircle(x(p[0]),y(p[1]),radius,paint);paint.setColor(Color.rgb(30,100,220));canvas.drawCircle(x(p[0]),y(p[1]),7,paint);}
    }
    @Override public boolean onTouchEvent(MotionEvent event){
        getParent().requestDisallowInterceptTouchEvent(true);pinch.onTouchEvent(event);
        if(event.getActionMasked()==MotionEvent.ACTION_DOWN){lastX=event.getX();lastY=event.getY();return true;}
        if(event.getActionMasked()==MotionEvent.ACTION_POINTER_UP){int index=event.getActionIndex()==0?1:0;lastX=event.getX(index);lastY=event.getY(index);}
        if(event.getActionMasked()==MotionEvent.ACTION_MOVE){if(!pinch.isInProgress()&&event.getPointerCount()==1){centerX-=(event.getX()-lastX)/scale;centerY+=(event.getY()-lastY)/scale;invalidate();}lastX=event.getX();lastY=event.getY();}
        if(event.getActionMasked()==MotionEvent.ACTION_UP){performClick();getParent().requestDisallowInterceptTouchEvent(false);}return true;
    }
    @Override public boolean performClick(){super.performClick();return true;}
}
