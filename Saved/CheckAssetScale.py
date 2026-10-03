import unreal

for path in ("/Game/_mygame/MetaHumans/SKM_test_UEFN78_Body",
             "/Game/_mygame/MetaHumans/SKM_test_UEFN78_Face",
             "/Game/_mygame/SKM_UEFN_Mannequin"):
    mesh = unreal.load_asset(path)
    bounds = mesh.get_bounds()
    origin = bounds.origin
    extent = bounds.box_extent
    print("ASSET|{}|origin=({:.1f},{:.1f},{:.1f})|extent=({:.1f},{:.1f},{:.1f})".format(
        path, origin.x, origin.y, origin.z, extent.x, extent.y, extent.z))
print("SCALE_CHECK_DONE")
