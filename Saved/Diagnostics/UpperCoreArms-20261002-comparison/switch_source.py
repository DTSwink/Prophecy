"""Switch only the four inertia source files; compile/refresh Unreal afterwards."""
from pathlib import Path
import hashlib, shutil, sys

folder=Path(__file__).resolve().parent
root=folder.parents[2]
choice=sys.argv[1] if len(sys.argv)==2 else ''
assert choice in ('shared','split'), 'usage: switch_source.py shared|split'
files=[
 'Source/GameAnimationSample3/Private/ProphecyUpperBodyInertiaLibrary.cpp',
 'Source/GameAnimationSample3/Private/ProphecyUpperBodyInertia.h',
 'Source/GameAnimationSample3/Private/ProphecyHandInertiaRuntime.inl',
 'Source/GameAnimationSample3/Public/ProphecyUpperBodyInertiaLibrary.h',
]
for name in files:
    current=(root/name).read_bytes()
    assert any(current==(folder/version/name).read_bytes() for version in ('shared','split')), 'New edits need review: '+name
for name in files:
    shutil.copy2(folder/choice/name,root/name)
    (root/name).touch()  # Force Unreal to notice restored files with older backup timestamps.
print('Source switched to',choice,'; Live Coding and Blueprint refresh still required.')
