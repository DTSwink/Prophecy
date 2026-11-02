"""Exact Fab render surface, with the existing cm conversion and seated cork.

The intact asset uses the original surface. Watertight cavity/boolean geometry
is only needed by the precomputed glass fragments, not by thin-glass rendering.
"""
import json,struct
from pathlib import Path
import numpy as np

def source_mesh():
    data=Path(__file__).with_name('Source').joinpath('MilkBottle.glb').read_bytes()
    length=struct.unpack_from('<I',data,12)[0];gltf=json.loads(data[20:20+length]);raw=data[28+length:]
    def read(index):
        a=gltf['accessors'][index];view=gltf['bufferViews'][a['bufferView']]
        width={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
        return np.frombuffer(raw,dtype={5126:'<f4',5123:'<u2',5125:'<u4'}[a['componentType']],
            count=a['count']*width,offset=view.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,width).copy()
    def mesh(index):
        p=gltf['meshes'][index]['primitives'][0];a=p['attributes']
        return read(a['POSITION']).astype(float),read(a['NORMAL']).astype(float),read(a['TEXCOORD_0']),read(p['indices']).reshape(-1,3)
    v,n,uv,t=mesh(1);scale=26/np.ptp(v[:,1]);v[:,1]-=v[:,1].min();v*=scale
    v=v[:,[0,2,1]];n=n[:,[0,2,1]]
    cv,cn,cu,ct=mesh(0);cv*=gltf['nodes'][0]['scale'][0]/gltf['nodes'][1]['scale'][0]*scale
    cv=cv[:,[0,2,1]];cn=cn[:,[0,2,1]]
    cv[:,:2]-=(cv[:,:2].min(axis=0)+cv[:,:2].max(axis=0))/2
    cv[:,2]+=26-cv[:,2].min()-1.2
    # Y/Z handedness conversion followed by UE clockwise raster convention.
    t=t[:,[0,2,1]][:,[1,0,2]];ct=ct[:,[0,2,1]][:,[1,0,2]]
    vertices=np.vstack([np.c_[v,n,uv],np.c_[cv,cn,cu]])
    triangles=np.vstack([t,ct+len(v)])
    return {'name':'SM_OilBottle','vertices':vertices.tolist(),
            'triangles':triangles.reshape(-1).tolist(),'slots':[0]*len(t)+[1]*len(ct)}

if __name__=='__main__':
    out=Path(__file__).resolve().parents[2]/'Saved/Diagnostics/Oil/Bottle/Shell'
    out.mkdir(parents=True,exist_ok=True)
    mesh=source_mesh();(out/'source.json').write_text(json.dumps(mesh,separators=(',',':')))
    print('Exact Fab surface:',len(mesh['vertices']),'vertices,',len(mesh['triangles'])//3,'triangles')
