package gr.mastixa.manager;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Pure B02.1 contracts. No Settings, provider calls, Android context or I/O.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CountryExtensions {
    private CountryExtensions() {}
    public static final String DEFAULT_CULTIVATION_COUNTRY = "GR";
    public static final String GREEK_SYSTEM = "kaek";
    public static final String GREEK_AUTHORITY = "hellenic-cadastre";

    /** Syntax only; future Settings must offer reviewed ISO country data.
     * Unknown alpha-2 shaped codes get an unavailable generic fallback. */
    public static String countryCode(String value) {
        if (value == null || !value.matches("[A-Z]{2}"))
            throw new IllegalArgumentException("Explicit uppercase alpha-2 country code required");
        return value;
    }

    public enum ValidationState { VALID, INVALID, UNSUPPORTED }

    public record IdentifierScope(String countryCode, String systemId, String authorityId,
                                  String jurisdictionKey) {
        public IdentifierScope {
            CountryExtensions.countryCode(countryCode);
            if (systemId == null || systemId.isBlank() || authorityId == null || authorityId.isBlank()
                    || jurisdictionKey == null)
                throw new IllegalArgumentException("Explicit system, authority and jurisdiction required");
        }
    }

    public record IdentifierValidation(IdentifierScope scope, String raw, ValidationState state,
                                       String comparisonKey, String validatorVersion) {
        public IdentifierValidation {
            if (scope == null || raw == null || state == null || validatorVersion == null
                    || validatorVersion.isEmpty())
                throw new IllegalArgumentException("Versioned scoped raw identifier required");
            if (state == ValidationState.VALID ? comparisonKey == null || comparisonKey.isEmpty()
                    : comparisonKey != null)
                throw new IllegalArgumentException("Comparison key requires valid identity");
        }
    }

    public interface IdentifierAdapter {
        IdentifierValidation validate(String raw, IdentifierScope scope);
    }

    /** Preserves the exact existing CadastralStore [0-9]{12} rule.
     * No trimming, legacy classification, coverage promise or form integration. */
    public static final class GreekIdentifierAdapter implements IdentifierAdapter {
        @Override public IdentifierValidation validate(String raw, IdentifierScope scope) {
            if (raw == null || scope == null)
                throw new IllegalArgumentException("Scoped raw identifier required");
            if (!scope.countryCode().equals("GR") || !scope.systemId().equals(GREEK_SYSTEM)
                    || !scope.authorityId().equals(GREEK_AUTHORITY))
                return new IdentifierValidation(scope, raw, ValidationState.UNSUPPORTED, null,
                        "gr-kaek-ascii12-v1");
            boolean valid = raw.matches("[0-9]{12}");
            return new IdentifierValidation(scope, raw, valid ? ValidationState.VALID : ValidationState.INVALID,
                    valid ? raw : null, "gr-kaek-ascii12-v1");
        }
    }

    public record CountryDescriptor(String code, String label, String version, String formConfiguration,
                                    List<String> identifierSystems, List<String> providerIds,
                                    List<String> supportedCrs, String coverage, String attributionReference) {
        public CountryDescriptor {
            countryCode(code);
            if (label == null || label.isEmpty() || version == null || version.isEmpty()
                    || formConfiguration == null || formConfiguration.isEmpty()
                    || coverage == null || attributionReference == null)
                throw new IllegalArgumentException("Versioned country descriptor required");
            identifierSystems = List.copyOf(identifierSystems);
            providerIds = List.copyOf(providerIds);
            supportedCrs = List.copyOf(supportedCrs);
            for (List<String> items : List.of(identifierSystems, providerIds, supportedCrs))
                for (String item : items) if (item.isEmpty())
                    throw new IllegalArgumentException("Descriptor capabilities must be strings");
        }
    }

    public record CountryExtension(CountryDescriptor descriptor, IdentifierAdapter identifierAdapter) {
        public CountryExtension {
            if (descriptor == null) throw new IllegalArgumentException("Country descriptor required");
        }
        public IdentifierValidation validate(String raw, IdentifierScope scope) {
            if (raw == null || scope == null)
                throw new IllegalArgumentException("Scoped raw identifier required");
            if (identifierAdapter == null || !scope.countryCode().equals(descriptor.code()))
                return new IdentifierValidation(scope, raw, ValidationState.UNSUPPORTED, null, "unsupported-v1");
            return identifierAdapter.validate(raw, scope);
        }
    }

    public static CountryExtension greeceExtension() {
        return new CountryExtension(new CountryDescriptor("GR", "Greece", "1", "existing-gr-main-form",
                List.of(GREEK_SYSTEM), List.of("hellenic-cadastre-north-aegean"),
                List.of("EPSG:2100", "EPSG:4326"),
                "North Aegean regional dataset only; retrieval is not connected",
                "app/gis/kaek_provider.py: NorthAegeanProvider attribution/terms"), new GreekIdentifierAdapter());
    }

    /** Source-reviewed extensions; no executable plugin loading or I/O. */
    public static final class CountryRegistry {
        private final Map<String, CountryExtension> extensions;
        public CountryRegistry() { this(List.of(greeceExtension())); }
        public CountryRegistry(List<CountryExtension> supplied) {
            Map<String, CountryExtension> result = new LinkedHashMap<>();
            for (CountryExtension extension : supplied) {
                if (result.putIfAbsent(extension.descriptor().code(), extension) != null)
                    throw new IllegalArgumentException("Duplicate country extension");
            }
            extensions = Collections.unmodifiableMap(result);
        }
        public CountryExtension get(String code) {
            countryCode(code);
            CountryExtension found = extensions.get(code);
            return found != null ? found : new CountryExtension(new CountryDescriptor(code, "Generic farming",
                    "1", "generic-farming", List.of(), List.of(), List.of(),
                    "No country-specific cadastral integration", ""), null);
        }
    }
}
