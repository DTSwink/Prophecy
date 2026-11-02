"""Build exact opaque PHAT before/after review for all eight slow motions."""
import json,pickle
import numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry,ROOT
OUT=ROOT/'Saved/MimicKitSlowLoco/contact-cleanup-20261031'
NAMES=['crawl','crawl_idle','agonising','agonising_idle','limpL','limpR','lying','sitting']
def main():
 OUT.mkdir(exist_ok=True);g=Geometry();clips=[]
 for name in NAMES:
  original=OUT/'before'/(name+'.pkl')
  if not original.exists():original=ROOT/'Saved/MimicKitSlowLoco/package/motions'/(name+'.pkl')
  motion=pickle.loads(original.read_bytes())
  candidate=OUT/'candidates'/(name+'.pkl');new=pickle.loads(candidate.read_bytes()) if candidate.exists() else motion
  variants={}
  for key,m in [('before',motion),('after',new)]:
   rows=[]
   for f in m['frames']:
    p,r=g.fk(f);g.set_pose(p,r)
    rows.append(dict(p=np.round(g.d.geom_xpos,7).tolist(),q=np.round(R.from_matrix(g.d.geom_xmat.reshape(-1,3,3)).as_quat(),7).tolist(),bottom=np.round(g.floors(),7).tolist(),root=f[:3].tolist()))
   variants[key]=dict(fps=m['fps'],rows=rows)
  clips.append(dict(name=name,variants=variants))
 report={p.stem:json.loads(p.read_text()) for p in (OUT/'candidates').glob('*.json')}
 deployed=OUT.parent/'reference-upper-deploy-20261101/deployment-verified.json'
 if not deployed.exists():deployed=OUT.parent/'contact-cleanup-deploy-20261031/deployment-verified.json'
 deployment=json.loads(deployed.read_text()) if deployed.exists() else None
 if deployment and any(deployment.get('motion_hashes',{}).get(n)!=report[n].get('candidate_sha256') for n in NAMES):deployment=None
 (OUT/'data.json').write_text(json.dumps(dict(geometry=g.gs,clips=clips,report=report,deployment=deployment),separators=(',',':')))
 for n in ['index.html','view.js']:(OUT/n).write_text((Path(__file__).parent/'contact_viewer'/n).read_text(encoding='utf-8'),encoding='utf-8')
 print(OUT)
if __name__=='__main__':main()
