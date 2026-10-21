"""Build and serve a read-only gallery of every animation in a saved Cutter dataset."""
import argparse
import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
from motion import atomic_json, load_dataset, read_motion

HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parents[1] / 'Saved/LafanCrawlViewer'
VENDOR = Path.home() / 'Downloads/LaFAN1'


def prepare(manifest):
    name, clips = load_dataset(manifest)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, clip in enumerate(clips):
        motion = read_motion(Path(clip['source']))
        filename = f'{i}_{motion.sha256[:12]}.bin'
        motion.positions.astype('<f4').tofile(OUTPUT / filename)
        pelvis = next((j for j, n in enumerate(motion.names) if n.lower() in ('pelvis', 'hips', 'hip')), 0)
        entries.append(dict(label=clip['label'], frames=motion.count, fps=motion.fps, dt=motion.dt,
                            names=motion.names, parents=list(map(int, motion.parents)), pelvis=pelvis,
                            positions=filename, source=clip.get('source_fbx', clip.get('original_source', clip['source'])),
                            range=clip.get('original_range', [clip['start'], clip['end']]),
                            bvh=clip['source'], sha256=motion.sha256,
                            retarget_model=clip.get('retarget_model')))
        if clip.get('retargeted_from'):
            original=read_motion(Path(clip['retargeted_from']))
            if original.sha256 != clip['retarget_source_sha256']:
                raise ValueError('Retarget source changed')
            original_file=f'{i}_{original.sha256[:12]}_overlay.bin'
            (original.positions*clip['root_uniform_scale']).astype('<f4').tofile(OUTPUT/original_file)
            entries[-1]['overlay']=dict(positions=original_file,names=original.names,
                parents=list(map(int,original.parents)),scale=clip['root_uniform_scale'],frames=original.count)
    atomic_json(OUTPUT/'gallery.json', dict(name=name, dataset=str(manifest), clips=entries))
    return entries


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = unquote(urlsplit(path).path)
        if path == '/':
            return str(HERE/'gallery.html')
        if path.startswith('/vendor/'):
            filename = path.removeprefix('/vendor/')
            return str(VENDOR/filename) if filename in ('three.module.js', 'OrbitControls.js') else str(OUTPUT/'missing')
        relative = path.lstrip('/')
        candidate = (OUTPUT/relative).resolve()
        return str(candidate) if candidate.is_relative_to(OUTPUT.resolve()) else str(OUTPUT/'missing')

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--port', type=int, default=8874)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args = parser.parse_args()
    OUTPUT=args.output.resolve()
    rows = prepare(args.dataset.resolve())
    print(json.dumps([dict(label=r['label'], frames=r['frames'], fps=r['fps']) for r in rows]), flush=True)
    if not args.prepare_only:
        ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
