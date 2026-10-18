"""Bounded regional Protomaps acquisition and local-only PMTiles v3 reading.

No public OSM raster endpoint, server, native SDK, web renderer or runtime pip.
"""
from collections import OrderedDict
from functools import lru_cache
import gzip
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
from urllib.request import Request, urlopen
from uuid import uuid4

from ..vendor.pmtiles.tile import (Compression, TileType, deserialize_header,
    deserialize_directory, find_tile, zxy_to_tileid)
from ..vendor.pmtiles.writer import Writer

SOURCE = 'https://data.source.coop/protomaps/openstreetmap/v4.pmtiles'
CHIOS = (25.75, 38.00, 26.65, 38.65)
MAX_FILE = 64 * 1024 * 1024
MAX_TRANSFER = 128 * 1024 * 1024
MAX_BLOCK = 4 * 1024 * 1024
ATTRIBUTION = '© OpenStreetMap contributors · Protomaps · Natural Earth'
DATA_LICENCE = 'ODbL 1.0 Produced Work'


def unpack(data, compression):
    if compression == Compression.NONE:
        if len(data) > 8 * 1024 * 1024: raise ValueError('Map block too large')
        return data
    if compression != Compression.GZIP: raise ValueError('Only none/gzip compression is supported')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        result = stream.read(8 * 1024 * 1024 + 1)
    if len(result) > 8 * 1024 * 1024: raise ValueError('Expanded map block too large')
    return result


class RangeSource:
    """Only precise HTTPS ranges; never accept a full-planet fallback response."""
    def __init__(self, url=SOURCE, cancel=lambda: False):
        if url != SOURCE: raise ValueError('Only the reviewed Protomaps mirror is enabled')
        self.url=url; self.cancel=cancel; self.transferred=0; self.etag=None; self.total=None
        self.cache=OrderedDict()

    def __call__(self, offset, length):
        if self.cancel(): raise InterruptedError('Download cancelled')
        if offset < 0 or not 0 < length <= MAX_BLOCK: raise ValueError('Invalid map range')
        key=(offset,length)
        if key in self.cache:
            self.cache.move_to_end(key); return self.cache[key]
        if self.transferred+length > MAX_TRANSFER: raise ValueError('128 MiB transfer limit reached')
        headers={'Range':f'bytes={offset}-{offset+length-1}', 'Accept-Encoding':'identity',
                 'User-Agent':'Fieltra/1.0.1 (+https://github.com/Sxara242/Fieltra)'}
        if self.etag: headers['If-Match']=self.etag
        with urlopen(Request(self.url,headers=headers),timeout=20) as response:
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
            if response.status != 206 or not match or tuple(map(int,match.groups()[:2])) != (offset,offset+length-1):
                raise ValueError('Server did not honour range; full download refused')
            etag=response.headers.get('ETag')
            if not etag or (self.etag and etag != self.etag): raise ValueError('Map version changed during download')
            total=int(match[3])
            if self.total is not None and total != self.total: raise ValueError('Map size changed')
            self.etag=etag; self.total=total
            data=response.read(length+1)
        if len(data) != length: raise ValueError('Truncated/oversized map range')
        self.transferred+=length
        if length < 512*1024:
            self.cache[key]=data
            while len(self.cache)>32:self.cache.popitem(last=False)
        return data


class Archive:
    """Validated reference-format reader; file stays seekable, not loaded in RAM."""
    def __init__(self, source, size=None):
        self.source=source; self.size=size
        raw=source(0,127)
        if len(raw)!=127:raise ValueError('Truncated PMTiles header')
        try:self.header=deserialize_header(raw)
        except Exception as error:raise ValueError('Invalid or unsupported PMTiles v3 header') from error
        h=self.header
        if h['internal_compression'] != Compression.GZIP:raise ValueError('Directory compression must be gzip')
        if h['tile_compression'] not in (Compression.NONE,Compression.GZIP):raise ValueError('Unsupported tile compression')
        if h['tile_type'] != TileType.MVT:raise ValueError('Select a Protomaps MVT archive')
        if not 0<=h['min_zoom']<=h['max_zoom']<=15:raise ValueError('Unsupported zoom range')
        for prefix in ('root','metadata','leaf_directory','tile_data'):
            offset,length=h[prefix+'_offset'],h[prefix+'_length']
            if offset<127 or length<0 or (size is not None and offset+length>size):raise ValueError('Map section outside file')
        self.metadata=json.loads(unpack(self.read(h['metadata_offset'],h['metadata_length']),h['internal_compression']))
        if not isinstance(self.metadata,dict):raise ValueError('Invalid map metadata')

    def read(self,offset,length):
        if offset<0 or not 0<length<=MAX_BLOCK or (self.size is not None and offset+length>self.size):
            raise ValueError('Map range outside file or too large')
        data=self.source(offset,length)
        if len(data)!=length:raise ValueError('Truncated map data')
        return data

    @lru_cache(maxsize=32)
    def directory(self,offset,length):
        data=self.read(offset,length)
        # Check decompressed size before entering the reference decoder.
        unpack(data,Compression.GZIP)
        return deserialize_directory(data)

    def get(self,z,x,y):
        h=self.header
        if not h['min_zoom']<=z<=h['max_zoom']:return None
        tile_id=zxy_to_tileid(z,x,y);offset=h['root_offset'];length=h['root_length']
        for _ in range(4):
            entry=find_tile(self.directory(offset,length),tile_id)
            if entry is None:return None
            if entry.run_length:
                if entry.offset+entry.length>h['tile_data_length']:raise ValueError('Tile outside data section')
                return self.read(h['tile_data_offset']+entry.offset,entry.length)
            if entry.offset+entry.length>h['leaf_directory_length']:raise ValueError('Directory outside leaf section')
            offset=h['leaf_directory_offset']+entry.offset;length=entry.length
        raise ValueError('PMTiles directory depth exceeded')


class LocalArchive(Archive):
    def __init__(self,path):
        self.path=Path(path);self.file=self.path.open('rb')
        try:super().__init__(self._read,self.path.stat().st_size)
        except Exception:self.file.close();raise

    def _read(self,offset,length):
        self.file.seek(offset);return self.file.read(length)

    def close(self):
        self.directory.cache_clear();self.file.close()


def region_tiles(bbox=CHIOS,max_zoom=12):
    west,south,east,north=bbox
    if not (-180<=west<east<=180 and -85<=south<north<=85 and 0<=max_zoom<=14):
        raise ValueError('Invalid region/zoom')
    for z in range(max_zoom+1):
        n=2**z
        def xy(lon,lat):
            return (min(n-1,max(0,int((lon+180)/360*n))),
                min(n-1,max(0,int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n))))
        x0,y1=xy(west,south);x1,y0=xy(east,north)
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):yield z,x,y


def extract_chios(destination,progress=lambda *_:None,cancel=lambda:False,source=None,max_zoom=12):
    """Explicit bounded cutout, written atomically; never replace an existing map."""
    destination=Path(destination)
    if destination.exists():raise FileExistsError('Map already exists; open it instead')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free < 2*MAX_FILE+8*1024*1024:
        raise OSError('At least 136 MiB free disk space required')
    source=source or RangeSource(cancel=cancel)
    archive=Archive(source);h=dict(archive.header)
    keys=sorted(region_tiles(max_zoom=max_zoom),key=lambda xyz:zxy_to_tileid(*xyz))
    if max_zoom>h['max_zoom']:raise ValueError('Requested zoom missing from source')
    part=destination.with_name(destination.name+'.'+uuid4().hex+'.part')
    count=0;stored=0
    try:
        with part.open('xb') as output:
            writer=Writer(output,temp_directory=destination.parent)
            try:
                for index,key in enumerate(keys):
                    if cancel():raise InterruptedError('Download cancelled')
                    data=archive.get(*key)
                    if data:
                        stored+=len(data)
                        if stored>MAX_FILE-1024*1024:raise ValueError('64 MiB map limit reached; reduce detail')
                        writer.write_tile(zxy_to_tileid(*key),data);count+=1
                    progress(index+1,len(keys),stored)
                if not count:raise ValueError('No tiles found for Chios')
                for key,value in zip(('min_lon_e7','min_lat_e7','max_lon_e7','max_lat_e7'),CHIOS):h[key]=round(value*1e7)
                h.update(center_zoom=min(10,max_zoom),center_lon_e7=round((CHIOS[0]+CHIOS[2])*5e6),
                         center_lat_e7=round((CHIOS[1]+CHIOS[3])*5e6))
                metadata=dict(archive.metadata)
                metadata['fieltra_source_attribution']=metadata.get('attribution','')
                metadata.update(name='Chios / Χίος',bounds=','.join(map(str,CHIOS)),
                    attribution=ATTRIBUTION,license=DATA_LICENCE,
                    fieltra_source=SOURCE,fieltra_source_etag=getattr(source,'etag',''),
                    fieltra_bbox=CHIOS,minzoom=0,maxzoom=max_zoom)
                writer.finalize(h,metadata)
            finally:writer.tile_f.close()
        os.rename(part,destination)  # Windows: fails if destination now exists.
    except Exception:
        # This invocation owns this random partial file, never a user's map.
        part.unlink(missing_ok=True)
        raise
    return {'bytes':destination.stat().st_size,'tiles':count,'max_zoom':max_zoom,
            'transferred':getattr(source,'transferred',None),'source_bytes':getattr(source,'total',None)}
