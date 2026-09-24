"""Stage the no-frozen Slash2 contract; never write training files or live models.

Usage: python ExportCurrentSlashCheckpoint.py CHECKPOINT --output Saved/Slash123793
"""
from pathlib import Path
import argparse
import io
import json
import numpy as np
import ExportProphecySlashPolicy as old
from ExportProphecySlashNetworks import Network
from ExportProphecySlashPolicy import torch, slash, sha, onnx
from slash2_hand_clamp import clean_upper


class Step(old.SlashStep):
    def forward(self, values):
        rt = self.runtime
        prev_l, cur_l = values[:, :41], values[:, 41:82]
        prev_u, cur_u = values[:, 82:172], values[:, 172:262]
        target, labels = values[:, 262:265], values[:, 265:270]
        armed, hit = values[:, 270], values[:, 271]
        pelvis = (cur_l[:, :3].unsqueeze(1) @ self.root_rot).squeeze(1) + self.root_pos
        heading = slash.target_codec.target_facing_heading(pelvis, target)
        to_l = lambda x: slash.lower_root_state_to_hybrid(rt.lower_store, self.ids, self.frame, x, target, heading)
        to_u = lambda x: slash.upper_root_state_to_hybrid(rt.lower_store, self.ids, self.frame, x, target, heading)
        pl, cl, pu, cu = to_l(prev_l), to_l(cur_l), to_u(prev_u), to_u(cur_u)
        zero = torch.zeros_like(armed[:, None])
        raw, _ = self.lower(slash.build_lower_learned_input(cl, None, labels, zero, zero, target))
        delta, pins = slash.split_lower_output(raw)
        nl, pin = slash.clean_lower_hybrid_delta(rt, rt.lower_batched_store, self.ids,
            self.frame, self.frame+1, cl, cl, delta, pins, target, heading)
        cb = slash.base_upper_hybrid_from_lower(rt, self.ids, self.ids, self.frame, cl, target, heading)
        nb = slash.base_upper_hybrid_from_lower(rt, self.ids, self.ids, self.frame+1, nl, target, heading)
        prior = slash.carry_upper_hybrid_deviation(cu, cb, nb)
        delta, probabilities = self.upper(slash.build_upper_learned_input(pu, prior, target, labels, pl, cl, nl, armed, hit))
        nu = slash.clamp_upper_hands(rt, self.ids, slash.clean_upper_state(prior+delta), nl)
        na, nh = slash.advance_phase_latches(armed, hit, probabilities, rt.recipe.gate_threshold)
        pos, rot = slash.hybrid_full_fk_globals(rt, self.ids, self.ids, self.frame+1, nl, nu, target, heading)
        lr = slash.lower_hybrid_state_to_root(rt.lower_store, self.ids, self.frame+1, nl, target, heading)
        ur = slash.upper_hybrid_state_to_root(rt.lower_store, self.ids, self.frame+1, nu, target, heading)
        return torch.cat((lr, ur, pos.flatten(1), rot.flatten(1), na[:, None], nh[:, None], probabilities, pin), -1)


class Cone(torch.nn.Module):
    def __init__(self, rt, checkpoint):
        super().__init__()
        self.module = torch.jit.load(io.BytesIO(checkpoint['pelvis_foot_cone']['program'])).eval()
        offsets = rt.lower_store.ik_toe_offsets.index_select(-2, rt.pelvis_foot_cone_limb_indices)
        self.register_buffer('offsets', offsets.reshape(-1, 2, 3)[:1])

    def forward(self, x):
        return self.module(x[:, :41], x[:, 41:], self.offsets.expand(x.shape[0], -1, -1))


class Upper(torch.nn.Module):
    def __init__(self, rt, network, checkpoint):
        super().__init__()
        self.network = network
        self.clamp = rt.hand_clamp_module
        self.register_buffer('offsets', rt.hand_clamp_offsets[:1])
        self.register_buffer('lengths', rt.hand_clamp_lengths[:1])

    def forward(self, x):
        delta, gates = self.network(x)
        assert gates is not None
        prior = x[:, 90:180]
        candidate = clean_upper(prior+delta)
        candidate = self.clamp(candidate, x[:, 204:213], self.offsets.expand(x.shape[0], -1, -1),
            self.lengths.expand(x.shape[0], -1))
        return torch.cat((candidate-prior, gates), -1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('checkpoint', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    old.CHECKPOINT = args.checkpoint.resolve()
    old.CHECKPOINT_SHA = sha(old.CHECKPOINT)
    rt, legacy, initial, _ = old.prepare(1)
    saved = torch.load(old.CHECKPOINT, map_location='cpu', weights_only=False)
    assert not rt.recipe.frozen_agent_enabled
    assert rt.recipe.calf_foot_clamp_m == .05
    oracle = Step(rt, legacy.lower, legacy.upper, 1).eval()
    traces = {}
    hooks = []
    for key, net in [('lower', legacy.lower), ('upper', legacy.upper)]:
        hooks.append(net.register_forward_hook(lambda m, a, r, key=key: traces.__setitem__(key, a[0].detach().clone())))
    with rt.policy_context(), torch.inference_mode():
        state = initial.clone()
        frames = []
        for i in range(120):
            output = oracle(state)
            if not torch.isfinite(output).all():
                raise RuntimeError(f'Nonfinite source rollout at {i}')
            frames.append(dict(frame=i+2, state=state[0].tolist(), output=output[0].tolist()))
            if i == 0:
                samples = dict(traces)
                target = state[:, 262:265]
                pelvis = (state[:, 41:44].unsqueeze(1) @ oracle.root_rot).squeeze(1)+oracle.root_pos
                heading = slash.target_codec.target_facing_heading(pelvis, target)
                cl = slash.lower_root_state_to_hybrid(rt.lower_store, oracle.ids, oracle.frame, state[:, 41:82], target, heading)
                samples['cone'] = torch.cat((cl, cl), -1)
            state = torch.cat((state[:, 41:82], output[:, :41], state[:, 172:262], output[:, 41:131],
                state[:, 262:270], output[:, 431:433]), -1)
        for h in hooks: h.remove()
        networks = [('cone', Cone(rt, saved), 82, 41), ('lower', Network(legacy.lower, 'lower'), 51, 43),
                    ('upper', Upper(rt, legacy.upper, saved), 217, 92)]
        contract = json.loads((old.PROJECT/'Content/locomotion/NN/prophecy_slash_native.json').read_text())
        contract.update(checkpoint_sha256=old.CHECKPOINT_SHA, transition_schema='slash2_no_frozen_clamped_v1',
            calf_foot_margin_m=.05, pin_full_strength_at=rt.recipe.pin_full_strength_at,
            networks={}, startup_expected=frames[0]['output'])
        # Geometry is exported from the same runtime that produced the oracle.
        contract.update(root_features=oracle.root_features[0].tolist(), root_position=oracle.root_pos[0].tolist(),
            root_rotation=oracle.root_rot[0].tolist(), lower_geometry={k:v[0].tolist() for k,v in rt.lower_fk_geometry.items()},
            full_geometry={k:v[0].tolist() for k,v in rt.full_fk_geometry.items()},
            foot_half_dims=rt.lower_store.foot_roll_foot_half_dims.tolist(), toe_half_dims=rt.lower_store.foot_roll_toe_half_dims.tolist(),
            ground=rt.lower_store.foot_roll_ground_y_tensor.tolist(), lower_limbs=rt.lower_clip.ik_limb_specs,
            full_limbs=rt.full_clip.ik_limb_specs, parents=rt.full_clip.parents_body_list, bone_names=rt.full_clip.body_names)
        import onnxruntime as ort
        report = {}
        for name, model, width, outwidth in networks:
            path = args.output/f'prophecy_slash_{name}.onnx'
            model.eval()
            export_model = torch.jit.script(model) if name == 'cone' else model
            torch.onnx.export(export_model, (samples[name],), str(path), opset_version=18, dynamo=False,
                input_names=['input'], output_names=['output'],
                dynamic_axes={'input':{0:'agents'}, 'output':{0:'agents'}})
            onnx.checker.check_model(onnx.load(path))
            session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
            errors = []
            for batch in (1, 3, 100):
                values = samples[name].expand(batch, -1).contiguous()
                expected = model(values).numpy()
                if name == 'upper':
                    embedded = torch.jit.load(io.BytesIO(saved['hand_clamp']['program'])).eval()
                    delta, _ = legacy.upper(values)
                    exact = embedded(clean_upper(values[:,90:180]+delta), values[:,204:213],
                        rt.hand_clamp_offsets[:1].expand(batch,-1,-1), rt.hand_clamp_lengths[:1].expand(batch,-1))
                    assert torch.allclose(torch.from_numpy(expected[:,:90])+values[:,90:180], exact, atol=2e-6, rtol=0)
                actual = session.run(None, {'input':values.numpy()})[0]
                error = float(np.max(np.abs(expected-actual)))
                assert np.isfinite(actual).all() and error < 1e-4, (name, batch, error)
                errors.append(dict(batch=batch,max_error=error))
            report[name] = errors
            contract['networks'][name] = dict(file=path.name, sha256=sha(path), input_dim=width, output_dim=outwidth)
        runtime = json.loads((old.PROJECT/'Content/locomotion/NN/prophecy_slash_runtime.json').read_text())
        runtime.update(checkpoint_path=str(old.CHECKPOINT), checkpoint_sha256=old.CHECKPOINT_SHA,
            checkpoint_step=saved['step'], transition_schema=contract['transition_schema'], seed_input=initial[0].tolist(),
            startup_expected=frames[0]['output'], root_position_m=oracle.root_pos[0].tolist(), root_rotation=oracle.root_rot[0].tolist(),
            reference_directory=str(old.REFERENCE), python_parity=report)
        runtime.pop('onnx_sha256', None)
        runtime.pop('model_file', None)
        for name, data in [('prophecy_slash_native.json',contract), ('prophecy_slash_runtime.json',runtime),
                           ('native_geometry_reference.json',frames), ('export_validation.json',report)]:
            (args.output/name).write_text(json.dumps(data, indent=2)+'\n')
        print(json.dumps(dict(checkpoint=old.CHECKPOINT_SHA, step=saved['step'], frames=len(frames), networks=report)), flush=True)


if __name__ == '__main__':
    main()
