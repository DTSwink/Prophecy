"""Distinctive lime hand/purple target desktop icon; vector-style drawing."""
from PIL import Image,ImageDraw
from pathlib import Path
p=Path(__file__).resolve().parent
im=Image.new('RGBA',(256,256));d=ImageDraw.Draw(im)
d.rounded_rectangle((8,8,248,248),radius=54,fill='#d6ff60')
ink='#142119'
for box in [(60,79,84,168),(84,58,108,164),(108,48,132,164),(132,67,156,170)]:d.rounded_rectangle(box,radius=12,fill=ink)
d.rounded_rectangle((60,125,156,213),radius=35,fill=ink)
d.line([(135,183),(181,136)],fill=ink,width=25);d.ellipse((169,124,193,148),fill=ink)
d.ellipse((170,41,216,87),fill='#9c48ed')
for a,b in [((193,29),(193,39)),((193,89),(193,99)),((158,64),(168,64)),((218,64),(228,64))]:d.line([a,b],fill=ink,width=7)
d.line([(88,231),(154,231)],fill=ink,width=6)
im.save(p/'icon.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
