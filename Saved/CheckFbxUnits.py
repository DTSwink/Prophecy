"""Proper FBX binary parse: read GlobalSettings Properties70 and print unit
and axis related values, comparing known-good UE export vs Blender exports."""

import struct
import sys
import zlib


def read_node(data, offset, version):
    if version >= 7500:
        end_offset, num_props, prop_len = struct.unpack_from("<QQQ", data, offset)
        name_len = data[offset + 24]
        pos = offset + 25
    else:
        end_offset, num_props, prop_len = struct.unpack_from("<III", data, offset)
        name_len = data[offset + 12]
        pos = offset + 13
    if end_offset == 0:
        return None
    name = data[pos:pos + name_len].decode("latin1")
    pos += name_len
    props = []
    for _ in range(num_props):
        t = chr(data[pos]); pos += 1
        if t == "Y": props.append(struct.unpack_from("<h", data, pos)[0]); pos += 2
        elif t == "C": props.append(bool(data[pos])); pos += 1
        elif t == "I": props.append(struct.unpack_from("<i", data, pos)[0]); pos += 4
        elif t == "F": props.append(struct.unpack_from("<f", data, pos)[0]); pos += 4
        elif t == "D": props.append(struct.unpack_from("<d", data, pos)[0]); pos += 8
        elif t == "L": props.append(struct.unpack_from("<q", data, pos)[0]); pos += 8
        elif t in "fdliby":
            length, encoding, comp_len = struct.unpack_from("<III", data, pos)
            pos += 12
            pos += comp_len
            props.append("<array {} x{}>".format(t, length))
        elif t == "S" or t == "R":
            length = struct.unpack_from("<I", data, pos)[0]; pos += 4
            raw = data[pos:pos + length]; pos += length
            props.append(raw.decode("latin1", "replace") if t == "S" else "<raw>")
        else:
            raise RuntimeError("bad type " + t)
    children = []
    while pos < end_offset:
        child = read_node(data, pos, version)
        if child is None:
            if version >= 7500:
                pos += 25
            else:
                pos += 13
            break
        children.append(child)
        pos = child["end"]
    return {"name": name, "props": props, "children": children, "end": end_offset}


def parse(path):
    with open(path, "rb") as handle:
        data = handle.read()
    assert data[:21] == b"Kaydara FBX Binary  \x00"
    version = struct.unpack_from("<I", data, 23)[0]
    pos = 27
    roots = []
    while True:
        node = read_node(data, pos, version)
        if node is None:
            break
        roots.append(node)
        pos = node["end"]
    return version, roots


def find(nodes, name):
    for n in nodes:
        if n["name"] == name:
            return n
    return None


for path in (
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange\UEFN_Mannequin.fbx",
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange\Body_UEFN78.fbx",
):
    version, roots = parse(path)
    gs = find(roots, "GlobalSettings")
    print("FILE|{}|version={}".format(path.split("\\")[-1], version))
    if gs:
        p70 = find(gs["children"], "Properties70")
        for p in p70["children"]:
            key = p["props"][0]
            if any(k in key for k in ("UnitScale", "Axis", "Scal")):
                print("  PROP|{}|{}".format(key, p["props"][4:]))
print("UNITS_DONE")
