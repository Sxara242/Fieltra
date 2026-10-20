package gr.mastixa.manager;

import java.util.List;
import java.util.UUID;
import gr.mastixa.manager.CountryExtensions.IdentifierScope;

/** Isolated cadastral DTOs/interfaces; no SQL, GIS wire format or I/O.
 * SPDX-License-Identifier: AGPL-3.0-only */
public final class CadastralProtocol {
    private CadastralProtocol() {}

    static String canonicalUuid(String value) {
        if (value == null || !UUID.fromString(value).toString().equals(value))
            throw new IllegalArgumentException("Canonical UUID required");
        return value;
    }
    static String farmScope(String value) {
        // Existing Windows default/hex IDs and Android legacy IDs are opaque.
        if (value == null || value.isBlank())
            throw new IllegalArgumentException("Explicit farm/profile store scope required");
        return value;
    }

    public record RecordVersion(long revision, long createdAt, long updatedAt, Long deletedAt) {
        public RecordVersion {
            if (revision < 1 || createdAt < 0 || updatedAt < createdAt
                    || deletedAt != null && (deletedAt < createdAt || deletedAt > updatedAt))
                throw new IllegalArgumentException("Invalid revision or UTC millisecond timestamps");
        }
    }

    /** Constructing this DTO does not persist a setting. */
    public record FarmCountryConfiguration(String farmScope, RecordVersion version, String cultivationCountry) {
        public FarmCountryConfiguration {
            CadastralProtocol.farmScope(farmScope);
            CountryExtensions.countryCode(cultivationCountry);
            if (version == null || version.deletedAt() != null)
                throw new IllegalArgumentException("Active configuration version required");
        }
        public FarmCountryConfiguration(String farmScope, RecordVersion version) {
            this(farmScope, version, CountryExtensions.DEFAULT_CULTIVATION_COUNTRY);
        }
    }

    public record CultivatedFieldRef(String farmScope, String fieldUuid) {
        public CultivatedFieldRef {
            CadastralProtocol.farmScope(farmScope);
            canonicalUuid(fieldUuid);
        }
    }

    /** Preserved namespace/dataset alias; no allocation or remapping. */
    public record FieldIdentityAlias(CultivatedFieldRef field, String namespace, String dataset, String aliasUuid) {
        public FieldIdentityAlias {
            if (field == null || namespace == null || namespace.isEmpty() || dataset == null || dataset.isEmpty())
                throw new IllegalArgumentException("Explicit field alias scope required");
            canonicalUuid(aliasUuid);
        }
    }

    public record ScopedParcelIdentity(IdentifierScope scope, String comparisonKey) {
        public ScopedParcelIdentity {
            if (scope == null || comparisonKey == null || comparisonKey.isEmpty())
                throw new IllegalArgumentException("Verified scoped comparison key required");
        }
    }

    public record CadastralParcel(String farmScope, String parcelUuid, ScopedParcelIdentity identity,
                                  String identifierRaw, String validatorVersion, RecordVersion version) {
        public CadastralParcel {
            CadastralProtocol.farmScope(farmScope);
            canonicalUuid(parcelUuid);
            if (identity == null || identifierRaw == null || validatorVersion == null
                    || validatorVersion.isEmpty() || version == null)
                throw new IllegalArgumentException("Versioned scoped parcel and exact raw string required");
        }
    }

    public record AssociationKey(String farmScope, String fieldUuid, String parcelUuid) {
        public AssociationKey {
            CadastralProtocol.farmScope(farmScope);
            canonicalUuid(fieldUuid);
            canonicalUuid(parcelUuid);
        }
    }

    public record FieldCadastralLink(CultivatedFieldRef field, String parcelUuid, RecordVersion version,
                                     boolean legacySlot, boolean manualLink) {
        public FieldCadastralLink {
            if (field == null || version == null)
                throw new IllegalArgumentException("Field and link version required");
            canonicalUuid(parcelUuid);
            if (version.deletedAt() == null && !legacySlot && !manualLink)
                throw new IllegalArgumentException("Active link requires an origin");
        }
        public AssociationKey associationKey() {
            return new AssociationKey(field.farmScope(), field.fieldUuid(), parcelUuid);
        }
    }

    /** Unclassified forever unless a later explicit provenance decision is made. */
    public record LegacyCadastralValue(CultivatedFieldRef field, String raw) {
        public LegacyCadastralValue {
            if (field == null || raw == null) throw new IllegalArgumentException("Legacy raw string required");
        }
    }

    /** Later storage implementations must enforce same-farm existing field/parcel
     * references; full scoped-identity dedup; UUID aliases/raw spelling retention;
     * unique association pairs; inverse M:N; one active legacy slot per field;
     * transactional revision CAS (0=absent), idempotence and safe conflict refusal.
     * Unlink tombstones only the association, preserves shared sources, and cannot
     * silently clear the main-form legacy value. No operation creates fields,
     * business history, totals/area, provider calls or fields.kaek writes.
     * These are requirements, not a storage implementation or schema-1 handler. */
    public interface ParcelRepository {
        CadastralParcel ensureParcel(CadastralParcel candidate);
        FieldCadastralLink link(FieldCadastralLink association, long expectedRevision);
        FieldCadastralLink unlink(CultivatedFieldRef field, String parcelUuid, long expectedRevision);
        List<FieldCadastralLink> listLinks(CultivatedFieldRef field, boolean includeDeleted);
    }
}
