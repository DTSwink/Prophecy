"""Dedicated housing UV patch with chased borders beside the actual S relief.

This texture-only pass keeps the original gold region's upper half as plain
metal and uses its lower half for the casting. The Blender caller remaps other
gold UVs to U.5..75/V.75..1 and the housing to U.5..75/V.5..75 using world
X[-.06,.06] and Z[1.64,1.77]. No mesh or Blender operation is performed here.
All pixels outside gold (2048,0)-(3072,2048) are preserved exactly.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Exports/ImperialSpear"
TEXTURES = OUT / "Textures"
BACKUP = ROOT / "Saved/Diagnostics/ImperialSpear/BeforeCastBodyAtlas_v1"
GOLD = (2048, 0, 3072, 2048)
PLAIN = (2048, 0, 3072, 1024)
BODY = (2048, 1024, 3072, 2048)
SIZE = 1024
X_MIN, X_MAX, Z_MIN, Z_MAX = -.06, .06, 1.64, 1.77
REF_SCALE = .00096
WIDTH_SCALE = 1.15
EDGE_OFFSET_MM = .60
STROKE_MM = 1.4
DEPTH_MM = .30
LIP_MM = .12
RASTER_PIXELS_PER_MM = 16
FILES = {"base": "T_ImperialSpear_BaseColor.png", "orm": "T_ImperialSpear_ORM.png",
         "gl": "T_ImperialSpear_NormalGL.png", "dx": "T_ImperialSpear_NormalDX.png"}

# Exact guide and width knots from rebuild_reference_gold.py. Geometry uses
# five Catmull-Rom samples per span, plus the last point:101 samples total.
GUIDE = [(563,318),(565,316),(568,319),(566,324),(561,325),(556,322),(553,316),
         (552,309),(555,301),(560,297),(568,296),(575,300),(579,308),(583,321),
         (588,333),(594,338),(601,338),(607,334),(610,329),(607,326),(604,327)]
WIDTH_KNOTS = [(0,1.4),(.20,3.2),(.35,6.5),(.48,9.5),(.64,8),(.80,5.5),(.92,3.4),(1,1.1)]


def width_at(u):
    for (a, x), (b, y) in zip(WIDTH_KNOTS, WIDTH_KNOTS[1:]):
        if a <= u <= b:
            t = (u-a)/(b-a)
            return x*(1-t)+y*t
    return WIDTH_KNOTS[-1][1]

def arch_factor(u):
    if u < .28 or u > .72: return 1.0
    if u < .42: return 1 + .25*(u-.28)/.14
    if u > .58: return 1 + .25*(.72-u)/.14
    return 1.25


def reference_to_world(p):
    ax, ay = .798, .603
    norm = math.hypot(ax, ay)
    ax, ay = ax/norm, ay/norm
    dx, dy = p[0]-172, p[1]-9
    return ((dx*ay-dy*ax)*REF_SCALE, 2.2-(dx*ax+dy*ay)*REF_SCALE)


def border_paths():
    guide = np.asarray(GUIDE, dtype=np.float64)
    points = []
    for i in range(len(guide)-1):
        a,b,c,d = guide[max(0,i-1)], guide[i], guide[i+1], guide[min(len(guide)-1,i+2)]
        for j in range(5):
            t = j/5
            points.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    points.append(guide[-1])
    assert len(points) == 101
    paths = [[], []]
    for i,p in enumerate(points):
        tangent = points[min(i+1,100)]-points[max(i-1,0)]
        tangent /= np.linalg.norm(tangent)
        normal = np.array((-tangent[1], tangent[0]))
        half_width_px = width_at(i/100)*WIDTH_SCALE*arch_factor(i/100)*.5
        offset_px = half_width_px+EDGE_OFFSET_MM/(REF_SCALE*1000)
        for target, sign in zip(paths, (-1,1)):
            x,z = reference_to_world(p+normal*sign*offset_px)
            target.append(((x-X_MIN)*1000, (Z_MAX-z)*1000))
    return paths


def cut_masks():
    ppm = RASTER_PIXELS_PER_MM
    size = (round((X_MAX-X_MIN)*1000*ppm), round((Z_MAX-Z_MIN)*1000*ppm))
    cut, lip = Image.new("L",size), Image.new("L",size)
    dc, dl = ImageDraw.Draw(cut), ImageDraw.Draw(lip)
    paths = border_paths()
    for points in paths:
        mapped = [(x*ppm,y*ppm) for x,y in points]
        dl.line(mapped, fill=255, width=round((STROKE_MM+2*LIP_MM)*ppm), joint="curve")
        # Nested negative-height strokes make actual tangent-normal walls.
        # Their union is safe even where the inner spiral overlaps itself.
        for width,value in ((STROKE_MM,75),(STROKE_MM*.78,180),(STROKE_MM*.55,255)):
            dc.line(mapped, fill=value, width=max(1,round(width*ppm)), joint="curve")
    cut = np.asarray(cut.resize((SIZE,SIZE),Image.Resampling.LANCZOS),dtype=np.float32)/255
    lip = np.asarray(lip.resize((SIZE,SIZE),Image.Resampling.LANCZOS),dtype=np.float32)/255
    return cut,np.clip(lip-cut*1.7,0,1),paths


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def backup():
    manifest_path = BACKUP/"manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name,checksum in manifest.items():
            if file_hash(BACKUP/name) != checksum:
                raise RuntimeError(f"Immutable backup checksum mismatch: {name}")
        return manifest
    if BACKUP.exists():
        raise RuntimeError(f"Incomplete backup: {BACKUP}")
    BACKUP.mkdir(parents=True,exist_ok=False)
    manifest = {}
    for filename in FILES.values():
        shutil.copy2(TEXTURES/filename,BACKUP/filename)
        manifest[filename] = file_hash(TEXTURES/filename)
        if manifest[filename] != file_hash(BACKUP/filename):
            raise RuntimeError(f"Backup verification failed: {filename}")
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def protected_hash(image):
    digest = hashlib.sha256()
    for top in range(0,4096,128):
        bottom = min(top+128,4096)
        digest.update(image.crop((0,top,2048,bottom)).tobytes())
        digest.update(image.crop((3072,top,4096,bottom)).tobytes())
        if top >= 2048:
            digest.update(image.crop((2048,top,3072,bottom)).tobytes())
    return digest.hexdigest()


def patches():
    plain = {}
    for key,filename in FILES.items():
        with Image.open(BACKUP/filename) as im:
            plain[key] = np.array(im.crop(GOLD).resize((SIZE,SIZE),Image.Resampling.LANCZOS))
    if plain["orm"].shape[2] != 4:
        raise ValueError("ORM must already contain packed specular alpha from add_reference_specular.py")
    plain["orm"][:,:,3] = 128
    body = {key:pixels.copy() for key,pixels in plain.items()}
    cut,lip,paths = cut_masks()
    tone = 1-cut*.75+lip*.055
    body["base"][:,:,:3] = np.rint(np.clip(plain["base"][:,:,:3].astype(np.float32)*tone[:,:,None],0,255)).astype(np.uint8)
    roughness = plain["orm"][:,:,1].astype(np.float32)/255
    body["orm"][:,:,0] = np.rint(plain["orm"][:,:,0].astype(np.float32)*(1-cut*.16)).astype(np.uint8)
    body["orm"][:,:,1] = np.rint(np.clip(roughness+cut*.15-lip*.045,.25,.70)*255).astype(np.uint8)
    body["orm"][:,:,2] = np.rint(plain["orm"][:,:,2].astype(np.float32)*(1-cut*.10)).astype(np.uint8)
    body["orm"][:,:,3] = 128
    height = -DEPTH_MM*cut
    dy,dx = np.gradient(height,(Z_MAX-Z_MIN)*1000/SIZE,(X_MAX-X_MIN)*1000/SIZE)
    old = (plain["gl"][:,:,:3].astype(np.float32)-128)/127
    nz = np.maximum(old[:,:,2],.15)
    nx = np.clip(-dx+old[:,:,0]/nz,-1.3,1.3)
    ny = np.clip(dy+old[:,:,1]/nz,-1.3,1.3)
    inv = 1/np.sqrt(nx*nx+ny*ny+1)
    normal = np.rint(np.clip(np.stack((nx*inv,ny*inv,inv),-1)*127+128,0,255)).astype(np.uint8)
    body["gl"][:,:,:3] = normal
    body["dx"][:,:,:3] = normal
    body["dx"][:,:,1] = 255-normal[:,:,1]
    return plain,body,paths


def main():
    originals = backup()
    plain,body,paths = patches()
    temporary,preservation = [],{}
    try:
        for key,filename in FILES.items():
            with Image.open(TEXTURES/filename) as source:
                if source.size != (4096,4096) or source.mode not in ("RGB","RGBA"):
                    raise ValueError(f"Unexpected atlas format: {filename}")
                image = source.copy()
            before = protected_hash(image)
            image.paste(Image.fromarray(plain[key]),PLAIN)
            image.paste(Image.fromarray(body[key]),BODY)
            after = protected_hash(image)
            assert before == after,f"Outside-gold pixels changed: {filename}"
            preservation[filename] = {"before_sha256":before,"after_sha256":after,"unchanged":True}
            path = TEXTURES/(filename+".cast-body-tmp.png")
            image.save(path,compress_level=3)
            temporary.append((path,TEXTURES/filename))
            del image
        for source,destination in temporary:
            source.replace(destination)
    finally:
        for path,_ in temporary:
            path.unlink(missing_ok=True)
    report = {"status":"cast-body border atlas generated","backup":str(BACKUP),"original_files":originals,
              "plain_pixels":list(PLAIN),"body_pixels":list(BODY),"housing_world_x_m":[X_MIN,X_MAX],"housing_world_z_m":[Z_MIN,Z_MAX],
              "guide_samples":101,"width_multiplier":WIDTH_SCALE,"offset_beyond_relief_edge_mm":EDGE_OFFSET_MM,
              "stroke_width_mm":STROKE_MM,"depth_mm":DEPTH_MM,"burnished_lip_mm":LIP_MM,
              "floor_albedo_reduction":.75,"local_arch_width_multiplier":1.25,"orm_specular_alpha":128,"geometry_modified":False,
              "border_path_bounds_mm":[[list(np.min(p,axis=0)),list(np.max(p,axis=0))] for p in paths],
              "protected_pixels":preservation}
    (OUT/"Cast_Body_Atlas_Verification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
