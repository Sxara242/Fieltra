"""Bounded explicit provider I/O, shared by optional WMS and offline foundations.
SPDX-License-Identifier: AGPL-3.0-only
"""
from dataclasses import dataclass
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from defusedxml import ElementTree


def public_url(url: str, *, allow_http=False):
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError('Invalid provider URL')
    parsed = urlsplit(url)
    if (parsed.scheme not in (('https', 'http') if allow_http else ('https',)) or not parsed.hostname
            or parsed.username is not None or parsed.password is not None or '#' in url
            or not parsed.hostname.isascii() or parsed.port is not None and not 1 <= parsed.port <= 65535):
        raise ValueError('Explicit credential-free provider URL required')
    return url


def safe_xml(data: bytes, *, max_bytes=2*1024*1024):
    if len(data) > max_bytes:
        raise ValueError('XML exceeds budget')
    root = ElementTree.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    pending = [(root, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > 20_000 or depth >= 64 or len(node.attrib) > 64:
            raise ValueError('XML structure exceeds budget')
        pending.extend((child, depth+1) for child in node)
    return root


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes
    source_url: str
    etag: str = ''


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError('Provider redirect requires explicit reviewed endpoint')


def get(url, *, max_bytes, cancelled=lambda: False, seconds=30, allow_http=False):
    """Explicit GET only; redirects require a reviewed endpoint, no TLS override."""
    public_url(url, allow_http=allow_http)
    if cancelled():
        raise InterruptedError('Cancelled')
    deadline = time.monotonic() + seconds
    request = Request(url, headers={'User-Agent': 'Fieltra/1.0.1', 'Accept-Encoding': 'identity'})
    with build_opener(_NoRedirect()).open(request, timeout=min(seconds, 15)) as stream:
        if stream.status != 200 or stream.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('Unexpected provider response')
        length = stream.headers.get('Content-Length')
        if length is not None and (not length.isdecimal() or int(length) > max_bytes):
            raise ValueError('Response exceeds budget')
        data = bytearray()
        while True:
            if cancelled():
                raise InterruptedError('Cancelled')
            if time.monotonic() > deadline:
                raise TimeoutError('Provider time budget exceeded')
            chunk = stream.read(min(65536, max_bytes+1-len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError('Response exceeds budget')
        if length is not None and len(data) != int(length):
            raise ValueError('Truncated provider response')
        return Response(200, stream.headers.get_content_type(), bytes(data), url, stream.headers.get('ETag', ''))
