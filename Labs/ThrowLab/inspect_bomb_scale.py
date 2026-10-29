"""Read the saved UE5.7 bomb template scale without launching or editing Unreal.

This deliberately validates the tagged serialization used by this asset. If its
layout changes, fail rather than guessing a default scale. Only source bytes are
read; no package or Blueprint writes are performed.
"""
import hashlib, json, re, struct
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / 'Content/_mygame/bomb/A_Bomb.uasset'


def inspect():
    data = SOURCE.read_bytes()
    package = b'/Game/_mygame/bomb/A_Bomb\0'
    candidates = []
    for match in re.finditer(re.escape(struct.pack('<i', len(package)) + package), data):
        names, cursor = [], match.start()
        while cursor + 4 < len(data):
            size = struct.unpack_from('<i', data, cursor)[0]
            if not 0 < size < 512 or cursor + 4 + size > len(data) or data[cursor + 3 + size] != 0:
                break
            try:
                name = data[cursor + 4:cursor + 3 + size].decode('ascii')
            except UnicodeDecodeError:
                break
            names.append(name)
            cursor += 4 + size + 4  # FString plus serialized name hashes.
        candidates.append((names, cursor))
    names, name_end = max(candidates, key=lambda item: len(item[0]))
    assert len(names) > 100 and 'bomb_GEN_VARIABLE' in names

    def refs(name):
        token = struct.pack('<ii', names.index(name), 0)
        return [m.start() for m in re.finditer(re.escape(token), data) if m.start() >= name_end]

    # FObjectExport places serial size/offset after ObjectName and ObjectFlags.
    exports = []
    for offset in refs('bomb_GEN_VARIABLE'):
        size, start = struct.unpack_from('<qq', data, offset + 12)
        if 0 < size < len(data) and name_end < start < start + size <= len(data):
            exports.append((start, start + size))
    assert len(exports) == 1, 'Expected one saved bomb component template'
    start, end = exports[0]
    scales = [p for p in refs('RelativeScale3D') if start <= p < end]
    assert len(scales) == 1, 'Expected an explicit scale on the bomb component'
    offset = scales[0]
    assert struct.unpack_from('<ii', data, offset + 8) == (names.index('StructProperty'), 0)
    assert struct.unpack_from('<ii', data, offset + 20) == (names.index('Vector'), 0)
    size = struct.unpack_from('<i', data, offset + 44)[0]
    assert size == 24 and data[offset + 48] == 8, 'Expected native FVector with no extra tag fields'
    scale = list(struct.unpack_from('<3d', data, offset + 49))
    assert all(0 < value <= 10 for value in scale) and offset + 49 + size <= end
    assert struct.unpack_from('<ii', data, offset + 73) == (names.index('None'), 0)
    return dict(file=str(SOURCE), sha256=hashlib.sha256(data).hexdigest(),
                template='/Game/_mygame/bomb/A_Bomb.A_Bomb_C:bomb_GEN_VARIABLE',
                relativeScale3D=scale, exportRange=[start, end], scaleTagOffset=offset,
                method='Read-only saved UE5.7 component export/tag inspection')


if __name__ == '__main__':
    print(json.dumps(inspect(), indent=2))
