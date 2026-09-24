"""Replay the viewer's 30-request seed with the staged checkpoint; emit native audit inputs."""
import json
import argparse
from pathlib import Path
from dataclasses import replace
import ExportProphecySlashPolicy as old
from ExportProphecySlashPolicy import torch, slash
import generate_latest_chain_variants as g


def main():
    torch.set_num_threads(1)
    parser=argparse.ArgumentParser()
    parser.add_argument('--staging',type=Path,default=old.PROJECT/'Saved/Slash123793')
    dest=parser.parse_args().staging.resolve()
    meta=json.loads((dest/'prophecy_slash_runtime.json').read_text())
    saved,recipe,lower,upper=slash.load_slash2_rollout_session(Path(meta['checkpoint_path']),torch.device('cpu'))
    recipe=replace(recipe,predictive_pin_checkpoint=None)
    manifest=json.loads((g.chain.SOURCE_DATASET/'dataset_manifest.json').read_text())
    g.SEED=2026092211;g.OUT=dest/'chain';g.OUT.mkdir(exist_ok=True)
    _,slots=g.chain.pick_candidates(manifest,g.SEED,30,4)
    rows=[r for slot in slots for r in slot]
    paths=[Path(r['runtimeSourcePath']) for r in rows]
    for p,r in zip(paths,rows):assert old.sha(p)==r['runtimeSourceSha256']
    rt=slash.load_runtime(recipe,torch.device('cpu'),attack_paths=paths,inference_only=True,prepared_corpus_cache_enabled=False)
    records={}
    original=g.chain.rollout_segment
    ids=torch.zeros(1,dtype=torch.long);frame=torch.ones_like(ids)
    def record(runtime, lower, upper, state, source_row, carrier_row, target, post_hit_tail, max_wait, record_states=False):
        entry=state
        final,frames,hit=original(runtime,lower,upper,state,source_row,carrier_row,target,post_hit_tail,max_wait,True)
        inputs=[];outputs=[];armed=hit_latch=torch.zeros(1)
        for f in frames:
            lr=lambda x,h:slash.lower_hybrid_state_to_root(rt.lower_store,ids,frame,x,target,h)
            ur=lambda x,h:slash.upper_hybrid_state_to_root(rt.lower_store,ids,frame,x,target,h)
            value=torch.cat((lr(entry.previous_lower,entry.previous_heading),lr(entry.current_lower,entry.current_heading),
                ur(entry.previous_upper,entry.previous_heading),ur(entry.current_upper,entry.current_heading),target,
                rt.attacks.labels[source_row:source_row+1],armed[:,None],hit_latch[:,None]),-1)
            output=torch.cat((lr(f['lower'],entry.current_heading),ur(f['upper'],entry.current_heading),
                f['pos'].flatten(1),f['rot'].flatten(1),f['armed'][:,None],f['hit'][:,None],f['gates'],f['pin']),-1)
            inputs.append(value[0].tolist());outputs.append(output[0].tolist())
            armed,hit_latch=f['armed'],f['hit'];entry=f['continuation_state']
        records[source_row]=(inputs,outputs)
        return final,frames,hit
    g.chain.rollout_segment=record
    colors=dict(zip(sorted({r['clip'] for r in manifest['rows']}),g.COLORS))
    tails=g.chain.dataset100.original_gt_post_hit_tails(Path(recipe.gt_dir).resolve())
    with rt.policy_context(),torch.inference_mode():
        result,_=g.make_chain(rt,lower,upper,slots,tails,'complete',saved['step'],colors)
        inputs=[];outputs=[]
        for slot,segment in enumerate(result['segments']):
            a,b=records[slot*4+segment['candidateAlternative']]
            inputs.extend(a);outputs.extend(b)
        fixture=dict(inputs=inputs,expected=outputs,four_step_oracle=outputs,segments=result['segments'])
        (dest/'chain_audit.json').write_text(json.dumps(fixture))
        geometry=json.loads((dest/'prophecy_slash_native.json').read_text())
        root,rotation,_,_=rt.lower_store.root_state(ids,frame)
        # Network clamp geometry must be identical; only the stationary carrier may differ.
        for key,source in [('lower_geometry',rt.lower_fk_geometry),('full_geometry',rt.full_fk_geometry)]:
            for name in ('local_offsets','ik_toe_offsets','ik_limb_lengths'):
                if name in source:
                    expected=torch.tensor(geometry[key][name])
                    assert torch.allclose(expected,source[name][0],atol=1e-6,rtol=0),(key,name)
        geometry.update(root_position=root[0].tolist(),root_rotation=rotation[0].tolist(),
            lower_geometry={k:v[0].tolist() for k,v in rt.lower_fk_geometry.items()},
            full_geometry={k:v[0].tolist() for k,v in rt.full_fk_geometry.items()},
            root_features=rt.lower_store.get_input_root_features(ids,frame)[0].tolist(),startup_expected=outputs[0])
        (dest/'source_native_geometry.json').write_text(json.dumps(geometry))
        print('NATIVE_CHAIN_READY',len(inputs),len(result['segments']),flush=True)


if __name__=='__main__':main()
