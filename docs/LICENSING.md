# Licensing scope

## Integrated map provider sprint — 2026-10-17

This section describes unreleased v1.0.1-alpha.1 development. It does not alter
the accepted v1.0.0 installer or reopen completed owner acceptance.

### Protomaps / PMTiles

PMTiles v3 is an archive, not a renderer. The existing QGraphicsView raster
pipeline cannot draw MVT bytes directly. Fieltra now decodes MVT geometry and
paints a limited native Qt overview style (land/water/landuse/buildings/roads,
boundaries, settlement labels) into its existing tile items. It is not a full
MapLibre style engine: no sprites, remote glyphs, terrain, road labels or
high-detail agricultural imagery. It uses existing PySide6 plus Python stdlib.

The [PMTiles reference implementation](https://github.com/protomaps/PMTiles/tree/aec8fa1341222fdddb3318e9ffa8e18e19b312f7/python/pmtiles)
is BSD-3-Clause, compatible with inclusion in an AGPL work while retaining its
notice. The format is public domain/CC0. The third-party code and full licence
ship as source; the legal manifest includes the notice for future binaries.
The first-party decoder follows the
[MVT 2.1 specification](https://github.com/mapbox/vector-tile-spec/tree/master/2.1).

[Protomaps distributes its basemap as an ODbL Produced Work](https://docs.protomaps.com/basemaps/downloads).
The app extracts only region-intersecting tiles using HTTP ranges from the
[officially linked Source Cooperative mirror](https://source.coop/protomaps/openstreetmap),
`https://data.source.coop/protomaps/openstreetmap/v4.pmtiles`.
This is a data archive, not the public OSM raster tile service. There is no
global download or bulk request to tile.openstreetmap.org. Original source
metadata and the OSM replication timestamp survive extraction; attribution
and licence remain separate from the application's AGPL licence.

The UI explicitly confirms Chios bounds 25.75,38.00–26.65,38.65 and z0–12.
It enforces a 64 MiB output budget, 128 MiB transfer budget, 4 MiB individual
range limit, ETag snapshot, 206/Content-Range validation and 136 MiB free-space
precondition. Finalization temporarily holds tile data plus the output file
on the same volume. No fallback full-planet response is accepted.
Completed files are never overwritten; cancellation removes only this job's
random partial file. A normal successful download needs no registration.

The measured cutout is **1,461,425 bytes (1.394 MiB), 172 tiles**, with
**2,118,028 bytes transferred**. Source archive: **134,812,420,554 bytes**;
this was NOT downloaded in full. Dataset OSM replication time:
**2026-03-31T04:00:00Z**, not the sprint date. SHA-256 of the retained cutout:
`9eb97f86defc8d6ce5af2e54026390c2c7d207930aae16f7e51fb38da11ed4d1`.
Tiles cross the requested bounding box at tile edges, especially at low zoom.
Overview detail ends at z12; overzoom adds no new geographic detail.

Map data and the last selected local path persist under the profile's
`offline-maps/` directory, separately from parcel geometry/database values.
Opening an existing file references its current location; it does not silently
copy large datasets. Missing/invalid files leave local geometry available.
The installer includes no regional map data. Attribution links credit
OpenStreetMap contributors, Protomaps and Natural Earth; preserve ODbL
attribution when sharing a regional file. Runtime rendering remains awaiting
guest acceptance even though real archive acquisition/decoding have passed.

### OpenAerialMap: real coverage result, not a supported imagery claim

The [official catalog API](https://docs.openaerialmap.org/api/api/) exposes
`/meta` and `/tms`. HTTPS GETs on 2026-10-17 returned HTTP 200 JSON for:

- [Exact-point neighbourhood](https://api.openaerialmap.org/meta?bbox=26.0549,38.2237,26.0552,38.2240&limit=100),
  containing 38.2238264672,26.0550712259: `meta.found=0`, `results=[]`.
- [Wider Chios region](https://api.openaerialmap.org/meta?bbox=25.7,38.0,26.7,38.7&limit=100):
  `meta.found=0`, `results=[]`.

Both responses identified OpenAerialMap and `meta.license="CC-BY 4.0"`.
This is a catalog metadata licence, not evidence about an absent image's
licence. There is no image resolution, author, acquisition date or dataset
licence to report at this location. No imagery layer or offline storage was
enabled. The app displays a dated Chios-unavailable explanation; it does not
assert that OAM has no imagery worldwide or that coverage can never change.
There is no owner registration action that can create missing coverage.
Any future dataset must independently provide footprint coverage, usable tile
endpoint, author/date/resolution and verified dataset-specific terms before
online use or offline storage can be enabled.

### ArcGIS World Imagery: online and offline disabled

The [deployment documentation](https://location.arcgis.com/help/deployment-considerations/)
permits public native applications with API-key authentication and no ArcGIS
sign-in by each end user. One owner application credential can serve those
users; its usage is pooled against the owner's subscription, not a fresh free
allowance for each installed copy. This is conditional on the owner's accepted
agreement, privileges and data attribution. No owner's account was accessed,
registered or authorized by this sprint.

World Imagery is explicitly listed at
`ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
in the [service data documentation](https://developers.arcgis.com/rest/basemap-styles/service-data/).
The [current basemap tile price](https://developers.arcgis.com/pricing/) covers
that host: **2,000,000 tiles free per billing cycle, then USD 0.15 per 1,000**.
This is the tile model, not the separate 1,000-session allowance. The limit is
shared with other billable basemap tile requests. It is not an unlimited free
World Imagery entitlement, nor proof of the image resolution/date at Chios.

[Billing documentation](https://location.arcgis.com/help/billing/) says PAYG
is off for new accounts; without PAYG the exhausted free-tier service stops
until reset. A new account with no payment method/PAYG and no other chargeable
resources can therefore use the free tier with a service cutoff. We cannot
guarantee an existing account has zero charges: previously metered charges or
chargeable hosted storage can remain payable after PAYG is disabled. No local
desktop request counter can guarantee a shared key's global spending cap.

[API key credentials](https://developers.arcgis.com/documentation/security-and-authentication/api-key-authentication/api-key-credentials/location-platform/)
support narrow privileges, expiry and HTTP referrer restrictions. Native
clients may need to set the referrer themselves. A distributed client can
expose its key, and another client can forge that header: referrers do not
provide desktop secrecy or bind a key to one binary. Use only basemap
privileges, a dedicated application credential, monitoring and revocation.
[Authentication documentation](https://developers.arcgis.com/documentation/security-and-authentication/api-key-authentication/)
allows two keys per credential for rotation and up to one-year validity;
changing credential privileges/expiry invalidates its generated keys. An
abused shared key can exhaust the owner's allowance for all users. No key,
client secret or credential placeholder is built into source or installer.

Esri [supports open-source clients](https://location.arcgis.com/help/licensing-and-attribution/),
but that does not relicense Esri data/SDKs under AGPL. Required Esri branding
and current data-provider attribution must be displayed. Living Atlas content
has a separate custom-agreement condition; it must not be substituted for the
documented basemap service's entitlement.
The current [E204CW agreement, Attachment B.1(k)](https://assets.esri.com/content/dam/esrisites/en-us/media/legal/ma-translations/english.pdf)
bars combinations that impose copyleft requirements on Esri offerings. Direct
REST access can potentially keep service/data rights separate; that is an
architectural inference, not verified permission for this AGPL distribution.
No SDK exception, applicable signed agreement or owner acceptance of Esri terms
was supplied. Consequently Fieltra does not expose an active ArcGIS layer or
credential entry control in this sprint. This is not a claim that every AGPL
client using an Esri REST service is prohibited.

The [current Qt SDK](https://developers.arcgis.com/qt/) is 300.1.
[Setup instructions](https://developers.arcgis.com/qt/install-and-set-up/)
describe a native C++ toolchain and extra Qt modules, not a drop-in PySide6
package. The current renderer is QGraphicsView; introducing an Esri view would
require a separate native/QML bridge, ABI and compiler review, redistribution
terms and deployment licensing. A Python sample wrapper is not an official
supported binding or an AGPL exception. No proprietary SDK, WebEngine or extra
native dependency was added.

The [Qt licence capabilities](https://developers.arcgis.com/qt/license-and-deployment/license-levels-and-capabilities/)
include a free Lite runtime licence string and creating raster/vector tile
packages from offline-enabled services. That is an SDK capability, not a grant
to export every image service. The separate
[World Imagery for Export item](https://www.arcgis.com/sharing/rest/content/items/226d23f076da478bba4589e7eae95952?f=json)
requires subscription/developer authorization, permits at most **150,000 tiles
per request**, is for ArcGIS/Runtime offline apps and is not a live tile source.
Its listed no-credit-consumption condition does not establish a free current
Location Platform entitlement or AGPL SDK compatibility. Platform offline
deployment also refers customers to sales. A guarantee of authorized zero-cost
offline World Imagery for Fieltra was NOT established. Offline remains disabled;
there is no scraping, tile cache, downloader or SDK export workaround.

**OWNER ACTION for ArcGIS:** obtain/accept the applicable Esri agreement and
written confirmation or qualified review covering this AGPL desktop's direct
REST distribution (and separately any proprietary SDK/offline export). If
online use is approved, register a dedicated Location Platform public app,
keep PAYG off with no payment method for the free-only model, grant only basemap
access, arrange key delivery/rotation/revocation and confirm the account has no
existing charges/storage. Provide credentials outside public source. Before
offline work, independently confirm the export service entitlement, runtime
licence, per-request limit, costs and AGPL-compatible distribution rights.
No message to Esri, account creation or billing authorization was performed.

---

Owner-controlled first-party code, tests, build scripts and documentation in
Fieltra are licensed under **AGPL-3.0-only**, including the Windows
and Android implementations. Fieltra is free, open-source software. Existing third-party copyright/license notices and
separately licensed material are exceptions to this first-party scope.

The full, unmodified GNU AGPL version 3 text is in [LICENSE](../LICENSE).
The project chooses version 3 only. The license's generic application appendix
is not a project grant of an “or later” option. AGPL permits commercial use
under its terms; this repository imposes no additional noncommercial condition.
Older private commits and previously distributed snapshots retain their own
licensing context. This release does not rewrite archival history.

The owner confirmed the existing first-party rights baseline on 2026-10-09;
see [CONTRIBUTION_RIGHTS.md](CONTRIBUTION_RIGHTS.md). Separate commercial terms
may be offered only within rights actually held. They do not override Qt/LGPL,
EPSG/IOGP, PROJ, GEOS, OCR models or any other third-party obligations.

Preserve all inherited texts in [licenses/](../licenses/), their hash index,
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md), Android notices, source
identities and build/replacement information. First-party assets retain the
owner's recorded project-created/AI-assisted provenance; dependency-provided
fonts and resources retain their original terms. No wholesale relicense of
the `licenses/` tree, datasets, dependency sources or upstream artwork is made.

Windows obligations include dynamic library replacement, corresponding source
access when required, PDFium/Qt native subcomponent notices, EPSG/PROJ/other
CRS attribution and the independently installed Microsoft runtime prerequisite.
Android binaries remain development outputs pending their own complete notice,
native dependency/source and EPSG-derived resource audit.

Reference texts: [FSF AGPL](https://www.gnu.org/licenses/agpl-3.0.html),
[FSF on separate exceptions](https://www.gnu.org/philosophy/selling-exceptions.html).
