"""Maintain Fieltra's compact offline Greece gazetteer (GeoNames, CC BY 4.0).

Explicit maintainer command only. The application never downloads this data.
Keeps named terrain/localities and settlement context; omits personal/POI data.
"""
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

SOURCE = 'https://download.geonames.org/export/dump/GR.zip'
OUTPUT = Path(__file__).resolve().parents[1]/'app/assets/geonames_gr.json'


def compact(data, acquired_at, modified=''):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.getinfo('GR.txt').file_size > 64*1024*1024:
            raise ValueError('Unexpected expanded GeoNames size')
        content = archive.read('GR.txt').decode('utf-8')
    entries = []
    for line in content.splitlines():
        row = line.split('\t')
        if len(row) != 19 or row[8] != 'GR' or row[6] not in {'L', 'T', 'V', 'H', 'P'}:
            continue
        greek = [name for name in row[3].split(',') if any('\u0370' <= c <= '\u03ff' for c in name)]
        name = greek[0] if greek else row[1]
        entries.append([int(row[0]), name, row[1], row[6]+'.'+row[7],
                        float(row[5]), float(row[4]), row[18]])
    return {'schema': 1, 'source': SOURCE, 'license': 'https://creativecommons.org/licenses/by/4.0/',
            'attribution': 'GeoNames (CC BY 4.0). Filtered and Greek display names selected by Fieltra.',
            'acquired_at': acquired_at, 'source_last_modified': modified,
            'source_sha256': hashlib.sha256(data).hexdigest(),
            'columns': ['id', 'name', 'original_name', 'feature', 'longitude', 'latitude', 'modified'],
            'features': entries}


def main():
    request = Request(SOURCE, headers={'User-Agent': 'Fieltra gazetteer maintenance (+https://github.com/Sxara242/Fieltra)'})
    with urlopen(request, timeout=45) as response:
        if response.status != 200 or response.geturl() != SOURCE:
            raise ValueError('Unexpected GeoNames response')
        data = response.read(12_000_001)
        if len(data) > 12_000_000:
            raise ValueError('Unexpected GeoNames archive size')
        result = compact(data, datetime.now(timezone.utc).isoformat(timespec='seconds'), response.headers.get('Last-Modified', ''))
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(f'Prepared {len(result["features"])} offline names; {OUTPUT.stat().st_size} bytes. No application imports or execution.')


if __name__ == '__main__':
    main()
