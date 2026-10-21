"""Draw the app's vector-style scissors / motion identity at multiple sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

p=Path(__file__).resolve().parent
im=Image.new('RGBA',(256,256));d=ImageDraw.Draw(im)
d.rounded_rectangle((7,7,249,249),radius=53,fill='#17212d')
d.rounded_rectangle((21,21,235,235),radius=43,outline='#ffa75a',width=5)
for y,x in [(67,93),(92,117),(117,140)]:
    d.line([(x,y),(207,y)],fill='#66d3dc',width=9)
d.line([(74,165),(178,55)],fill='#ffa75a',width=15)
d.line([(75,114),(175,210)],fill='#ffa75a',width=15)
d.ellipse((39,144,96,202),fill='#17212d',outline='#ffa75a',width=13)
d.ellipse((38,77,96,135),fill='#17212d',outline='#ffa75a',width=13)
d.ellipse((102,131,118,147),fill='#edf2f8')
im.save(p/'icon.png')
im.save(p/'icon.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
