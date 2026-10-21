package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class PlantingHistoryTest {
    private final android.content.Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();

    private JSONObject fixture() throws Exception {
        try (var input = InstrumentationRegistry.getInstrumentation().getContext()
            .getAssets().open("phase14_planting_history.json")) {
            return new JSONObject(new String(input.readAllBytes(), StandardCharsets.UTF_8));
        }
    }

    @Test public void sharedFixtureCountsPositionsReplantingsAndHistoricalLosses() throws Exception {
        String name = "planting-history-test.db";
        context.deleteDatabase(name);
        try (FarmStore store = new FarmStore(context, name)) {
            store.saveField(null, "History field", 2, "", "", 500, "");
            String field = store.fields().get(0).id();
            WorkStore work = new WorkStore(store);
            JSONObject root = fixture();
            JSONObject batch = root.getJSONObject("planting_batch");
            String batchId = work.savePlanting(new WorkStore.Planting(
                null,
                batch.getString("planting_date"),
                field,
                batch.getInt("initial_positions"),
                batch.getInt("current_alive"),
                "Δενδρύλλια", "", "Mastic", "2 x 6 m", 0, "", ""
            ));
            PlantingHistory history = new PlantingHistory(store);
            var events = root.getJSONArray("replantings");
            for (int i = 0; i < events.length(); i++) {
                JSONObject row = events.getJSONObject(i);
                history.add(
                    row.getString("id"),
                    batchId,
                    row.getString("replanting_date"),
                    row.getInt("tree_count"),
                    row.getString("notes")
                );
            }
            JSONObject expected = root.getJSONObject("expected");
            var totals = history.totals(batchId);
            assertEquals(expected.getLong("positions"), totals.positions());
            assertEquals(expected.getLong("replantings"), totals.replantings());
            assertEquals(expected.getLong("historical_plantings"), totals.historicalPlantings());
            assertEquals(expected.getLong("living"), totals.living());
            assertEquals(expected.getLong("historical_losses"), totals.historicalLosses());
            assertEquals(expected.getLong("vacant_positions"), totals.vacantPositions());
            assertEquals(2, history.events(batchId).size());
            assertEquals("replacement-01", history.events(batchId).get(0).id());
            assertEquals(500, work.plantings().get(0).trees_planted());
            assertEquals(500, work.plantings().get(0).trees_alive());
        } finally {
            context.deleteDatabase(name);
        }
    }

    @Test public void appendOnlyValidationAndLogicalBackupRoundTrip() throws Exception {
        String name = "planting-history-backup.db";
        context.deleteDatabase(name);
        File recovery = new File(context.getCacheDir(), "planting-history-recovery.json");
        try (FarmStore store = new FarmStore(context, name)) {
            store.saveField(null, "History field", 2, "", "", 20, "");
            String field = store.fields().get(0).id();
            WorkStore work = new WorkStore(store);
            String batch = work.savePlanting(new WorkStore.Planting(
                null, "2026-03-01", field, 20, 20, "Δενδρύλλια", "", "", "", 0, "", ""
            ));
            PlantingHistory history = new PlantingHistory(store);
            history.add("event-1", batch, "2026-03-10", 2, "replacement");
            try {
                history.add("event-1", batch, "2026-03-11", 1, "duplicate");
                fail("Duplicate immutable event id must fail");
            } catch (IllegalArgumentException expected) {
                assertTrue(expected.getMessage().contains("υπάρχει"));
            }
            try {
                history.add("early", batch, "2026-02-28", 1, "too early");
                fail("Replanting before original planting must fail");
            } catch (IllegalArgumentException expected) {
                assertTrue(expected.getMessage().contains("προηγείται"));
            }
            byte[] backup = LocalBackup.snapshot(store);
            assertEquals(19, new JSONObject(new String(backup, StandardCharsets.UTF_8)).getInt("schema"));
            history.add("event-2", batch, "2026-03-20", 3, "newer");
            assertEquals(5, history.totals(batch).replantings());
            LocalBackup.restore(store, backup, recovery);
            assertEquals(1, history.events(batch).size());
            assertEquals(2, history.totals(batch).replantings());
        } finally {
            context.deleteDatabase(name);
            recovery.delete();
        }
    }
}
