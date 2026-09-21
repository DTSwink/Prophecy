from pathlib import Path
s=Path('Saved/Diagnostics/ExperimentSidePlane.py').read_text()
s=s.replace('    if A[2]>0 and np.dot(N*q-T,pole)>np.dot(desired,pole):desired=N*q-T\n','')
exec(s)
