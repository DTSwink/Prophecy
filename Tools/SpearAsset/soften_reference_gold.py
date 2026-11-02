"""Subtle socket chasing and smoother cast gold, without touching other finishes.

Run only when the material pass is approved for generation. First run snapshots
current atlases and the socket motif code. Repeats use immutable gold patches
but paste into CURRENT atlases, preserving all later wood/steel/leather work.
Housing S-border pixels and ORM AO/metal/specular alpha are retained exactly.
No Blender, geometry, texture download or shader modifications are performed.
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"Exports/ImperialSpear"
TEXTURES=OUT/"Textures"
BACKUP=ROOT/"Saved/Diagnostics/ImperialSpear/BeforeSoftGold_v1"
FILES={"base":"T_ImperialSpear_BaseColor.png","orm":"T_ImperialSpear_ORM.png",
       "gl":"T_ImperialSpear_NormalGL.png","dx":"T_ImperialSpear_NormalDX.png"}
BOXES={"plain":(2048,0,3072,1024),"body":(2048,1024,3072,2048),"socket":(3584,0,4096,2048)}
MOTIF_SOURCE=ROOT/"Tools/SpearAsset/make_connected_socket_engraving.py"
MOTIF_SNAPSHOT="socket_motif_source.py"
FINISH_VARIATION_RETAIN=.30
SOCKET_DEPTH_MM=.045
SOCKET_ALBEDO_CUT=.035
SOCKET_ROUGHNESS_CUT=.032
SOCKET_LIP_ALBEDO=.006
SOCKET_LIP_ROUGHNESS=-.008
OLD_SOCKET_ALBEDO_CUT=.48
OLD_SOCKET_ROUGHNESS_CUT=.17
OLD_SOCKET_LIP_ALBEDO=.075
OLD_SOCKET_LIP_ROUGHNESS=-.065


def file_hash(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def backup_current():
    manifest_path=BACKUP/"manifest.json"
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        for name,checksum in manifest.items():
            if file_hash(BACKUP/name)!=checksum:
                raise RuntimeError(f"Immutable backup verification failed: {name}")
        return manifest
    if BACKUP.exists():
        raise RuntimeError(f"Incomplete backup exists: {BACKUP}")
    BACKUP.mkdir(parents=True,exist_ok=False)
    manifest={}
    pairs=[(TEXTURES/name,name) for name in FILES.values()]+[(MOTIF_SOURCE,MOTIF_SNAPSHOT)]
    for source,name in pairs:
        shutil.copy2(source,BACKUP/name)
        manifest[name]=file_hash(source)
        if file_hash(BACKUP/name)!=manifest[name]:
            raise RuntimeError(f"Backup copy failed: {name}")
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def current_motif():
    """Compile only pure mask functions/constants, never another script's main."""
    tree=ast.parse((BACKUP/MOTIF_SNAPSHOT).read_text(encoding="utf-8"))
    constants={"W","H","CIRCUMFERENCE_MM","AXIAL_MM","COLUMNS","ROWS","STROKE_MM","LIP_MM","PIXELS_PER_MM"}
    functions={"bezier","pattern"}
    statements=[]
    for node in tree.body:
        if isinstance(node,ast.Assign):
            assigned={n.id for target in node.targets for n in ast.walk(target) if isinstance(n,ast.Name)}
            if assigned & constants:statements.append(node)
        elif isinstance(node,ast.FunctionDef) and node.name in functions:
            statements.append(node)
    scope={"np":np,"Image":Image,"ImageDraw":ImageDraw}
    exec(compile(ast.Module(body=statements,type_ignores=[]),"preserved_socket_motif","exec"),scope)
    cut,lip=scope["pattern"]()
    return cut,lip,{key:scope[key] for key in constants}


def read_regions():
    regions={region:{} for region in BOXES}
    for key,name in FILES.items():
        with Image.open(BACKUP/name) as image:
            if image.size!=(4096,4096) or image.mode not in ("RGB","RGBA"):
                raise ValueError(f"Unexpected atlas format: {name}")
            for region,box in BOXES.items():regions[region][key]=np.array(image.crop(box))
    if any(region["orm"].shape[2]!=4 for region in regions.values()):
        raise ValueError("Current ORM must contain packed specular alpha")
    return regions


def housing_border_mask(plain,body):
    # The original body atlas was built over the identical resized plain gold.
    # Preserve differences from that carrier plus any strong normal cut. This
    # protects the actual stored border, not an inferred/possibly changed guide.
    difference=np.max(np.abs(body["base"][:,:,:3].astype(np.int16)-plain["base"][:,:,:3].astype(np.int16)),axis=2)>2
    difference|=np.max(np.abs(body["gl"][:,:,:3].astype(np.int16)-plain["gl"][:,:,:3].astype(np.int16)),axis=2)>2
    difference|=np.max(np.abs(body["orm"][:,:,:3].astype(np.int16)-plain["orm"][:,:,:3].astype(np.int16)),axis=2)>2
    normal=(body["gl"][:,:,:3].astype(np.float32)-128)/127
    slope=np.linalg.norm(normal[:,:,:2],axis=2)/np.maximum(normal[:,:,2],.15)
    difference|=slope>.20
    # Four-texel halo (~0.5mm) retains anti-aliased walls and polished lips.
    return np.asarray(Image.fromarray((difference*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)))>0


def encode_slopes(nx,ny):
    inv=1/np.sqrt(nx*nx+ny*ny+1)
    gl=np.rint(np.clip(np.stack((nx*inv,ny*inv,inv),-1)*127+128,0,255)).astype(np.uint8)
    dx=gl.copy();dx[:,:,1]=255-dx[:,:,1]
    return gl,dx


def smooth_finish(old,preserve=None):
    result={key:value.copy() for key,value in old.items()}
    valid=np.ones(old["base"].shape[:2],dtype=bool) if preserve is None else ~preserve
    if not np.any(valid):
        raise RuntimeError("Housing protection mask covers every pixel; inspect the current body atlas")
    colour=old["base"][:,:,:3].astype(np.float32)
    centre=np.mean(colour[valid],axis=0)
    result["base"][:,:,:3]=np.rint(np.clip(centre+(colour-centre)*FINISH_VARIATION_RETAIN,0,255)).astype(np.uint8)
    rough=old["orm"][:,:,1].astype(np.float32)
    mean=float(np.mean(rough[valid]))
    result["orm"][:,:,1]=np.rint(mean+(rough-mean)*FINISH_VARIATION_RETAIN).astype(np.uint8)
    normal=(old["gl"][:,:,:3].astype(np.float32)-128)/127
    nz=np.maximum(normal[:,:,2],.15)
    gl,dx=encode_slopes(normal[:,:,0]/nz*FINISH_VARIATION_RETAIN,normal[:,:,1]/nz*FINISH_VARIATION_RETAIN)
    result["gl"][:,:,:3]=gl;result["dx"][:,:,:3]=dx
    if preserve is not None:
        for key in result:result[key][preserve]=old[key][preserve]
    return result,{"base_std_before":np.std(colour[valid],axis=0).tolist(),
                   "base_std_after":np.std(result["base"][:,:,:3][valid],axis=0).tolist(),
                   "roughness_std_before":float(np.std(rough[valid])/255),
                   "roughness_std_after":float(np.std(result["orm"][:,:,1][valid])/255)}


def subtle_socket(old):
    cut,lip,layout=current_motif()
    assert cut.shape==old["base"].shape[:2]
    bare=(cut<.015)&(lip<.015)
    base_centre=np.median(old["base"][:,:,:3][bare],axis=0).astype(np.float32)
    rough=old["orm"][:,:,1].astype(np.float32)/255
    rough_centre=float(np.median(rough[bare]))
    result={key:value.copy() for key,value in old.items()}
    # Remove the former ink-like contrast while retaining its small carrier
    # variation and current gold colour. Layout masks are exactly unchanged.
    residual=old["base"][:,:,:3].astype(np.float32)/np.maximum(base_centre,1)-1
    residual+=cut[:,:,None]*OLD_SOCKET_ALBEDO_CUT-lip[:,:,None]*OLD_SOCKET_LIP_ALBEDO
    residual=np.clip(residual,-.04,.04)*FINISH_VARIATION_RETAIN
    tone=1+residual-cut[:,:,None]*SOCKET_ALBEDO_CUT+lip[:,:,None]*SOCKET_LIP_ALBEDO
    result["base"][:,:,:3]=np.rint(np.clip(base_centre*tone,0,255)).astype(np.uint8)
    rough_residual=rough-rough_centre-cut*OLD_SOCKET_ROUGHNESS_CUT-lip*OLD_SOCKET_LIP_ROUGHNESS
    new_rough=rough_centre+np.clip(rough_residual,-.04,.04)*FINISH_VARIATION_RETAIN+cut*SOCKET_ROUGHNESS_CUT+lip*SOCKET_LIP_ROUGHNESS
    result["orm"][:,:,1]=np.rint(np.clip(new_rough,0,1)*255).astype(np.uint8)
    height=-SOCKET_DEPTH_MM*cut
    dy,dx=np.gradient(height,layout["AXIAL_MM"]/cut.shape[0],layout["CIRCUMFERENCE_MM"]/cut.shape[1])
    gl,directx=encode_slopes(-dx,dy)
    result["gl"][:,:,:3]=gl;result["dx"][:,:,:3]=directx
    return result,{"motif_layout":layout,"base_carrier_median_srgb":base_centre.tolist(),
                   "roughness_carrier_median":rough_centre,"new_depth_mm":SOCKET_DEPTH_MM,
                   "max_albedo_cut":SOCKET_ALBEDO_CUT,"roughness_cut_increment":SOCKET_ROUGHNESS_CUT,
                   "lip_albedo_increment":SOCKET_LIP_ALBEDO,"lip_roughness_increment":SOCKET_LIP_ROUGHNESS,
                   "normal_slope_max":float(max(np.max(np.abs(dx)),np.max(np.abs(dy))))}


def outside_hash(image):
    digest=hashlib.sha256()
    for top in range(0,4096,128):
        boxes=((0,top,2048,top+128),(3072,top,3584,top+128)) if top<2048 else ((0,top,4096,top+128),)
        for box in boxes:digest.update(image.crop(box).tobytes())
    return digest.hexdigest()


def main():
    originals=backup_current();old=read_regions()
    mask=housing_border_mask(old["plain"],old["body"])
    generated,details={},{}
    generated["plain"],details["plain"]=smooth_finish(old["plain"])
    generated["body"],details["body"]=smooth_finish(old["body"],mask)
    generated["socket"],details["socket"]=subtle_socket(old["socket"])
    body_checks={}
    for key in FILES:
        assert np.array_equal(old["body"][key][mask],generated["body"][key][mask])
        body_checks[key]=hashlib.sha256(generated["body"][key][mask].tobytes()).hexdigest()
    temporary,preservation=[],{}
    try:
        for key,name in FILES.items():
            with Image.open(TEXTURES/name) as source:image=source.copy()
            before=outside_hash(image)
            alpha_before=hashlib.sha256(image.getchannel("A").tobytes()).hexdigest() if key=="orm" else None
            for region,box in BOXES.items():
                pixels=generated[region][key].copy()
                if key=="orm":
                    current=np.array(image.crop(box))
                    for channel in (0,2,3):pixels[:,:,channel]=current[:,:,channel]
                image.paste(Image.fromarray(pixels),box)
            after=outside_hash(image)
            assert before==after,f"Pixels outside target gold regions changed: {name}"
            if key=="orm":assert hashlib.sha256(image.getchannel("A").tobytes()).hexdigest()==alpha_before
            preservation[name]={"before_sha256":before,"after_sha256":after,"unchanged":True}
            path=TEXTURES/(name+".soft-gold-tmp.png")
            image.save(path,compress_level=3);temporary.append((path,TEXTURES/name))
            del image
        for source,destination in temporary:source.replace(destination)
    finally:
        for path,_ in temporary:path.unlink(missing_ok=True)
    report={"status":"gold finish softened","backup":str(BACKUP),"original_files":originals,
            "target_regions":{key:list(box) for key,box in BOXES.items()},
            "finish_variation_retained":FINISH_VARIATION_RETAIN,"body_border_protected_pixels":int(mask.sum()),
            "body_border_protected_fraction":float(mask.mean()),"body_border_sha256":body_checks,
            "ORM_AO_metal_alpha_preserved":True,"outside_gold_preserved":preservation,"details":details}
    (OUT/"Soft_Gold_Verification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
