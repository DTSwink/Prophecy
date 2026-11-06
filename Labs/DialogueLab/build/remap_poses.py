"""Drop one pose from the lab's saved data and renumber the poses above it (user: removed "Pose 3" = FBX frame 4).
usage: python remap_poses.py <lab_dir> <removed_pose_index>   (backs up motions.json + settings.json first)"""
import json, re, sys, shutil, time, pathlib
lab = pathlib.Path(sys.argv[1]); R = int(sys.argv[2])
bk = lab / 'build' / ('backup_' + time.strftime('%Y%m%d_%H%M%S')); bk.mkdir(parents=True)
for f in ('motions.json', 'settings.json'):
    if (lab / f).exists(): shutil.copy2(lab / f, bk / f)
print('backup', bk)
sh = lambda k: k - 1 if k > R else k
renum = lambda name: re.sub(r'^Pose (\d+)', lambda m: 'Pose %d' % (int(m.group(1)) - 1) if int(m.group(1)) > R else m.group(0), name)
def write(f, v):
    tmp = lab / (f + '.tmp'); tmp.write_text(json.dumps(v, indent=1), encoding='utf-8'); tmp.replace(lab / f)
m = json.loads((lab / 'motions.json').read_text(encoding='utf-8'))
before = [(x['name'], x['pose']) for x in m['motions']]
dropped = [x['name'] for x in m['motions'] if x['pose'] == R]
m['motions'] = [x for x in m['motions'] if x['pose'] != R]
for x in m['motions']:
    x['pose'] = sh(x['pose']); x['name'] = renum(x['name']); x['poseName'] = renum(x.get('poseName', ''))
if isinstance(m.get('poseNames'), list) and len(m['poseNames']) > R: m['poseNames'] = [renum(n) for i, n in enumerate(m['poseNames']) if i != R]
write('motions.json', m)
print('dropped', dropped); print('motions', before, '->', [(x['name'], x['pose']) for x in m['motions']])
s = json.loads((lab / 'settings.json').read_text(encoding='utf-8'))
for key in ('poseNames', 'motionLast'):
    if isinstance(s.get(key), dict): s[key] = {str(sh(int(k))): v for k, v in s[key].items() if int(k) != R}
if isinstance(s.get('motionRanges'), dict):
    p = s['motionRanges'].get('pose', 1); s['motionRanges']['pose'] = 1 if p == R else sh(p)
write('settings.json', s)
print('settings', {k: s.get(k) for k in ('poseNames', 'motionLast')}, 'pose', s.get('motionRanges', {}).get('pose'))
