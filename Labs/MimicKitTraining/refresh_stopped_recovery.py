"""Recover available replay/evaluation history without starting a stopped GPU."""
import io,json,sys,zipfile,tempfile,time
from pathlib import Path
import deploy_limp_floor as d
from bridge import publish_rollout
from replay import convert
from dashboard import scalars
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary

class RemoteZip(io.RawIOBase):
    def __init__(self,client,key,size):self.client,self.key,self.size,self.pos=client,key,size,0
    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,size=-1):
        end=self.size if size<0 else min(self.size,self.pos+size)
        if end<=self.pos:return b''
        stream=self.client.get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=self.key,Range=f'bytes={self.pos}-{end-1}')['Body']
        try:data=stream.read()
        finally:stream.close()
        if len(data)!=end-self.pos:raise IOError('Incomplete archive range')
        self.pos=end;return data

def main():
    name=json.loads((d.OUT/'active_run.json').read_text())['run']
    assert name=='20261020_193455_uefn_limp_floor_512'
    client=d.cloud.s3()
    local=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name)
    debug=local/'debug';geom=json.loads((d.OUT/'geometry.json').read_text())
    manifest=json.loads((d.OUT/(name+'-dashboard.json')).read_text())
    target=Path(manifest['output'])/manifest['runs'][0]['name']
    seen={(tag,e.step) for tag,events in scalars(target).items() for e in events}
    inventory=json.loads((d.OUT/'refresh-persistent-inventory.json').read_text())
    latest=max(int(p.stem.split('_')[-1]) for p in debug.glob('rollout_step_*.json'))
    items=[x for x in inventory if '/checkpoint_' in x['key'] and int(Path(x['key']).stem.split('_')[1])>latest]
    items.sort(key=lambda x:x['key'])
    records=[];writer=EventFileWriter(str(target))
    try:
        for item in items:
            with zipfile.ZipFile(RemoteZip(client,item['key'],item['bytes'])) as z:
                evaluation=json.loads(z.read('evaluation.json'));raw=z.read('replay.npz')
                with tempfile.TemporaryDirectory() as tmp:
                    p=Path(tmp)/'replay.npz';p.write_bytes(raw)
                    payload=convert(p,geom,'mimickit_'+name)
                publish_rollout(debug,payload)
                for filename,data in [('replay.npz',raw),('evaluation.json',json.dumps(evaluation).encode())]:
                    p=local/filename;t=p.with_suffix('.refresh');t.write_bytes(data);t.replace(p)
            meta=evaluation['replay'];step=meta['samples'];wall=meta['generated_unix']
            # Only actual saved evaluation aggregates, never substitute sampled
            # replay outcomes for the missing full-batch training failure counts.
            values={'episode/test_seconds':evaluation['mean_ep_len']/30,'reward/test':evaluation['mean_return']}
            added=[]
            for tag,value in values.items():
                if (tag,step) in seen:continue
                writer.add_event(Event(wall_time=wall,step=step,summary=Summary(value=[Summary.Value(tag=tag,simple_value=value)])))
                seen.add((tag,step));added.append(tag)
            records.append(dict(iteration=payload['step'],samples=step,tags=added,source=item['key']))
            print('Recovered replay/evaluation',payload['step'],flush=True)
        writer.flush()
    finally:writer.close()
    (debug/'training.active.json').unlink(missing_ok=True)
    report=dict(run=name,recovered=records,training_event_gap_remaining=True,pod_restarted=False,updated_unix=time.time())
    (d.OUT/'refresh-stopped-recovery-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(recovered_captures=len(records),latest=records[-1]['iteration'] if records else latest)))

if __name__=='__main__':main()
