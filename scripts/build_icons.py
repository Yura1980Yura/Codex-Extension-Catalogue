"""Draw the catalogue's geometric A icon without external dependencies."""
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
shape=[(49,202),(110,50),(146,50),(207,202),(169,202),(155,165),(101,165),(87,202)]
hole=[(113,132),(128,91),(143,132)]
for y in range(size):
    pixels.append(0)
    for x in range(size):
        corner=(x<30 or x>=226) and (y<30 or y>=226)
        cx=30 if x<128 else 225;cy=30 if y<128 else 225
        alpha=0 if corner and (x-cx)**2+(y-cy)**2>30**2 else 255
        light=inside(x,y,shape) and not inside(x,y,hole)
        pixels.extend((244,244,232,alpha) if light else (39,83,72,alpha))
def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(pixels)))+chunk(b'IEND',b'')
(root/'asemic.png').write_bytes(png)
(root/'asemic.ico').write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22)+png)
(root/'asemic.icns').write_bytes(b'icns'+struct.pack('>I',16+len(png))+b'ic08'+struct.pack('>I',8+len(png))+png)
(root/'asemic.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" rx="30" fill="#275348"/><path fill="#f4f4e8" fill-rule="evenodd" d="M49 202 110 50H146L207 202H169L155 165H101L87 202ZM113 132H143L128 91Z"/></svg>\n',encoding='utf-8')
