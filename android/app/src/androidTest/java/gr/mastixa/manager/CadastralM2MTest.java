package gr.mastixa.manager;

import androidx.test.platform.app.InstrumentationRegistry;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
import gr.mastixa.manager.CountryExtensions.IdentifierScope;
import gr.mastixa.manager.CadastralProtocol.*;

/** DTO/cardinality tests only, not database, migration or business-integration proof.
 * SPDX-License-Identifier: AGPL-3.0-only */
public class CadastralM2MTest {
    private static final RecordVersion VERSION = new RecordVersion(1, 0, 0, null);

    static JSONObject fixture() throws Exception {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        assertTrue(instrumentation.getTargetContext().getPackageName().endsWith(".checks"));
        try (var input = instrumentation.getContext().getAssets().open("cadastral_b021.json")) {
            var output = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            return new JSONObject(new String(output.toByteArray(), StandardCharsets.UTF_8));
        }
    }

    @Test public void oneFieldFiveParcelsAndInverseSharedParcel() throws Exception {
        var data = fixture();
        String before = data.toString();
        var field = new CultivatedFieldRef(data.getString("farm_scope"), data.getJSONArray("field_uuids").getString(0));
        var parcels = new ArrayList<CadastralParcel>();
        var links = new ArrayList<FieldCadastralLink>();
        var rows = data.getJSONArray("parcels");
        for (int i = 0; i < rows.length(); i++) {
            var p = rows.getJSONObject(i);
            var identity = new ScopedParcelIdentity(new IdentifierScope("GR", "kaek", "hellenic-cadastre", ""),
                    p.getString("raw"));
            var parcel = new CadastralParcel(field.farmScope(), p.getString("uuid"), identity,
                    p.getString("raw"), "gr-kaek-ascii12-v1", VERSION);
            parcels.add(parcel);
            links.add(new FieldCadastralLink(field, parcel.parcelUuid(), VERSION, i == 0, i != 0));
        }
        var keys = new HashSet<AssociationKey>();
        for (var link : links) {
            keys.add(link.associationKey());
            assertEquals(field, link.field());
            assertNotEquals(field.fieldUuid(), link.parcelUuid());
        }
        assertEquals(5, keys.size());
        var second = new CultivatedFieldRef(field.farmScope(), data.getJSONArray("field_uuids").getString(1));
        var inverse = new FieldCadastralLink(second, parcels.get(0).parcelUuid(), VERSION, false, true);
        assertNotEquals(links.get(0).associationKey(), inverse.associationKey());
        assertEquals(links.get(0).parcelUuid(), inverse.parcelUuid());
        assertEquals(links.get(0).associationKey(),
                new FieldCadastralLink(field, parcels.get(0).parcelUuid(), VERSION, true, false).associationKey());
        assertEquals(before, data.toString());
        assertEquals(3.25, data.getJSONObject("business").getDouble("cultivated_area_stremma"), 0);
        assertEquals(1, data.getJSONObject("business").getInt("crop_link_count"));
        // Stored totals, source immutability and union rendering remain later A–N gates.
    }

    @Test public void eachScopeDimensionAndFarmDistinguishesIdentity() throws Exception {
        var identities = new HashSet<ScopedParcelIdentity>();
        for (var scope : List.of(
                new IdentifierScope("GR", "synthetic", "fixture", "A"),
                new IdentifierScope("ES", "synthetic", "fixture", "A"),
                new IdentifierScope("GR", "other", "fixture", "A"),
                new IdentifierScope("GR", "synthetic", "other", "A"),
                new IdentifierScope("GR", "synthetic", "fixture", "B")))
            identities.add(new ScopedParcelIdentity(scope, "AB/00-1"));
        assertEquals(5, identities.size());
        var data = fixture();
        String field = data.getJSONArray("field_uuids").getString(0);
        String parcel = data.getJSONArray("parcels").getJSONObject(0).getString("uuid");
        assertNotEquals(new AssociationKey(data.getString("farm_scope"), field, parcel),
                new AssociationKey(data.getString("other_farm_scope"), field, parcel));
    }

    @Test public void legacyValuesAliasesAndTombstonesRemainIndependent() throws Exception {
        var data = fixture();
        var field = new CultivatedFieldRef(data.getString("farm_scope"), data.getJSONArray("field_uuids").getString(0));
        var values = data.getJSONArray("legacy_values");
        for (int i = 0; i < values.length(); i++)
            assertEquals(values.getString(i), new LegacyCadastralValue(field, values.getString(i)).raw());
        String parcel = data.getJSONArray("parcels").getJSONObject(0).getString("uuid");
        var kaek = new FieldIdentityAlias(field, "legacy-kaek", "fixture-dataset", parcel);
        var gis = new FieldIdentityAlias(field, "legacy-gis", "fixture-dataset", parcel);
        assertNotEquals(kaek, gis);
        assertEquals(field.fieldUuid(), kaek.field().fieldUuid());
        assertThrows(IllegalArgumentException.class, () -> new FieldCadastralLink(field, parcel, VERSION, false, false));
        var tombstone = new FieldCadastralLink(field, parcel, new RecordVersion(2, 0, 2, 2L), false, false);
        assertEquals(Long.valueOf(2), tombstone.version().deletedAt());
        assertThrows(IllegalArgumentException.class, () -> new RecordVersion(0, 0, 0, null));
        assertThrows(IllegalArgumentException.class, () -> new RecordVersion(1, 2, 1, null));
        assertThrows(IllegalArgumentException.class, () -> new RecordVersion(1, 0, 1, 2L));
        assertThrows(IllegalArgumentException.class, () -> new CultivatedFieldRef(field.farmScope(), "not-a-uuid"));
    }
}
