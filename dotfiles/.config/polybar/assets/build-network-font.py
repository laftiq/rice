#!/usr/bin/python3
"""Build five small, monochrome network status glyphs without dependencies."""
import math
from pathlib import Path
import struct as S
P = S.pack

def stroke(points, width=55):
    result=[]
    for (a,b),(c,d) in zip(points,points[1:]):
        length=math.hypot(c-a,d-b)
        if not length:continue
        dx,dy=-(d-b)*width/(2*length),(c-a)*width/(2*length)
        result.append([(a+dx,b+dy),(c+dx,d+dy),(c-dx,d-dy),(a-dx,b-dy)])
    return result

def ellipse(cx,cy,rx,ry,start=0,end=360,width=50):
    angles=[math.radians(start+(end-start)*i/40) for i in range(41)]
    return stroke([(cx+rx*math.cos(t),cy+ry*math.sin(t)) for t in angles],width)

def theme_icon(name, category='status'):
    import ctypes as C
    import ctypes.util
    source = Path('/usr/share/icons/Papirus/16x16/symbolic')/category/(name+'.svg')
    svg = C.CDLL(ctypes.util.find_library('rsvg-2'))
    cairo = C.CDLL(ctypes.util.find_library('cairo'))
    obj = C.CDLL(ctypes.util.find_library('gobject-2.0'))
    def bind(lib, name, result, *args):
        f = getattr(lib,name);f.restype=result;f.argtypes=list(args);return f
    ptr = C.c_void_p
    handle = bind(svg,'rsvg_handle_new_from_file',ptr,C.c_char_p,ptr)(str(source).encode(),None)
    assert handle, source
    surface = bind(cairo,'cairo_image_surface_create',ptr,C.c_int,C.c_int,C.c_int)(0,64,64)
    context = bind(cairo,'cairo_create',ptr,ptr)(surface)
    bind(cairo,'cairo_scale',None,ptr,C.c_double,C.c_double)(context,4,4)
    assert bind(svg,'rsvg_handle_render_cairo',C.c_int,ptr,ptr)(handle,context)
    bind(cairo,'cairo_surface_flush',None,ptr)(surface)
    data = bind(cairo,'cairo_image_surface_get_data',C.POINTER(C.c_ubyte),ptr)(surface)
    stride = bind(cairo,'cairo_image_surface_get_stride',C.c_int,ptr)(surface)
    alpha = [[data[row*stride+col*4+3] for col in range(64)] for row in range(64)]
    bind(cairo,'cairo_destroy',None,ptr)(context)
    bind(cairo,'cairo_surface_destroy',None,ptr)(surface)
    bind(obj,'g_object_unref',None,ptr)(handle)
    # Remove a quarter of a source pixel from the edge of each filled shape.
    # This keeps Papirus geometry while avoiding a heavy silhouette at panel size.
    alpha = [[min(alpha[y][x], alpha[max(0,y-1)][x], alpha[min(63,y+1)][x],
                       alpha[y][max(0,x-1)], alpha[y][min(63,x+1)])
              for x in range(64)] for y in range(64)]
    contours = []
    for row in range(64):
        col = 0
        while col < 64:
            if alpha[row][col] < 128:
                col += 1
                continue
            start = col
            while col < 64 and alpha[row][col] >= 128:
                col += 1
            x1, x2 = start*1000/64, col*1000/64
            y1, y2 = (63-row)*1000/64, (64-row)*1000/64
            contours.append([(x1,y1),(x2,y1),(x2,y2),(x1,y2)])
    points = [point for contour in contours for point in contour]
    xs, ys = zip(*points)
    dx = 550-(min(xs)+max(xs))/2
    dy = 500-(min(ys)+max(ys))/2
    return [[(x+dx,y+dy) for x,y in contour] for contour in contours]


def glyf(contours):
    contours=[[(round(x),round(y)) for x,y in poly] for poly in contours]
    points=[p for poly in contours for p in poly]
    if not points:return P('>hhhhh',0,0,0,0,0)
    xs,ys=zip(*points)
    b=P('>hhhhh',len(contours),min(xs),min(ys),max(xs),max(ys))
    end=-1
    for poly in contours:
        end+=len(poly);b+=P('>H',end)
    b+=P('>H',0)+bytes([1])*len(points)
    previous=0
    for x,y in points:b+=P('>h',x-previous);previous=x
    previous=0
    for x,y in points:b+=P('>h',y-previous);previous=y
    return b+b'\0'*(-len(b)%4)

shapes=[[],theme_icon('network-wired-symbolic','devices'),
        theme_icon('network-wireless-signal-excellent-symbolic'),
        theme_icon('network-no-route-symbolic'),theme_icon('network-offline-symbolic'),
        theme_icon('network-acquiring-symbolic')]
glyphs=[glyf(s) for s in shapes]
offsets=[0]
for g in glyphs:offsets.append(offsets[-1]+len(g))
tables={}
tables['glyf']=b''.join(glyphs)
tables['loca']=b''.join(P('>I',i) for i in offsets)
tables['head']=P('>IIIIHHQQhhhhHHhhh',0x10000,0x10000,0,0x5f0f3cf5,3,1000,0,0,0,-100,1100,1000,0,8,2,1,0)
tables['hhea']=P('>IhhhH',0x10000,950,-100,0,1100)+P('>hhhhhh',0,0,1100,1,0,0)+P('>hhhh',0,0,0,0)+P('>hH',0,len(glyphs))
tables['hmtx']=P('>Hh',1100,0)*len(glyphs)
tables['maxp']=P('>IH',0x10000,len(glyphs))+P('>13H',max(sum(len(c) for c in shape) for shape in shapes),max(map(len,shapes)),0,0,2,0,0,0,0,0,0,0,0)
os2=bytearray(78)
S.pack_into('>HhHHH',os2,0,0,1100,400,5,0)
S.pack_into('>4sHHHhhhHH',os2,58,b'HOME',0x40,0xe000,0xe004,950,-100,0,950,100)
tables['OS/2']=bytes(os2)
# A format-4 cmap: one private-use range and the required terminal segment.
sub=P('>HHHHHHH',4,32,0,4,4,1,0)+P('>HHH',0xe004,0xffff,0)+P('>HH',0xe000,0xffff)+P('>HH',0x2001,1)+P('>HH',0,0)
tables['cmap']=P('>HHHHI',0,1,3,1,12)+sub
names={1:'Panel Network Icons',2:'Regular',3:'PanelNetworkIcons-Regular-1',4:'Panel Network Icons',5:'Version 1.0',6:'PanelNetworkIcons-Regular'}
records=b'';strings=b''
for key,value in names.items():
    encoded=value.encode('utf-16-be')
    records+=P('>HHHHHH',3,1,0x409,key,len(encoded),len(strings));strings+=encoded
tables['name']=P('>HHH',0,len(names),6+12*len(names))+records+strings
tables['post']=P('>IIhhIIIII',0x30000,0,0,0,1,0,0,0,0)

def checksum(data):
    data+=b'\0'*(-len(data)%4)
    return sum(S.unpack('>'+str(len(data)//4)+'I',data))&0xffffffff
n=len(tables);power=2**int(math.log2(n))
header=P('>IHHHH',0x10000,n,power*16,int(math.log2(n)),n*16-power*16)
directory=b'';body=b'';head_offset=0
for tag,data in sorted(tables.items()):
    offset=12+16*n+len(body)
    directory+=P('>4sIII',tag.encode(),checksum(data),offset,len(data))
    if tag=='head':head_offset=offset
    body+=data+b'\0'*(-len(data)%4)
font=bytearray(header+directory+body)
S.pack_into('>I',font,head_offset+8,(0xb1b0afba-checksum(font))&0xffffffff)
out=Path.home()/'.local/share/fonts/PanelNetworkIcons.ttf'
out.write_bytes(font)
print(out)
