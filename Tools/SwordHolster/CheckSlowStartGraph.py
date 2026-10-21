"""Verify the narrow correction against every authored sword Blueprint pin."""
import json, pathlib, re
out = pathlib.Path("Saved/Diagnostics/SceneClock")
def read(name):
    text = (out / name).read_text(encoding="utf-8")
    graphs = set(re.findall(r'^   (?:FunctionGraphs|UbergraphPages|MacroGraphs)\(\d+\)="[^\'\n]+\'([^\']+)\'"', text, re.M))
    stack, pins = [], {}
    for line in text.splitlines():
        if re.match(r"\s*Begin Object ", line):
            stack.append(re.search(r'\bName="([^"]+)"', line).group(1))
        elif line.strip() == "End Object": stack.pop()
        elif "CustomProperties Pin " in line and len(stack) > 1 and stack[1] in graphs:
            pins[tuple(stack[1:]) + (re.search(r"PinId=(\w+)", line).group(1),)] = line.strip()
    return graphs, pins
graphs, before = read("sword-before-fix.txt")
after_graphs, after = read("sword-after-fix.txt")
assert graphs == after_graphs
assert not before.keys() - after.keys(), "Existing pins removed"
expected = {
    ("begin play f", "K2Node_CallFunction_2", "FPS"),
    ("begin play f", "K2Node_CallFunction_2", "then"),
    ("begin play f", "K2Node_CallFunction_159", "then"),
    ("begin play f", "K2Node_CallFunction_51", "ReturnValue"),
    ("begin play f", "K2Node_Knot_1", "InputPin"),
    ("EventGraph", "K2Node_CallFunction_159", "then"),
}
changes = []
for key in before:
    old, new = before[key], after[key]
    if old == new: continue
    name = re.search(r'PinName="([^"]+)"', old).group(1)
    assert key[:-1] + (name,) in expected, (key, name)
    def normalize(value):
        value = re.sub(r"LinkedTo=\([^)]*\),", "", value)
        if name == "FPS": value = re.sub(r'(?<![A-Za-z])DefaultValue="[^"]*",', "", value)
        return value
    assert normalize(old) == normalize(new), key
    changes.append({"graph": key[0], "node": key[1], "pin": name})
assert len(changes) == len(expected), changes
new_nodes = sorted({".".join(key[:-1]) for key in after.keys() - before.keys()})
assert len(new_nodes) == 4, new_nodes
receipt = {"authored_graphs": len(graphs), "existing_pins": len(before),
           "allowed_changes": changes, "added_nodes": new_nodes}
(out / "slow-graph-check.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
