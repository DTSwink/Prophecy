from pathlib import Path
LOTUS_VIEW='detail'
p=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/render_lotus_gold.py')
exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'))
