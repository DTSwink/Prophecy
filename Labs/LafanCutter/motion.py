"""Lossless BVH cuts, forward kinematics and versioned local datasets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import uuid

import numpy as np
from scipy.spatial.transform import Rotation


@dataclass
class Motion:
    path: Path
    header: str
    frame_time_line: str
    rows: list[str]
    dt: float
    names: list[str]
    parents: list[int]
    offsets: np.ndarray
    channels: list[list[str]]
    values: np.ndarray
    positions: np.ndarray
    sha256: str

    @property
    def count(self):
        return len(self.rows)

    @property
    def fps(self):
        return 1 / self.dt


def read_motion(path: Path, decode=True) -> Motion:
    path = Path(path).resolve()
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    match = re.search(r'(?m)^\s*MOTION\s*\r?$', text)
    if not match:
        raise ValueError('BVH is missing MOTION')
    header = text[:match.start()].rstrip() + '\nMOTION\n'
    lines = text[match.end():].strip('\r\n').splitlines()
    count_match = re.fullmatch(r'\s*Frames:\s*(\d+)\s*', lines[0])
    dt_match = re.fullmatch(r'\s*Frame Time:\s*([\d.eE+-]+)\s*', lines[1])
    if not count_match or not dt_match:
        raise ValueError('Invalid BVH frame metadata')
    count, dt = int(count_match[1]), float(dt_match[1])
    rows = [row for row in lines[2:] if row.strip()]
    if count != len(rows) or count < 1 or not np.isfinite(dt) or dt <= 0:
        raise ValueError('Invalid BVH frame count or frame time')
    if not decode:
        # Export operates on already-validated source rows. Avoid calculating
        # a complete animation's FK again merely to copy a short selection.
        return Motion(path,header,lines[1],rows,dt,[],[],None,[],None,None,
                      hashlib.sha256(raw).hexdigest())
    tokens = re.findall(r'[^\s{}]+|[{}]', text[:match.start()])
    names, parents, offsets, channels = [], [], [], []
    i = 1

    def joint(parent):
        nonlocal i
        kind = tokens[i]; i += 1
        if kind not in ('ROOT', 'JOINT', 'End'):
            raise ValueError('Invalid BVH hierarchy')
        name = tokens[i]; i += 1
        if kind == 'End':
            name = names[parent] + '_End'
        index = len(names)
        names.append(name); parents.append(parent); offsets.append([0., 0., 0.]); channels.append([])
        if tokens[i] != '{':
            raise ValueError('Expected joint opening brace')
        i += 1
        while tokens[i] != '}':
            word = tokens[i]
            if word == 'OFFSET':
                offsets[index] = [float(x) for x in tokens[i+1:i+4]]; i += 4
            elif word == 'CHANNELS':
                n = int(tokens[i+1]); channels[index] = tokens[i+2:i+2+n]; i += 2+n
            else:
                joint(index)
        i += 1

    joint(-1)
    width = sum(map(len, channels))
    # Validate each row so malformed whitespace cannot silently shift channel boundaries.
    if any(len(row.split()) != width for row in rows):
        raise ValueError('A BVH frame has the wrong number of channels')
    # loadtxt's line-oriented parser avoids the severe whole-string parsing
    # slowdown on large Re-solved files in this Windows NumPy runtime.
    values = np.loadtxt(rows, dtype=np.float64, ndmin=2)
    if values.size != count * width or not np.isfinite(values).all():
        raise ValueError('Invalid or non-finite BVH channels')
    values = values.reshape(count, width)
    offsets = np.asarray(offsets, dtype=np.float64)
    positions = np.empty((count, len(names), 3), dtype=np.float32)
    rotations = np.empty((count, len(names), 3, 3), dtype=np.float32)
    col = 0
    for j, chans in enumerate(channels):
        local_pos = np.broadcast_to(offsets[j], (count, 3)).copy()
        axes, angles = '', []
        for k, channel in enumerate(chans):
            axis = 'XYZ'.index(channel[0].upper())
            if channel.lower().endswith('position'):
                # LAFAN's root channels and Re-solved's per-joint channels are
                # complete local translations. OFFSET is the rest fallback,
                # not an extra translation (see the authors' BVH exporters).
                local_pos[:, axis] = values[:, col+k]
            elif channel.lower().endswith('rotation'):
                axes += channel[0].upper(); angles.append(values[:, col+k])
            else:
                raise ValueError('Unsupported BVH channel: ' + channel)
        local_rot = Rotation.from_euler(axes, np.stack(angles, -1), degrees=True).as_matrix() if axes else np.broadcast_to(np.eye(3), (count, 3, 3))
        parent = parents[j]
        if parent < 0:
            positions[:, j] = local_pos * .01
            rotations[:, j] = local_rot
        else:
            positions[:, j] = positions[:, parent] + np.einsum('fij,fj->fi', rotations[:, parent], local_pos * .01)
            rotations[:, j] = rotations[:, parent] @ local_rot
        col += len(chans)
    return Motion(path, header, lines[1], rows, dt, names, parents, offsets, channels, values, positions, hashlib.sha256(raw).hexdigest())


def clip_record(motion, start, end):
    if not 0 <= start <= end < motion.count:
        raise ValueError('Trim range is outside the motion')
    return dict(id=uuid.uuid4().hex, source=str(motion.path), source_sha256=motion.sha256,
                label=f'{motion.path.stem} [{start}–{end}]', start=start, end=end,
                frames=end-start+1, fps=motion.fps)


def write_cut(motion, dest, start, end):
    if not 0 <= start <= end < motion.count:
        raise ValueError('Trim range is outside the motion')
    # Original channels, joint offsets and timing. No recentering or resampling.
    text = motion.header + f'Frames: {end-start+1}\n' + motion.frame_time_line + '\n'
    text += '\n'.join(motion.rows[start:end+1]) + '\n'
    Path(dest).write_text(text, encoding='utf-8', newline='\n')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def dataset_name(name):
    name = name.strip()
    if (not name or len(name) > 80 or name.endswith('.') or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name in ('.', '..') or
            name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}):
        raise ValueError('Use a dataset name of 1–80 characters without / \\ : * ? " < > |')
    return name


def save_dataset(root, name, clips):
    name = dataset_name(name)
    if not clips:
        raise ValueError('Add at least one trim before saving')
    destination = Path(root).resolve() / name
    revision = 'revision_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    folder = destination / revision
    folder.mkdir(parents=True)
    entries = []
    previous = None
    motion = None
    for n, clip in enumerate(clips, 1):
        if previous != clip['source']:
            motion = read_motion(Path(clip['source']),decode=False); previous = clip['source']
        if motion.sha256 != clip['source_sha256']:
            raise ValueError(f'Source changed since selection: {motion.path.name}. Please select the trim again.')
        start, end = clip['start'], clip['end']
        if type(start) is not int or type(end) is not int:
            raise ValueError('Frame indices must be integers')
        filename = f'{n:04d}_{motion.path.stem}_{start:06d}_{end:06d}.bvh'
        write_cut(motion, folder / filename, start, end)
        entries.append({**clip, 'file': f'{revision}/{filename}',
                        'frames': end-start+1, 'fps': motion.fps,
                        'sha256': hashlib.sha256((folder / filename).read_bytes()).hexdigest()})
    manifest = dict(format='lafan-cutter-dataset', version=1, name=name,
                    saved_utc=datetime.now(timezone.utc).isoformat(),
                    frame_range='zero-based inclusive', preserve_source_motion=True,
                    clips=entries)
    # Old revisions are retained. The manifest changes only after all cuts succeed.
    atomic_json(folder / 'manifest.json', {**manifest, 'clips': [
        {**row, 'file': Path(row['file']).name} for row in entries]})
    atomic_json(destination / 'dataset.json', manifest)
    return destination / 'dataset.json'


def load_dataset(path):
    path = Path(path).resolve()
    doc = json.loads(path.read_text(encoding='utf-8'))
    if doc.get('format') != 'lafan-cutter-dataset' or doc.get('version') != 1:
        raise ValueError('Not a Lafan Cutter dataset')
    clips = []
    for row in doc['clips']:
        exported = (path.parent / row['file']).resolve()
        if not exported.is_relative_to(path.parent) or not exported.is_file():
            raise ValueError('Dataset cut is missing or outside its dataset folder')
        # Reopening uses the self-contained saved BVH, even if originals moved.
        digest = hashlib.sha256(exported.read_bytes()).hexdigest()
        if digest != row['sha256']:
            raise ValueError('Saved cut checksum does not match: ' + exported.name)
        clips.append({**row, 'source': str(exported), 'source_sha256': digest,
                      'start': 0, 'end': row['frames']-1,
                      'original_source': row.get('original_source', row['source']),
                      'original_range': row.get('original_range', [row['start'], row['end']])})
    return doc['name'], clips
