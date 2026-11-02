"""Four sequential, bounded inspection stills. No concurrent renders."""
from pathlib import Path
_render_path=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/render_lotus_gold.py')
_render_source=_render_path.read_text(encoding='utf-8')
for _requested_view in ('detail','front','diagonal','end'):
    exec(compile(_render_source,str(_render_path),'exec'),{'LOTUS_VIEW':_requested_view})
print('Four detailed pommel inspection views refreshed.')
