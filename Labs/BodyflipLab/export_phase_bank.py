"""One-shot, single-thread CPU export. Exact original phase seeds and warmup."""
import gc, json, struct, time
from locomotion import Locomotion, ROOT

if __name__ == '__main__':
    begin = time.perf_counter()
    for gait, stride in [('run', 19), ('walk', 29)]:
        model = Locomotion(gait)
        for drawn in (False, True):
            stem = gait + ('-drawn' if drawn else '') + '-phases'
            path = ROOT / 'data' / (stem + '.bin')
            with path.with_suffix('.tmp').open('wb') as f:
                for slot in range(stride + 1):
                    data = model.generate(5, min(slot / stride, .999999), drawn)
                    for root, pose in zip(data['roots'], data['poses']):
                        row = list(root)
                        for point, axes in zip(pose['points'], pose['axes']):
                            row.extend(point)
                            row.extend(v for axis in axes for v in axis)
                        f.write(struct.pack('<' + str(len(row)) + 'f', *row))
                    if slot % 10 == 0:
                        print(stem, slot, '/', stride, 'elapsed', round(time.perf_counter()-begin, 1), flush=True)
            path.with_suffix('.tmp').replace(path)
            meta = {k:v for k,v in data.items() if k not in ('poses','roots','duration','phase','seconds','upperInferences')}
            meta.update(stride=stride, framesPerPhase=len(data['poses']), format='root3-body-point3-axes9-f32le')
            path.with_suffix('.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
            print(stem, 'complete', path.stat().st_size, flush=True)
        del model
        gc.collect()
