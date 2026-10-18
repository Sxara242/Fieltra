package gr.mastixa.manager;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.location.*;
import android.os.*;
import android.provider.OpenableColumns;
import android.view.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;

/** Profile-local parcel workspace. GNSS callbacks exist only while this screen is resumed. */
public final class ParcelMapActivity extends Activity implements LocationListener {
    private static final int PERMISSION=201,IMPORT=202;
    private ProfileStore.Profile profile;
    private FarmStore farm;
    private GeoStore geo;
    private CadastralStore cadastre;
    private CadastralStore.Record cadastral;
    private FarmStore.Field field;
    private GeoStore.Record parcel;
    private ParcelGeometry geometry;
    private ParcelGeometry cadastralGeometry;
    private ParcelMapView map;
    private TextView metadata,gpsStatus,trackStatus,mapStatus;
    private CheckBox followControl;
    private int basemapChoice;
    private android.net.ConnectivityManager connectivity;
    private boolean connectivityRegistered;
    private final android.net.ConnectivityManager.NetworkCallback networkCallback=new android.net.ConnectivityManager.NetworkCallback(){
        @Override public void onAvailable(android.net.Network network){runOnUiThread(()->{if(resumed){showMapStatus();map.networkAvailable();}});}
        @Override public void onLost(android.net.Network network){runOnUiThread(()->{if(resumed)showMapStatus();});}
        @Override public void onCapabilitiesChanged(android.net.Network network,android.net.NetworkCapabilities caps){runOnUiThread(()->{if(resumed){showMapStatus();if(caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED))map.networkAvailable();}});}
    };
    private LinearLayout body;
    private LocationManager locations;
    private Location fix;
    private GpsTrack track;
    private boolean gpsWanted,resumed,listening;
    private long gpsSessionStartedNanos;
    private String importCrs="";
    private boolean importCadastral;
    private final ExecutorService imports=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable freshness=new Runnable(){public void run(){if(resumed){showFix();handler.postDelayed(this,5000);}}};
    private String w(String el,String en){return profile!=null&&profile.language().equals("en")?en:el;}
    private String formatUiDate(long millis){var locale=profile.language().equals("en")?Locale.ENGLISH:Locale.forLanguageTag("el-GR");return java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.MEDIUM,java.text.DateFormat.MEDIUM,locale).format(new Date(millis));}
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private TextView label(String text){var view=new TextView(this);view.setText(text);view.setTextSize(16);view.setTextColor(0xff20372b);view.setPadding(0,dp(6),0,dp(6));body.addView(view);return view;}
    private void button(String text,Runnable action){var button=new Button(this);button.setText(text);button.setAllCaps(false);button.setMinHeight(dp(48));body.addView(button);button.setOnClickListener(v->{if(authorised())try{action.run();}catch(Exception e){error(e);}});}
    private void message(String text){if(!isFinishing()&&!isDestroyed())new AlertDialog.Builder(this).setMessage(text).setPositiveButton(w("Εντάξει","OK"),null).show();}
    private void error(Exception e){message(w("Η ενέργεια δεν ολοκληρώθηκε. Έλεγξε τα δεδομένα και τον διαθέσιμο χώρο.","Action failed. Check data and available storage."));}
    private boolean authorised(){
        if(profile!=null&&UserSession.valid(this)&&UserSession.profile.id().equals(profile.id()))return true;
        startActivity(new Intent(this,WelcomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));finish();return false;
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);profile=UserSession.valid(this)?UserSession.profile:null;if(!authorised())return;
        farm=new FarmStore(this,profile.database());geo=new GeoStore(farm);cadastre=new CadastralStore(farm);
        String id=getIntent().getStringExtra("field_id");for(var item:farm.fields())if(item.id().equals(id))field=item;
        if(field==null){finish();return;}
        locations=(LocationManager)getSystemService(LOCATION_SERVICE);
        connectivity=(android.net.ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
        try{track=new GpsTrack(geo,field.id());}catch(Exception e){error(e);finish();return;}
        var scroll=new ScrollView(this);body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(16),dp(8),dp(16),dp(24));scroll.addView(body);setContentView(scroll);
        if(Build.VERSION.SDK_INT>=30)getWindow().getInsetsController().setSystemBarsAppearance(WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        else getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        scroll.setOnApplyWindowInsetsListener((view,insets)->{if(Build.VERSION.SDK_INT>=30){var bars=insets.getInsets(WindowInsets.Type.systemBars());view.setPadding(bars.left,bars.top,bars.right,bars.bottom);}else view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        button(w("‹ Πίσω","‹ Back"),this::finish);label(field.name()+"\nKAEK: "+field.kaek());
        metadata=label("");map=new ParcelMapView(this);map.setContentDescription(w("Χάρτης αγροτεμαχίου","Parcel map"));body.addView(map,new LinearLayout.LayoutParams(-1,dp(370)));
        mapStatus=label("");showMapStatus();
        gpsStatus=label(w("GPS ανενεργό","GPS off"));
        button(w("Κεντράρισμα στο αγροτεμάχιο","Fit parcel"),()->{followControl.setChecked(false);map.fitParcel();});
        button(w("Κεντράρισμα στη θέση μου","Center on my location"),()->{if(currentFix())map.centerGps();else enableGps();});
        button(w("Ενεργοποίηση / απενεργοποίηση GPS","Enable / disable GPS"),()->{if(gpsWanted){gpsWanted=false;stopGps();pauseTrack();fix=null;map.clearLocation();showFix();}else enableGps();});
        var follow=new CheckBox(this);followControl=follow;follow.setText(w("Ακολούθηση GPS","Follow GPS"));body.addView(follow);follow.setOnCheckedChangeListener((v,value)->{map.followGps=value;if(value&&resumed){if(currentFix())map.centerGps();else enableGps();}});
        var vertices=new CheckBox(this);vertices.setText(w("Κορυφές","Vertices"));vertices.setChecked(true);body.addView(vertices);vertices.setOnCheckedChangeListener((v,value)->{map.vertices=value;map.invalidate();});
        var boundary=new CheckBox(this);boundary.setText(w("Όρια καλλιέργειας","Cultivated boundary"));boundary.setChecked(true);body.addView(boundary);boundary.setOnCheckedChangeListener((v,value)->{map.boundary=value;map.invalidate();});
        var reference=new CheckBox(this);reference.setText(w("Κτηματολογική αναφορά (μπλε διακεκομμένη)","Cadastral reference (blue dashed)"));reference.setChecked(true);body.addView(reference);reference.setOnCheckedChangeListener((v,value)->{map.cadastralBoundary=value;map.invalidate();});
        button("+",()->map.zoom(1.5));button("−",()->map.zoom(1/1.5));
        button(w("Υπόβαθρο χάρτη","Basemap"),this::basemaps);
        button(w("Λήψη χάρτη για χρήση εκτός σύνδεσης","Download offline map"),this::offlinePack);
        button(w("Εισαγωγή ορίων από αρχείο","Import boundaries from file"),()->{importCadastral=false;chooseImport();});
        button(w("Εισαγωγή κτηματολογικής αναφοράς από αρχείο","Import cadastral reference from file"),()->{if(!field.kaek().matches("[0-9]{12}")){message(w("Καταχώρισε πρώτα έγκυρο 12ψήφιο ΚΑΕΚ.","Enter a valid 12-digit KAEK first."));return;}importCadastral=true;chooseImport();});
        button(w("Χειροκίνητες συντεταγμένες","Manual coordinates"),this::manual);
        button(w("Εξαγωγή κορυφών / συντεταγμένων","Export vertices / coordinates"),()->startActivity(new Intent(this,CoordinateExportActivity.class).putExtra("field_id",field.id())));
        button(w("Ανάκτηση ορίων από Κτηματολόγιο","Retrieve Cadastre boundaries"),()->message(MapProviders.cadastreMessage(profile.language())));
        button(w("Αποθήκευση τρέχουσας θέσης","Save current location"),()->{if(currentFix())pointForm(null,new Location(fix));else message(w("Χρειάζεται πρόσφατη θέση GPS (έως 30 δευτερόλεπτα).","A recent GPS fix is required (up to 30 seconds old)."));});
        button(w("Αποθηκευμένα σημεία","Saved points"),this::points);
        trackStatus=label("");
        button(w("Έναρξη διαδρομής","Start track"),()->{var title=new EditText(this);title.setHint(w("Όνομα διαδρομής","Track title"));var dialog=new AlertDialog.Builder(this).setTitle(w("Νέα διαδρομή","New track")).setView(title).setNegativeButton(w("Ακύρωση","Cancel"),null).setPositiveButton(w("Έναρξη","Start"),null).create();dialog.setOnShowListener(v->dialog.getButton(-1).setOnClickListener(b->{if(!authorised())return;try{track.start(title.getText().toString(),System.currentTimeMillis(),SystemClock.elapsedRealtime());dialog.dismiss();showTrack();enableGps();}catch(Exception e){error(e);}}));dialog.show();});
        button(w("Παύση / συνέχεια διαδρομής","Pause / resume track"),()->{if(track.current()==null)return;track.change(track.recording()?"paused":"recording",System.currentTimeMillis(),SystemClock.elapsedRealtime());showTrack();if(track.recording())enableGps();});
        button(w("Τερματισμός διαδρομής","Stop track"),()->{track.change("stopped",System.currentTimeMillis(),SystemClock.elapsedRealtime());showTrack();});
        button(w("Αποθηκευμένες διαδρομές","Saved tracks"),this::tracks);
        label(w("Η καταγραφή παύει όταν φύγεις από την οθόνη. Το GPS του κινητού δεν αποτελεί τοπογραφική μέτρηση.","Recording pauses when you leave this screen. Phone GPS is not a survey measurement."));
        try{reloadGeometry();}catch(Exception e){error(e);}
        if(state!=null){gpsWanted=state.getBoolean("gps");basemapChoice=state.getInt("basemap",0);importCrs=state.getString("import_crs","");importCadastral=state.getBoolean("import_cadastral");follow.setChecked(state.getBoolean("follow"));vertices.setChecked(state.getBoolean("vertices",true));boundary.setChecked(state.getBoolean("boundary",true));reference.setChecked(state.getBoolean("cadastral_boundary",true));map.restoreViewport(state.getDoubleArray("viewport"));}
        showTrack();
    }
    private void reloadGeometry(){
        parcel=geo.parcel(field.id());geometry=parcel==null?null:GeoStore.geometry(parcel);cadastral=cadastre.parcel(field.id());cadastralGeometry=cadastral==null?null:cadastral.geometry();map.setGeometries(geometry,cadastralGeometry);map.setPoints(geo.records(field.id(),"point"));
        metadata.setText(geometry==null?w("Δεν έχουν αποθηκευτεί όρια.","No boundaries saved."):w("Όρια καλλιέργειας\n","Cultivated boundaries\n")+String.format(Locale.getDefault(),"%.2f m² · %.2f m · %d %s\n%s · %s\n%s",geometry.area,geometry.perimeter,ParcelGeometry.vertices(geometry.original).size(),w("κορυφές","vertices"),geometry.sourceCrs,parcel.payload().optString("geometry_source"),formatUiDate(parcel.updated())));
        if(cadastral!=null)metadata.append("\n"+w("Κτηματολογική αναφορά από αρχείο — μη επαληθευμένη επίσημη προέλευση","Imported cadastral reference — official origin not verified")+"\nKAEK: "+cadastral.kaek()+" · "+cadastralGeometry.sourceCrs+"\n"+cadastral.payload().optString("geometry_source")+" · "+formatUiDate(cadastral.updated())+"\n"+w("Υπολογισμός WGS84 (γεωδαιτικός)","Calculated WGS84 geodesic measurements")+String.format(Locale.getDefault(),"\n%.2f m² · %.2f m",cadastralGeometry.area,cadastralGeometry.perimeter));
        showFix();
    }
    private boolean currentFix(){return GpsFix.usable(fix,SystemClock.elapsedRealtimeNanos());}
    private void enableGps(){gpsWanted=true;if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION},PERMISSION);return;}startGps();}
    private void startGps(){
        stopGps();if(!resumed||!gpsWanted)return;
        gpsSessionStartedNanos=SystemClock.elapsedRealtimeNanos();fix=null;map.clearLocation();
        if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){gpsStatus.setText(w("Χρειάζεται άδεια ακριβούς τοποθεσίας. Πάτησε ενεργοποίηση GPS.","Precise location permission is required. Tap Enable GPS."));return;}
        try{if(locations==null||!locations.getAllProviders().contains(LocationManager.GPS_PROVIDER)){gpsStatus.setText(w("GPS απενεργοποιημένο στη συσκευή. Ενεργοποίησε την τοποθεσία στις ρυθμίσεις.","Device GPS is disabled. Enable location in device settings."));return;}
            // Keep the listener registered while disabled so onProviderEnabled can recover this screen.
            locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,5000,2,this,Looper.getMainLooper());listening=true;showFix();
        }catch(SecurityException|IllegalArgumentException e){gpsStatus.setText(w("Το GPS δεν είναι διαθέσιμο. Έλεγξε τις άδειες τοποθεσίας.","GPS unavailable. Check location permissions."));}
    }
    private void stopGps(){if(locations!=null&&listening){locations.removeUpdates(this);listening=false;}}
    @Override public void onLocationChanged(Location value){if(!resumed||!authorised()||!GpsFix.usable(value,SystemClock.elapsedRealtimeNanos())||value.getElapsedRealtimeNanos()<gpsSessionStartedNanos||(fix!=null&&value.getElapsedRealtimeNanos()<=fix.getElapsedRealtimeNanos()))return;fix=new Location(value);map.setLocation(fix);showFix();try{track.append(fix,SystemClock.elapsedRealtimeNanos());showTrack();}catch(Exception e){pauseTrack();error(e);}}
    @Override public void onProviderDisabled(String provider){gpsSessionStartedNanos=SystemClock.elapsedRealtimeNanos();fix=null;map.clearLocation();pauseTrack();showFix();}
    @Override public void onProviderEnabled(String provider){if(gpsWanted)startGps();}
    @Override public void onStatusChanged(String provider,int status,Bundle extras){}
    private void showFix(){
        if(gpsStatus==null)return;
        if(!gpsWanted&&fix==null){gpsStatus.setText(w("GPS ανενεργό","GPS off"));return;}
        if(gpsWanted&&(locations==null||!locations.isProviderEnabled(LocationManager.GPS_PROVIDER))){gpsStatus.setText(w("GPS απενεργοποιημένο στη συσκευή. Ενεργοποίησε την τοποθεσία στις ρυθμίσεις.","Device GPS is disabled. Enable location in device settings."));return;}
        if(fix==null){gpsStatus.setText(w("Αναμονή θέσης GNSS · Έλεγξε άδεια ακριβούς θέσης και ενεργοποίηση GPS.","Waiting for GNSS · Check precise location permission and device GPS."));return;}
        String status=w("Παλιά θέση — αναμονή νέου στίγματος","Stale position — waiting for a new fix");
        if(currentFix()){
            var boundary=cadastralGeometry!=null?cadastralGeometry:geometry;
            if(boundary==null)status=w("Δεν υπάρχουν όρια για σύγκριση θέσης.","No boundaries available for position comparison.");
            else{
                var relation=boundary.classifyFix(fix.getLongitude(),fix.getLatitude(),fix.getAccuracy());
                status=switch(relation){
                    case INSIDE->w("Πιθανώς εντός ορίων","Likely inside boundary");
                    case OUTSIDE->w("Πιθανώς εκτός ορίων","Likely outside boundary");
                    case UNCERTAIN->w("Αβέβαιο — η ακρίβεια GPS διασχίζει το όριο","Uncertain — GPS accuracy overlaps boundary");
                };
                status+=" · "+(cadastralGeometry!=null?w("κτηματολογική αναφορά","cadastral reference"):w("όρια καλλιέργειας","cultivated boundary"));
                status+="\n"+w("Εκτίμηση βάσει δηλωμένης ακρίβειας GPS, όχι τοπογραφική μέτρηση.","Estimate using reported GPS accuracy, not a survey measurement.");
            }
        }else map.clearLocation();
        gpsStatus.setText(String.format(Locale.getDefault(),"%.8f, %.8f · ±%.1f m\n%s\n%s%s%s",fix.getLatitude(),fix.getLongitude(),fix.getAccuracy(),formatUiDate(fix.getTime()),status,fix.hasBearing()?String.format(Locale.getDefault(),"\n%.1f°",fix.getBearing()):"",fix.hasSpeed()?String.format(Locale.getDefault()," · %.1f m/s",fix.getSpeed()):""));
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){super.onRequestPermissionsResult(request,permissions,grants);if(request==PERMISSION&&authorised()){if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED)startGps();else{gpsWanted=false;pauseTrack();message(w("Η άδεια ακριβούς τοποθεσίας δεν δόθηκε. Τα αποθηκευμένα όρια παραμένουν διαθέσιμα.","Precise location permission was not granted. Saved boundaries remain available."));}}}
    private void pauseTrack(){if(track!=null&&track.recording())try{track.change("paused",System.currentTimeMillis(),SystemClock.elapsedRealtime());showTrack();}catch(Exception e){error(e);}}
    private String trackStateLabel(String state){return switch(state){case "recording"->w("Καταγραφή","Recording");case "paused"->w("Σε παύση","Paused");case "stopped"->w("Σταματημένο","Stopped");default->state;};}
    private void showTrack(){if(trackStatus==null)return;var row=track.current();if(map!=null&&row!=null)map.setTrack(row.payload());trackStatus.setText(row==null?w("Δεν υπάρχει ενεργή διαδρομή.","No active track."):row.payload().optString("title")+" · "+trackStateLabel(row.payload().optString("state"))+String.format(Locale.getDefault()," · %.1f m · %d s",row.payload().optDouble("distance_m"),row.payload().optLong("duration_ms")/1000));}
    @Override protected void onResume(){super.onResume();if(farm==null||map==null||!authorised())return;resumed=true;startGps();handler.post(freshness);if(basemapChoice==1)map.setBasemap(new AndroidBasemap(this,AndroidBasemap.OSM,map::invalidate));showMapStatus();if(connectivity!=null&&!connectivityRegistered){connectivity.registerDefaultNetworkCallback(networkCallback);connectivityRegistered=true;}}
    @Override protected void onPause(){resumed=false;handler.removeCallbacks(freshness);stopGps();pauseTrack();if(map!=null)map.setBasemap(null);if(connectivityRegistered){connectivity.unregisterNetworkCallback(networkCallback);connectivityRegistered=false;}super.onPause();}
    @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);imports.shutdownNow();if(farm!=null)farm.close();super.onDestroy();}
    @Override protected void onSaveInstanceState(Bundle out){if(map!=null){out.putBoolean("gps",gpsWanted);out.putInt("basemap",basemapChoice);out.putBoolean("follow",map.followGps);out.putBoolean("vertices",map.vertices);out.putBoolean("boundary",map.boundary);out.putDoubleArray("viewport",map.viewport());out.putString("import_crs",importCrs);out.putBoolean("import_cadastral",importCadastral);out.putBoolean("cadastral_boundary",map.cadastralBoundary);}super.onSaveInstanceState(out);}
    private void basemaps(){new AlertDialog.Builder(this).setTitle(w("Υπόβαθρο χάρτη","Basemap")).setItems(MapProviders.labels(profile.language()),(d,index)->{if(index<2){basemapChoice=index;map.setBasemap(index==1?new AndroidBasemap(this,AndroidBasemap.OSM,map::invalidate):null);showMapStatus();}message(MapProviders.description(index,profile.language()));}).show();}
    private void showMapStatus(){if(mapStatus==null)return;String status=w("Χάρτης εκτός σύνδεσης · Τα όρια και το GPS λειτουργούν χωρίς σύνδεση στο διαδίκτυο.","Offline map · Boundaries and GPS work without internet.");if(basemapChoice==1){var caps=connectivity==null?null:connectivity.getNetworkCapabilities(connectivity.getActiveNetwork());boolean online=caps!=null&&caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED);status=(online?w("OSM σε σύνδεση · Κενά πλακίδια: αναμονή ή μη διαθέσιμα.","OSM online · Blank tiles: loading or unavailable."):w("Εκτός σύνδεσης · Μόνο διαθέσιμα πλακίδια προσωρινής μνήμης.","Offline · Only available cached tiles."))+"\n"+AndroidBasemap.OSM.attribution()+"\n"+w("Όρια και GPS λειτουργούν χωρίς σύνδεση στο διαδίκτυο.","Boundaries and GPS work without internet.");}mapStatus.setText(status);}
    private void offlinePack(){message(MapProviders.offlinePack(geometry!=null?geometry:cadastralGeometry,profile.language()));}
    private LinearLayout form(){var layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setPadding(dp(20),dp(8),dp(20),dp(8));return layout;}
    private EditText input(LinearLayout form,String hint,String value){var text=new EditText(this);text.setHint(hint);text.setText(value);form.addView(text);return text;}
    private void chooseImport(){var crs=new EditText(this);crs.setHint(w("EPSG προέλευσης (κενό: από αρχείο)","Source EPSG (blank: from file)"));crs.setText(importCrs);new AlertDialog.Builder(this).setTitle(w("GeoJSON / KML / GML","GeoJSON / KML / GML")).setView(crs).setNegativeButton(w("Ακύρωση","Cancel"),null).setPositiveButton(w("Επιλογή αρχείου","Choose file"),(d,v)->{if(!authorised())return;importCrs=crs.getText().toString().trim();startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),IMPORT);}).show();}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request!=IMPORT||result!=RESULT_OK||data==null||data.getData()==null||!authorised())return;
        var uri=data.getData();String source=importCrs;boolean reference=importCadastral;importCadastral=false;long expected=reference?cadastre.revision(field.id()):parcel==null?0:parcel.revision();
        imports.execute(()->{try{String name="geometry.json";try(var c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())name=c.getString(0);}byte[] bytes;try(var in=getContentResolver().openInputStream(uri)){bytes=GeometryImport.read(in);}var value=GeometryImport.parse(bytes,name,source);String filename=name;runOnUiThread(()->{if(!isDestroyed()&&!isFinishing()&&authorised())preview(value,filename,expected,reference);});}catch(Exception e){runOnUiThread(()->{if(!isDestroyed()&&!isFinishing())error(e);});}});
    }
    private void manual(){var form=form();var crs=input(form,"EPSG",geometry==null?"EPSG:4326":geometry.sourceCrs);var coords=input(form,w("Ανά γραμμή: X Y ή γεωγραφικό μήκος και πλάτος · δεκαδική τελεία","Each line: X Y / longitude latitude · decimal dot"),"");coords.setMinLines(5);long expected=parcel==null?0:parcel.revision();var dialog=new AlertDialog.Builder(this).setTitle(w("Χειροκίνητα όρια","Manual boundaries")).setView(form).setNegativeButton(w("Ακύρωση","Cancel"),null).setPositiveButton(w("Προεπισκόπηση","Preview"),null).create();dialog.setOnShowListener(v->dialog.getButton(-1).setOnClickListener(b->{try{if(!authorised())return;var value=ParcelGeometry.manual(coords.getText().toString(),crs.getText().toString());dialog.dismiss();preview(value,"manual",expected,false);}catch(Exception e){error(e);}}));dialog.show();}
    private void preview(ParcelGeometry value,String source,long expected,boolean reference){StringBuilder text=new StringBuilder(field.name()+"\nKAEK: "+field.kaek()+"\n"+value.sourceCrs+String.format(Locale.getDefault(),"\n%.2f m² · %.2f m\n",value.area,value.perimeter));var vertices=ParcelGeometry.vertices(value.original);text.append(vertices.size()).append(w(" κορυφές\n"," vertices\n"));for(var v:vertices.subList(0,Math.min(5,vertices.size())))text.append(String.format(Locale.ROOT,"%d/%d/%d  %.8f  %.8f\n",v.part(),v.ring(),v.index(),v.x(),v.y()));text.append(reference?w("Εισαγωγή χωριστής κτηματολογικής αναφοράς; Η επίσημη προέλευση δεν επαληθεύεται. Δεν αλλάζουν τα όρια καλλιέργειας.","Import a separate cadastral reference? Official origin is not verified. Cultivated boundaries remain unchanged."):w("Αποθήκευση αυτών των ορίων καλλιέργειας;","Save these cultivated boundaries?"));new AlertDialog.Builder(this).setTitle(w("Προεπισκόπηση ορίων","Boundary preview")).setMessage(text).setNegativeButton(w("Ακύρωση","Cancel"),null).setPositiveButton(w("Αποθήκευση","Save"),(d,v)->{if(!authorised())return;try{if(reference)cadastre.saveImported(field.id(),field.kaek(),value,source,expected);else geo.saveGeometry(field.id(),value,source,java.time.Instant.now().toString(),expected);reloadGeometry();}catch(Exception e){error(e);}}).show();}
    private String[] pointTypes(){return profile.language().equals("en")?new String[]{"Tree","Valve","Irrigation point","Tank","Borehole","Problem","Note","Other"}:new String[]{"Δέντρο","Βάνα","Σημείο άρδευσης","Δεξαμενή","Γεώτρηση","Πρόβλημα","Σημείωση","Άλλο"};}
    private void pointForm(GeoStore.Record row,Location position){
        var form=form();var type=new Spinner(this);type.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,pointTypes()));form.addView(type);if(row!=null)type.setSelection(GeoStore.POINT_TYPES.indexOf(row.payload().optString("point_type")));
        var title=input(form,w("Τίτλος","Title"),row==null?"":row.payload().optString("title"));var notes=input(form,w("Σημειώσεις","Notes"),row==null?"":row.payload().optString("notes"));
        var info=new TextView(this);info.setText(String.format(Locale.getDefault(),"%.8f, %.8f · ±%.1f m\n%s",position.getLatitude(),position.getLongitude(),position.getAccuracy(),position.getTime()>0?formatUiDate(position.getTime()):w("Χρόνος στίγματος μη διαθέσιμος","GPS fix time unavailable")));form.addView(info);
        var dialog=new AlertDialog.Builder(this).setTitle(w("Σημείο αγροτεμαχίου","Parcel point")).setView(form).setNegativeButton(w("Ακύρωση","Cancel"),null).setPositiveButton(w("Αποθήκευση","Save"),null).create();dialog.setOnShowListener(v->dialog.getButton(-1).setOnClickListener(b->{if(!authorised())return;try{if(position.getTime()>0)geo.saveGpsPoint(row==null?null:row.id(),field.id(),GeoStore.POINT_TYPES.get(type.getSelectedItemPosition()),title.getText().toString(),notes.getText().toString(),position.getLongitude(),position.getLatitude(),position.getAccuracy(),position.getTime(),row==null?0:row.revision());else geo.savePoint(row.id(),field.id(),GeoStore.POINT_TYPES.get(type.getSelectedItemPosition()),title.getText().toString(),notes.getText().toString(),position.getLongitude(),position.getLatitude(),position.getAccuracy(),row.revision());map.setPoints(geo.records(field.id(),"point"));dialog.dismiss();}catch(Exception e){error(e);}}));dialog.show();
    }
    private void points(){var points=geo.records(field.id(),"point");if(points.isEmpty()){message(w("Δεν υπάρχουν σημεία.","No saved points."));return;}new AlertDialog.Builder(this).setTitle(w("Σημεία","Points")).setItems(points.stream().map(r->r.payload().optString("title")).toArray(String[]::new),(d,index)->{var row=points.get(index);var position=new Location("saved");position.setLatitude(row.payload().optDouble("latitude"));position.setLongitude(row.payload().optDouble("longitude"));position.setAccuracy((float)row.payload().optDouble("accuracy"));position.setTime(row.payload().optLong("fix_time_ms",0));new AlertDialog.Builder(this).setTitle(row.payload().optString("title")).setItems(new String[]{w("Επεξεργασία","Edit"),w("Διαγραφή","Delete")},(a,b)->{if(b==0)pointForm(row,position);else new AlertDialog.Builder(this).setMessage(w("Διαγραφή σημείου;","Delete point?")).setNegativeButton(w("Ακύρωση","Cancel"),null).setPositiveButton(w("Διαγραφή","Delete"),(x,y)->{if(!authorised())return;try{geo.delete(row.id(),row.revision());map.setPoints(geo.records(field.id(),"point"));}catch(Exception e){error(e);}}).show();}).show();}).show();}
    private void tracks(){var rows=geo.records(field.id(),"track");if(rows.isEmpty()){message(w("Δεν υπάρχουν διαδρομές.","No saved tracks."));return;}new AlertDialog.Builder(this).setTitle(w("Διαδρομές","Tracks")).setItems(rows.stream().map(r->r.payload().optString("title")).toArray(String[]::new),(d,index)->{var row=rows.get(index);message(row.payload().optString("title")+String.format(Locale.getDefault(),"\n%.1f m · %d s · %d %s\n%s",row.payload().optDouble("distance_m"),row.payload().optLong("duration_ms")/1000,row.payload().optJSONArray("positions").length(),w("θέσεις","positions"),formatUiDate(row.payload().optLong("started_at"))));map.setTrack(row.payload());followControl.setChecked(false);map.fitTrack();}).show();}
}
