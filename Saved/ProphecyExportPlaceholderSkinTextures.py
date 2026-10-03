import os
import traceback
import unreal


EXPORTS = {
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor": "T_Face_Basecolor.png",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal": "T_Face_Normal.png",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor": "T_Body_Basecolor.png",
}


def log(message):
    unreal.log(f"[ProphecySkinTextureExport] {message}")


def main():
    output_dir = os.path.join(unreal.Paths.project_saved_dir(), "ProphecySkinTextureExports")
    os.makedirs(output_dir, exist_ok=True)

    exporter = unreal.TextureExporterPNG()
    for asset_path, file_name in EXPORTS.items():
        texture = unreal.load_asset(asset_path)
        if texture is None:
            raise RuntimeError(f"Missing texture: {asset_path}")

        task = unreal.AssetExportTask()
        task.object = texture
        task.filename = os.path.join(output_dir, file_name)
        task.automated = True
        task.replace_identical = True
        task.prompt = False
        task.exporter = exporter
        ok = unreal.Exporter.run_asset_export_task(task)
        log(f"{asset_path} -> {task.filename} ok={ok}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
