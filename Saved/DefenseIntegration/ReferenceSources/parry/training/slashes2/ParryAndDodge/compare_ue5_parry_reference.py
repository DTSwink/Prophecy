"""Strict stage-by-stage Parry reference comparison; never ignores missing keys."""
import argparse
import json
from pathlib import Path
import numpy as np


def read(path):
    if path.suffix == '.npz':
        with np.load(path,allow_pickle=False) as z: return {k:z[k] for k in z.files}
    return {k:np.asarray(v) for k,v in json.loads(path.read_text()).items()}


def compare(expected,actual,prefix='',atol=1e-5,rtol=1e-5):
    keys=sorted(k for k in expected if k.startswith(prefix))
    if not keys: raise ValueError('No reference keys match prefix')
    errors=[];maxima={}
    for key in keys:
        if key not in actual:
            errors.append(dict(key=key,error='missing'));continue
        a,b=np.asarray(actual[key]),np.asarray(expected[key])
        if a.shape!=b.shape:
            errors.append(dict(key=key,error='shape',actual=list(a.shape),expected=list(b.shape)));continue
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            errors.append(dict(key=key,error='nonfinite'));continue
        delta=np.abs(a.astype(np.float64)-b.astype(np.float64))
        maxima[key]=float(delta.max(initial=0))
        if not np.allclose(a,b,atol=atol,rtol=rtol):
            i=np.unravel_index(int(delta.argmax()),delta.shape)
            errors.append(dict(key=key,error='values',max_abs=maxima[key],index=list(map(int,i)),
                actual=float(a[i]),expected=float(b[i])))
    return dict(passed=not errors,keys_checked=len(keys),scope=prefix or 'all',
        atol=atol,rtol=rtol,max_abs_by_key=maxima,failures=errors)


def self_test():
    ref={'frame/002/network/input':np.array([[1.,2.]]),'trajectory/positions':np.zeros((1,2,3))}
    assert compare(ref,ref)['passed']
    assert not compare(ref,{})['passed']
    assert not compare(ref,{**ref,'trajectory/positions':np.zeros((2,3))})['passed']
    assert not compare(ref,{**ref,'trajectory/positions':np.ones((1,2,3))})['passed']
    assert not compare(ref,{**ref,'trajectory/positions':np.full((1,2,3),np.nan)})['passed']
    assert compare(ref,{'frame/002/network/input':ref['frame/002/network/input']},'frame/002/') ['passed']
    try: compare(ref,ref,'absent/')
    except ValueError: pass
    else: raise AssertionError('Empty selection must fail')
    return dict(passed=True,tests=7,scope='comparison utility, NOT Unreal execution')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path);p.add_argument('--candidate',type=Path)
    p.add_argument('--prefix',default='');p.add_argument('--atol',type=float,default=1e-5);p.add_argument('--rtol',type=float,default=1e-5)
    p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test: report=self_test()
    else:
        if a.reference is None or a.candidate is None: p.error('reference and candidate required')
        report=compare(read(a.reference),read(a.candidate),a.prefix,a.atol,a.rtol)
    print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
