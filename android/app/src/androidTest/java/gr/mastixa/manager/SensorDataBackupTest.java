package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import static org.junit.Assert.*;

public class SensorDataBackupTest {
    private static byte[] envelope(JSONObject source, JSONObject payload) throws Exception {
        String data = payload.toString();
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(data.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder();
        for (byte b : digest) hex.append(String.format("%02x", b & 255));
        return source.put("schema",19).put("payload",data).put("sha256",hex.toString())
            .toString().getBytes(StandardCharsets.UTF_8);
    }

    @Test public void signedObservationRoundTripAndBrokenRelationsAreRejectedAtomically() throws Exception {
        var context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        String name = "sensor-backup-test.db";
        context.deleteDatabase(name);
        File recovery = new File(context.getCacheDir(), "sensor-backup-recovery.json");
        try (FarmStore store = new FarmStore(context, name)) {
            store.saveField(null,"Sensor field",1,"","",0,"");
            String field = store.fields().get(0).id();
            SensorDataStore sensors = new SensorDataStore(store);
            sensors.saveDevice(new SensorData.Device(
                "station","Station","manual",field,"","active",""
            ));
            sensors.saveChannel(new SensorData.Channel(
                "temperature","station","air_temperature","celsius","Air"
            ));
            sensors.appendObservation(new SensorData.Observation(
                "cold","temperature","2026-01-01T06:00:00Z",-7.25,"good","packet-cold"
            ));

            byte[] before = LocalBackup.snapshot(store);
            JSONObject current = new JSONObject(new String(before, StandardCharsets.UTF_8));
            assertEquals(19,current.getInt("schema"));
            assertEquals(1,LocalBackup.inspect(store,before));

            sensors.appendObservation(new SensorData.Observation(
                "later","temperature","2026-01-01T07:00:00Z",-6.0,"good","packet-later"
            ));
            LocalBackup.restore(store,before,recovery);
            assertEquals(1,sensors.observations("temperature").size());
            assertEquals(-7.25,sensors.snapshot("station").channels().get(0).latestValue(),0.000001);

            JSONObject brokenEnvelope = new JSONObject(new String(before, StandardCharsets.UTF_8));
            JSONObject brokenPayload = new JSONObject(brokenEnvelope.getString("payload"));
            brokenPayload.getJSONArray("sensor_channels").getJSONObject(0).put("device_id","missing-device");
            byte[] broken = envelope(brokenEnvelope,brokenPayload);
            byte[] stable = LocalBackup.snapshot(store);
            try {
                LocalBackup.restore(store,broken,recovery);
                fail("Broken sensor relationship must be rejected before restore");
            } catch (java.io.IOException expected) {
                assertTrue(expected.getMessage().contains("sensor") || expected.getMessage().contains("Sensor"));
            }
            assertArrayEquals(stable,LocalBackup.snapshot(store));
        } finally {
            context.deleteDatabase(name);
            recovery.delete();
        }
    }
}
