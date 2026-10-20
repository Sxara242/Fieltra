package gr.mastixa.manager;

import java.util.List;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
import gr.mastixa.manager.CountryExtensions.*;
import gr.mastixa.manager.CadastralProtocol.*;

/** Synthetic B02.1 specifications. Run only through separately approved hosted CI.
 * SPDX-License-Identifier: AGPL-3.0-only */
public class CountryExtensionsTest {
    private static final IdentifierScope GR = new IdentifierScope("GR", "kaek", "hellenic-cadastre", "");

    @Test public void greekAdapterMatchesExistingRuleAndRetainsRaw() throws Exception {
        var cases = CadastralM2MTest.fixture().getJSONArray("identifier_cases");
        for (int i = 0; i < cases.length(); i++) {
            JSONObject item = cases.getJSONObject(i);
            String raw = item.getString("raw");
            var result = new GreekIdentifierAdapter().validate(raw, GR);
            // The accepted CadastralStore import/backup rule, not ordinary-field save validation.
            assertEquals(item.getBoolean("valid"), raw.matches("[0-9]{12}"));
            assertEquals(item.getBoolean("valid"), result.state() == ValidationState.VALID);
            assertEquals(raw, result.raw());
            assertEquals(item.getBoolean("valid") ? raw : null, result.comparisonKey());
        }
    }

    @Test public void explicitCountryAndGenericFallbackHaveNoLocaleOrGpsInput() {
        var config = new FarmCountryConfiguration("legacy", new RecordVersion(1, 0, 0, null));
        var registry = new CountryRegistry();
        assertEquals("GR", config.cultivationCountry());
        var fallback = registry.get("ES");
        assertEquals("ES", fallback.descriptor().code());
        assertEquals("generic-farming", fallback.descriptor().formConfiguration());
        assertTrue(fallback.descriptor().providerIds().isEmpty());
        assertTrue(fallback.descriptor().identifierSystems().isEmpty());
        var result = fallback.validate("AB/00-1", new IdentifierScope("ES", "synthetic", "fixture", ""));
        assertEquals(ValidationState.UNSUPPORTED, result.state());
        assertNull(result.comparisonKey());
        assertEquals(ValidationState.UNSUPPORTED, registry.get("GR").validate("510201507004",
                new IdentifierScope("GR", "other", "hellenic-cadastre", "")).state());
        assertEquals(ValidationState.UNSUPPORTED, registry.get("GR").validate("510201507004",
                new IdentifierScope("GR", "kaek", "other", "")).state());
        for (String invalid : List.of("gr", "", "GRC", "12"))
            assertThrows(IllegalArgumentException.class, () -> registry.get(invalid));
        // Neither API accepts language, device locale, IP, timezone or location.
        assertEquals("GR", config.cultivationCountry());
    }

    @Test public void reviewedSourceExtensionDoesNotRequireBusinessChanges() {
        // ZZ is deliberately synthetic, not an implemented foreign country.
        var descriptor = new CountryDescriptor("ZZ", "Synthetic test only", "1", "generic-farming",
                List.of(), List.of(), List.of(), "No integration", "");
        var registry = new CountryRegistry(List.of(CountryExtensions.greeceExtension(),
                new CountryExtension(descriptor, null)));
        assertEquals(descriptor, registry.get("ZZ").descriptor());
        assertEquals("existing-gr-main-form", registry.get("GR").descriptor().formConfiguration());
        assertThrows(IllegalArgumentException.class, () -> new CountryRegistry(
                List.of(CountryExtensions.greeceExtension(), CountryExtensions.greeceExtension())));
    }
}
