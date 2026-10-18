# Licensing scope

## Integrated map provider sprint — 2026-10-17

This section describes unreleased v1.0.1-alpha.1 development. It does not alter
the accepted v1.0.0 installer or reopen completed owner acceptance.

Protomaps/PMTiles and OpenAerialMap were removed by owner decision. Their
code, vendored component and provider-specific notices are no longer shipped.
User-owned map files are left untouched. Retained component notices follow.

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
