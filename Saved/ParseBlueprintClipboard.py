import ctypes
import re


CF_UNICODETEXT = 13
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.GetClipboardData.argtypes = [ctypes.c_uint]
user32.GetClipboardData.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = ctypes.c_bool
if not user32.OpenClipboard(None):
    raise RuntimeError("Could not open clipboard")
try:
    handle = user32.GetClipboardData(CF_UNICODETEXT)
    if not handle:
        raise RuntimeError("Clipboard does not contain Unicode text")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        raise RuntimeError("Could not lock clipboard data")
    try:
        text = ctypes.wstring_at(pointer)
    finally:
        kernel32.GlobalUnlock(handle)
finally:
    user32.CloseClipboard()

blocks = re.findall(r"Begin Object Class=(.*?)\n(.*?)\nEnd Object", text, re.S)
nodes = {}
pin_owners = {}
for class_line, body in blocks:
    name_match = re.search(r'Name="([^"]+)"', class_line)
    if not name_match:
        continue
    name = name_match.group(1)
    label = name
    for pattern in [
        r'EventReference=.*?MemberName="([^"]+)',
        r'FunctionReference=.*?MemberName="([^"]+)',
        r'CustomFunctionName="([^"]+)',
        r'VariableReference=.*?MemberName="([^"]+)',
        r'MacroGraphReference=.*?GraphName="([^"]+)',
    ]:
        match = re.search(pattern, body)
        if match:
            label = match.group(1)
            break
    pos_x = int(re.search(r'NodePosX=(-?\d+)', body).group(1)) if re.search(r'NodePosX=(-?\d+)', body) else 0
    pos_y = int(re.search(r'NodePosY=(-?\d+)', body).group(1)) if re.search(r'NodePosY=(-?\d+)', body) else 0
    pins = []
    for line in body.splitlines():
        if "CustomProperties Pin (" not in line:
            continue
        pin_id_match = re.search(r'PinId=([A-F0-9]+)', line)
        pin_name_match = re.search(r'PinName="([^"]+)', line)
        if not pin_id_match or not pin_name_match:
            continue
        pin_id = pin_id_match.group(1)
        pin_name = pin_name_match.group(1)
        direction = "out" if 'Direction="EGPD_Output"' in line else "in"
        category_match = re.search(r'PinType.PinCategory="([^"]+)', line)
        category = category_match.group(1) if category_match else ""
        default_match = re.search(r'DefaultValue="([^"]*)', line)
        default = default_match.group(1) if default_match else ""
        linked_match = re.search(r'LinkedTo=\((.*?)\),PersistentGuid=', line)
        links = []
        if linked_match:
            links = re.findall(r'([A-Za-z0-9_]+)\s+([A-F0-9]+)', linked_match.group(1))
        pin = {
            "id": pin_id, "name": pin_name, "direction": direction,
            "category": category, "default": default, "links": links,
        }
        pins.append(pin)
        pin_owners[pin_id] = (name, pin_name)
    nodes[name] = {
        "name": name, "label": label, "class": class_line.split()[0],
        "x": pos_x, "y": pos_y, "pins": pins,
    }

print("NODES={} CHARS={}".format(len(nodes), len(text)))
for node in sorted(nodes.values(), key=lambda item: (item["y"], item["x"])):
    exec_pins = [pin for pin in node["pins"] if pin["category"] == "exec"]
    if not exec_pins and node["label"] not in [
        "GetBoneTransform", "GetBoneLinearVelocity", "spring_cpp", "angspring_cpp",
        "Multiply_VectorVector", "Add_VectorVector", "MakeVector2D",
    ]:
        continue
    print("\n{} [{}] at {},{}".format(node["name"], node["label"], node["x"], node["y"]))
    for pin in exec_pins:
        targets = []
        for target_node, target_pin_id in pin["links"]:
            owner = pin_owners.get(target_pin_id, (target_node, target_pin_id))
            target = nodes.get(owner[0])
            targets.append("{}.{}[{}]".format(
                owner[0], owner[1], target["label"] if target else "?"))
        print("  EXEC {} {} -> {}".format(pin["direction"], pin["name"], targets))
    for pin in node["pins"]:
        if pin["category"] != "exec" and (pin["links"] or pin["default"]):
            targets = []
            for target_node, target_pin_id in pin["links"]:
                owner = pin_owners.get(target_pin_id, (target_node, target_pin_id))
                target = nodes.get(owner[0])
                targets.append("{}.{}[{}]".format(
                    owner[0], owner[1], target["label"] if target else "?"))
            if targets or pin["name"] in [
                "Duration", "bSimulate", "NewType", "Channel", "NewResponse",
                "DVelMax", "DAngVelMax", "DeltaSeconds", "BoneName", "InBoneName",
            ]:
                print("  DATA {} {} default={!r} -> {}".format(
                    pin["direction"], pin["name"], pin["default"], targets))
