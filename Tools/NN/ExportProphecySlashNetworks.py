"""Float32 neural-only Slash exports and the immutable native-geometry contract.

The original complete transition is retained as a numerical oracle, not changed.
No training, checkpoint, or viewer files are written.
"""
from __future__ import annotations

import json
from ExportProphecySlashPolicy import PROJECT, CHECKPOINT_SHA, prepare, sha, slash, torch, onnx

class Network(torch.nn.Module):
    def __init__(self, source, kind):
        super().__init__()
        self.source, self.kind = source, kind

    def forward(self, values):
        result = self.source(values)
        if self.kind == "frozen":
            return result
        delta, gates = result
        return delta if gates is None else torch.cat((delta, gates), -1)


def main():
    torch.set_num_threads(2)
    rt, oracle, initial, selection = prepare(1)
    dest = PROJECT / "Content/locomotion/NN"
    report_dir = PROJECT / "Saved/SlashParity"
    networks = [("frozen", oracle.frozen, 152), ("lower", oracle.lower, 92), ("upper", oracle.upper, 217)]
    contract = {"checkpoint_sha256": CHECKPOINT_SHA, "networks": {}, "core_bones": slash.CORE_BONES,
                "foot_roll_steps": 4, "full_precision": True}
    traces = {}
    hooks = []
    for name, net, width in networks:
        wrapped = Network(net, name).eval()
        path = dest / f"prophecy_slash_{name}.onnx"
        torch.onnx.export(wrapped, (torch.zeros(1, width),), path, opset_version=18,
                          dynamo=False, input_names=["input"], output_names=["output"],
                          dynamic_axes={"input": {0: "agents"}, "output": {0: "agents"}})
        exported = onnx.load(path)
        contract["networks"][name] = {"file": path.name, "sha256": sha(path), "input_dim": width,
            "output_dim": 92 if name == "upper" else 43, "nodes": len(exported.graph.node)}
        def hook(module, args, result, key=name):
            value = result if key == "frozen" else (result[0] if result[1] is None else torch.cat(result, -1))
            traces[key] = {"input": args[0][0].tolist(), "output": value[0].tolist()}
        hooks.append(net.register_forward_hook(hook))

    with rt.policy_context(), torch.inference_mode():
        # Only the accepted four-step approximation is applied, in the isolated
        # exporter process. Original source files and checkpoint remain untouched.
        previous_steps = slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS
        slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS = 4
        contract.update({"frozen_original_pin_steps": previous_steps,
            "frozen_pin_mode": slash.ik_ctl.FOOT_ROLL_PIN_MODE,
            "frozen_height_gate": slash.ik_ctl.FOOT_ROLL_HEIGHT_PIN_GATE,
            "fake_gravity": slash.ik_ctl.FAKE_GRAVITY_ENABLED,
            "clamp_reach": slash.tl.IK_CLAMP_END_EFFECTORS_TO_REACH,
            "pose_delta_scale": rt.cfg.pose_delta_scale_final,
            "root_features": oracle.root_features[0].tolist(),
            "root_position": oracle.root_pos[0].tolist(), "root_rotation": oracle.root_rot[0].tolist(),
            "pin_up_axis": slash.ik_ctl.FOOT_ROLL_UP_AXIS,
            "foot_half_dims": rt.lower_store.foot_roll_foot_half_dims.tolist(),
            "toe_half_dims": rt.lower_store.foot_roll_toe_half_dims.tolist(),
            "sole_offset": slash.ik_ctl.FOOT_ROLL_SOLE_VERTICAL_OFFSET_M,
            "ground": rt.lower_store.foot_roll_ground_y_tensor.tolist(),
            "lower_geometry": {k: v[0].tolist() for k, v in rt.lower_fk_geometry.items()},
            "full_geometry": {k: v[0].tolist() for k, v in rt.full_fk_geometry.items()},
            "lower_limbs": rt.lower_clip.ik_limb_specs, "full_limbs": rt.full_clip.ik_limb_specs,
            "parents": rt.full_clip.parents_body_list, "bone_names": rt.full_clip.body_names})
        state = initial.clone()
        frames = []
        for frame in range(2, 20):
            output = oracle(state)
            frames.append({"frame": frame, "state": state[0].tolist(), "output": output[0].tolist(),
                           "networks": dict(traces)})
            state = torch.cat((state[:, 41:82], output[:, :41], state[:, 172:262], output[:, 41:131],
                               state[:, 262:270], output[:, 431:433]), -1)
        contract["startup_expected"] = frames[0]["output"]
        (report_dir / "native_geometry_reference.json").write_text(json.dumps(frames))
        (dest / "prophecy_slash_native.json").write_text(json.dumps(contract, indent=2) + "\n")
    for hook in hooks:
        hook.remove()
    print(json.dumps({k: v for k, v in contract.items() if "geometry" not in k and k != "startup_expected"}, indent=2))


if __name__ == "__main__":
    main()
