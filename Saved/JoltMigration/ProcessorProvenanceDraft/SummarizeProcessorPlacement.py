#!/usr/bin/env python3
"""Read benchmark JSON and summarize observed processor placement (not residency).

Usage: python SummarizeProcessorPlacement.py report.json [report2.json ...] [-o new.json]
No dependencies, process queries, configuration changes, or benchmark launches.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys

PHASES = ("compose", "refresh_bones")


def stats(values):
    values = list(values)
    if not values:
        return {"frames": 0, "mean_ms": None, "median_ms": None}
    return {"frames": len(values), "mean_ms": statistics.mean(values),
            "median_ms": statistics.median(values), "min_ms": min(values),
            "max_ms": max(values)}


def finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: expected a finite number")
    return value


def nonnegative_int(value, label):
    finite_number(value, label)
    if value < 0 or int(value) != value:
        raise ValueError(f"{label}: expected a nonnegative integer")
    return int(value)


def processor_key(value):
    return (int(value["group"]), int(value["logical_processor_index"]))


def core_json(key, mapping):
    result = {"group": key[0], "logical_processor_index": key[1]}
    entry = mapping.get(key, {})
    result.update({"cpu_set_id": entry.get("id"), "core_index": entry.get("core_index"),
                   "efficiency_class": entry.get("efficiency_class")})
    return result


def scope_accumulator():
    return {phase: {"total_ms": 0.0, "calls": 0, "different_exit_processor": 0,
                    "world_by_sample_frame": {}} for phase in PHASES}


def add_scope(target, phase, duration, calls, migrations, sample_frame, world_ms):
    row = target[phase]
    row["total_ms"] += duration
    row["calls"] += calls
    row["different_exit_processor"] += migrations
    if calls:
        row["world_by_sample_frame"][sample_frame] = world_ms


def scope_result(source):
    result = {}
    for phase, data in source.items():
        calls = data["calls"]
        result[phase] = {"total_ms": data["total_ms"], "calls": calls,
                         "mean_wall_us_per_call": 1000 * data["total_ms"] / calls if calls else None,
                         "different_exit_processor": data["different_exit_processor"],
                         "world_for_frames_with_entry_samples": stats(data["world_by_sample_frame"].values()),
                         "sample_frames": sorted(data["world_by_sample_frame"])}
    return result


def summarize_pass(case, mapping, tolerance_ms):
    result = {"mode": case.get("mode"), "fixture": case.get("fixture"), "repeat": case.get("repeat"),
              "reported_benchmark_world_tick": case.get("world_tick")}
    frames = case.get("multi_jolt_frames", [])
    world_values = case.get("world_ms", [])
    if not frames:
        result["validation"] = {"success": False, "errors": ["No multi_jolt_frames: placement was not captured for this pass."]}
        return result

    errors = []
    seen_frames = set()
    start_groups, start_efficiency = {}, {}
    scope_cores, scope_efficiency = {}, {}
    totals = scope_accumulator()
    world_matched = []
    boundary_migrations = 0
    mixed_entry_frames = 0
    overflow_count = 0
    max_partition_error = {phase: 0.0 for phase in PHASES}
    partition_count_error = {phase: 0 for phase in PHASES}
    missing_core_mapping = set()
    for frame in frames:
        sample_frame = nonnegative_int(frame["sample_frame"], "sample_frame")
        if sample_frame in seen_frames:
            errors.append(f"Duplicate sample_frame {sample_frame}")
            continue
        seen_frames.add(sample_frame)
        if sample_frame >= len(world_values):
            errors.append(f"sample_frame {sample_frame}: no matching world_ms entry")
            continue
        world_ms = finite_number(world_values[sample_frame], f"world_ms[{sample_frame}]")
        if world_ms < 0:
            errors.append(f"sample_frame {sample_frame}: negative world_ms")
            continue
        provenance = frame.get("processor_provenance")
        if not provenance:
            errors.append(f"sample_frame {sample_frame}: processor_provenance missing")
            continue
        start, end = processor_key(provenance["begin"]), processor_key(provenance["end"])
        if min(start) < 0 or min(end) < 0:
            errors.append(f"sample_frame {sample_frame}: unavailable processor location")
        boundary_migrations += start != end
        world_matched.append(world_ms)
        start_groups.setdefault(start, []).append(world_ms)
        efficiency = mapping.get(start, {}).get("efficiency_class")
        start_efficiency.setdefault(efficiency, []).append(world_ms)
        if start not in mapping:
            missing_core_mapping.add(start)
        overflow = nonnegative_int(provenance.get("overflowed_scope_samples", 0), "overflowed_scope_samples")
        overflow_count += overflow
        partition_ms = {phase: 0.0 for phase in PHASES}
        partition_calls = {phase: 0 for phase in PHASES}
        frame_processors = set()
        for entry in provenance.get("phase_entry_processors", []):
            key = processor_key(entry)
            if key in frame_processors:
                errors.append(f"sample_frame {sample_frame}: duplicate processor entry {key}")
            frame_processors.add(key)
            if key not in mapping:
                missing_core_mapping.add(key)
            efficiency = mapping.get(key, {}).get("efficiency_class")
            by_core = scope_cores.setdefault(key, scope_accumulator())
            by_efficiency = scope_efficiency.setdefault(efficiency, scope_accumulator())
            for phase in PHASES:
                sample = entry[phase]
                duration = finite_number(sample["ms"], f"{phase}.ms")
                calls = nonnegative_int(sample["calls"], f"{phase}.calls")
                migrations = nonnegative_int(sample["different_exit_processor"], f"{phase}.different_exit_processor")
                if duration < 0 or migrations > calls:
                    errors.append(f"sample_frame {sample_frame}: invalid {phase} duration/migration count")
                partition_ms[phase] += duration
                partition_calls[phase] += calls
                for target in (by_core, by_efficiency, totals):
                    add_scope(target, phase, duration, calls, migrations, sample_frame, world_ms)
        mixed_entry_frames += len(frame_processors) > 1
        for phase in PHASES:
            expected_ms = finite_number(frame["character_cpu_ms"][phase], f"character_cpu_ms.{phase}")
            expected_calls = nonnegative_int(frame["character_cpu_calls"][phase], f"character_cpu_calls.{phase}")
            difference = abs(partition_ms[phase] - expected_ms)
            max_partition_error[phase] = max(max_partition_error[phase], difference)
            count_difference = abs(partition_calls[phase] - expected_calls)
            partition_count_error[phase] += count_difference
            if difference > tolerance_ms or count_difference:
                errors.append(f"sample_frame {sample_frame}: {phase} partition differs by {difference:.12g} ms / {count_difference} calls")

    if len(world_matched) != len(world_values):
        errors.append(f"Matched {len(world_matched)} placement frames, but world_ms has {len(world_values)} entries")
    if overflow_count:
        errors.append(f"{overflow_count} scope samples overflowed fixed processor storage")
    if missing_core_mapping:
        errors.append("CPU-set map missing observed processors: " + str(sorted(missing_core_mapping)))
    result.update({
        "world_for_placement_frames": stats(world_matched),
        "frame_begin_end_differ": boundary_migrations,
        "frames_with_multiple_scope_entry_processors": mixed_entry_frames,
        "world_by_frame_begin_processor": [dict(core_json(key, mapping), world=stats(values))
                                            for key, values in sorted(start_groups.items())],
        "world_by_frame_begin_efficiency_class": [{"efficiency_class": key, "world": stats(values)}
            for key, values in sorted(start_efficiency.items(), key=lambda item: str(item[0]))],
        "scopes_by_entry_processor": [dict(core_json(key, mapping), phases=scope_result(value))
                                       for key, value in sorted(scope_cores.items())],
        "scopes_by_entry_efficiency_class": [{"efficiency_class": key, "phases": scope_result(value)}
            for key, value in sorted(scope_efficiency.items(), key=lambda item: str(item[0]))],
        "sampled_scope_totals": scope_result(totals),
        "validation": {"success": not errors, "partition_tolerance_ms": tolerance_ms,
                       "max_partition_error_ms": max_partition_error,
                       "partition_call_error_total": partition_count_error,
                       "overflowed_scope_samples": overflow_count, "errors": errors},
    })
    return result


def summarize_report(path, tolerance_ms):
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    environment = document.get("processor_environment", {})
    mapping = {}
    for entry in environment.get("cpu_sets", []):
        key = processor_key(entry)
        if key in mapping:
            raise ValueError(f"Duplicate CPU-set mapping for {key}")
        mapping[key] = entry
    return {"report": str(path.resolve()), "benchmark_error": document.get("error"),
            "count": document.get("count"), "fixed_dt": document.get("fixed_dt"),
            "processor_environment": environment,
            "passes": [summarize_pass(case, mapping, tolerance_ms) for case in document.get("passes", [])]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="New output JSON; never overwrites an existing file")
    parser.add_argument("--tolerance-ms", type=float, default=1e-6,
                        help="Absolute per-frame sampled-phase partition tolerance; counts must match exactly (default: 1e-6 ms)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.tolerance_ms) or args.tolerance_ms < 0:
        parser.error("--tolerance-ms must be finite and nonnegative")
    result = {"interpretation": [
        "Observed entry-processor placement is not residency; matching begin/end cannot exclude intervening migration or preemption.",
        "Efficiency classes are raw OS labels, not hard-coded P/E classifications. No frequency, turbo, temperature or hardware power telemetry is measured.",
        "Per-entry scope durations are wall time attributed to sampled entry processors. A frame may appear in more than one core/efficiency group; group world means are not additive.",
        "World by frame-begin processor uses mutually exclusive observed-entry groups. Per-scope group world metrics include the exact unique frames in which that group was observed.",
        "This script's median averages the two middle observations for even counts; the original benchmark summary is preserved separately because its percentile convention may select the upper middle observation.",
        "Processor sampling overhead remains inside measured world time. Nothing is subtracted and no performance/quality acceptance threshold is changed."],
        "reports": []}
    success = True
    for path in args.reports:
        try:
            report = summarize_report(path, args.tolerance_ms)
            if report.get("benchmark_error") or not report["passes"]:
                success = False
            success &= all(case["validation"]["success"] for case in report["passes"])
            result["reports"].append(report)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["reports"].append({"report": str(path), "read_or_schema_error": str(exc)})
            success = False
    result["validation_success"] = bool(success)
    serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8", newline="\n") as output:
                output.write(serialized)
        except OSError as exc:
            print(f"Cannot create output: {exc}", file=sys.stderr)
            return 2
    else:
        print(serialized, end="")
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
