"""Versioned binary framing shared with Java; no JSON canonicalization assumption.
SPDX-License-Identifier: AGPL-3.0-only
"""
import hashlib


def fingerprint(*fields: str | bytes | None) -> str:
    """Each field is signed big-endian int32 length + exact UTF8/raw bytes.
    Null length is -1; empty is 0. No normalization, separator ambiguity or locale.
    Callers supply an explicit protocol/version tag as the first field.
    """
    result = hashlib.sha256()
    for field in fields:
        data = field.encode('utf-8', errors='strict') if isinstance(field, str) else field
        if data is not None and not isinstance(data, bytes):
            raise ValueError('Fingerprint fields must be exact text/bytes/null')
        result.update((-1 if data is None else len(data)).to_bytes(4, 'big', signed=True))
        if data is not None:
            result.update(data)
    return result.hexdigest()


def input_fingerprint(scope, field_uuid, configuration_revision, inputs):
    fields = ['fieltra-cadastral-input-v1', scope, field_uuid, str(configuration_revision)]
    for source in inputs:
        fields.extend((source.parcel_uuid, str(source.link_revision), source.provider_id,
            str(source.selected_revision), source.state, source.snapshot_uuid, source.content_hash,
            source.geometry_json, source.source_crs, source.provenance_json))
    return fingerprint(*fields)
