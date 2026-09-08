"""Read the saved FK section keys without relying on Control Rig evaluation."""

import json
import re

import unreal


SEQUENCE_PATH = "/Game/_mygame/MetaHumans/NewLevelSequence"
BODY_BINDING_NAME = "test_UEFNFit_ExportedBody5"


sequence = unreal.load_asset(SEQUENCE_PATH)
binding = sequence.find_binding_by_name(BODY_BINDING_NAME)
proxies = [
    proxy
    for proxy in unreal.ControlRigSequencerLibrary.get_control_rigs(sequence)
    if proxy.track in binding.get_tracks()
]
if len(proxies) != 1:
    raise RuntimeError("Expected exactly one Body Control Rig proxy")

section = proxies[0].track.get_section_to_key()
changed = []
all_keyed = []
for channel in section.get_all_channels():
    keys = list(channel.get_keys())
    if not keys:
        continue
    name = str(channel.get_name())
    value = float(keys[0].get_value())
    all_keyed.append((name, value))
    default = 1.0 if ".Scale." in name else 0.0
    if abs(value - default) > 1.0e-6:
        changed.append((name, value))

by_control = {}
pattern = re.compile(
    r"^(?P<control>.+?)\.(?P<kind>Location|Rotation|Scale)\.(?P<axis>[XYZ])(?:_\d+)?$"
)
unparsed = []
for name, value in changed:
    match = pattern.match(name)
    if not match:
        unparsed.append((name, value))
        continue
    control = match.group("control")
    by_control.setdefault(control, {})[
        match.group("kind") + "." + match.group("axis")
    ] = value

report = {
    "section_active": bool(section.is_active()),
    "all_channel_count": len(section.get_all_channels()),
    "keyed_channel_count": len(all_keyed),
    "changed_channel_count": len(changed),
    "changed_control_count": len(by_control),
    "changed_controls": by_control,
    "unparsed": unparsed,
}
print("FK_CHANNEL_AUDIT=" + json.dumps(report, sort_keys=True))
