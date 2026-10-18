"""Capabilities must be verified before a provider is enabled."""
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode
from uuid import UUID
from typing import Protocol

CADASTRE_LAYER = "https://gis.ktimanet.gr/inspire/rest/services/cadastralparcels/CadastralParcel/MapServer/0"


class ParcelProvider(Protocol):
    def fetch(self, request: dict) -> dict: ...


class UnverifiedCadastreProvider:
    def fetch(self, kaek: str):
        if not kaek.strip():
            raise ValueError("Συμπλήρωσε ΚΑΕΚ / KAEK required")
        raise ConnectionError(
            "Το δημοσιευμένο ArcGIS layer επέστρεψε HTTP 404 στον τελευταίο έλεγχο. "
            "Δεν επαληθεύτηκαν schema/CRS/query. Χρησιμοποίησε εξουσιοδοτημένο αρχείο ορίων.\n"
            "Published ArcGIS layer returned HTTP 404; live schema/CRS/query remain unverified. "
            "Import an authorized boundary file.\n" + CADASTRE_LAYER)


@dataclass(frozen=True)
class BasemapProvider:
    identity: str
    title: str
    attribution: str = ""
    tile_template: str = ""
    offline_allowed: bool = False
    unavailable_reason: str = ""
    tile_size: int = 256
    max_zoom: int = 19
    persistent_cache: bool = True
    description: str = ""
    wms_instance: str = field(default="", repr=False)
    wms_layer: str = ""
    time_range: str = ""
    local_path: str = ""

    def tile_url(self, z, x, y):
        if not self.wms_instance:
            return self.tile_template.format(z=z, x=x, y=y)
        # XYZ north-down tile grid -> conventional EPSG:3857 west/south/east/north.
        world = 20037508.342789244
        span = 2 * world / 2**z
        bbox = (-world+x*span, world-(y+1)*span, -world+(x+1)*span, world-y*span)
        return 'https://sh.dataspace.copernicus.eu/ogc/wms/' + self.wms_instance + '?' + urlencode({
            'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetMap',
            'CRS': 'EPSG:3857', 'BBOX': ','.join(f'{v:.8f}' for v in bbox),
            'WIDTH': self.tile_size, 'HEIGHT': self.tile_size, 'FORMAT': 'image/png',
            'LAYERS': self.wms_layer, 'TIME': self.time_range, 'MAXCC': 30,
        })


def cdse_provider(instance, layer, start, end):
    """Session-local CDSE configuration. No account creation, tokens or persisted secrets."""
    try:
        identity = str(UUID(instance.strip()))
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last or first.year < 2015 or last > date.today():
            raise ValueError()
        if not layer.strip() or len(layer) > 120 or any(ord(c) < 32 for c in layer):
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('CDSE: valid instance UUID, layer ID and past ISO date range required') from None
    return BasemapProvider('sentinel', 'Copernicus CDSE · experimental',
        f'Contains modified Copernicus Sentinel data ({first.year}–{last.year}), processed by Sentinel Hub / CDSE',
        tile_template='https://sh.dataspace.copernicus.eu/ogc/wms/',
        tile_size=512, max_zoom=13, persistent_cache=False,
        description=f'Sentinel-2 RGB: native 10 m · requested {start}/{end}; mosaic, exact acquisition dates not returned. Zooming enlarges pixels.',
        wms_instance=identity, wms_layer=layer.strip(), time_range=f'{start}/{end}')


BASEMAPS = (
    BasemapProvider("neutral", "Χωρίς υπόβαθρο / No basemap"),
    BasemapProvider("osm", "OpenStreetMap · Online", "© OpenStreetMap contributors",
                    "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
    BasemapProvider("sentinel", "Copernicus / Sentinel", unavailable_reason="Δεν έχει ρυθμιστεί υπηρεσία εικόνων / Imagery service not configured"),
    BasemapProvider('pmtiles','Protomaps · Offline',offline_allowed=True,
        unavailable_reason='Άνοιξε ή κατέβασε τοπικό αρχείο PMTiles / Open or download a local PMTiles map'),
    BasemapProvider('oam','OpenAerialMap',unavailable_reason=
        'OpenAerialMap: 0 εικόνες στη Χίο στον έλεγχο 2026-10-17 (38.2238264672, 26.0550712259). / No Chios coverage found on 2026-10-17.',
        persistent_cache=False),
    BasemapProvider('arcgis','ArcGIS World Imagery',unavailable_reason=
        'ArcGIS: εκκρεμεί έγκριση όρων AGPL/διανομής και λογαριασμός ιδιοκτήτη. Online και offline ανενεργά. / Distribution terms and owner account pending; online/offline disabled.',
        persistent_cache=False),
)


def restored_basemap(value):
    """Resolve saved identities/legacy slots; removed or unknown values are local-only.

    The map currently keeps selection in memory, not in a field/database setting.
    Explicit legacy resolution avoids reinterpreting old slot2 as the new CDSE slot.
    """
    if type(value) is int:
        value = {0: 'neutral', 1: 'osm', 3: 'sentinel'}.get(value)
    return next((provider for provider in BASEMAPS if provider.identity == value), BASEMAPS[0])


@dataclass(frozen=True)
class OfflinePackState:
    parcel_id: str
    bbox: tuple
    status: str = "blocked"
    bytes_stored: int = 0
    progress: float = 0
    updated_at: int | None = None
    reason: str = "Δεν έχει ρυθμιστεί πάροχος με άδεια offline λήψης / No licensed offline provider configured"


def offline_pack(parcel_id, bbox):
    west,south,east,north=bbox
    margin=max(east-west,north-south)*.1 + .0005
    return OfflinePackState(parcel_id,(max(-180,west-margin),max(-85,south-margin),
                                       min(180,east+margin),min(85,north+margin)))
