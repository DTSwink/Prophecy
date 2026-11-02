"""Incremental wood-only finish with irregular fibres that survive game scale.

No Blender calls. First execution backs up the CURRENT four atlas files.
Repeated runs rebuild only the wood patch from that immutable backup and
paste it into CURRENT atlases, retaining later work in every other region.
ORM AO, Metallic and Specular alpha stay byte-identical, including inside wood.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear"
TEXTURES = OUT / "Textures"
BACKUP = ROOT / "Saved/Diagnostics/ImperialSpear/BeforeWoodStructure_v1"
BOX = (0, 2048, 2048, 4096)
N = 2048
CIRCUMFERENCE_MM, AXIAL_MM = 100.0, 1570.0
BASE_RGB = (54, 21, 21)
SEED = 27102712
MAJOR_FIBRES = 32
FIBRE_WIDTH_MM = (.80, 1.80)
FIBRE_DEPTH_MM = .055
PORE_WIDTH_MM = (.30, .80)
PORE_DEPTH_MM = .105
MAX_DEPTH_MM = .12
ALBEDO_CONTRAST = 1.7
NORMAL_SLOPE_LIMIT = .45
FILES = {"base": "T_ImperialSpear_BaseColor.png", "orm": "T_ImperialSpear_ORM.png",
         "gl": "T_ImperialSpear_NormalGL.png", "dx": "T_ImperialSpear_NormalDX.png"}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_current():
    manifest_path = BACKUP / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, checksum in manifest.items():
            if file_hash(BACKUP/name) != checksum:
                raise RuntimeError(f"Immutable backup checksum mismatch: {name}")
        return manifest
    if BACKUP.exists():
        raise RuntimeError(f"Incomplete backup exists: {BACKUP}")
    BACKUP.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for name in FILES.values():
        shutil.copy2(TEXTURES/name, BACKUP/name)
        manifest[name] = file_hash(TEXTURES/name)
        if file_hash(BACKUP/name) != manifest[name]:
            raise RuntimeError(f"Backup copy failed: {name}")
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def smooth_field(rng, cells_x, cells_y):
    tiny = rng.integers(0, 256, (cells_y, cells_x), dtype=np.uint8)
    return (np.asarray(Image.fromarray(tiny).resize((N,N), Image.Resampling.BICUBIC), dtype=np.float32)-127.5)/127.5


def fibre_masks(rng):
    fibres, glints, pores = [Image.new("L", (N,N)) for _ in range(3)]
    df, dg, dp = ImageDraw.Draw(fibres), ImageDraw.Draw(glints), ImageDraw.Draw(pores)
    px, py = N/CIRCUMFERENCE_MM, N/AXIAL_MM
    # Unequal, tapered paths have staggered starts/ends, local width changes,
    # wandering bundles and occasional forks; never an even comb of stripes.
    for k in range(MAJOR_FIBRES):
        x = (k+rng.uniform(-.35,1.35))*CIRCUMFERENCE_MM/MAJOR_FIBRES
        start = rng.uniform(-650,220) if k%2 == 0 else rng.uniform(-100,1100)
        length = rng.uniform(650,1950) if k%2 == 0 else rng.uniform(240,950)
        width = rng.uniform(*FIBRE_WIDTH_MM)
        bend, phase = rng.uniform(.25,1.4), rng.uniform(0,math.tau)
        centres, widths = [], []
        for t in np.linspace(0,1,70):
            xx = x+bend*math.sin(t*3.3+phase)+.22*math.sin(t*13+phase*.7)
            yy = start+t*length
            taper = .22+.78*math.sin(math.pi*t)**.45
            ww = width*taper*(.83+.17*math.sin(t*17+phase))
            centres.append((xx,yy)); widths.append(ww)
        fibre_value,glint_value=int(rng.integers(155,235)),int(rng.integers(85,165))
        a,b = sorted(rng.integers(8,62,2))
        if b-a < 10: b=min(69,a+15)
        for wrap in (-CIRCUMFERENCE_MM,0,CIRCUMFERENCE_MM):
            left = [((x+wrap-w*.5)*px,y*py) for (x,y),w in zip(centres,widths)]
            right = [((x+wrap+w*.5)*px,y*py) for (x,y),w in zip(centres,widths)]
            df.polygon(left+list(reversed(right)), fill=fibre_value)
            # Pale fibres occupy separated portions, not a subpixel adjacent
            # dark/light pair that filtering would average into plain brown.
            line = [((centres[j][0]+wrap+width*.9)*px,centres[j][1]*py) for j in range(a,b)]
            dg.line(line, fill=glint_value, width=max(2,round(width*.40*px)), joint="curve")
            if k%4 == 1:
                branch=[]
                for j in range(28,60):
                    t=(j-28)/31
                    branch.append(((centres[j][0]+wrap+math.sin(t*math.pi*.5)*width*1.65)*px,centres[j][1]*py))
                df.line(branch, fill=125, width=max(2,round(width*.32*px)), joint="curve")
    # Elongated open pores break up fibres at a second physical scale. Their
    # lengths and starts are independent, so they do not resemble dotted rows.
    for _ in range(1500):
        x,y=rng.uniform(0,CIRCUMFERENCE_MM),rng.uniform(-10,AXIAL_MM)
        width=rng.uniform(*PORE_WIDTH_MM)
        length=float(np.clip(rng.lognormal(math.log(4.5),.65),1.4,21))
        drift=rng.uniform(-.25,.25)
        polygon=[((x-width*.18)*px,y*py),((x-width*.50)*px,(y+length*.28)*py),
                 ((x+drift-width*.30)*px,(y+length*.85)*py),((x+drift)*px,(y+length)*py),
                 ((x+drift+width*.32)*px,(y+length*.67)*py),((x+width*.45)*px,(y+length*.18)*py)]
        dp.polygon(polygon,fill=int(rng.integers(120,245)))
    convert=lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(.65)),dtype=np.float32)/255
    return convert(fibres),convert(glints),convert(pores)


def make_patch():
    old={}
    for key,name in FILES.items():
        with Image.open(BACKUP/name) as image:
            if image.size != (4096,4096) or image.mode not in ("RGB","RGBA"):
                raise ValueError(f"Unexpected atlas format: {name}")
            old[key]=np.array(image.crop(BOX))
    if old["orm"].shape[2] != 4:
        raise ValueError("Expected ORM with packed specular alpha")
    rng=np.random.default_rng(SEED)
    fibres,glints,pores=fibre_masks(rng)
    bundles=smooth_field(rng,42,10)
    fine=smooth_field(rng,330,95)
    # Retain a subdued component of the existing fine grain, while replacing
    # the previously dominant evenly spaced lines with irregular structure.
    old_tone=old["base"][:,:,0].astype(np.float32)/max(1,float(np.median(old["base"][:,:,0])))
    old_tone=np.clip(old_tone-1,-.5,.5)
    tone=1+old_tone*.18+bundles*.085+fine*.025-fibres*.37-pores*.48+glints*.24
    mean_tone=float(tone.mean())
    tone=np.clip(mean_tone+(tone-mean_tone)*ALBEDO_CONTRAST,.50,1.35)
    tone*=mean_tone/float(tone.mean())
    result={key:pixels.copy() for key,pixels in old.items()}
    result["base"][:,:,:3]=np.rint(np.clip(tone[:,:,None]*np.asarray(BASE_RGB,dtype=np.float32),0,255)).astype(np.uint8)
    roughness=np.clip(.785+bundles*.020+fine*.012+pores*.055-fibres*.012-glints*.020,.72,.85)
    result["orm"][:,:,1]=np.rint(roughness*255).astype(np.uint8)
    height=-np.minimum(MAX_DEPTH_MM,fibres*FIBRE_DEPTH_MM+pores*PORE_DEPTH_MM)+glints*.012
    dy,dx=np.gradient(height,AXIAL_MM/N,CIRCUMFERENCE_MM/N)
    previous=(old["gl"][:,:,:3].astype(np.float32)-128)/127
    nz=np.maximum(previous[:,:,2],.1)
    nx=np.clip(-dx+previous[:,:,0]/nz*.18,-NORMAL_SLOPE_LIMIT,NORMAL_SLOPE_LIMIT)
    ny=np.clip(dy+previous[:,:,1]/nz*.18,-NORMAL_SLOPE_LIMIT,NORMAL_SLOPE_LIMIT)
    inv=1/np.sqrt(nx*nx+ny*ny+1)
    normal=np.rint(np.clip(np.stack((nx*inv,ny*inv,inv),-1)*127+128,0,255)).astype(np.uint8)
    result["gl"][:,:,:3]=normal
    result["dx"][:,:,:3]=normal
    result["dx"][:,:,1]=255-normal[:,:,1]
    for channel in (0,2,3):
        assert np.array_equal(result["orm"][:,:,channel],old["orm"][:,:,channel])
    report={"base_median_srgb":np.median(result["base"][:,:,:3],axis=(0,1)).tolist(),
            "roughness_min_mean_max":[float(roughness.min()),float(roughness.mean()),float(roughness.max())],
            "physical_height_min_max_mm":[float(height.min()),float(height.max())],
            "normal_lateral_slope_limit":NORMAL_SLOPE_LIMIT,
            "wood_ao_metal_specular_preserved":True}
    return result,report


def outside_hash(image):
    digest=hashlib.sha256()
    for top in range(0,4096,128):
        if top<2048:
            digest.update(image.crop((0,top,4096,top+128)).tobytes())
        else:
            digest.update(image.crop((2048,top,4096,top+128)).tobytes())
    return digest.hexdigest()


def main():
    originals=backup_current()
    generated,details=make_patch()
    temporary,preservation=[],{}
    try:
        for key,name in FILES.items():
            # Crucially, the destination starts from CURRENT files, not the
            # backup. Rerunning cannot restore stale gold/body/silk changes.
            with Image.open(TEXTURES/name) as source:
                image=source.copy()
            if image.size!=(4096,4096) or image.mode!=Image.fromarray(generated[key]).mode:
                raise ValueError(f"Current atlas format changed: {name}")
            before=outside_hash(image)
            patch=generated[key].copy()
            if key=="orm":
                current=np.array(image.crop(BOX))
                for channel in (0,2,3):
                    patch[:,:,channel]=current[:,:,channel]
                assert np.array_equal(patch[:,:,[0,2,3]],current[:,:,[0,2,3]])
            image.paste(Image.fromarray(patch),BOX)
            after=outside_hash(image)
            assert before==after,f"Pixels outside wood changed: {name}"
            preservation[name]={"before_sha256":before,"after_sha256":after,"unchanged":True}
            path=TEXTURES/(name+".wood-structure-tmp.png")
            image.save(path,compress_level=3)
            temporary.append((path,TEXTURES/name))
            del image
        for source,destination in temporary:
            source.replace(destination)
    finally:
        for path,_ in temporary:
            path.unlink(missing_ok=True)
    report={"status":"irregular wood structure generated","backup":str(BACKUP),"original_files":originals,
            "region":list(BOX),"seed":SEED,"circumference_mm":CIRCUMFERENCE_MM,"axial_span_mm":AXIAL_MM,
            "major_fibres":MAJOR_FIBRES,"fibre_width_mm":list(FIBRE_WIDTH_MM),"fibre_depth_mm":FIBRE_DEPTH_MM,
            "albedo_contrast":ALBEDO_CONTRAST,"mean_tone_preserved":True,
            "pore_width_mm":list(PORE_WIDTH_MM),"pore_depth_mm":PORE_DEPTH_MM,"max_depth_mm":MAX_DEPTH_MM,
            "fibre_width_at_reference_resolution_px":[v/.96 for v in FIBRE_WIDTH_MM],
            "protected_pixels":preservation,**details}
    (OUT/"Wood_Structure_Verification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
