"""Generate a disposable cache variant; never edits the production solver."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def generate():
 source=(ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text()
 source=source.replace('retry=False):','retry=False,shared_rows=False,shared_fallback=False):',1)
 marker='w,lane=wp.tid();dt=p.dt[0]'
 source=source.replace(marker,marker+'''
        eligible=p.ncontact[w]<=8 and p.nlimit[w]<=16
        if p.manifold.enabled:eligible=eligible and p.manifold.count[w]<=8
        if wp.static(shared_rows):
            if not eligible:return
        if wp.static(shared_fallback):
            if eligible:return''',1)
 before='''        if wp.static(shared_rows):
            cached_j=wp.tile_load(p.J[w],shape=(8,3,nv),storage='shared')
            cached_lj=wp.tile_load(p.limit_J[w],shape=(16,nv),storage='shared')
            cached_sj=wp.tile_load(p.manifold.J[w],shape=(8,3,nv),storage='shared')
'''
 source=source.replace('        converged=bool(False)',before+'        converged=bool(False)',1)
 begin=source.index('            for it in range(iterations):')
 end=source.index('            changed=bool(False)',begin)
 loop=source[begin:end]
 arrays={
  'p.J[w,c,0]':('cached_j','(c,0)'),
  'p.J[w,c,1]':('cached_j','(c,1)'),
  'p.J[w,c,2]':('cached_j','(c,2)'),
  'p.limit_J[w,c]':('cached_lj','(c,)'),
  'p.manifold.J[w,g,2]':('cached_sj','(g,2)'),
  'p.response[w,c,0]':('cached_r','(c,0)'),
  'p.response[w,c,1]':('cached_r','(c,1)'),
  'p.response[w,c,2]':('cached_r','(c,2)'),
  'p.limit_response[w,c]':('cached_lr','(c,)'),
  'p.manifold.response[w,g,2]':('cached_sr','(g,2)'),
 }
 lines=[]
 for line in loop.splitlines():
  changed=False
  for array,(cache,offset) in arrays.items():
   old=f'wp.tile_load({array},shape=(nv,))'
   if old in line:
    indent=line[:len(line)-len(line.lstrip())]
    lines.extend((indent+'if wp.static(shared_rows):',indent+'    '+line.lstrip().replace(old,f'wp.tile_view({cache},offset={offset})'),indent+'else:',indent+'    '+line.lstrip()))
    changed=True;break
  if not changed:lines.append(line)
 before_loop='''            if wp.static(shared_rows):
                cached_r=wp.tile_load(p.response[w],shape=(8,3,nv),storage='shared')
                cached_lr=wp.tile_load(p.limit_response[w],shape=(16,nv),storage='shared')
                cached_sr=wp.tile_load(p.manifold.response[w],shape=(8,3,nv),storage='shared')
'''
 source=source[:begin]+before_loop+'\n'.join(lines)+'\n'+source[end:]
 path=ROOT/'Saved/MimicKitEquipment/floor-recovery/block_contact_shared_candidate.py'
 path.write_text(source)
 return path

if __name__=='__main__':print(generate())
