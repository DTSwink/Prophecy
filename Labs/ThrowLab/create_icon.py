"""Draw Throw Lab's own simple spear-and-target mark at Windows icon sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent/'assets'
S=4
im=Image.new('RGBA',(256*S,256*S),(0,0,0,0))
d=ImageDraw.Draw(im)
def box(v):return tuple(round(x*S) for x in v)
def line(points,fill,width):d.line([tuple(round(x*S) for x in p) for p in points],fill=fill,width=round(width*S))
d.rounded_rectangle(box((8,8,248,248)),radius=48*S,fill='#112f39',outline='#275763',width=4*S)
for radius,width in [(62,10),(39,8),(14,8)]:
    d.ellipse(box((166-radius,91-radius,166+radius,91+radius)),outline='#57e1cc',width=width*S)
# Dark separation makes the spear readable across the target rings.
line([(48,208),(170,86)],'#112f39',24)
line([(48,208),(163,93)],'#ffb46b',12)
d.polygon([tuple(x*S for x in p) for p in [(181,75),(169,117),(154,102),(139,87)]],fill='#fff2d7')
line([(45,211),(70,186)],'#ff865f',17)
line([(59,197),(45,182)],'#ff865f',8)
line([(64,202),(79,216)],'#ff865f',8)
im=im.resize((256,256),Image.Resampling.LANCZOS)
im.save(ROOT/'throw-target.png')
im.save(ROOT/'throw-target.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(ROOT/'throw-target.ico')
