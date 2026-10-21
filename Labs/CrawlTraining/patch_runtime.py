"""Add original locked ankle twist support to the isolated crawl runtime only."""
from pathlib import Path

def replace(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)

def patch(package):
    folder=package/'assets/MimicKitTransfer'
    file=folder/'sequential_contact_adapter.py';text=file.read_text()
    text=replace(text,'np.testing.assert_array_equal(self.limit_metadata.modes.numpy(),1)',
        "modes=self.limit_metadata.modes.numpy()\n            assert np.all(modes[:,1:]==1) and np.all((modes[:,0]==1)|(modes[:,0]==2)), 'Only limited swing and limited/locked twist supported'")
    text=replace(text,'limits.angles,m.jnt_qposadr,m.jnt_dofadr,self.limitrows,self.error]',
        'limits.angles,limits.modes,m.jnt_qposadr,m.jnt_dofadr,self.limitrows,self.error]')
    file.write_text(text)
    file=folder/'jolt_limit_directions.py';text=file.read_text()
    text=replace(text,'reference_wxyz:wp.array(dtype=wp.quat),angles:wp.array(dtype=wp.vec3),',
        'reference_wxyz:wp.array(dtype=wp.quat),angles:wp.array(dtype=wp.vec3),modes:wp.array(dtype=wp.vec3i),')
    text=replace(text,'twist_active,swing_active,tg,sg=directions(rotation,angles[index])',
        'effective=angles[index]\n        locked=modes[index][0]==2\n        if locked:effective=wp.vec3(0.,effective[1],effective[2])\n        twist_active,swing_active,tg,sg=directions(rotation,effective)\n        if locked:\n            twist_active=True\n            tg=wp.vec3(1.,0.,0.) # Jolt: current swing X, expressed in child axes')
    text=replace(text,'p.limit_target[w,slot]=0.;p.limit_compliance[w,slot]=0.;p.limit_bilateral[w,slot]=0',
        'p.limit_target[w,slot]=0.;p.limit_compliance[w,slot]=0.;p.limit_bilateral[w,slot]=int(locked and axis==1)')
    file.write_text(text)
    file=folder/'limit_projection_gpu.py';text=file.read_text()
    text=replace(text,"assert row['modes']==[1,1,1]",
        "assert row['modes'] in ([1,1,1],[2,1,1])")
    text=replace(text,"refs[idx]=np.roll(row['reference_wxyz'],-1);angles[idx]=row['limits_rad']",
        "refs[idx]=np.roll(row['reference_wxyz'],-1);angles[idx]=row['limits_rad']\n                if row['modes'][0]==2:angles[idx,0]=0. # Exact locked twist, not a narrow angular interval")
    file.write_text(text)

def patch_contact_capacity(package):
    # All centroid, friction/spin and solver loops already iterate the actual
    # point count. Keep every generated normal row; only lift the four-point
    # admission restriction. No truncation, changed friction or solver tolerance.
    file=package/'assets/MimicKitTransfer/contact_manifolds_gpu.py'
    text=file.read_text()
    text=replace(text,'if p.size[w,g]>4:error[w]=7','if p.size[w,g]>p.contact_ids.shape[1]:error[w]=7')
    file.write_text(text)

if __name__=='__main__':
    import sys
    package=Path(__file__).resolve().parents[2]/'Saved/MimicKitCrawl/package'
    if '--contact-capacity' in sys.argv:patch_contact_capacity(package)
    else:patch(package)
