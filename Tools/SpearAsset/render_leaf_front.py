from pathlib import Path
LEAF_VIEW='front'
p=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/render_leaf_pommel.py')
exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'))
