"""Independent double-precision check of common-scale friction preconditioning."""
import inspect,json,time,textwrap
from pathlib import Path
import numpy as np
from probe_block_failure import Equations,OUT

class Accelerated(Equations):
    pass

source=textwrap.dedent(inspect.getsource(Equations.contacts))
# Dedented source has four spaces in the method body.
source=source.replace('    for _ in range(iterations):','''    original_diag=self.diag;original_sd=self.sd
    rate=.5 if motor is not None else self.rate
    if motor is None and self.precondition:
        self.diag=self.diag.copy();self.sd=self.sd.copy()
        for c in range(len(self.J)):
            if self.mu[c]<=0:continue
            a=self.J[c,1:]@inverse@self.J[c,1:].T
            norm=np.sqrt(np.outer(self.diag[c,1:],self.diag[c,1:]))
            scale=max(float(np.linalg.eigvalsh(a/norm)[-1]),1e-12)
            self.scales.append(scale)
            self.diag[c,1:]*=scale
        for g in range(len(self.S)):
            self.sd[g]=max(self.S[g]@inverse@self.S[g],1e-12)
    if motor is None:iterations=self.passes
    for _ in range(iterations):''')
source=source.replace('    return v','    self.diag=original_diag;self.sd=original_sd\n    return v')
source=source.replace('value=(value+limit[a])*.5','value=limit[a]+rate*(value-limit[a])')
source=source.replace('t=(t+contact[c,1:])*.5','t=contact[c,1:]+rate*(t-contact[c,1:])')
source=source.replace('value=(value+spin[g])*.5','value=spin[g]+rate*(value-spin[g])')
source=source.replace('value=(value+contact[c,0])*.5','value=contact[c,0]+rate*(value-contact[c,0])')
scope={'np':np};exec(source,scope);Accelerated.contacts=scope['contacts']

def main():
 reports=[]
 for filename in ('contact_first_solver_failure.npz','contact_first_solver_failure_graph.npz'):
  e=Equations(OUT/filename);ref,c,l,s=e.scalar(3000)
  baseline,old=e.block(.5)
  rows=[]
  for rate,precondition,passes in ((1.,False,8),(1.,False,16),(1.,False,32),(1.,False,100),(1.,True,16),(1.,True,32)):
   candidate=Accelerated(OUT/filename);candidate.passes=passes;candidate.scales=[];candidate.rate=rate;candidate.precondition=precondition
   # defect must always be measured through the original equations.
   candidate.defect=lambda v,c,l,s:e.defect(v,c,l,s)
   v,result=candidate.block(.5)
   row=dict(passes=passes,rate=rate,precondition=precondition,error_to_reference=float(abs(v-ref).max()),outer=len(result['history']),
            defect=result['history'][-1],scales=[float(min(candidate.scales)),float(max(candidate.scales))] if candidate.scales else [])
   rows.append(row);print(filename,json.dumps(row),flush=True)
  reports.append(dict(capture=filename,baseline_error=float(abs(baseline-ref).max()),baseline=old['history'][-1],candidates=rows))
 path=Path(__file__).resolve().parents[2]/'Saved/MimicKitEquipment/floor-recovery/contact-preconditioner.json'
 path.write_text(json.dumps(reports,indent=2))

if __name__=='__main__':main()
