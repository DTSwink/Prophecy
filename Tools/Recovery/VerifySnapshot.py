"""Verify every stored recovery blob without requiring Unreal, LFS or a checkout.

  python Tools/Recovery/VerifySnapshot.py HEAD
  python Tools/Recovery/VerifySnapshot.py --git-dir path/to/bare.git HEAD
  python Tools/Recovery/VerifySnapshot.py --write-index  # before committing
"""
import argparse
import collections
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = 'Tools/Recovery/Snapshot20261003.json'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', nargs='?', default='HEAD')
    parser.add_argument('--git-dir')
    parser.add_argument('--write-index', action='store_true')
    args = parser.parse_args()
    git = ['git', '--git-dir', args.git_dir] if args.git_dir else ['git', '-C', str(ROOT)]
    if args.write_index:
        records = subprocess.check_output(git + ['ls-files', '--stage', '-z']).split(b'\0')
        files = {}
        for record in records:
            if not record:
                continue
            meta, path = record.decode('utf8').split('\t', 1)
            mode, oid, stage = meta.split()
            if stage != '0':
                raise SystemExit('Unmerged index: ' + path)
            files[path] = oid
    else:
        manifest = json.loads(subprocess.check_output(git + ['show', args.revision + ':' + MANIFEST]))
        records = subprocess.check_output(git + ['ls-tree', '-r', '-z', args.revision]).split(b'\0')
        files = {}
        for record in records:
            if record:
                meta, path = record.decode('utf8').split('\t', 1)
                mode, kind, oid = meta.split()
                if kind != 'blob':
                    raise SystemExit('Uncaptured submodule: ' + path)
                files[path] = oid
        expected = {row['path']: row for row in manifest['files']}
        if set(files) - {MANIFEST} != set(expected):
            raise SystemExit('Manifest/tree path mismatch')
    files.pop(MANIFEST, None)
    rows = []
    cache = {}
    with subprocess.Popen(git + ['cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
        for path, oid in sorted(files.items()):
            if oid not in cache:
                proc.stdin.write((oid + '\n').encode('ascii'))
                proc.stdin.flush()
                header = proc.stdout.readline().split()
                if len(header) != 3 or header[1] != b'blob':
                    raise SystemExit('Missing blob: ' + path)
                size = int(header[2])
                remaining = size
                digest = hashlib.sha256()
                prefix = b''
                while remaining:
                    chunk = proc.stdout.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise SystemExit('Truncated blob: ' + path)
                    if not prefix:
                        prefix = chunk[:128]
                    digest.update(chunk)
                    remaining -= len(chunk)
                if proc.stdout.read(1) != b'\n':
                    raise SystemExit('Invalid Git batch framing')
                if prefix.startswith(b'version https://git-lfs.github.com/spec/v1'):
                    raise SystemExit('Unresolved LFS pointer: ' + path)
                if size >= 100 * 1024 * 1024:
                    raise SystemExit('Oversized blob: ' + path)
                cache[oid] = (size, digest.hexdigest())
            size, sha = cache[oid]
            row = dict(path=path, git_blob=oid, bytes=size, sha256=sha)
            if not args.write_index and row != expected[path]:
                raise SystemExit('Content mismatch: ' + path)
            rows.append(row)
        proc.stdin.close()
        if proc.wait() != 0:
            raise SystemExit('Git blob read failed')
    total = sum(row['bytes'] for row in rows)
    if args.write_index:
        output = dict(date='2026-10-03', branch='codex/standalone-sim',
                      note='Git-normalized file bytes; manifest excludes itself. External assets are not backed up.',
                      file_count=len(rows), bytes=total, files=rows)
        (ROOT / MANIFEST).write_text(json.dumps(output, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(result='manifest written' if args.write_index else 'verified',
                          files=len(rows), bytes=total, unique_blobs=len(cache),
                          groups=dict(collections.Counter(row['path'].split('/')[0] for row in rows)))))

if __name__ == '__main__':
    main()
