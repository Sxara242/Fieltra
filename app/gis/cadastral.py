"""Computed cadastral presentation; never writes cultivated-field values."""
from datetime import datetime, timezone
from shapely.geometry import shape
from shapely.ops import transform

from ..localized_messages import _text
from .geometry import transformer
from .kaek_lookup import LookupStore


def grid_measurements(payload):
    geometry = shape(payload['geometry'])
    if payload['source_crs'] != 'EPSG:2100':
        geometry = transform(transformer(payload['source_crs'], 'EPSG:2100').transform, geometry)
    return {'area_m2': geometry.area, 'area_stremma': geometry.area/1000,
            'perimeter_m': geometry.length, 'measurement_crs': 'EPSG:2100'}


def _stamp(seconds):
    if seconds is None:
        return _text('Μη διαθέσιμο')
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec='seconds')


def cadastral_text(db, field_id):
    store = LookupStore(db)
    payload = store.geometry(field_id)
    if not payload:
        return _text('Δεν έχει ανακτηθεί κτηματολογικό πολύγωνο.')
    measurements = grid_measurements(payload)
    details = store.details(field_id)
    snapshot = details.get('snapshot', {})
    lines = [
        _text('Κτηματολογικό γεωτεμάχιο · ΚΑΕΚ {kaek}', kaek=payload['kaek']),
        _text('Υπολογισμένη κτηματολογική έκταση: {m2:.2f} m² · {stremma:.3f} στρ.',
              m2=measurements['area_m2'], stremma=measurements['area_stremma']),
        _text('Υπολογισμένη περίμετρος: {metres:.2f} m · Μέθοδος: EPSG:2100',
              metres=measurements['perimeter_m']),
        _text('Υπολογισμός από το πολύγωνο· δεν αποτελεί επίσημο καταχωρισμένο νομικό εμβαδόν.'),
        _text('Τελευταία ενημέρωση γεωτεμαχίου: {date}', date=payload['source_date'] or _text('Μη διαθέσιμο')),
        _text('Επίσημο κτηματολογικό τοπωνύμιο: μη διαθέσιμο από την πηγή.'),
    ]
    if payload['provider'] == 'hellenic-cadastre-north-aegean':
        # Historical catalogue reference, explicitly not inferred from a parcel's date.
        lines.append(_text('Τελευταία επαληθευμένη αναφορά περιφερειακού καταλόγου: 2026-10-06'))
    lines += [
        _text('Λήψη συνόλου δεδομένων: {date}', date=_stamp(snapshot.get('downloaded_at'))),
        _text('Έλεγχος ενημέρωσης συνόλου: {date}', date=_stamp(snapshot.get('checked_at'))),
        _text('Ανάκτηση γεωτεμαχίου: {date}', date=_stamp(payload['retrieved_at']/1000)),
        _text('CRS πηγής: {crs}', crs=payload['source_crs']),
        payload['attribution'], payload['source_url'],
        _text('Τα τοπικά όρια καλλιέργειας παραμένουν ανεξάρτητα.'),
    ]
    from .toponyms import ToponymStore
    locality=ToponymStore(db).load(field_id)
    if locality['decision']=='confirmed':
        lines.append(_text('Αγροτικό τοπωνύμιο επιβεβαιωμένο από χρήστη: {name}',name=locality['confirmed_name']))
    if snapshot.get('refresh_error'):
        lines.append(_text('Χρησιμοποιείται παλαιότερο επαληθευμένο τοπικό στιγμιότυπο· ο έλεγχος ενημέρωσης δεν ολοκληρώθηκε.'))
    return '\n'.join(lines)


def cultivated_area_text(value):
    if not value or float(value) <= 0:
        return _text('Δεν έχει δηλωθεί')
    return _text('{area:.3f} στρ.', area=float(value))


def cadastral_summary(db, field_id):
    """Short map summary; full provenance remains in cadastral_text/Sources."""
    payload = LookupStore(db).geometry(field_id)
    if not payload:
        return _text('Δεν έχει ανακτηθεί κτηματολογικό πολύγωνο.')
    values = grid_measurements(payload)
    lines = [
        _text('Κτηματολογική έκταση (υπολογισμένη): {area:.3f} στρ.', area=values['area_stremma']),
        _text('Κτηματολογική περίμετρος: {metres:.2f} m', metres=values['perimeter_m']),
        _text('Από το πολύγωνο· όχι επίσημο νομικό εμβαδόν.'),
    ]
    if payload['source_date']:
        lines.append(_text('Ημερομηνία πηγής: {date}', date=payload['source_date']))
    if any(word in (payload['provider']+' '+payload['attribution']).lower()
           for word in ('fixture', 'synthetic')):
        lines.append(_text('Δοκιμαστικά δεδομένα'))
    return '\n'.join(lines)
