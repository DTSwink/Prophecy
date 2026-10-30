"""Offline collider contact sheets from audit-sweep-turn.mjs; no desktop/browser."""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

folder = Path('Saved/BodyflipLab/SweepTurn') / (sys.argv[1] if len(sys.argv)>1 else '')
index = json.loads((folder/'mesh-index.json').read_text())
meshes = np.memmap(folder/'meshes.bin', dtype=np.float32, mode='r')
origin = np.array(index['origin'])
font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 16)
small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 13)
lookup = {(x['row'], x['frame']): x for x in index['index']}

def render(row, frame, size=(240, 270), view=(4, 2, 5)):
    item = lookup[row, frame]
    a = meshes[item['offset']//4:item['offset']//4+item['count']].reshape(-1, 9)
    towards = np.array(view, dtype=float); towards /= np.linalg.norm(towards)
    right = np.cross([0, 1, 0], towards); right /= np.linalg.norm(right)
    up = np.cross(towards, right)
    local = a[:, :3]-origin
    xy = np.stack((local@right, -local@up), axis=1)*min(size)*.38
    xy += [size[0]/2, size[1]*.52]
    depth = (local@towards).reshape(-1, 3).mean(axis=1)
    tris = xy.reshape(-1, 3, 2)
    light = np.array([-.35, .85, .4]); light /= np.linalg.norm(light)
    shade = .35+.65*np.maximum(0, a[:, 3:6]@light)
    rgb = np.clip(a[:, 6:9]*shade[:, None]*255, 0, 255).reshape(-1, 3, 3).mean(axis=1).astype(np.uint8)
    im = Image.new('RGB', size, '#141b26'); draw = ImageDraw.Draw(im)
    for i in np.argsort(depth):
        draw.polygon([tuple(p) for p in tris[i]], fill=tuple(rgb[i]))
    draw.text((8, 7), f'F {frame}', font=small, fill='#b7c7df')
    return im

count = index.get('frameCount', 36)
chosen = [8, 12, 17, 24, 35, 42, count-1] if index.get('sourceFrames', count)==36 else [0, 5, 9, 12, 13, 16, count-1]
w, h = 240, 270
sheet = Image.new('RGB', (w*len(chosen), (h+28)*4+35), '#0c121c')
d = ImageDraw.Draw(sheet)
d.text((12, 5), index.get('attack', 'sweepKick')+' · actual lab collider meshes · Direct to Armed · same fixed camera', font=font, fill='white')
for row, label in enumerate(index['rows']):
    y = 35+row*(h+28)
    d.text((10, y+3), label, font=font, fill='#c5a9ff')
    for col, frame in enumerate(chosen): sheet.paste(render(row, frame), (col*w, y+28))
sheet.save(folder/'comparison.png')
for row in [2, 3]:
    sheet = Image.new('RGB', (w*6, (h+24)*((count+5)//6)), '#0c121c')
    d = ImageDraw.Draw(sheet)
    for frame in range(count):
        x, y = frame%6*w, frame//6*(h+24)
        sheet.paste(render(row, frame), (x, y+24))
        d.text((x+8, y+3), index['rows'][row], font=small, fill='#c5a9ff')
    sheet.save(folder/f'frames-{row}.png')
frames = []
for frame in range(count):
    im = Image.new('RGB', (720, 420), '#0c121c'); d = ImageDraw.Draw(im)
    for col, row in enumerate([0, 2, 3]):
        im.paste(render(row, frame, (240, 385)), (col*240, 35))
        d.text((col*240+8, 7), index['rows'][row], font=font, fill='white')
    frames.append(im)
frames[0].save(folder/'sweep-comparison.gif', save_all=True, append_images=frames[1:], duration=67, loop=0)
print('Wrote comparison.png, frames-2.png, frames-3.png, sweep-comparison.gif')
