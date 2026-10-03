import unreal

for owner in (unreal.BlueprintEditorLibrary,):
    print("OWNER", owner)
    for name in dir(owner):
        if "variable" in name.lower() or "member" in name.lower():
            value = getattr(owner, name)
            print("METHOD", name, getattr(value, "__doc__", ""))

for type_name in ("EdGraphPinType", "MemberReference"):
    owner = getattr(unreal, type_name, None)
    print("TYPE", type_name, owner, getattr(owner, "__doc__", ""))

pin = unreal.EdGraphPinType()
print("PIN", pin)
for name in dir(pin):
    if not name.startswith("_"):
        try:
            print("PIN_FIELD", name, getattr(pin, name))
        except Exception as exc:
            print("PIN_FIELD_ERROR", name, exc)
