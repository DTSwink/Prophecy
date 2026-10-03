import json
import unreal


ASSETS = {
    "test": "/Game/_mygame/MetaHumans/test.test",
    "test_UEFNFit": "/Game/_mygame/MetaHumans/test_UEFNFit.test_UEFNFit",
}


def read_field(value, field, default=None):
    try:
        return getattr(value, field)
    except Exception:
        try:
            return value.get_editor_property(field)
        except Exception:
            return default


def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return str(value)
    except Exception:
        return repr(value)


subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
report = {"assets": {}, "differences": []}

for label, asset_path in ASSETS.items():
    character = unreal.load_asset(asset_path)
    if character is None:
        report["assets"][label] = {"error": "asset not found", "path": asset_path}
        continue

    registered_here = False
    try:
        if not subsystem.is_object_added_for_editing(character):
            registered_here = bool(subsystem.try_add_object_to_edit(character))
            if not registered_here:
                raise RuntimeError(
                    "Could not create temporary MetaHuman editing state for "
                    + character.get_path_name()
                )

        constraints = subsystem.get_body_constraints(
            character=character,
            scale_measurement_ranges_with_height=False,
        )
        values = {}
        for index, constraint in enumerate(constraints):
            name = read_field(constraint, "name", f"constraint_{index}")
            name = str(name)
            values[name] = {
                "target": json_value(read_field(constraint, "target_measurement")),
                "active": json_value(read_field(constraint, "is_active")),
                "minimum": json_value(read_field(constraint, "min_measurement")),
                "maximum": json_value(read_field(constraint, "max_measurement")),
            }

        report["assets"][label] = {
            "path": asset_path,
            "constraint_count": len(constraints),
            "constraints": values,
        }
    finally:
        # Only remove state owned by this script. An open MetaHuman asset
        # editor owns its existing registration and must be allowed to close it.
        if registered_here:
            subsystem.remove_object_to_edit(character)

left = report["assets"].get("test", {}).get("constraints", {})
right = report["assets"].get("test_UEFNFit", {}).get("constraints", {})
for name in sorted(set(left) | set(right)):
    left_value = left.get(name, {}).get("target")
    right_value = right.get(name, {}).get("target")
    if left_value != right_value:
        report["differences"].append(
            {
                "measurement": name,
                "test": left_value,
                "test_UEFNFit": right_value,
            }
        )

print("MH_MEASUREMENT_REPORT=" + json.dumps(report, sort_keys=True))
