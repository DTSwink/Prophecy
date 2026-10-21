"""Compare the actual before/after Blueprint exports before saving the change."""
import json, pathlib, re

out = pathlib.Path("Saved/Diagnostics/SkeletalBloodBrush")

def pins(filename):
    stack, result = [], {}
    text = (out / filename).read_text(encoding="utf-8")
    # Compiler-generated function graphs are regenerated on every compile.
    graphs = set(re.findall(r'^   (?:FunctionGraphs|UbergraphPages)\(\d+\)="[^\'\n]+\'([^\']+)\'"', text, re.M))
    assert graphs == {"EventGraph", "UserConstructionScript", "NewFunction"}, graphs
    for line in text.splitlines():
        if re.match(r"\s*Begin Object ", line):
            stack.append(re.search(r'\bName="([^"]+)"', line).group(1))
        elif line.strip() == "End Object":
            stack.pop()
        elif "CustomProperties Pin " in line and len(stack) > 1 and stack[1] in graphs:
            pin_id = re.search(r"PinId=(\w+)", line).group(1)
            result[tuple(stack) + (pin_id,)] = line.strip()
    return result

before, after = pins("before-install.txt"), pins("after-install.txt")
assert not (before.keys() - after.keys()), "Existing pins were removed"
changed = [key for key in before if before[key] != after[key]]
assert len(changed) == 3, changed
report = []
for key in changed:
    old, new = before[key], after[key]
    assert 'PinType.PinCategory="exec"' not in old, key
    assert re.sub(r"LinkedTo=\([^)]*\),", "", old) == re.sub(r"LinkedTo=\([^)]*\),", "", new), key
    report.append({
        "node": ".".join(key[:-1]),
        "pin": re.search(r'PinName="([^"]+)"', old).group(1),
        "before": re.search(r"LinkedTo=\(([^)]*)\)", old).group(1),
        "after": re.search(r"LinkedTo=\(([^)]*)\)", new).group(1),
    })
assert {row["node"].split(".")[-1] for row in report} == {
    "K2Node_CallFunction_6", "K2Node_VariableGet_10", "K2Node_Knot_0"
}, report
new_nodes = sorted({".".join(key[:-1]) for key in after.keys() - before.keys()})
assert len(new_nodes) == 4, new_nodes
receipt = {"existing_pins": len(before), "changed_links_only": report,
           "added_nodes": new_nodes, "existing_exec_pins_unchanged": True}
(out / "graph-check.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
