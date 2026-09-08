"""Isolated CPU neural-layer timing; not the complete native attack-step cost."""
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT / "Saved/SlashPythonDependencies"))
import numpy as np
import onnxruntime as ort

reference = json.loads((PROJECT / "Saved/SlashParity/native_geometry_reference.json").read_text())
results = []
for threads in (1, 2):
    sessions = []
    for name in ("frozen", "lower", "upper"):
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(PROJECT / f"Content/locomotion/NN/prophecy_slash_{name}.onnx"),
                                       options, providers=["CPUExecutionProvider"])
        sessions.append((name, session))
    for batch in (1, 4, 16, 32, 100):
        inputs = [[np.array([reference[(frame + lane) % len(reference)]["networks"][name]["input"]
                            for lane in range(batch)], dtype=np.float32) for name, _ in sessions]
                  for frame in range(len(reference))]
        timings = []
        for iteration in range(220):
            values = inputs[iteration % len(inputs)]
            start = time.perf_counter()
            for (_, session), value in zip(sessions, values):
                session.run(None, {"input": value})
            elapsed = (time.perf_counter() - start) * 1000
            if iteration >= 20:
                timings.append(elapsed)
        result = {"backend": "standalone ORT CPU", "threads": threads, "agents": batch,
                  "median_three_networks_ms": float(np.median(timings)),
                  "p95_three_networks_ms": float(np.percentile(timings, 95))}
        results.append(result)
        print(json.dumps(result), flush=True)
(PROJECT / "Saved/SlashParity/neural_only_cpu_benchmark.json").write_text(json.dumps(results, indent=2))
