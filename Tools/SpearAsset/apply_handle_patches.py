"""Apply reviewed handle candidates, verifying every accepted head pixel is fixed."""
import json,hashlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish'
OUT=ROOT/'Exports/ImperialSpear';TEX=OUT/'Textures';PATCH=WORK/'patches'
manifest=json.loads((PATCH/'HandlePatchManifest.json').read_text(encoding='utf-8'))
def protected(image):
    digest=hashlib.sha256()
    digest.update(image.crop((0,0,4096,2048)).tobytes())
    digest.update(image.crop((3072,2048,4096,4096)).tobytes())
    return digest.hexdigest()
rows=[];staged=[]
for kind in ('BaseColor','ORM','NormalGL','NormalDX'):
    name='T_ImperialSpear_'+kind+'.png'
    with Image.open(TEX/name) as source:image=source.copy()
    with Image.open(WORK/'Before/Textures'/name) as source:baseline=protected(source)
    before=protected(image);assert before==baseline,('Protected head/silk already changed',name)
    with Image.open(PATCH/'wood_v8'/('Wood_'+kind+'.png')) as patch:image.paste(patch,(0,2048,2048,4096))
    for target in ('Leather','KeeperGold'):
        spec=manifest['patches'][target];info=spec['files'][kind];path=PATCH/info['filename']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==info['sha256']
        with Image.open(path) as patch:image.paste(patch,tuple(spec['atlas_pixel_box']))
    assert protected(image)==before
    temp=TEX/(name+'.handle-tmp.png');image.save(temp,compress_level=3);staged.append((temp,TEX/name))
    rows.append({'image':name,'protected_head_and_silk_sha256':before,'protected_pixels_unchanged':True})
for temp,destination in staged:temp.replace(destination)
report={'scope':'Wood and grip-only tiles; all accepted spearhead and silk pixels unchanged','images':rows,
        'wood_report':str(PATCH/'wood_v8/Wood_Patch_Report.json'),'grip_manifest':str(PATCH/'HandlePatchManifest.json')}
(WORK/'Handle_Texture_Application.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
