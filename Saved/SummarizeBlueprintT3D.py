import re
import sys
from pathlib import Path


BEGIN_RE = re.compile(r'^\s*Begin Object(?: Class=(\S+))? Name="([^"]+)"(?: ExportPath="([^"]+)")?')
FUNCTION_RE = re.compile(r'FunctionReference=\([^\n]*MemberName="([^"]+)"')
VARIABLE_RE = re.compile(r'VariableReference=\(MemberName="([^"]+)"')
EVENT_RE = re.compile(r'EventReference=\([^\n]*MemberName="([^"]+)"')
CUSTOM_RE = re.compile(r'CustomFunctionName="([^"]+)"')
PIN_RE = re.compile(r'CustomProperties Pin \((.*)\)\s*$')
PIN_NAME_RE = re.compile(r'PinName="([^"]+)"')
LINK_RE = re.compile(r'LinkedTo=\(([^)]*)\)')
DEFAULT_RE = re.compile(r'DefaultValue="([^"]*)"')
DIRECTION_RE = re.compile(r'Direction="([^"]+)"')


class Block:
    def __init__(self, cls, name, export_path, parent=None):
        self.cls = cls or ""
        self.name = name
        self.export_path = export_path or ""
        self.parent = parent
        self.lines = []
        self.children = []

    @property
    def text(self):
        return "\n".join(self.lines)


def parse(path):
    root = Block("", "ROOT", "")
    stack = [root]
    data = Path(path).read_bytes()
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    for raw in data.decode(encoding, errors="replace").splitlines():
        match = BEGIN_RE.match(raw)
        if match:
            block = Block(match.group(1), match.group(2), match.group(3), stack[-1])
            stack[-1].children.append(block)
            stack.append(block)
            continue
        if raw.strip() == "End Object":
            if len(stack) > 1:
                stack.pop()
            continue
        stack[-1].lines.append(raw)
    return root


def walk(block):
    yield block
    for child in block.children:
        yield from walk(child)


def graph_name(block):
    if not block.export_path or ":" not in block.export_path:
        return ""
    suffix = block.export_path.rsplit(":", 1)[1].rstrip("'")
    return suffix.split(".", 1)[0]


def node_kind(block):
    text = block.text
    for regex, prefix in ((FUNCTION_RE, "call"), (VARIABLE_RE, "get/set"),
                          (EVENT_RE, "event"), (CUSTOM_RE, "custom")):
        match = regex.search(text)
        if match:
            return prefix, match.group(1)
    return block.cls.rsplit(".", 1)[-1], ""


def pins(block):
    result = []
    for line in block.lines:
        match = PIN_RE.search(line)
        if not match:
            continue
        value = match.group(1)
        name_match = PIN_NAME_RE.search(value)
        if not name_match:
            continue
        link_match = LINK_RE.search(value)
        default_match = DEFAULT_RE.search(value)
        direction_match = DIRECTION_RE.search(value)
        links = []
        if link_match:
            tokens = link_match.group(1).split(",")
            for token in tokens:
                parts = token.strip().split()
                if parts:
                    links.append(parts[0])
        result.append({
            "name": name_match.group(1),
            "direction": direction_match.group(1) if direction_match else "input",
            "default": default_match.group(1) if default_match else "",
            "links": links,
        })
    return result


def main():
    path = sys.argv[1]
    filters = [arg.lower() for arg in sys.argv[2:]]
    root = parse(path)
    blocks = [b for b in walk(root) if b.export_path and ".K2Node_" in b.export_path]
    # Prefer the populated definition when the export contains both a declaration and full block.
    selected = {}
    for block in blocks:
        key = block.export_path
        if key not in selected or len(block.lines) > len(selected[key].lines):
            selected[key] = block
    grouped = {}
    for block in selected.values():
        grouped.setdefault(graph_name(block), []).append(block)

    print(Path(path).name)
    for graph in sorted(grouped):
        matches = []
        for block in grouped[graph]:
            kind, member = node_kind(block)
            haystack = " ".join((graph, block.name, kind, member, block.text)).lower()
            if filters and not any(term in haystack for term in filters):
                continue
            matches.append((block, kind, member))
        if not matches:
            continue
        print(f"\n[{graph}]")
        for block, kind, member in sorted(matches, key=lambda item: item[0].name):
            print(f"{block.name}: {kind} {member}".rstrip())
            for pin in pins(block):
                if pin["links"] or pin["name"] in {
                    "execute", "then", "bSimulate", "self", "DeltaSeconds",
                    "NewLocation", "NewRotation", "BoneName", "TargetPosition",
                    "TargetRotation", "Position", "Rotation",
                }:
                    extra = f" default={pin['default']}" if pin["default"] else ""
                    links = f" -> {','.join(pin['links'])}" if pin["links"] else ""
                    print(f"  {pin['direction']} {pin['name']}{extra}{links}")


if __name__ == "__main__":
    main()
