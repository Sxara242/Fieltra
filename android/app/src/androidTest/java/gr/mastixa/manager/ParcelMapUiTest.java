package gr.mastixa.manager;

import android.app.Activity;
import android.content.Intent;
import android.location.Location;
import android.os.*;
import android.view.*;
import android.widget.*;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;

public class ParcelMapUiTest {
    private List<View> views(View view){var rows=new ArrayList<View>();rows.add(view);if(view instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++)rows.addAll(views(group.getChildAt(i)));return rows;}
    private void click(String text){for(var root:android.view.inspector.WindowInspector.getGlobalWindowViews())for(var view:views(root))if(view instanceof Button button&&button.getText().toString().equals(text)){button.performClick();return;}fail("Missing button "+text);}
    private boolean has(Activity a,String text){for(var view:views(a.getWindow().getDecorView()))if(view instanceof TextView label&&label.getText().toString().contains(text))return true;return false;}
    private boolean hasGlobal(String text){for(var root:android.view.inspector.WindowInspector.getGlobalWindowViews())for(var view:views(root))if(view instanceof TextView label&&label.getText().toString().contains(text))return true;return false;}
    private Object field(Activity a,String name){try{var field=ParcelMapActivity.class.getDeclaredField(name);field.setAccessible(true);return field.get(a);}catch(Exception e){throw new RuntimeException(e);}}
    private void invoke(Activity a,String name,Class<?>[] types,Object...values){try{var method=ParcelMapActivity.class.getDeclaredMethod(name,types);method.setAccessible(true);method.invoke(a,values);}catch(Exception e){throw new RuntimeException(e);}}
    private void screenshot(String name)throws Exception{var i=InstrumentationRegistry.getInstrumentation();try(var out=new java.io.FileOutputStream(new java.io.File(i.getTargetContext().getExternalFilesDir(null),name))){i.getUiAutomation().takeScreenshot().compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);}}
    @Test public void offlineMapFixPointTrackAndBackgroundPause()throws Exception{
        var i=InstrumentationRegistry.getInstrumentation();var context=i.getTargetContext();assertTrue(context.getPackageName().endsWith(".checks"));var profile=new ProfileStore.Profile("gis-map-ui","GIS test","test","en");context.deleteDatabase(profile.database());String id;
        if(InstrumentationRegistry.getArguments().getString("require_offline","").equals("true")){
            var manager=(android.net.ConnectivityManager)context.getSystemService(android.content.Context.CONNECTIVITY_SERVICE);var caps=manager.getNetworkCapabilities(manager.getActiveNetwork());
            assertTrue("Offline run must have no validated internet connection",caps==null||!caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED));
            assertEquals(1,android.provider.Settings.Global.getInt(context.getContentResolver(),"airplane_mode_on",0));
        }
        try(var farm=new FarmStore(context,profile.database())){farm.addField("Synthetic parcel",1);id=farm.fields().get(0).id();new GeoStore(farm).saveGeometry(id,ParcelGeometry.manual("26 38\n26.001 38\n26.001 38.001\n26 38.001","EPSG:4326"),"manual","",0);}
        Activity screen=null;
        try{i.runOnMainSync(()->{UserSession.clear();UserSession.signIn(profile);});screen=i.startActivitySync(new Intent(context,ParcelMapActivity.class).putExtra("field_id",id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));var a=(ParcelMapActivity)screen;i.waitForIdleSync();
            i.runOnMainSync(()->{assertTrue(has(a,"EPSG:4326"));assertTrue(has(a,"Offline map"));var fix=new Location("gps");fix.setLongitude(26.0005);fix.setLatitude(38.0005);fix.setAccuracy(25);fix.setTime(System.currentTimeMillis());fix.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());a.onLocationChanged(fix);assertTrue(has(a,"Likely inside boundary"));assertTrue(has(a,"25.0 m"));click("Save current location");
            });i.waitForIdleSync();i.runOnMainSync(()->{
                boolean entered=false;for(var root:android.view.inspector.WindowInspector.getGlobalWindowViews())for(var view:views(root))if(view instanceof EditText edit&&"Title".contentEquals(edit.getHint())){edit.setText("Synthetic tree");entered=true;}assertTrue("Point title input visible",entered);click("Save");
                var track=(GpsTrack)field(a,"track");track.start("Synthetic walk",System.currentTimeMillis(),SystemClock.elapsedRealtime());
            });i.waitForIdleSync();screenshot("parcel-map-android.png");
            try(var farm=new FarmStore(context,profile.database())){assertEquals(1,new GeoStore(farm).records(id,"point").size());}
            if(InstrumentationRegistry.getArguments().getString("live_osm","").equals("true")){
                i.runOnMainSync(()->{try{var method=ParcelMapActivity.class.getDeclaredMethod("basemaps");method.setAccessible(true);method.invoke(a);}catch(Exception e){throw new RuntimeException(e);}});i.waitForIdleSync();
                i.runOnMainSync(()->{boolean selected=false;for(var root:android.view.inspector.WindowInspector.getGlobalWindowViews())for(var view:views(root))if(view instanceof ListView list){list.performItemClick(list.getChildAt(1),1,list.getAdapter().getItemId(1));selected=true;}assertTrue(selected);});i.waitForIdleSync();i.runOnMainSync(()->click("OK"));
                long deadline=SystemClock.elapsedRealtime()+20000;int[] loaded={0};while(loaded[0]==0&&SystemClock.elapsedRealtime()<deadline){Thread.sleep(250);i.runOnMainSync(()->{try{var map=(ParcelMapView)field(a,"map");var providerField=ParcelMapView.class.getDeclaredField("basemap");providerField.setAccessible(true);var provider=providerField.get(map);var images=AndroidBasemap.class.getDeclaredField("images");images.setAccessible(true);loaded[0]=((android.util.LruCache<?,?>)images.get(provider)).size();}catch(Exception e){throw new RuntimeException(e);}});}
                assertTrue("Official OSM visible tiles downloaded/decoded",loaded[0]>0);screenshot("parcel-map-osm-android.png");
            }
            i.runOnMainSync(a::finish);i.waitForIdleSync();boolean[] active={true};long stoppedBy=SystemClock.elapsedRealtime()+5000;
            while(active[0]&&SystemClock.elapsedRealtime()<stoppedBy){Thread.sleep(50);i.runOnMainSync(()->active[0]=(boolean)field(a,"resumed"));}assertFalse("Activity must complete onPause",active[0]);
            try(var farm=new FarmStore(context,profile.database())){var tracks=new GeoStore(farm).records(id,"track");assertEquals(1,tracks.size());assertEquals("paused",tracks.get(0).payload().getString("state"));LocalBackup.inspect(farm,LocalBackup.snapshot(farm));}
        }finally{var a=screen;i.runOnMainSync(()->{if(a!=null)a.finish();UserSession.clear();});}
    }
    @Test public void deniedPermissionKeepsMapUsableAndViewportRestorable()throws Exception{
        var i=InstrumentationRegistry.getInstrumentation();var context=i.getTargetContext();var profile=new ProfileStore.Profile("gis-denied-ui","GIS denial","test","el");context.deleteDatabase(profile.database());String id;
        try(var farm=new FarmStore(context,profile.database())){farm.addField("Δοκιμαστικό",1);id=farm.fields().get(0).id();}
        Activity screen=null;try{i.runOnMainSync(()->{UserSession.clear();UserSession.signIn(profile);});screen=i.startActivitySync(new Intent(context,ParcelMapActivity.class).putExtra("field_id",id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));var a=(ParcelMapActivity)screen;i.runOnMainSync(()->{a.onRequestPermissionsResult(201,new String[]{android.Manifest.permission.ACCESS_FINE_LOCATION},new int[]{-1});assertTrue(has(a,"Δεν έχουν αποθηκευτεί όρια"));click("Εντάξει");var map=(ParcelMapView)field(a,"map");map.restoreViewport(new double[]{123,456,.5});assertArrayEquals(new double[]{123,456,.5},map.viewport(),0);click("Λήψη χάρτη για χρήση εκτός σύνδεσης");click("Εντάξει");click("‹ Πίσω");});i.waitForIdleSync();assertTrue(a.isFinishing());}finally{var a=screen;i.runOnMainSync(()->{if(a!=null)a.finish();UserSession.clear();});}
    }
    @Test public void technicalErrorsAreLocalizedWithoutLeakingExceptionText()throws Exception{
        var i=InstrumentationRegistry.getInstrumentation();var context=i.getTargetContext();
        for(var language:List.of("el","en")){
            var profile=new ProfileStore.Profile("gis-error-"+language,"GIS error "+language,"test",language);context.deleteDatabase(profile.database());String id;
            try(var farm=new FarmStore(context,profile.database())){farm.addField(language.equals("el")?"Αγρός RAW_PARCEL_DATA":"Field RAW_PARCEL_DATA",1);id=farm.fields().get(0).id();}
            Activity screen=null;
            try{
                i.runOnMainSync(()->{UserSession.clear();UserSession.signIn(profile);});screen=i.startActivitySync(new Intent(context,ParcelMapActivity.class).putExtra("field_id",id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));var a=screen;i.waitForIdleSync();
                i.runOnMainSync(()->invoke(a,"error",new Class[]{Exception.class},new IllegalArgumentException("RAW_PARCEL_SENTINEL")));i.waitForIdleSync();
                String expected=language.equals("el")?"Η ενέργεια δεν ολοκληρώθηκε. Έλεγξε τα δεδομένα και τον διαθέσιμο χώρο.":"Action failed. Check data and available storage.";
                assertTrue(hasGlobal(expected));assertFalse(hasGlobal("RAW_PARCEL_SENTINEL"));assertTrue("Stored field names remain verbatim",has(a,"RAW_PARCEL_DATA"));
                i.runOnMainSync(()->click(language.equals("el")?"Εντάξει":"OK"));i.waitForIdleSync();
            }finally{var a=screen;i.runOnMainSync(()->{if(a!=null)a.finish();UserSession.clear();});i.waitForIdleSync();context.deleteDatabase(profile.database());}
        }
    }
}
