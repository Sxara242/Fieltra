package gr.mastixa.manager;

import android.location.Location;

/** A current GNSS fix is distinct from an old displayed position. No network. */
final class GpsFix {
    static boolean usable(Location fix,long elapsedNanos){
        if(fix==null||fix.getTime()<=0||!fix.hasAccuracy()||!Float.isFinite(fix.getAccuracy())||fix.getAccuracy()<0)return false;
        try{ParcelGeometry.position(fix.getLongitude(),fix.getLatitude());}catch(IllegalArgumentException e){return false;}
        long age=elapsedNanos-fix.getElapsedRealtimeNanos();
        return fix.getElapsedRealtimeNanos()>0&&age>=0&&age<=30_000_000_000L;
    }
}
