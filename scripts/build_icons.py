"""Draw a catalogue icon without external dependencies."""
from pathlib import Path
import struct
import zlib

root=Path(__file__).resolve().parents[1]/"assets"
root.mkdir(exist_ok=True)
size=256
pixels=bytearray()
def inside(x,y,poly):
    found=False
    for (a,b),(c,d) in zip(poly,poly[1:]+poly[:1]):
        if (b>y)!=(d>y) and x<(c-a)*(y-b)/(d-b)+a:found=not found
    return found
shape=[(42,54),(110,54),(130,76),(214,76),(214,208),(42,208)]
for y in range(size):
    pixels.append(0)
    for x in range(size):
        corner=(x<30 or x>=226) and (y<30 or y>=226)
        cx=30 if x<128 else 225;cy=30 if y<128 else 225
        alpha=0 if corner and (x-cx)**2+(y-cy)**2>30**2 else 255
        row=any(top<=y<top+12 and ((72<=x<84) or (100<=x<184)) for top in (104,140,176))
        light=inside(x,y,shape) and not row
        pixels.extend((244,244,232,alpha) if light else (39,83,72,alpha))
def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(pixels)))+chunk(b'IEND',b'')
(root/'catalogue.png').write_bytes(png)
(root/'catalogue.ico').write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22)+png)
(root/'catalogue.icns').write_bytes(b'icns'+struct.pack('>I',16+len(png))+b'ic08'+struct.pack('>I',8+len(png))+png)
(root/'catalogue.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" rx="30" fill="#275348"/><path fill="#f4f4e8" d="M42 54H110L130 76H214V208H42Z"/><path fill="#275348" d="M72 104H84V116H72ZM100 104H184V116H100ZM72 140H84V152H72ZM100 140H184V152H100ZM72 176H84V188H72ZM100 176H184V188H100Z"/></svg>\n',encoding='utf-8')
