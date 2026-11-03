import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import json,numpy as np
from pathlib import Path
from audit_body_jiggle_24524 import ROOT,OUT,PATH,body_features
from analyze_crawl_jiggle_termination import features as hand_features
BASE=ROOT/'Saved/MimicKitSlowLoco/jiggle-termination-20261103'
def trigger(hand,body):
 high=(((hand[:,:,0]>.08)&(hand[:,:,1]>=4))|((hand[:,:,2]>.8)&(hand[:,:,3]>=4))).any(1)
 high|=((body[:,:9,2]>.8)&(body[:,:9,3]>=4)).any(1)
 high[:30]=False;streak=0
 for f,h in enumerate(high):
  streak=streak+1 if h else 0
  if streak>=6:return f
 return None

def main():
 records=json.loads((BASE/'records.json').read_text());cached=np.load(BASE/'features.npz')
 previous=None;rows=[]
 for i,r in enumerate(records):
  if r['source']!=previous:data=json.loads(Path(r['source']).read_text());previous=r['source']
  prefix='mse_target_' if r['kind']=='reference' else ''
  x=body_features(data[prefix+'positions'][r['row']],data[prefix+'basis'][r['row']])[0]
  rows.append(dict(**r,first_frame=trigger(cached[str(i)],x)))
 data=json.loads(PATH.read_text());exact=[]
 for i,r in enumerate(data['rows']):
  h=hand_features(data['positions'][i],data['basis'][i]);b=body_features(data['positions'][i],data['basis'][i])[0]
  exact.append(dict(row=i,first_frame=trigger(h,b),length=len(b)-1))
 counts={k:dict(rows=sum(r['kind']==k for r in rows),terminated=sum(r['kind']==k and r['first_frame'] is not None for r in rows)) for k in ('normal','one_leg','reference','current')}
 report=dict(passed=all(counts[k]['terminated']==0 for k in ('normal','one_leg','reference')),counts=counts,exact_capture=str(PATH),exact_rows=exact,rows=rows)
 (OUT/'coverage-calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
