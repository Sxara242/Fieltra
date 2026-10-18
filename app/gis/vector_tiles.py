"""Small Protomaps MVT decoder and native Qt overview style.

First-party AGPL implementation of the public Mapbox Vector Tile 2.1 wire
format. This is an overview basemap, not a MapLibre style interpreter.
"""
import struct


def varint(data,pos):
    value=0
    for shift in range(0,70,7):
        if pos>=len(data):raise ValueError('Truncated MVT varint')
        byte=data[pos];pos+=1;value|=(byte&127)<<shift
        if byte<128:return value,pos
    raise ValueError('Oversized MVT varint')


def fields(data):
    pos=0
    while pos<len(data):
        tag,pos=varint(data,pos);number,wire=tag>>3,tag&7
        if not number:raise ValueError('Invalid MVT field')
        if wire==0:value,pos=varint(data,pos)
        elif wire in (1,5):
            size=8 if wire==1 else 4;value=data[pos:pos+size];pos+=size
            if len(value)!=size:raise ValueError('Truncated MVT number')
        elif wire==2:
            size,pos=varint(data,pos);value=data[pos:pos+size];pos+=size
            if len(value)!=size:raise ValueError('Truncated MVT field')
        else:raise ValueError('Unsupported MVT wire type')
        yield number,value


def packed(data):
    pos=0;result=[]
    while pos<len(data):
        value,pos=varint(data,pos);result.append(value)
    return result


def value_of(data):
    for number,value in fields(data):
        if number==1:return value.decode('utf-8',errors='replace')
        if number==2:return struct.unpack('<f',value)[0]
        if number==3:return struct.unpack('<d',value)[0]
        if number in (4,5):return value
        if number==6:return (value>>1)^-(value&1)
        if number==7:return bool(value)
    return ''


def geometry(commands):
    pos=0;x=y=0;paths=[];current=None
    while pos<len(commands):
        command=commands[pos];pos+=1;kind,count=command&7,command>>3
        if not count or kind not in (1,2,7):raise ValueError('Invalid MVT geometry command')
        if kind==7:
            if current:current.append(current[0])
            continue
        if pos+2*count>len(commands):raise ValueError('Truncated MVT geometry')
        for _ in range(count):
            dx,dy=commands[pos:pos+2];pos+=2
            x+=(dx>>1)^-(dx&1);y+=(dy>>1)^-(dy&1)
            if kind==1:current=[];paths.append(current)
            if current is None:raise ValueError('MVT line before move')
            current.append((x,y))
    return paths


def decode(data):
    """Return (layer, extent, type, properties, paths), with bounded work."""
    if len(data)>8*1024*1024:raise ValueError('MVT too large')
    result=[];vertices=0
    for number,layer in fields(data):
        if number!=3:continue
        name='';extent=4096;keys=[];values=[];features=[]
        for field,value in fields(layer):
            if field==1:name=value.decode('utf-8')
            elif field==2:features.append(value)
            elif field==3:keys.append(value.decode('utf-8'))
            elif field==4:values.append(value_of(value))
            elif field==5:extent=value
        if not 0<extent<=65536:raise ValueError('Invalid MVT extent')
        for feature in features:
            tags=[];kind=0;commands=[]
            for field,value in fields(feature):
                if field==2:tags=packed(value)
                elif field==3:kind=value
                elif field==4:commands=packed(value)
            if len(tags)%2:raise ValueError('Invalid MVT tags')
            props={}
            for i in range(0,len(tags),2):
                if tags[i]>=len(keys) or tags[i+1]>=len(values):raise ValueError('MVT tag index outside table')
                props[keys[tags[i]]]=values[tags[i+1]]
            paths=geometry(commands);vertices+=sum(map(len,paths))
            if vertices>300000 or len(result)>30000:raise ValueError('MVT geometry budget exceeded')
            result.append((name,extent,kind,props,paths))
    return result


def render(data,size=256):
    # Import Qt only here: format/acquisition tests never load host-native Qt.
    from PySide6.QtCore import Qt,QRectF
    from PySide6.QtGui import QImage,QPainter,QPainterPath,QColor,QPen,QFont
    image=QImage(size,size,QImage.Format.Format_ARGB32_Premultiplied);image.fill(QColor('#eeeadd'))
    features=decode(data);painter=QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colours={'earth':'#eeeadd','landcover':'#dce3c9','landuse':'#dde3cd',
                 'water':'#acd0df','buildings':'#c8c1b6'}
        for name,extent,kind,props,paths in sorted(features,key=lambda f:
                {'earth':0,'landcover':1,'landuse':2,'water':3,'buildings':4,'roads':5}.get(f[0],6)):
            factor=size/extent
            if kind in (2,3) and (name in colours or name in ('roads','boundaries')):
                path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
                for points in paths:
                    if not points:continue
                    path.moveTo(points[0][0]*factor,points[0][1]*factor)
                    for x,y in points[1:]:path.lineTo(x*factor,y*factor)
                    if kind==3:path.closeSubpath()
                if kind==3:
                    painter.fillPath(path,QColor(colours.get(name,'#ddd9cb')))
                else:
                    major=props.get('kind') in ('highway','major_road')
                    pen=QPen(QColor('#dcae72' if major else '#ffffff'),2 if major else 1)
                    if name=='water':pen=QPen(QColor('#acd0df'),1)
                    if name=='boundaries':pen=QPen(QColor('#b1aaa1'),.6,Qt.PenStyle.DashLine)
                    painter.strokePath(path,pen)
        painter.setFont(QFont('Segoe UI',9));painter.setPen(QColor('#384437'))
        used=[]
        for name,extent,kind,props,paths in features:
            if name!='places' or kind!=1 or not paths:continue
            text=str(props.get('name:el') or props.get('name') or '')[:80]
            if not text:continue
            x,y=paths[0][0];x*=size/extent;y*=size/extent
            width=painter.fontMetrics().horizontalAdvance(text)
            rect=QRectF(x-width/2,y-7,width,15)
            if 0<=rect.left() and rect.right()<size and 0<=rect.top() and rect.bottom()<size and not any(r.intersects(rect) for r in used):
                painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,text);used.append(rect)
    finally:painter.end()
    return image
