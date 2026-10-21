"""Publish recovered replay outcomes under their original TensorBoard runs."""
import json
from pathlib import Path
from dashboard import scalars
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary


def main():
    root = Path(__file__).resolve().parents[2]
    state = root/'Saved/MimicKitEquipment'
    active = json.loads((state/'active_run.json').read_text())['run']
    records = json.loads((state/'perturbed-outcomes-historical-remote.json').read_text())['records']
    records += json.loads((state/'perturbed-outcomes-historical-local.json').read_text())
    groups = {}
    for record in records:
        groups.setdefault(record['run'], {})[record['samples']] = record
    report = []
    for run, captures in groups.items():
        manifest = json.loads((state/(run+'-dashboard.json')).read_text())
        spec = next(r for r in manifest['runs']
                    if any(Path(s).name == 'mimickit_'+run for s in r['sources']))
        target = Path(manifest['output'])/spec['name']
        events = scalars(target)
        seen = {(tag, e.step) for tag, items in events.items() for e in items}
        # Let the live publisher own new captures. Only fill history through
        # its already-published sample, avoiding concurrent duplicate points.
        cutoff = max((e.step for e in events.get(
            'perturbed_eval_sample/all_no_failure_percent', [])), default=-1)
        published = []
        writer = EventFileWriter(str(target))
        try:
            for sample, capture in sorted(captures.items()):
                if run == active and sample > cutoff:
                    continue
                values = [Summary.Value(tag=tag, simple_value=value)
                          for tag, value in capture['values'].items()
                          if (tag, sample) not in seen]
                if not values:
                    continue
                writer.add_event(Event(wall_time=capture['wall_time'], step=sample,
                                       summary=Summary(value=values)))
                seen.update((value.tag, sample) for value in values)
                published.append(dict(samples=sample, iteration=capture['iteration'],
                                      scalars=len(values), source=capture['source']))
            writer.flush()
        finally:
            writer.close()
        report.append(dict(run=run, tensorboard_run=spec['name'], added=published))
    (state/'perturbed-outcomes-backfill.json').write_text(json.dumps(report, indent=2))
    print(json.dumps([dict(run=r['run'], added_capture_points=len(r['added']))
                      for r in report]))


if __name__ == '__main__':
    main()
