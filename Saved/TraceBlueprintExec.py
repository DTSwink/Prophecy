import re
import sys

from SummarizeBlueprintT3D import graph_name, node_kind, parse, pins, walk


CATEGORY_RE = re.compile(r'PinType\.PinCategory="([^"]+)"')


def exec_outputs(block):
    outputs = []
    for line in block.lines:
        if "CustomProperties Pin" not in line:
            continue
        category = CATEGORY_RE.search(line)
        if not category or category.group(1) != "exec" or 'Direction="EGPD_Output"' not in line:
            continue
        parsed = pins(type("PinBlock", (), {"lines": [line]})())
        if parsed:
            outputs.append((parsed[0]["name"], parsed[0]["links"]))
    return outputs


def main():
    path, graph, start = sys.argv[1:4]
    root = parse(path)
    selected = {}
    for block in walk(root):
        if not block.export_path or ".K2Node_" not in block.export_path:
            continue
        if graph_name(block) != graph:
            continue
        if block.name not in selected or len(block.lines) > len(selected[block.name].lines):
            selected[block.name] = block

    seen = set()

    def visit(name, depth):
        prefix = "  " * depth
        if name in seen:
            print(f"{prefix}{name} (already shown)")
            return
        block = selected.get(name)
        if not block:
            print(f"{prefix}{name} (missing)")
            return
        seen.add(name)
        kind, member = node_kind(block)
        label = f"{kind} {member}".strip()
        print(f"{prefix}{name}: {label}")
        for pin_name, links in exec_outputs(block):
            if not links:
                print(f"{prefix}  {pin_name} -> END")
                continue
            print(f"{prefix}  {pin_name} -> {', '.join(links)}")
            for linked in links:
                visit(linked, depth + 2)

    visit(start, 0)


if __name__ == "__main__":
    main()
