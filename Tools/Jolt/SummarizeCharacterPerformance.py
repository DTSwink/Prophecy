"""Summarize a character benchmark without printing its per-body validation payload."""
import argparse
import csv
import json
import statistics
from pathlib import Path


def summarize(report_path, csv_path=None):
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    result = {"report": str(report_path.resolve()), "error": report.get("error"),
              "count": report.get("count"), "fixed_dt": report.get("fixed_dt"), "passes": []}
    partial = report.get("failed_case_partial_measurements")
    if partial:
        result["failed_case_partial_measurements"] = {key: value for key, value in partial.items() if key != "world_ms"}
    for run in report.get("passes", []):
        validation = run.get("multi_jolt_validation", run.get("live_jolt_validation", run.get("manual_crowd_validation", {})))
        result["passes"].append({
            "mode": run.get("mode"), "fixture": run.get("fixture"),
            "world_tick": run.get("world_tick"), "success": validation.get("success"),
            "jolt_update_mean_ms": validation.get("mean_synchronous_jolt_step_ms"),
            "character_cpu_mean_ms": validation.get("mean_character_cpu_ms"),
            "actual_nn_validation": run.get("actual_nn_validation"),
            "frame_interval": run.get("frame_interval"),
        })
    if csv_path:
        with csv_path.open(encoding="utf-8-sig", newline="") as source:
            rows = [row for row in csv.DictReader(source) if row.get("ProphecyBenchmarkMeasured") == "1"]
        metrics = {}
        if rows:
            for key in rows[0]:
                if key and key.startswith(("Exclusive/GameThread/", "PhysicsVerbose/AllWorkers/", "Animation/")):
                    values = [float(row[key]) for row in rows if row.get(key)]
                    if values:
                        metrics[key] = statistics.fmean(values)
        result["engine_csv"] = {"path": str(csv_path.resolve()), "measured_rows": len(rows),
                                "scope_mean_ms": dict(sorted(metrics.items(), key=lambda pair: -pair[1])),
                                "scope_note": "Worker scopes can overlap; world-misc includes validation outside the benchmark's world-tick timer. Do not sum nested scopes."}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.report, args.csv)
    encoded = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        # Preserve earlier evidence; callers choose a new output path.
        with args.output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(encoded + "\n")
        print(json.dumps({"summary": str(args.output.resolve()), "error": result["error"]}))
    else:
        print(encoded)
