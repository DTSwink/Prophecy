"""Validate all-point manifold grouping for the original and larger contact sets."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitCrawl/package/assets/MimicKitTransfer'))
import numpy as np,warp as wp
from contact_manifolds_gpu import allocate,group_contacts

def main():
    wp.init();device='cuda:0';rng=np.random.default_rng(71);reports=[]
    for size in (1,2,4,5,8,16):
        positions=rng.uniform(-.1,.1,(size,3)).astype(np.float32);positions[:,2]=0
        frame=np.tile(np.array([[0,0,1],[1,0,0],[0,1,0]],np.float32),(size,1,1))
        p=allocate(1,16,3,device);p.contact_ids.assign(np.arange(16,dtype=np.int32)[None])
        error=wp.zeros(1,dtype=int,device=device)
        wp.launch(group_contacts,dim=1,inputs=[p,wp.array([size],dtype=int,device=device),
            wp.ones((1,16),device=device),wp.array(np.tile([0,1],(size,1)),dtype=wp.vec2i,device=device),
            wp.array(positions,dtype=wp.vec3,device=device),wp.array(frame,dtype=wp.mat33,device=device),error],device=device)
        assert not error.numpy().any()
        assert p.count.numpy()[0]==1 and p.size.numpy()[0,0]==size
        np.testing.assert_allclose(p.center.numpy()[0,0],positions.mean(0),atol=2e-8)
        np.testing.assert_allclose(p.radius.numpy()[0,:size],np.linalg.norm(positions-positions.mean(0),axis=-1),atol=3e-8)
        np.testing.assert_array_equal(p.group.numpy()[0,:size],0)
        reports.append(dict(points=size,centroid_and_radii_verified=True,all_points_retained=True))
    (ROOT/'Saved/MimicKitCrawl/contact-capacity-test.json').write_text(json.dumps(dict(passed=True,cases=reports),indent=2))
    print(json.dumps(dict(passed=True,point_counts=[1,2,4,5,8,16])))

if __name__=='__main__':main()
