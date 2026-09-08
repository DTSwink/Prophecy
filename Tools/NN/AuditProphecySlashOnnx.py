"""Independent ONNX execution against the immutable accepted world-space rollout."""
import json
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT / "Saved/SlashPythonDependencies"))
import numpy as np
import onnxruntime as ort

directory = PROJECT / "Content/locomotion/NN"
contract = json.loads((directory / "prophecy_slash_runtime.json").read_text())
reference = json.loads((Path(contract["reference_directory"]) / "rollout_unreal.json").read_text())
options = ort.SessionOptions()
options.intra_op_num_threads = 2
options.inter_op_num_threads = 1
options.optimized_model_filepath = str(PROJECT / "Saved/SlashParity/slash_optimized.onnx")
start = time.perf_counter()
session = ort.InferenceSession(sys.argv[1] if len(sys.argv) > 1 else str(directory / contract["model_file"]), sess_options=options,
                              providers=["CPUExecutionProvider"])
print("Loaded ONNX", time.perf_counter() - start, flush=True)
state = np.tile(np.asarray(contract["seed_input"], dtype=np.float32), (contract["batch_size"], 1))
report = {"frames": []}
for frame in range(2, 20):
    start = time.perf_counter()
    output = session.run(None, {"state": state})[0]
    elapsed = time.perf_counter() - start
    assert np.isfinite(output).all()
    expected = reference["frames"][frame]
    pos = output[0, 131:206].reshape(25, 3)
    rot = output[0, 206:431].reshape(25, 3, 3)
    row = {"frame": frame, "batch_inference_ms": elapsed * 1000,
           "position_error_m": float(np.linalg.norm(pos - np.asarray(expected["globalJointPositionsM"]), axis=-1).max()),
           "matrix_error": float(np.abs(rot - expected["globalJointRotations3x3"]).max()),
           "latches_match": bool(output[0, 431] == expected["armedLatch"] and output[0, 432] == expected["hitLatch"]),
           "pin_error": float(np.abs(output[0, 435:437] - expected["lowerPinProbabilities"]).max()),
           "gate_error": float(np.abs(output[0, 433:435] - expected["phaseProbabilities"]).max())}
    report["frames"].append(row)
    print(row, flush=True)
    state = np.concatenate((state[:, 41:82], output[:, :41], state[:, 172:262], output[:, 41:131], state[:, 262:270], output[:, 431:433]), axis=1)
report["passed"] = all(r["position_error_m"] < 0.0001 and r["matrix_error"] < 0.001 and r["latches_match"] and r["pin_error"] < 0.001 and r["gate_error"] < 0.001 for r in report["frames"])
(PROJECT / "Saved/SlashParity/onnx_parity.json").write_text(json.dumps(report, indent=2))
assert report["passed"], "ONNX parity failed"
