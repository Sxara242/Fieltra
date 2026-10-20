"""Independent optional WMS protocol. No imagery provider is activated.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import dataclass
import math
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .provider_io import safe_xml, public_url, get


@dataclass(frozen=True)
class WmsDescriptor:
    endpoint: str = 'http://gis.ktimanet.gr/wms/wmsopen/wmsserver.aspx'
    attribution: str = 'Ελληνικό Κτηματολόγιο — ορθοφωτογραφίες WMS'
    terms_url: str = 'https://gis.ktimanet.gr/wms/ktbasemap/default.aspx'
    # Terms URL is a source/viewer reference; no offline license is inferred.
    allow_http: bool = True
    cache_max_bytes: int = 0  # No disk caching without reviewed provider policy.

    def __post_init__(self):
        public_url(self.endpoint, allow_http=self.allow_http)
        if not self.attribution or self.cache_max_bytes < 0:
            raise ValueError('Explicit attribution/cache policy required')


@dataclass(frozen=True)
class Layer:
    name: str
    title: str
    crs: tuple[str, ...]
    styles: tuple[str, ...]


@dataclass(frozen=True)
class Capabilities:
    version: str
    layers: tuple[Layer, ...]
    formats: tuple[str, ...]
    source_url: str
    attribution: str
    fees: str
    access_constraints: str


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _children(node, name):
    return [c for c in node if _local(c.tag) == name]


def _text(node, name):
    return next(((c.text or '').strip() for c in node if _local(c.tag) == name), '')


def _request(endpoint, parameters):
    parts = urlsplit(endpoint)
    keys = {'SERVICE','REQUEST','VERSION','LAYERS','STYLES','CRS','SRS','BBOX','WIDTH','HEIGHT','FORMAT','TRANSPARENT','BGCOLOR','EXCEPTIONS'}
    existing = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.upper() not in keys]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(existing+list(parameters.items())), ''))


def capabilities_request(descriptor, version='1.3.0'):
    if version not in ('1.3.0', '1.1.1'):
        raise ValueError('Unsupported WMS version')
    return _request(descriptor.endpoint, dict(SERVICE='WMS', REQUEST='GetCapabilities', VERSION=version))


def parse_capabilities(data, descriptor):
    root = safe_xml(data)
    version = root.attrib.get('version')
    if _local(root.tag) not in ('WMS_Capabilities', 'WMT_MS_Capabilities') or version not in ('1.3.0', '1.1.1'):
        raise ValueError('Unsupported WMS capabilities or service exception')
    formats = []
    for node in root.iter():
        if _local(node.tag) == 'GetMap':
            formats.extend((c.text or '').strip() for c in _children(node, 'Format'))
    layers = []

    def visit(node, inherited_crs=(), inherited_styles=()):
        crs = set(inherited_crs)
        for c in list(node):
            if _local(c.tag) in ('CRS', 'SRS'):
                crs.update((c.text or '').split())
        styles = set(inherited_styles)
        styles.update(_text(s, 'Name') for s in _children(node, 'Style'))
        name = _text(node, 'Name')
        if name:
            if any(l.name == name for l in layers):
                raise ValueError('Ambiguous WMS layer name')
            layers.append(Layer(name, _text(node, 'Title'), tuple(sorted(crs)), tuple(sorted(styles))))
        for child in _children(node, 'Layer'):
            visit(child, crs, styles)

    capability = _children(root, 'Capability')
    if len(capability) != 1:
        raise ValueError('Missing/ambiguous WMS Capability')
    for node in _children(capability[0], 'Layer'):
        visit(node)
    service = _children(root, 'Service')
    return Capabilities(version, tuple(layers), tuple(sorted(set(formats))), descriptor.endpoint,
        descriptor.attribution, _text(service[0], 'Fees') if service else '',
        _text(service[0], 'AccessConstraints') if service else '')


def map_request(descriptor, capabilities, *, layers, crs, bbox, width, height, image_format='image/png', styles=None):
    if capabilities.version not in ('1.3.0', '1.1.1'):
        raise ValueError('Unsupported WMS version')
    if capabilities.source_url != descriptor.endpoint:
        raise ValueError('Capabilities belong to another source')
    if type(width) is not int or type(height) is not int or not 1 <= width <= 2048 or not 1 <= height <= 2048:
        raise ValueError('Map dimensions exceed budget')
    if len(bbox) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox):
        raise ValueError('Finite XY BBOX required')
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError('Nonempty BBOX required')
    if crs not in ('EPSG:2100', 'EPSG:3857', 'EPSG:4326', 'CRS:84'):
        raise ValueError('Unreviewed CRS axis contract')
    if crs in ('EPSG:4326', 'CRS:84') and not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('Geographic BBOX out of bounds')
    if image_format not in capabilities.formats or image_format not in ('image/png', 'image/jpeg'):
        raise ValueError('Unsupported advertised image format')
    layers = tuple(layers)
    styles = ('',)*len(layers) if styles is None else tuple(styles)
    if not 1 <= len(layers) <= 16 or len(styles) != len(layers):
        raise ValueError('Bounded layers/styles required')
    for name, style in zip(layers, styles):
        layer = next((l for l in capabilities.layers if l.name == name), None)
        if not layer or ',' in name or crs not in layer.crs or (style and style not in layer.styles) or ',' in style:
            raise ValueError('Layer/style/CRS not advertised')
    ordered = (south, west, north, east) if capabilities.version == '1.3.0' and crs == 'EPSG:4326' else bbox
    parameters = dict(SERVICE='WMS', VERSION=capabilities.version, REQUEST='GetMap', LAYERS=','.join(layers),
        STYLES=','.join(styles), BBOX=','.join(str(float(v)) for v in ordered), WIDTH=str(width), HEIGHT=str(height), FORMAT=image_format)
    parameters['CRS' if capabilities.version == '1.3.0' else 'SRS'] = crs
    return _request(descriptor.endpoint, parameters)


class WmsClient:
    """URL/format-identical requests share a future and its cancellation. No disk cache."""
    def __init__(self, descriptor=WmsDescriptor(), transport=get):
        self.descriptor, self.transport = descriptor, transport
        self._lock, self._inflight = threading.RLock(), {}

    def submit(self, executor, url, *, cancelled=lambda: False, image_format=None):
        public_url(url, allow_http=self.descriptor.allow_http)
        if image_format is not None and image_format not in ('image/png', 'image/jpeg'):
            raise ValueError('Unsupported WMS image format')
        # Only URLs created from this exact configured endpoint may be retrieved.
        original, requested = urlsplit(self.descriptor.endpoint), urlsplit(url)
        if (requested.scheme, requested.netloc, requested.path) != (original.scheme, original.netloc, original.path):
            raise ValueError('Unreviewed WMS endpoint')
        key = (url, image_format)
        with self._lock:
            if key in self._inflight:
                return self._inflight[key]

            def run():
                if cancelled():
                    raise InterruptedError('Cancelled')
                budget = 16*1024*1024 if image_format else 2*1024*1024
                response = self.transport(url, max_bytes=budget,
                                          cancelled=cancelled, allow_http=self.descriptor.allow_http)
                if cancelled():
                    raise InterruptedError('Cancelled')
                if response.status != 200 or response.source_url != url or len(response.body) > budget:
                    raise ValueError('Unexpected WMS response')
                if image_format:
                    signature = b'\x89PNG\r\n\x1a\n' if image_format == 'image/png' else b'\xff\xd8\xff'
                    if response.content_type != image_format or not response.body.startswith(signature):
                        raise ValueError('WMS image/service exception response')
                    return response  # Original image/URL/ETag and descriptor attribution retained.
                return parse_capabilities(response.body, self.descriptor)

            future = executor.submit(run)
            self._inflight[key] = future
            def finished(done):
                with self._lock:
                    if self._inflight.get(key) is done:
                        self._inflight.pop(key, None)
            future.add_done_callback(finished)
            return future
