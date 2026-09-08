"""Read-only handoff -> independent root-state/native audit fixtures.

Only Saved/SlashChain is written. Training, weights and handoff remain immutable.
"""
import json
import sys
from pathlib import Path
from ExportProphecySlashPolicy import PROJECT, sha, slash, torch, np, SlashStep
from dataclasses import replace

HANDOFF = Path(r"C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260907_good_pt_continuous_random_30_hits_unreal_handoff")

def main():
    torch.set_num_threads(2)
    manifest = json.loads((HANDOFF / "manifest.json").read_text())
    assert sha(HANDOFF / manifest["rolloutFile"]) == manifest["rolloutSha256"]
    assert sha(HANDOFF / "checkpoint/good.pt") == manifest["checkpoint"]["sha256"]
    z = np.load(HANDOFF / manifest["rolloutFile"], allow_pickle=False)
    data = json.loads((HANDOFF / "unreal_interchange.json").read_text())
    source_manifest = json.loads((HANDOFF / "source_dataset_manifest.json").read_text())
    source = next(r for r in source_manifest["rows"] if r["file"] == data["attacks"][0]["sourceFile"])
    _, recipe, lower_nn, upper_nn = slash.load_slash2_rollout_session(HANDOFF / "checkpoint/good.pt", torch.device("cpu"))
    recipe = replace(recipe, predictive_pin_checkpoint=None)
    rt = slash.load_runtime(recipe, torch.device("cpu"), attack_paths=[Path(source["runtimeSourcePath"])], inference_only=True)
    model = SlashStep(rt, lower_nn, upper_nn, 1).eval()
    native = json.loads((PROJECT / "Content/locomotion/NN/prophecy_slash_native.json").read_text())
    print('Carrier root', model.root_pos.tolist(), model.root_rot.tolist(), 'features',model.root_features.tolist(),flush=True)
    print('Native root',native['root_position'], native['root_rotation'],'features',native['root_features'],flush=True)
    outdir = PROJECT / "Saved/SlashChain"
    outdir.mkdir(parents=True, exist_ok=True)
    source_native = dict(native)
    source_native.update(root_position=model.root_pos[0].tolist(),root_rotation=model.root_rot[0].tolist(),
        ground=rt.lower_store.foot_roll_ground_y_tensor.tolist(),
        lower_geometry={k:v[0].tolist() for k,v in rt.lower_fk_geometry.items()},
        full_geometry={k:v[0].tolist() for k,v in rt.full_fk_geometry.items()})
    (outdir / 'source_native_geometry.json').write_text(json.dumps(source_native))
    print('Geometry differences', {section:{k:float(np.max(np.abs(np.array(v)-np.array(native[section][k])))) for k,v in source_native[section].items()} for section in ['lower_geometry','full_geometry']}, 'ground',source_native['ground'],native['ground'],flush=True)
    if '--geometry-only' in sys.argv: return
    with rt.policy_context(), torch.inference_mode():
        pos = torch.from_numpy(z["rollout_global_joint_pos_m"])
        targets = torch.from_numpy(z["target_world_by_frame_m"])
        # Generated state i is expressed in the heading held at i-1, not i.
        # Only the two conditioning states have their own respective headings.
        pelvis_index = data["boneNames"].index("pelvis")
        basis_pos = torch.cat((pos[:2, pelvis_index], pos[1:-1, pelvis_index]), 0)
        heading = slash.target_codec.target_facing_heading(basis_pos, targets)
        root_p = model.root_pos.expand(len(pos), -1)
        root_r = model.root_rot.expand(len(pos), -1, -1)
        lower = slash.target_codec.lower_target_frame_to_root(rt.lower_store,
            torch.from_numpy(z["rollout_lower_state"]), root_p, root_r, targets, heading)
        upper = slash.target_codec.upper_target_frame_to_root(
            torch.from_numpy(z["rollout_upper_state"]), root_p, root_r, targets, heading)
        root_states = torch.cat((lower, upper), -1)
        segments = data["attacks"]
        by_frame = {i:s for s in segments for i in range(s["startFrame"],s["finalFrame"]+1)}
        inputs, expected = [], []
        for i in range(2, len(pos)):
            s = by_frame[i]
            reset = i == s["startFrame"]
            labels = torch.tensor(slash.ATTACK_LABELS[s["family"].lower()])
            latches = torch.zeros(2) if reset else torch.tensor([data["armedLatch"][i-1], data["hitLatch"][i-1]])
            inputs.append(torch.cat((lower[i-2],lower[i-1],upper[i-2],upper[i-1],targets[i],labels,latches)))
            expected.append(torch.cat((root_states[i], pos[i].flatten(), torch.from_numpy(z["rollout_global_rot"][i]).flatten(),
                torch.tensor([data["armedLatch"][i],data["hitLatch"][i],*data["gateProbabilities"][i],*data["pinProbabilities"][i]]))))
        source_steps = slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS
        slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS = 4
        state = inputs[0][None].clone()
        oracle, teacher_oracle, teacher_errors, exact_teacher_errors = [], [], [], []
        for k, values in enumerate(inputs):
            i = k + 2
            state[:,262:270] = values[262:270]
            if i == by_frame[i]["startFrame"]: state[:,270:272] = 0
            result = model(state)
            oracle.append(result[0].tolist())
            if k % 50 == 0: print(f"Python four-step chain {i}/{len(pos)}", flush=True)
            teacher = model(values[None])
            teacher_oracle.append(teacher[0].tolist())
            teacher_errors.append(float(torch.linalg.vector_norm((teacher[0,131:206]-expected[k][131:206]).reshape(25,3),dim=-1).max()))
            slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS = source_steps
            exact_teacher = model(values[None])
            exact_teacher_errors.append(float(torch.linalg.vector_norm((exact_teacher[0,131:206]-expected[k][131:206]).reshape(25,3),dim=-1).max()))
            slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS = 4
            state = torch.cat((state[:,41:82],result[:,:41],state[:,172:262],result[:,41:131],state[:,262:270],result[:,431:433]),-1)
        fixture = {"source_sha256":manifest["rolloutSha256"],"checkpoint_sha256":manifest["checkpoint"]["sha256"],
            "source_frozen_pin_steps":source_steps,"native_pin_steps":4,"bone_names":data["boneNames"],
            "segments":segments,"inputs":[v.tolist() for v in inputs],"expected":[v.tolist() for v in expected],
            "four_step_oracle":oracle,"teacher_oracle":teacher_oracle,"python_teacher_position_errors_m":teacher_errors,
            "source_step_teacher_errors_m":exact_teacher_errors}
        # The audit model uses the source's stationary carrier. Gameplay keeps
        # its own frame; changing the audit frame is not a gameplay modification.
        source_p = model.root_pos[0].numpy(); source_r = model.root_rot[0].numpy()
        fixture['source_root_position'] = source_p.tolist()
        fixture['source_root_rotation'] = source_r.tolist()
        fixture['coordinate_frame'] = 'source_world'
        (outdir / "chain_audit.json").write_text(json.dumps(fixture))
        e = np.array(fixture['expected']); a = np.array(fixture['four_step_oracle'])
        errors = np.linalg.norm((a[:,131:206]-e[:,131:206]).reshape(-1,25,3),axis=-1)
        print(json.dumps({"four_step_vs_source_max_mm":float(errors.max()*1000),"teacher_max_mm":max(teacher_errors)*1000,
            "source_step_teacher_max_mm":max(exact_teacher_errors)*1000,
            "latches_equal":bool(np.array_equal(a[:,431:433],e[:,431:433])),"fixture":str(outdir / 'chain_audit.json')}),flush=True)

if __name__ == "__main__": main()
