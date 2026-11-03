"""
Bird LODs + texture budget (run after setup_birds.py, or on its own: -ExecutePythonScript=.../setup_bird_lods.py -BirdSetupQuit).

Birds are small on screen: a gull (bounds radius ~0.7 m) covers a screen size of ~0.12 at 10 m and ~0.04 at 30 m, so most of
the time a flock is drawn far from its 11-12k triangle LOD0. Four LODs, reduced automatically from LOD0 (works for any
replacement mesh, e.g. the final Tripo models: just run this again after re-importing):

  LOD0 100 %  screen size >= 0.12      LOD2 25 %  >= 0.025
  LOD1  50 %  >= 0.06                  LOD3 10 %  below

Feather textures are capped at 1024 (2K on a 30 cm bird is never sampled at its top mip).
"""
import os
import json
import unreal

DEST = "/Game/Prophecy/Creatures/Birds"
SPECIES = ["Gull", "Kingfisher"]
LODS = [(1.0, 1.0), (0.06, 0.5), (0.025, 0.25), (0.01, 0.10)]	# (min screen size, fraction of LOD0 triangles)
TEX_CAP = {"Feathers_BC": 1024, "Feathers_N": 1024, "Feathers_M": 1024}
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "BirdTest", "lods.json")
SMES = unreal.SkeletalMeshEditorSubsystem


def _log(m):
	unreal.log("[BirdLods] " + m)


def lod_settings_asset(rep):
	path = f"{DEST}/LODS_Birds"
	s = unreal.load_asset(path)
	if s is None:
		f = unreal.DataAssetFactory()
		f.set_editor_property("data_asset_class", unreal.SkeletalMeshLODSettings)
		s = unreal.AssetToolsHelpers.get_asset_tools().create_asset("LODS_Birds", DEST, unreal.SkeletalMeshLODSettings, f)
	if s is None:
		rep["errors"].append("could not create LODS_Birds")
		return None
	groups = []
	for ss, pct in LODS:
		g = unreal.SkeletalMeshLODGroupSettings()
		pf = unreal.PerPlatformFloat()
		pf.set_editor_property("default", ss)
		g.set_editor_property("screen_size", pf)
		r = g.get_editor_property("reduction_settings")
		r.set_editor_property("termination_criterion", unreal.SkeletalMeshTerminationCriterion.SMTC_NUM_OF_TRIANGLES)
		r.set_editor_property("num_of_triangles_percentage", pct)
		g.set_editor_property("reduction_settings", r)
		groups.append(g)
	s.set_editor_property("lod_groups", groups)
	return s


def tri_estimate(mesh, lod):
	try:
		return unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).get_num_verts(mesh, lod)
	except Exception as e:
		return str(e)


def apply(rep):
	settings = lod_settings_asset(rep)
	for sp in SPECIES:
		info = {}
		mesh = unreal.load_asset(f"{DEST}/{sp}/SK_{sp}")
		if not isinstance(mesh, unreal.SkeletalMesh):
			rep["errors"].append(f"{sp}: SK_{sp} not found")
			continue
		try:
			info["before_lods"] = SMES.get_lod_count(mesh)
			ok1 = SMES.regenerate_lod(mesh, len(LODS), False, False)			# create the LOD entries
			if settings is not None:
				mesh.set_editor_property("lod_settings", settings)				# screen sizes + reduction % onto every LOD
			ok2 = SMES.regenerate_lod(mesh, len(LODS), True, False)			# rebuild LOD1-3 with those settings
			info["regenerate"] = [bool(ok1), bool(ok2)]
			info["lods"] = SMES.get_lod_count(mesh)
			info["verts"] = [tri_estimate(mesh, i) for i in range(info["lods"])]
		except Exception:
			import traceback
			rep["errors"].append(f"{sp} LODs: " + traceback.format_exc())
		for key, cap in TEX_CAP.items():
			t = unreal.load_asset(f"{DEST}/{sp}/Textures/T_{sp}_{key}")
			if t is None:
				continue
			try:
				if t.get_editor_property("max_texture_size") != cap:
					t.set_editor_property("max_texture_size", cap)
				info.setdefault("textures", {})[key] = cap
			except Exception as e:
				rep["warnings"].append(f"{sp} {key}: {e}")
		rep["meshes"][sp] = info
		_log(f"{sp}: {info}")
	return rep


def main():
	rep = {"errors": [], "warnings": [], "meshes": {}}
	try:
		apply(rep)
		rep["saved"] = bool(unreal.EditorAssetLibrary.save_directory(DEST, only_if_is_dirty=True, recursive=True))
	except Exception:
		import traceback
		rep["errors"].append(traceback.format_exc())
	os.makedirs(os.path.dirname(REPORT), exist_ok=True)
	with open(REPORT, "w", encoding="utf-8") as f:
		json.dump(rep, f, indent=1)
	unreal.log("BIRDLODS errors=%d %s" % (len(rep["errors"]), json.dumps(rep["meshes"])))
	if "-BirdSetupQuit" in unreal.SystemLibrary.get_command_line():
		unreal.SystemLibrary.quit_editor()


if __name__ == "__main__":
	main()
