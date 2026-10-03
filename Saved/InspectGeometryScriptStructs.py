import unreal


for cls_name in (
    "GeometryScriptCopyMeshFromAssetOptions",
    "GeometryScriptMeshReadLOD",
    "GeometryScriptTransferBoneWeightsOptions",
    "GeometryScriptCopySkinWeightProfileToAssetOptions",
    "GeometryScriptMeshWriteLOD",
):
    cls = getattr(unreal, cls_name)
    value = cls()
    print("STRUCT|{}|{}".format(cls_name, value))
    print("FIELDS|{}|{}".format(cls_name, ",".join(name for name in dir(value) if not name.startswith("_"))))
for enum_name in (
    "GeometryScriptLODType",
    "TransferBoneWeightsMethod",
    "OutputTargetMeshBones",
    "GeometryScriptOutcomePins",
):
    value = getattr(unreal, enum_name, None)
    print("ENUM|{}|{}|{}".format(enum_name, value, ",".join(name for name in dir(value) if name.isupper()) if value else ""))
